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
    if session.get('user_id') and not request.args.get('logout'):
        return redirect(url_for('dashboard'))
    
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
    if session.get('user_id') and not request.args.get('logout'):
        return redirect(url_for('dashboard'))
    
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

# In-memory expiry items for demo (replace with DB in production)
expiry_items = []

@app.route('/expiry', methods=['GET', 'POST'])
def expiry():
    global expiry_items
    if request.method == 'POST':
        item = request.form['item']
        qty = request.form['qty']
        expiry = request.form['expiry']
        expiry_items.append({
            'item': item,
            'qty': qty,
            'expiry': expiry
        })
    # Mark items expiring within 3 days
    items = []
    for row in expiry_items:
        try:
            exp_date = datetime.strptime(row['expiry'], '%Y-%m-%d')
            exp_soon = (exp_date - datetime.now()).days <= 3
        except Exception:
            exp_soon = False
        items.append({
            'item': row['item'],
            'qty': row['qty'],
            'expiry': row['expiry'],
            'expiring_soon': exp_soon
        })
    return render_template('expiry.html', items=items)

# --- Inventory API (CRUD) ---
from flask import jsonify

# --- Households CRUD ---
@app.route('/api/households', methods=['GET'])
@login_required
def get_households():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM households h JOIN household_members m ON h.id=m.household_id WHERE m.user_id=%s', (session['user_id'],))
    households = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(households)

@app.route('/api/households', methods=['POST'])
@login_required
def create_household():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    cursor.execute('INSERT INTO households (name) VALUES (%s)', (data['name'],))
    hid = cursor.lastrowid
    cursor.execute('INSERT INTO household_members (household_id, user_id, role) VALUES (%s, %s, %s)', (hid, session['user_id'], 'owner'))
    db.commit(); cursor.close(); db.close()
    return jsonify({'success': True, 'household_id': hid})

# --- Household Members CRUD ---
@app.route('/api/households/<int:household_id>/members', methods=['GET'])
@login_required
def get_household_members(household_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM household_members WHERE household_id=%s', (household_id,))
    members = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(members)

# --- Locations CRUD ---
@app.route('/api/locations', methods=['GET'])
@login_required
def get_locations():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM locations WHERE household_id IN (SELECT household_id FROM household_members WHERE user_id=%s)', (session['user_id'],))
    locations = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(locations)

# --- Items CRUD (master catalog) ---
@app.route('/api/items', methods=['GET'])
@login_required
def get_items():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM items')
    items = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(items)

# --- Recipes CRUD (basic) ---
@app.route('/api/recipes', methods=['GET'])
@login_required
def get_recipes():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM recipes WHERE created_by=%s', (session['user_id'],))
    recipes = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(recipes)

# --- Meal Plans CRUD (basic) ---
@app.route('/api/mealplans', methods=['GET'])
@login_required
def get_mealplans():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM meal_plans WHERE user_id=%s', (session['user_id'],))
    plans = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(plans)

# --- Grocery Lists CRUD (basic) ---
@app.route('/api/grocerylists', methods=['GET'])
@login_required
def get_grocerylists():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM grocery_lists WHERE user_id=%s', (session['user_id'],))
    lists = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(lists)

# --- Grocery Items CRUD (basic) ---
@app.route('/api/grocerylists/<int:list_id>/items', methods=['GET'])
@login_required
def get_grocery_items(list_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM grocery_items WHERE list_id=%s', (list_id,))
    items = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(items)

# --- Waste Logs CRUD (basic) ---
@app.route('/api/wastelogs', methods=['GET'])
@login_required
def get_waste_logs():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM waste_logs WHERE user_id=%s', (session['user_id'],))
    logs = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(logs)

# --- Automation Rules CRUD (basic) ---
@app.route('/api/automationrules', methods=['GET'])
@login_required
def get_automation_rules():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM automation_rules WHERE user_id=%s', (session['user_id'],))
    rules = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(rules)

# --- Achievements CRUD (basic) ---
@app.route('/api/achievements', methods=['GET'])
@login_required
def get_achievements():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM achievements WHERE user_id=%s', (session['user_id'],))
    achievements = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(achievements)

# --- Audit Logs CRUD (basic) ---
@app.route('/api/auditlogs', methods=['GET'])
@login_required
def get_audit_logs():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM audit_logs WHERE user_id=%s', (session['user_id'],))
    logs = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(logs)

@app.route('/api/inventory', methods=['GET'])
@login_required
def api_inventory_list():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM inventory WHERE user_id=%s ORDER BY expiry_date ASC', (session['user_id'],))
    items = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(items)

@app.route('/api/inventory', methods=['POST'])
@login_required
def api_inventory_add():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    cursor.execute('INSERT INTO inventory (user_id, name, quantity, expiry_date, category, barcode) VALUES (%s, %s, %s, %s, %s, %s)',
        (session['user_id'], data['name'], data['quantity'], data['expiry_date'], data['category'], data.get('barcode')))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'success': True})

