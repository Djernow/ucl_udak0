import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

DATABASE = os.environ.get('DATABASE_PATH', '/data/udako.db')
SEASON_START_MONTH = 6
SEASON_START_DAY = 11

# ============================================================
# SEASON HELPERS
# ============================================================
def current_season_start(today):
    start_this_year = datetime(today.year, SEASON_START_MONTH, SEASON_START_DAY).date()
    if today >= start_this_year:
        return start_this_year
    return datetime(today.year - 1, SEASON_START_MONTH, SEASON_START_DAY).date()

# ============================================================
# DATABASE INITIALIZATION
# ============================================================
def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def get_password_columns(db):
    cursor = db.execute('PRAGMA table_info(users)')
    columns = [row[1] for row in cursor.fetchall()]
    return {
        'password_hash': 'password_hash' in columns,
        'password': 'password' in columns
    }

def init_db():
    """Initialize database schema if not exists."""
    db = get_db()
    cursor = db.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
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
            wi INTEGER DEFAULT 0,
            jo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, date)
        )
    ''')
    
    db.commit()
    
    # Migrate legacy schema: password -> password_hash
    try:
        cursor.execute('PRAGMA table_info(users)')
        columns = [row[1] for row in cursor.fetchall()]
        if 'password_hash' not in columns and 'password' in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
            cursor.execute('UPDATE users SET password_hash = password WHERE password_hash IS NULL')
            db.commit()
    except Exception:
        pass

    # Ensure new columns exist for older databases
    try:
        cursor.execute('PRAGMA table_info(checkins)')
        columns = [row[1] for row in cursor.fetchall()]
        if 'wi' not in columns:
            cursor.execute('ALTER TABLE checkins ADD COLUMN wi INTEGER DEFAULT 0')
            db.commit()
    except Exception:
        pass

    # Add default admin if not exists
    try:
        cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
        if not cursor.fetchone():
            pw_hash = generate_password_hash('admin123')
            cursor.execute(
                'INSERT INTO users (username, password_hash, role, must_change_pw) VALUES (?, ?, ?, ?)',
                ('admin', pw_hash, 'admin', 0)
            )
            db.commit()
    except:
        pass
    
    db.close()

# Initialize DB on startup
init_db()

# ============================================================
# DECORATORS
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
# HELPER FUNCTIONS
# ============================================================
def get_user_by_id(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    db.close()
    return user

def get_user_by_username(username):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    db.close()
    return user

def user_to_dict(user):
    return {
        'id': user['id'],
        'username': user['username'],
        'role': user['role'],
        'must_change_pw': bool(user['must_change_pw']),
        'created_at': user['created_at']
    }

def checkin_to_dict(row):
    return {
        'id': row['id'],
        'user_id': row['user_id'],
        'date': row['date'],
        'nb': row['nb'],
        'sb': row['sb'],
        'sh': row['sh'],
        'co': row['co'],
        'wi': row['wi'],
        'jo': row['jo'],
        'created_at': row['created_at']
    }

# ============================================================
# HEALTH CHECK
# ============================================================
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

# ============================================================
# AUTHENTICATION ENDPOINTS
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
    cursor.execute(
        'SELECT id, password_hash, password, role, must_change_pw FROM users WHERE username = ?',
        (username,)
    )
    user = cursor.fetchone()
    db.close()

    if not user:
        return jsonify({'error': 'Invalid username or password'}), 401

    pw_hash = user['password_hash'] or user['password']
    if not pw_hash or not check_password_hash(pw_hash, password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    session.clear()
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
def logout():
    session.clear()
    response = jsonify({'success': True})
    response.delete_cookie(
        app.config.get('SESSION_COOKIE_NAME', 'session'),
        path='/',
        samesite=app.config.get('SESSION_COOKIE_SAMESITE', 'Lax'),
        secure=app.config.get('SESSION_COOKIE_SECURE', True),
        httponly=app.config.get('SESSION_COOKIE_HTTPONLY', True)
    )
    return response, 200

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({'user': user_to_dict(user)}), 200

@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    data = request.get_json() or {}
    password = data.get('password', '')
    
    if not password or len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    
    db = get_db()
    pw_hash = generate_password_hash(password)
    pw_columns = get_password_columns(db)
    if not pw_columns['password_hash'] and not pw_columns['password']:
        db.close()
        return jsonify({'error': 'Password column not found'}), 500

    if pw_columns['password_hash'] and pw_columns['password']:
        db.execute(
            'UPDATE users SET password_hash = ?, password = ?, must_change_pw = 0 WHERE id = ?',
            (pw_hash, pw_hash, session['user_id'])
        )
    else:
        column = 'password_hash' if pw_columns['password_hash'] else 'password'
        db.execute(
            f'UPDATE users SET {column} = ?, must_change_pw = 0 WHERE id = ?',
            (pw_hash, session['user_id'])
        )
    db.commit()
    db.close()
    
    return jsonify({'success': True}), 200

# ============================================================
# USER MANAGEMENT ENDPOINTS (ADMIN ONLY)
# ============================================================
@app.route('/api/users', methods=['GET'])
@require_admin
def get_users():
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY username').fetchall()
    db.close()
    
    # Enrich with checkin stats
    result = []
    for user in users:
        u_dict = user_to_dict(user)
        
        # Get checkin count and last date
        db = get_db()
        row = db.execute(
            'SELECT COUNT(*) as days, MAX(date) as last_date FROM checkins WHERE user_id = ?',
            (user['id'],)
        ).fetchone()
        db.close()
        
        u_dict['days'] = row['days'] or 0
        u_dict['last_date'] = row['last_date']
        
        result.append(u_dict)
    
    return jsonify({'users': result}), 200

@app.route('/api/users/add', methods=['POST'])
@require_admin
def add_user():
    data = request.get_json() or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if ' ' in username:
        return jsonify({'error': 'Username cannot contain spaces'}), 400
    
    if len(password) < 3:
        return jsonify({'error': 'Password too short'}), 400
    
    # Check if username exists
    if get_user_by_username(username):
        return jsonify({'error': 'User already exists'}), 409
    
    db = get_db()
    pw_hash = generate_password_hash(password)
    pw_columns = get_password_columns(db)
    if not pw_columns['password_hash'] and not pw_columns['password']:
        db.close()
        return jsonify({'error': 'Password column not found'}), 500
    
    try:
        if pw_columns['password_hash'] and pw_columns['password']:
            db.execute(
                'INSERT INTO users (username, password_hash, password, role, must_change_pw) VALUES (?, ?, ?, ?, ?)',
                (username, pw_hash, pw_hash, 'user', 1)
            )
        else:
            column = 'password_hash' if pw_columns['password_hash'] else 'password'
            db.execute(
                f'INSERT INTO users (username, {column}, role, must_change_pw) VALUES (?, ?, ?, ?)',
                (username, pw_hash, 'user', 1)
            )
        db.commit()
        db.close()
        
        return jsonify({'success': True, 'message': f'User {username} created'}), 201
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({'error': 'User already exists'}), 409

@app.route('/api/users/reset-password', methods=['POST'])
@require_admin
def reset_password():
    data = request.get_json() or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user = get_user_by_username(username)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    db = get_db()
    pw_hash = generate_password_hash(password)
    pw_columns = get_password_columns(db)
    if not pw_columns['password_hash'] and not pw_columns['password']:
        db.close()
        return jsonify({'error': 'Password column not found'}), 500

    if pw_columns['password_hash'] and pw_columns['password']:
        db.execute(
            'UPDATE users SET password_hash = ?, password = ?, must_change_pw = 1 WHERE id = ?',
            (pw_hash, pw_hash, user['id'])
        )
    else:
        column = 'password_hash' if pw_columns['password_hash'] else 'password'
        db.execute(
            f'UPDATE users SET {column} = ?, must_change_pw = 1 WHERE id = ?',
            (pw_hash, user['id'])
        )
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'message': f'Password reset for {username}'}), 200

@app.route('/api/users/delete', methods=['POST'])
@require_admin
def delete_user():
    data = request.get_json() or {}
    username = data.get('username', '').strip().lower()
    
    user = get_user_by_username(username)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user['role'] == 'admin' and session['user_id'] == user['id']:
        return jsonify({'error': 'Cannot delete own admin account'}), 403
    
    db = get_db()
    # Delete checkins first (cascade)
    db.execute('DELETE FROM checkins WHERE user_id = ?', (user['id'],))
    db.execute('DELETE FROM users WHERE id = ?', (user['id'],))
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'message': f'User {username} deleted'}), 200

# ============================================================
# CHECK-IN ENDPOINTS
# ============================================================
@app.route('/api/checkins', methods=['GET'])
@require_auth
def get_checkins():
    today_date = datetime.now().date()
    scope = (request.args.get('scope') or '').strip().lower()
    season_start = current_season_start(today_date)
    range_start = season_start.strftime('%Y-%m-%d')
    range_end = today_date.strftime('%Y-%m-%d')

    db = get_db()
    if scope == 'all':
        checkins = db.execute(
            'SELECT * FROM checkins WHERE user_id = ? ORDER BY date DESC',
            (session['user_id'],)
        ).fetchall()
    else:
        checkins = db.execute(
            'SELECT * FROM checkins WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date DESC',
            (session['user_id'], range_start, range_end)
        ).fetchall()
    db.close()
    
    return jsonify({
        'checkins': [checkin_to_dict(row) for row in checkins]
    }), 200

@app.route('/api/checkins', methods=['POST'])
@require_auth
def create_or_update_checkin():
    data = request.get_json() or {}
    
    # Extract counts
    nb = data.get('nb', 0)
    sb = data.get('sb', 0)
    sh = data.get('sh', 0)
    co = data.get('co', 0)
    wi = data.get('wi', 0)
    jo = data.get('jo', 0)
    
    # Validate
    for val in [nb, sb, sh, co, wi, jo]:
        if not isinstance(val, int) or val < 0:
            return jsonify({'error': 'Invalid input'}), 400
    
    requested_date = data.get('date')
    today_date = datetime.now().date()
    yesterday_date = today_date - timedelta(days=1)
    allowed_dates = {today_date.strftime('%Y-%m-%d')}
    if yesterday_date.year == today_date.year:
        allowed_dates.add(yesterday_date.strftime('%Y-%m-%d'))

    if requested_date:
        try:
            datetime.strptime(requested_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

        if requested_date not in allowed_dates:
            return jsonify({'error': 'Only today or yesterday is allowed'}), 400
        target_date = requested_date
    else:
        target_date = today_date.strftime('%Y-%m-%d')
    
    db = get_db()
    
    # Check if exists
    existing = db.execute(
        'SELECT id FROM checkins WHERE user_id = ? AND date = ?',
        (session['user_id'], target_date)
    ).fetchone()
    
    if existing:
        # Update
        db.execute(
            'UPDATE checkins SET nb=?, sb=?, sh=?, co=?, wi=?, jo=? WHERE id = ?',
            (nb, sb, sh, co, wi, jo, existing['id'])
        )
    else:
        # Insert
        db.execute(
            'INSERT INTO checkins (user_id, date, nb, sb, sh, co, wi, jo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (session['user_id'], target_date, nb, sb, sh, co, wi, jo)
        )
    
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'message': 'Check-in saved'}), 200

# ============================================================
# SCOREBOARD ENDPOINT (PUBLIC)
# ============================================================
@app.route('/api/scoreboard', methods=['GET'])
def get_scoreboard():
    """Public endpoint with ranking and score calculation."""

    mode = (request.args.get('mode') or 'champions').strip().lower()
    if mode not in {'champions', 'europa', 'conference'}:
        return jsonify({'error': 'Invalid mode'}), 400

    today_date = datetime.now().date()
    season_start = current_season_start(today_date)
    range_start = season_start.strftime('%Y-%m-%d')
    range_end = today_date.strftime('%Y-%m-%d')

    db = get_db()

    if mode == 'europa':
        score_expr = 'c.nb * 1.0 + c.sb * 1.5 + c.sh * 0.75 + c.co * 1.25 + c.wi * 1.5'
        day_expr = '(c.nb + c.sb + c.sh + c.co + c.wi) > 0'
    elif mode == 'conference':
        score_expr = 'c.jo * 1.0'
        day_expr = 'c.jo > 0'
    else:
        score_expr = 'c.nb * 1.0 + c.sb * 1.5 + c.sh * 0.75 + c.co * 1.25 + c.wi * 1.5 + c.jo * 1.25'
        day_expr = '(c.nb + c.sb + c.sh + c.co + c.wi + c.jo) > 0'

    day_case = f'CASE WHEN c.id IS NOT NULL AND {day_expr} THEN 1 ELSE 0 END'
    last_case = f'CASE WHEN c.id IS NOT NULL AND {day_expr} THEN c.date ELSE NULL END'
    
    # Get all users with checkin stats
    users_query = f'''
        SELECT 
            u.id,
            u.username,
            SUM({day_case}) as days,
            MAX({last_case}) as last_date,
            SUM(CASE WHEN c.id IS NOT NULL THEN {score_expr} ELSE 0 END) as total_score,
            SUM(CASE WHEN c.id IS NOT NULL THEN c.nb ELSE 0 END) as total_nb,
            SUM(CASE WHEN c.id IS NOT NULL THEN c.sb ELSE 0 END) as total_sb,
            SUM(CASE WHEN c.id IS NOT NULL THEN c.sh ELSE 0 END) as total_sh,
            SUM(CASE WHEN c.id IS NOT NULL THEN c.co ELSE 0 END) as total_co,
            SUM(CASE WHEN c.id IS NOT NULL THEN c.wi ELSE 0 END) as total_wi,
            SUM(CASE WHEN c.id IS NOT NULL THEN c.jo ELSE 0 END) as total_jo
        FROM users u
        LEFT JOIN checkins c ON u.id = c.user_id AND c.date BETWEEN ? AND ?
        WHERE u.role = 'user'
        GROUP BY u.id, u.username
        ORDER BY total_score DESC, u.username ASC
    '''

    rows = db.execute(users_query, (range_start, range_end)).fetchall()
    db.close()
    
    # Build scoreboard with ranks
    scoreboard = []
    for idx, row in enumerate(rows, 1):
        score = row['total_score'] or 0.0
        days = row['days'] or 0
        avg = score / days if days > 0 else 0.0
        
        scoreboard.append({
            'rank': idx,
            'username': row['username'],
            'score': round(score, 1),
            'days': days,
            'avg': round(avg, 1),
            'last_date': row['last_date'] or '—',
            'totals': {
                'nb': int(row['total_nb'] or 0),
                'sb': int(row['total_sb'] or 0),
                'sh': int(row['total_sh'] or 0),
                'co': int(row['total_co'] or 0),
                'wi': int(row['total_wi'] or 0),
                'jo': int(row['total_jo'] or 0)
            }
        })
    
    return jsonify({'scoreboard': scoreboard}), 200

# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================
# RUN
# ============================================================
if __name__ == '__main__':
    # Ensure /data directory exists
    os.makedirs('/data', exist_ok=True)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False
    )
