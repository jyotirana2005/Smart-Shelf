from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import mysql.connector
from mysql.connector import pooling
import re
import os
from datetime import datetime, timedelta
import logging

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '1234')
app.config['MYSQL_DATABASE'] = os.environ.get('MYSQL_DATABASE', 'smart_shelf')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection pool
try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name='smart_shelf_pool',
        pool_size=10,
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DATABASE']
    )
except mysql.connector.Error as err:
    logger.error(f"Error creating database pool: {err}")
    raise

def get_db():
    """Get database connection from pool."""
    return db_pool.get_connection()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Check if user is already logged in and the user actually exists in database
    if session.get('user_id') and not request.args.get('logout'):
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute('SELECT id FROM users WHERE id=%s', (session['user_id'],))
        user_exists = cursor.fetchone()
        cursor.close()
        db.close()
        
        if user_exists:
            return redirect(url_for('dashboard'))
        else:
            # Clear invalid session if user doesn't exist
            session.clear()
    
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email=%s', (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if not user:
            error = 'User not found.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'
        else:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
    
    return render_template('login.html', error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # Check if user is already logged in and the user actually exists in database
    if session.get('user_id') and not request.args.get('logout'):
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute('SELECT id FROM users WHERE id=%s', (session['user_id'],))
        user_exists = cursor.fetchone()
        cursor.close()
        db.close()
        
        if user_exists:
            return redirect(url_for('dashboard'))
        else:
            # Clear invalid session if user doesn't exist
            session.clear()
    
    error = None
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form.get('confirm_password')
        # Email format check
        email_regex = r'^[\w\.-]+@[\w\.-]+\.\w{2,}$'
        if not re.match(email_regex, email):
            error = 'Please enter a valid email address.'
        # Password strength check
        elif len(password) < 8 or not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
            error = 'Password must be at least 8 characters and include a letter and a number.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        else:
            db = get_db()
            cursor = db.cursor()
            try:
                cursor.execute('SELECT id FROM users WHERE email=%s', (email,))
                if cursor.fetchone():
                    error = 'Email already registered.'
                else:
                    cursor.execute('SELECT id FROM users WHERE username=%s', (username,))
                    if cursor.fetchone():
                        error = 'Username already registered.'
                    else:
                        hash_pw = generate_password_hash(password)
                        cursor.execute(
                            'INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
                            (username, email, hash_pw)
                        )
                        db.commit()
                        return render_template('signup.html', success=True)
            except Exception:
                error = 'Signup failed.'
            finally:
                cursor.close()
                db.close()

    return render_template('signup.html', error=error)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', session=session)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/inventory')
@login_required
def inventory():
    return render_template('inventory.html', session=session)

@app.route('/alerts')
@login_required
def alerts():
    return render_template('alerts.html', session=session)

@app.route('/insights')
@login_required
def insights():
    return render_template('insights.html', session=session)

@app.route('/recipes')
@login_required
def recipes():
    return render_template('recipes.html', session=session)

@app.route('/marketplace')
@login_required
def marketplace():
    return render_template('marketplace.html', session=session)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', session=session)

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html', session=session)

# Dashboard API Endpoint
@app.route('/api/dashboard-data', methods=['GET'])
@login_required
def api_dashboard_data():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    uid = session['user_id']

    # Total active items
    cursor.execute(""" 
        SELECT COUNT(*) AS total FROM inventory 
        WHERE user_id=%s AND (status='active' OR status IS NULL) 
    """, (uid,))
    total_items = cursor.fetchone()['total']

    # Expiring soon (next 3 days)
    cursor.execute(""" 
        SELECT COUNT(*) AS expiring FROM inventory 
        WHERE user_id=%s AND (status='active' OR status IS NULL) AND expiry_date BETWEEN CURDATE() AND (CURDATE() + INTERVAL 3 DAY) 
    """, (uid,))
    expiring = cursor.fetchone()['expiring']

    # Low stock (items with quantity below threshold)
    cursor.execute(""" 
        SELECT COUNT(*) AS low_stock FROM inventory 
        WHERE user_id=%s AND (status='active' OR status IS NULL) AND quantity < 5 
    """, (uid,))
    low_stock = cursor.fetchone()['low_stock']

    # Waste reduced (kg, this month)
    cursor.execute(""" 
        SELECT IFNULL(SUM(quantity),0) AS waste_kg FROM waste_logs 
        WHERE user_id=%s AND MONTH(logged_at)=MONTH(CURDATE()) AND YEAR(logged_at)=YEAR(CURDATE()) 
    """, (uid,))
    waste_kg = float(cursor.fetchone()['waste_kg'])

    # Money saved (for now, 0; can be calculated from price diff or waste logs)
    money_saved = 0

    # Recipe matches (recipes that can be made with current inventory)
    cursor.execute("SELECT COUNT(*) AS recipe_count FROM recipes WHERE created_by=%s", (uid,))
    recipe_count = cursor.fetchone()['recipe_count']

    cursor.close()
    db.close()

    return jsonify({
        'stats': {
            'total_items': total_items,
            'expiring': expiring,
            'low_stock': low_stock,
            'money_saved': money_saved,
            'waste_kg': waste_kg,
            'recipe_count': recipe_count
        }
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