@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
@login_required
def api_inventory_update(item_id):
    data = request.json
    db = get_db()
    cursor = db.cursor()
    cursor.execute('UPDATE inventory SET name=%s, quantity=%s, expiry_date=%s, category=%s, barcode=%s WHERE id=%s AND user_id=%s',
        (data['name'], data['quantity'], data['expiry_date'], data['category'], data.get('barcode'), item_id, session['user_id']))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'success': True})

@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
@login_required
def api_inventory_delete(item_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('DELETE FROM inventory WHERE id=%s AND user_id=%s', (item_id, session['user_id']))
    db.commit()
    cursor.close()
    db.close()
    return jsonify({'success': True})

# --- Dashboard API Endpoint ---
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

    # Expired
    cursor.execute("""
        SELECT COUNT(*) AS expired FROM inventory
        WHERE user_id=%s AND status='expired'
    """, (uid,))
    expired = cursor.fetchone()['expired']

    # Waste reduced (kg, this month)
    cursor.execute("""
        SELECT IFNULL(SUM(quantity),0) AS waste_kg FROM waste_logs
        WHERE user_id=%s AND MONTH(logged_at)=MONTH(CURDATE()) AND YEAR(logged_at)=YEAR(CURDATE())
    """, (uid,))
    waste_kg = float(cursor.fetchone()['waste_kg'])

    # Money saved (for now, 0; can be calculated from price diff or waste logs)
    money_saved = 0

    # Recipe count
    cursor.execute("SELECT COUNT(*) AS recipe_count FROM recipes WHERE created_by=%s", (uid,))
    recipe_count = cursor.fetchone()['recipe_count']

    # Recent items (last 5)
    cursor.execute("""
        SELECT i.name, inv.quantity, inv.unit, inv.expiry_date, l.name AS location
        FROM inventory inv
        JOIN items i ON inv.item_id = i.id
        LEFT JOIN locations l ON inv.location_id = l.id
        WHERE inv.user_id=%s
        ORDER BY inv.created_at DESC LIMIT 5
    """, (uid,))
    recent_items = cursor.fetchall()

    # Alerts (last 3 expiring/expired)
    cursor.execute("""
        SELECT i.name, inv.expiry_date, inv.status
        FROM inventory inv
        JOIN items i ON inv.item_id = i.id
        WHERE inv.user_id=%s AND (inv.status='expired' OR (inv.status='active' AND inv.expiry_date <= CURDATE() + INTERVAL 3 DAY))
        ORDER BY inv.expiry_date ASC LIMIT 3
    """, (uid,))
    alerts = [
        {
            "title": f"{row['name']} ({row['status']})",
            "message": f"Expiry: {row['expiry_date']}"
        }
        for row in cursor.fetchall()
    ]

    # Category breakdown
    cursor.execute("""
        SELECT i.category, COUNT(*) AS count
        FROM inventory inv
        JOIN items i ON inv.item_id = i.id
        WHERE inv.user_id=%s
        GROUP BY i.category
    """, (uid,))
    category_breakdown = {row['category']: row['count'] for row in cursor.fetchall()}

    cursor.close()
    db.close()

    return jsonify({
        'stats': {
            'total_items': total_items,
            'expiring': expiring,
            'expired': expired,
            'money_saved': money_saved,
            'waste_kg': waste_kg,
            'recipe_count': recipe_count
        },
        'categoryBreakdown': category_breakdown,
        'recentItems': recent_items,
        'alerts': alerts
    })
@app.route('/inventory')
@login_required
def inventory():
    return render_template('inventory.html', session=session)

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html', session=session)

@app.route('/recipes')
@login_required
def recipes():
    return render_template('recipes.html', session=session)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', session=session)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
