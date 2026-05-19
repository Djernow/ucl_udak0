"""
UDAKO Champions League Backend
Flask + SQLite API for persistent scoreboard tracking
"""

import os
import json
from datetime import datetime
from functools import wraps
import sqlite3
from flask import Flask, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# Configuration
# ============================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True  # Set to False if not using HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

DATABASE = os.environ.get('DATABASE_PATH', '/data/udako.db')

# ============================================================
# Database helpers
# ============================================================
def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize database schema"""
    db = get_db()
    cursor = db.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            must_change_pw INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check-ins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            nb INTEGER DEFAULT 0,
            sb INTEGER DEFAULT 0,
            sh INTEGER DEFAULT 0,
            co INTEGER DEFAULT 0,
            jo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, date)
        )
    ''')
    
    db.commit()
    
    # Add default admin if not exists
    try:
        cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
        if not cursor.fetchone():
            pw_hash = generate_password_hash('admin123')
            cursor.execute(
                'INSERT INTO users (username, password, role, must_change_pw) VALUES (?, ?, ?, ?)',
                ('admin', pw_hash, 'admin', 0)
            )
            db.commit()
    except:
        pass
    
    db.close()

# ============================================================
# Auth helpers
# ============================================================
def require_auth(f):
    """Decorator: require user to be logged in"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    """Decorator: require admin role"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()
        db.close()
        
        if not user or user['role'] != 'admin':
            return jsonify({'error': 'Forbidden: admin required'}), 403
        
        return f(*args, **kwargs)
    return decorated

