from flask import Flask, render_template, request, redirect, url_for, session, flash
from db_config import get_db_connection
import webbrowser
import threading

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Login Page
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user_type = request.form['user_type']
        username = request.form['username']
        password = request.form['password']

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            if user_type == 'admin':
                cursor.execute('SELECT * FROM admin WHERE username=%s AND password=%s', (username, password))
                user = cursor.fetchone()
                if user:
                    session['user_type'] = 'admin'
                    session['username'] = username
                    return redirect(url_for('admin_dashboard'))
                else:
                    error = 'Invalid Credentials'

            elif user_type == 'branch':
                cursor.execute('SELECT * FROM branch WHERE username=%s AND password=%s', (username, password))
                user = cursor.fetchone()
                if user:
                    session['user_type'] = 'branch'
                    session['username'] = username
                    session['branch_id'] = user['id']
                    return redirect(url_for('branch_dashboard'))
                else:
                    error = 'Invalid Credentials'

            cursor.close()
            conn.close()

        except Exception as e:
            print("Login Error:", e)
            error = "Server error. Please try again later."

    return render_template('login.html', error=error)

# Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM stock')
    stocks = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin_dashboard.html', stocks=stocks)

# Add Stock
@app.route('/add_stock', methods=['POST'])
def add_stock():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    item_name = request.form['item_name']
    quantity = int(request.form['quantity'])

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM stock WHERE item_name = %s', (item_name,))
    stock_item = cursor.fetchone()

    if stock_item:
        cursor.execute('UPDATE stock SET quantity = quantity + %s WHERE item_name = %s', (quantity, item_name))
    else:
        cursor.execute('INSERT INTO stock (item_name, quantity) VALUES (%s, %s)', (item_name, quantity))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_dashboard'))

# Issue Stock to Branch
@app.route('/issue_stock', methods=['POST'])
def issue_stock():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    stock_id = int(request.form['stock_id'])
    branch_id = int(request.form['branch_id'])
    issued_quantity = int(request.form['issued_quantity'])

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT quantity FROM stock WHERE id = %s', (stock_id,))
    stock = cursor.fetchone()

    if stock and stock[0] >= issued_quantity:
        cursor.execute('UPDATE stock SET quantity = quantity - %s WHERE id = %s', (issued_quantity, stock_id))

        cursor.execute('SELECT * FROM issued_stock WHERE stock_id = %s AND branch_id = %s', (stock_id, branch_id))
        issued_item = cursor.fetchone()

        if issued_item:
            cursor.execute('UPDATE issued_stock SET issued_quantity = issued_quantity + %s WHERE stock_id = %s AND branch_id = %s',
                           (issued_quantity, stock_id, branch_id))
        else:
            cursor.execute('INSERT INTO issued_stock (stock_id, branch_id, issued_quantity) VALUES (%s, %s, %s)',
                           (stock_id, branch_id, issued_quantity))

        conn.commit()
        flash('Stock issued successfully!')
    else:
        flash('Not enough stock available.')

    cursor.close()
    conn.close()

    return redirect(url_for('admin_dashboard'))

# Branch Dashboard
@app.route('/branch_dashboard')
def branch_dashboard():
    if session.get('user_type') != 'branch':
        return redirect(url_for('login'))

    branch_id = session.get('branch_id')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT stock.id, stock.item_name, issued_stock.issued_quantity
        FROM issued_stock
        JOIN stock ON issued_stock.stock_id = stock.id
        WHERE issued_stock.branch_id = %s
    ''', (branch_id,))
    stocks = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('branch_dashboard.html', stocks=stocks, branch_id=branch_id)

# Report Damaged Stock
@app.route('/report_damage/<int:branch_id>', methods=['POST'])
def report_damage(branch_id):
    if session.get('user_type') != 'branch':
        return redirect(url_for('login'))

    stock_id = int(request.form['stock_id'])
    damaged_quantity = int(request.form['damaged_quantity'])

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT issued_quantity FROM issued_stock WHERE stock_id = %s AND branch_id = %s', (stock_id, branch_id))
    issued_item = cursor.fetchone()

    if issued_item and issued_item[0] >= damaged_quantity:
        cursor.execute('UPDATE issued_stock SET issued_quantity = issued_quantity - %s WHERE stock_id = %s AND branch_id = %s',
                       (damaged_quantity, stock_id, branch_id))
        conn.commit()
        flash('Damaged stock reported successfully!')
    else:
        flash('Invalid stock ID or damaged quantity exceeds available stock.')

    cursor.close()
    conn.close()

    return redirect(url_for('branch_dashboard'))

# Return Stock to Company
@app.route('/return_stock/<int:branch_id>', methods=['POST'])
def return_stock(branch_id):
    if session.get('user_type') != 'branch':
        return redirect(url_for('login'))

    stock_id = int(request.form['stock_id'])
    return_quantity = int(request.form['return_quantity'])

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT issued_quantity FROM issued_stock WHERE stock_id = %s AND branch_id = %s', (stock_id, branch_id))
    issued_item = cursor.fetchone()

    if issued_item and issued_item[0] >= return_quantity:
        cursor.execute('UPDATE issued_stock SET issued_quantity = issued_quantity - %s WHERE stock_id = %s AND branch_id = %s',
                       (return_quantity, stock_id, branch_id))
        cursor.execute('UPDATE stock SET quantity = quantity + %s WHERE id = %s', (return_quantity, stock_id))
        conn.commit()
        flash('Stock returned to company successfully!')
    else:
        flash('Invalid stock ID or return quantity exceeds available stock.')

    cursor.close()
    conn.close()

    return redirect(url_for('branch_dashboard'))

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Auto-open browser on run
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    threading.Timer(1.0, open_browser).start()
    app.run(debug=True)