# ============================================================
# Auth endpoints
# ============================================================
@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, password, role, must_change_pw FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    db.close()
    
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    session['user_id'] = user['id']
    session['username'] = username
    session['role'] = user['role']
    
    return jsonify({
        'success': True,
        'user': {
            'username': username,
            'role': user['role'],
            'must_change_pw': bool(user['must_change_pw'])
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Logout user"""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def get_me():
    """Get current user info"""
    return jsonify({
        'user': {
            'username': session.get('username'),
            'role': session.get('role')
        }
    })

@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change user password"""
    data = request.json or {}
    new_password = data.get('password', '')
    
    if len(new_password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    
    db = get_db()
    cursor = db.cursor()
    pw_hash = generate_password_hash(new_password)
    cursor.execute(
        'UPDATE users SET password = ?, must_change_pw = 0 WHERE id = ?',
        (pw_hash, session['user_id'])
    )
    db.commit()
    db.close()
    
    return jsonify({'success': True})

# ============================================================
# User management (admin)
# ============================================================
@app.route('/api/users', methods=['GET'])
@require_admin
def get_users():
    """Get all users (admin only)"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, username, role, must_change_pw FROM users WHERE role != ?', ('admin',))
    users = cursor.fetchall()
    db.close()
    
    result = []
    for u in users:
        # Get score and check-in count
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT COUNT(*) as days FROM checkins WHERE user_id = ?', (u['id'],))
        days = cursor.fetchone()['days']
        db.close()
        
        result.append({
            'username': u['username'],
            'role': u['role'],
            'must_change_pw': bool(u['must_change_pw']),
            'days': days
        })
    
    return jsonify({'users': result})

@app.route('/api/users/add', methods=['POST'])
@require_admin
def add_user():
    """Add new user (admin only)"""
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    
    if not username or username.count(' ') > 0:
        return jsonify({'error': 'Username required, no spaces'}), 400
    
    if len(password) < 3:
        return jsonify({'error': 'Password too short'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Check if user exists
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        db.close()
        return jsonify({'error': 'Username already exists'}), 400
    
    # Create user
    try:
        pw_hash = generate_password_hash(password)
        cursor.execute(
            'INSERT INTO users (username, password, role, must_change_pw) VALUES (?, ?, ?, ?)',
            (username, pw_hash, 'user', 1)
        )
        db.commit()
        db.close()
        return jsonify({'success': True, 'message': f'User "{username}" created'})
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/delete', methods=['POST'])
@require_admin
def delete_user():
    """Delete user (admin only)"""
    data = request.json or {}
    username = data.get('username', '')
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('DELETE FROM users WHERE username = ? AND role != ?', (username, 'admin'))
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'message': f'User "{username}" deleted'})

@app.route('/api/users/reset-password', methods=['POST'])
@require_admin
def reset_password():
    """Reset user password (admin only)"""
    data = request.json or {}
    username = data.get('username', '')
    new_password = data.get('password', '')
    
    if len(new_password) < 3:
        return jsonify({'error': 'Password too short'}), 400
    
    db = get_db()
    cursor = db.cursor()
    pw_hash = generate_password_hash(new_password)
    cursor.execute(
        'UPDATE users SET password = ?, must_change_pw = 1 WHERE username = ?',
        (pw_hash, username)
    )
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'message': f'Password reset for "{username}"'})

# ============================================================
# Check-ins
# ============================================================
@app.route('/api/checkins', methods=['POST'])
@require_auth
def create_checkin():
    """Create or update check-in for today"""
    data = request.json or {}
    
    checkin = {
        'nb': int(data.get('nb', 0)),
        'sb': int(data.get('sb', 0)),
        'sh': int(data.get('sh', 0)),
        'co': int(data.get('co', 0)),
        'jo': int(data.get('jo', 0))
    }
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    db = get_db()
    cursor = db.cursor()
    
    # Check if exists
    cursor.execute(
        'SELECT id FROM checkins WHERE user_id = ? AND date = ?',
        (session['user_id'], today)
    )
    existing = cursor.fetchone()
    
    if existing:
        # Update
        cursor.execute(
            'UPDATE checkins SET nb=?, sb=?, sh=?, co=?, jo=? WHERE user_id = ? AND date = ?',
            (checkin['nb'], checkin['sb'], checkin['sh'], checkin['co'], checkin['jo'], session['user_id'], today)
        )
    else:
        # Insert
        cursor.execute(
            'INSERT INTO checkins (user_id, date, nb, sb, sh, co, jo) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (session['user_id'], today, checkin['nb'], checkin['sb'], checkin['sh'], checkin['co'], checkin['jo'])
        )
    
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'message': 'Check-in saved'})

@app.route('/api/checkins', methods=['GET'])
@require_auth
def get_checkins():
    """Get user's check-ins"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'SELECT date, nb, sb, sh, co, jo FROM checkins WHERE user_id = ? ORDER BY date DESC',
        (session['user_id'],)
    )
    checkins = cursor.fetchall()
    db.close()
    
    result = [dict(c) for c in checkins]
    return jsonify({'checkins': result})

# ============================================================
# Scoreboard
# ============================================================
@app.route('/api/scoreboard', methods=['GET'])
def get_scoreboard():
    """Get scoreboard (public)"""
    db = get_db()
    cursor = db.cursor()
    
    # Get all non-admin users with their stats
    cursor.execute('''
        SELECT u.id, u.username, 
               COUNT(c.id) as days,
               SUM(c.nb * 1.0 + c.sb * 1.5 + c.sh * 0.75 + c.co * 1.25 + c.jo * 2.0) as total_score,
               MAX(c.date) as last_date
        FROM users u
        LEFT JOIN checkins c ON u.id = c.user_id
        WHERE u.role = 'user'
        GROUP BY u.id
        ORDER BY total_score DESC, days DESC
    ''')
    
    users = cursor.fetchall()
    db.close()
    
    result = []
    for i, u in enumerate(users, 1):
        score = u['total_score'] or 0.0
        days = u['days'] or 0
        avg = score / days if days > 0 else 0.0
        
        result.append({
            'rank': i,
            'username': u['username'],
            'score': round(score, 1),
            'days': days,
            'avg': round(avg, 1),
            'last_date': u['last_date'] or '—'
        })
    
    return jsonify({'scoreboard': result})

# ============================================================
# Health check
# ============================================================
@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

# ============================================================
# Error handlers
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Server error'}), 500

# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
