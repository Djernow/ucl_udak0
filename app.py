import os
import sqlite3
import random
import re
import json
from uuid import uuid4
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pywebpush import webpush, WebPushException

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "BAh3GCL7dRp3dD_B7TkCw41VJ4-Zw0da_8S9IZAW7JV8g1o5_Ej3iRuAFza3TJZr1s0PhCArtGEhV4jlQ2FpI1w")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgciB0yrlTD8q6qBrh
2MH4CKq9wX52V6Do75mAfidP58mhRANCAAQIdxgi+3Uad3Q/we05AsONVSePmcNH
Wv/EvSGQFuyVfINaOfxI94kbgBc2t0yWa9bND4QgK7RhIVeI5UNhaSNc
-----END PRIVATE KEY-----""")
VAPID_CLAIMS = {
    "sub": "mailto:admin@udako.libertronics.org"
}

app = Flask(__name__)
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError("SECRET_KEY environment variable is required in production mode!")
    secret_key = 'dev-key-change-in-production'
app.config['SECRET_KEY'] = secret_key
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)

DATABASE = os.environ.get('DATABASE_PATH', '/data/udako.db')
QUOTES_FILE = os.environ.get('QUOTES_FILE', 'daily_quotes.txt')
CONSUMPTION_PHOTOS_DIR = os.environ.get('CONSUMPTION_PHOTOS_DIR', os.path.join('/data', 'consumption-photos'))
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

    # Push subscriptions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            endpoint TEXT UNIQUE NOT NULL,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consumption_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            uploaded_by_user_id INTEGER NOT NULL,
            caption TEXT DEFAULT '',
            consumed_on TEXT,
            filename TEXT NOT NULL,
            original_filename TEXT,
            likes_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consumption_photo_likes (
            photo_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (photo_id, user_id),
            FOREIGN KEY (photo_id) REFERENCES consumption_photos(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS italy_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            link TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Seed initial items if empty
    cursor.execute('SELECT COUNT(*) FROM italy_info')
    if cursor.fetchone()[0] == 0:
        default_items = [
            ('vervoer', 'Heenvlucht', 'Charleroi (13:35) -> Bari (15:55)\nNa de vlucht: taxi of bus naar Bari Centrale -> trein naar Lecce Stazione', ''),
            ('vervoer', 'Terugvlucht', 'Brindisi (19:50) -> Charleroi (22:20)', ''),
            ('vervoer', "Auto's", 'Regelt Jarno met nonkel', ''),
            ('huisje', 'Adres', 'Via Prov.le per Castro, 51\nVignacastrisi, Castro, Puglia 73030', 'https://maps.google.com/?q=Via+Prov.le+per+Castro,+51,+Castro,+Puglia+73030'),
            ('huisje', 'Check In', 'Na 17:00 (geen probleem met vluchten)', ''),
            ('huisje', 'Check Out', 'Voor 11:00', ''),
            ('todo', 'Lecce', 'Gezellig barok stadje verkennen', ''),
            ('todo', 'Feesten', 'Gallipoli, Lecce', ''),
            ('snorkelen', 'Grotta Verde', 'Spiaggia della Grotta Verde', ''),
            ('snorkelen', 'Occhio di Nettuno', 'Occhio di Nettuno', ''),
            ('snorkelen', 'Torre Sant\'Emiliano', 'Torre Sant\'Emiliano', ''),
            ('snorkelen', 'Mulino d\'Acqua', 'Mulino d\'Acqua Beach', ''),
            ('snorkelen', 'spiaggetta dell\'Orte', 'spiaggetta dell\'Orte', ''),
            ('snorkelen', 'Cala dell\'Acquaviva', 'Cala dell\'Acquaviva', ''),
            ('diving', 'Torre Miggiano', 'Torre Miggiano', ''),
            ('diving', 'Il Ciolo', 'Il Ciolo', ''),
            ('diving', 'Cala del Canale', 'Cala del Canale del Càfaro', ''),
            ('special', 'Boot Huren', 'Muma Boat | Otranto\n± €200 + brandstof (per 6 personen)', ''),
            ('special', 'Karten', 'La Conca Circuit', 'https://www.themotorsportnetwork.com/circuits/la-conca')
        ]
        cursor.executemany(
            'INSERT INTO italy_info (category, title, content, link) VALUES (?, ?, ?, ?)',
            default_items
        )

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

    try:
        cursor.execute('PRAGMA table_info(consumption_photos)')
        columns = [row[1] for row in cursor.fetchall()]
        if 'likes_count' not in columns:
            cursor.execute('ALTER TABLE consumption_photos ADD COLUMN likes_count INTEGER DEFAULT 0')
            db.commit()
    except Exception:
        pass

    os.makedirs(CONSUMPTION_PHOTOS_DIR, exist_ok=True)

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

def allowed_photo_file(filename):
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    _, extension = os.path.splitext(filename.lower())
    return extension in allowed_extensions

def normalize_quote_text(text):
    value = text.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1].strip()
    return value

def parse_quote_author_line(line):
    value = line.strip()
    if value.startswith('~'):
        author = value[1:].strip()
        return author or None
    return None

def consumption_photo_to_dict(row):
    return {
        'id': row['id'],
        'user_id': row['user_id'],
        'username': row['username'],
        'uploaded_by_user_id': row['uploaded_by_user_id'],
        'caption': row['caption'] or '',
        'consumed_on': row['consumed_on'],
        'filename': row['filename'],
        'original_filename': row['original_filename'],
        'created_at': row['created_at'],
        'image_url': f"/api/consumption-photos/{row['id']}/file",
        'likes_count': row['likes_count'] if 'likes_count' in row.keys() else 0,
        'liked_by_me': bool(row['liked_by_me']) if 'liked_by_me' in row.keys() else False
    }

def load_quotes_from_file():
    quotes = []

    if not os.path.exists(QUOTES_FILE):
        return quotes

    with open(QUOTES_FILE, 'r', encoding='utf-8') as handle:
        pending_quote = None
        pending_line_number = None

        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue

            author = parse_quote_author_line(line)
            if author and pending_quote:
                quotes.append({
                    'id': len(quotes) + 1,
                    'quote': pending_quote,
                    'author': author,
                    'category': None,
                    'is_active': True,
                    'created_at': None,
                    'updated_at': None,
                    'source_line': pending_line_number,
                })
                pending_quote = None
                pending_line_number = None
                continue

            if pending_quote:
                quotes.append({
                    'id': len(quotes) + 1,
                    'quote': pending_quote,
                    'author': None,
                    'category': None,
                    'is_active': True,
                    'created_at': None,
                    'updated_at': None,
                    'source_line': pending_line_number,
                })
                pending_quote = None
                pending_line_number = None

            if ' ~ ' in line:
                quote_part, author_part = line.rsplit(' ~ ', 1)
                quote = normalize_quote_text(quote_part)
                author = author_part.strip() or None
                if quote:
                    quotes.append({
                        'id': len(quotes) + 1,
                        'quote': quote,
                        'author': author,
                        'category': None,
                        'is_active': True,
                        'created_at': None,
                        'updated_at': None,
                        'source_line': line_number,
                    })
                continue

            quote = normalize_quote_text(line)
            if not quote:
                continue

            pending_quote = quote
            pending_line_number = line_number

        if pending_quote:
            quotes.append({
                'id': len(quotes) + 1,
                'quote': pending_quote,
                'author': None,
                'category': None,
                'is_active': True,
                'created_at': None,
                'updated_at': None,
                'source_line': pending_line_number,
            })

    return quotes

def get_quote_by_id(quote_id):
    for quote in load_quotes_from_file():
        if quote['id'] == quote_id:
            return quote
    return None

def get_daily_quote():
    quotes = load_quotes_from_file()
    if not quotes:
        return None

    today_key = datetime.now().date().isoformat()
    seed = 0
    for char in today_key:
        seed = ((seed * 31) + ord(char)) & 0xFFFFFFFF

    return quotes[seed % len(quotes)]

def quote_to_dict(quote):
    return {
        'id': quote['id'],
        'quote': quote['quote'],
        'author': quote.get('author'),
        'category': quote.get('category'),
        'is_active': bool(quote.get('is_active', True)),
        'created_at': quote.get('created_at'),
        'updated_at': quote.get('updated_at'),
        'source_line': quote.get('source_line')
    }

def vapid_configured():
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)

def send_webpush(subscription, payload):
    webpush(
        subscription_info=subscription,
        data=payload,
        vapid_private_key=VAPID_PRIVATE_KEY,
        vapid_claims=VAPID_CLAIMS
    )

# ============================================================
# PUSH NOTIFICATIONS ENDPOINTS
# ============================================================
@app.route('/api/push/public-key', methods=['GET'])
def get_push_public_key():
    return jsonify({'publicKey': VAPID_PUBLIC_KEY}), 200

@app.route('/api/push/subscribe', methods=['POST'])
@require_auth
def subscribe_push():
    data = request.get_json() or {}
    sub = data.get('subscription')
    if not sub or 'endpoint' not in sub or 'keys' not in sub:
        return jsonify({'error': 'Subscription object required'}), 400
    
    endpoint = sub['endpoint']
    p256dh = sub['keys'].get('p256dh')
    auth = sub['keys'].get('auth')
    
    if not p256dh or not auth:
        return jsonify({'error': 'Subscription keys required'}), 400
        
    db = get_db()
    try:
        db.execute('''
            INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id, p256dh=excluded.p256dh, auth=excluded.auth
        ''', (session['user_id'], endpoint, p256dh, auth))
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 500
    db.close()
    return jsonify({'success': True}), 200

@app.route('/api/push/test', methods=['POST'])
@require_auth
def test_push():
    if not vapid_configured():
        return jsonify({'error': 'VAPID keys not configured on server'}), 500
        
    db = get_db()
    rows = db.execute('SELECT * FROM push_subscriptions WHERE user_id = ?', (session['user_id'],)).fetchall()
    db.close()
    
    if not rows:
        return jsonify({'error': 'No active push subscriptions found for this user'}), 400
        
    payload = json.dumps({
        'title': 'UDAKO CL',
        'body': 'Test Push Notification works! 🍺'
    })
    
    success_count = 0
    fail_count = 0
    
    db = get_db()
    for row in rows:
        sub_info = {
            'endpoint': row['endpoint'],
            'keys': {
                'p256dh': row['p256dh'],
                'auth': row['auth']
            }
        }
        try:
            send_webpush(sub_info, payload)
            success_count += 1
        except WebPushException as ex:
            if ex.response is not None and ex.response.status_code in {410, 404}:
                db.execute('DELETE FROM push_subscriptions WHERE id = ?', (row['id'],))
                db.commit()
            fail_count += 1
        except Exception:
            fail_count += 1
            
    db.close()
    return jsonify({
        'success': True,
        'sent': success_count,
        'failed': fail_count
    }), 200

# ============================================================
# ANNOUNCEMENTS ENDPOINTS
# ============================================================
@app.route('/api/announcements', methods=['GET'])
@require_auth
def get_announcements():
    db = get_db()
    rows = db.execute('SELECT * FROM announcements ORDER BY created_at DESC, id DESC').fetchall()
    db.close()
    return jsonify({'announcements': [{'id': r['id'], 'content': r['content'], 'created_at': r['created_at']} for r in rows]}), 200

@app.route('/api/announcements', methods=['POST'])
@require_admin
def add_announcement():
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    
    db = get_db()
    db.execute('INSERT INTO announcements (content) VALUES (?)', (content,))
    db.commit()
    db.close()
    return jsonify({'success': True}), 201

@app.route('/api/announcements/<int:announcement_id>', methods=['DELETE'])
@require_admin
def delete_announcement(announcement_id):
    db = get_db()
    row = db.execute('SELECT id FROM announcements WHERE id = ?', (announcement_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'error': 'Announcement not found'}), 404
    db.execute('DELETE FROM announcements WHERE id = ?', (announcement_id,))
    db.commit()
    db.close()
    return jsonify({'success': True}), 200

# ============================================================
# ITALY INFO ENDPOINTS
# ============================================================
@app.route('/api/italy-info', methods=['GET'])
@require_admin
def get_italy_info():
    db = get_db()
    rows = db.execute('SELECT * FROM italy_info ORDER BY id ASC').fetchall()
    db.close()
    return jsonify({
        'items': [{
            'id': r['id'],
            'category': r['category'],
            'title': r['title'],
            'content': r['content'],
            'link': r['link'],
            'created_at': r['created_at']
        } for r in rows]
    }), 200

@app.route('/api/italy-info', methods=['POST'])
@require_admin
def add_italy_info():
    data = request.get_json() or {}
    category = data.get('category', '').strip()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    link = data.get('link', '').strip()

    if not category or not content:
        return jsonify({'error': 'Category and content are required'}), 400

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO italy_info (category, title, content, link) VALUES (?, ?, ?, ?)',
        (category, title, content, link)
    )
    new_id = cursor.lastrowid
    db.commit()
    db.close()

    return jsonify({'success': True, 'id': new_id}), 201

@app.route('/api/italy-info/<int:item_id>', methods=['DELETE'])
@require_admin
def delete_italy_info(item_id):
    db = get_db()
    row = db.execute('SELECT id FROM italy_info WHERE id = ?', (item_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'error': 'Item not found'}), 404
    db.execute('DELETE FROM italy_info WHERE id = ?', (item_id,))
    db.commit()
    db.close()
    return jsonify({'success': True}), 200

@app.route('/api/italy-info/<int:item_id>', methods=['PUT'])
@require_admin
def update_italy_info(item_id):
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    link = data.get('link', '').strip()

    if not content:
        return jsonify({'error': 'Content is required'}), 400

    db = get_db()
    row = db.execute('SELECT id FROM italy_info WHERE id = ?', (item_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'error': 'Item not found'}), 404

    db.execute(
        'UPDATE italy_info SET title = ?, content = ?, link = ? WHERE id = ?',
        (title, content, link, item_id)
    )
    db.commit()
    db.close()
    return jsonify({'success': True}), 200

# ============================================================
# HEALTH CHECK
# ============================================================
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

# ============================================================
# QUOTES ENDPOINTS
# ============================================================
@app.route('/api/quotes', methods=['GET'])
def get_quotes():
    quotes = load_quotes_from_file()
    return jsonify({'quotes': [quote_to_dict(quote) for quote in quotes]}), 200

@app.route('/api/quotes/today', methods=['GET'])
def get_today_quote():
    quote = get_daily_quote()
    if not quote:
        return jsonify({'quote': None}), 200

    return jsonify({'quote': quote_to_dict(quote)}), 200

@app.route('/api/quotes/random', methods=['GET'])
def get_random_quote():
    quotes = load_quotes_from_file()
    if not quotes:
        return jsonify({'quote': None}), 200
    quote = random.choice(quotes)
    return jsonify({'quote': quote_to_dict(quote)}), 200

@app.route('/api/quotes/<int:quote_id>', methods=['GET'])
def get_quote(quote_id):
    quote = get_quote_by_id(quote_id)

    if not quote:
        return jsonify({'error': 'Quote not found'}), 404

    return jsonify({'quote': quote_to_dict(quote)}), 200

# ============================================================
# CONSUMPTION PHOTOS ENDPOINTS
# ============================================================
@app.route('/api/consumption-photos', methods=['GET'])
@require_auth
def get_consumption_photos():
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', type=int)

    db = get_db()
    query = '''
        SELECT p.id, p.user_id, p.uploaded_by_user_id, p.caption, p.consumed_on, p.filename, p.original_filename, p.created_at,
               u.username,
               (SELECT COUNT(*) FROM consumption_photo_likes WHERE photo_id = p.id) as likes_count,
               (SELECT EXISTS(SELECT 1 FROM consumption_photo_likes WHERE photo_id = p.id AND user_id = ?)) as liked_by_me
        FROM consumption_photos p
        JOIN users u ON u.id = p.user_id
        ORDER BY p.created_at DESC, p.id DESC
    '''
    params = [session['user_id']]

    if limit is not None:
        query += ' LIMIT ?'
        params.append(limit)
    if offset is not None:
        query += ' OFFSET ?'
        params.append(offset)

    rows = db.execute(query, tuple(params)).fetchall()
    db.close()

    return jsonify({'photos': [consumption_photo_to_dict(row) for row in rows]}), 200

@app.route('/api/consumption-photos', methods=['POST'])
@require_auth
def add_consumption_photo():
    photo_file = request.files.get('photo')

    if not photo_file or not photo_file.filename:
        return jsonify({'error': 'Photo file is required'}), 400

    original_filename = secure_filename(photo_file.filename)
    if not allowed_photo_file(original_filename):
        return jsonify({'error': 'Unsupported image type'}), 400

    file_extension = os.path.splitext(original_filename)[1].lower()
    stored_filename = f"{uuid4().hex}{file_extension}"
    stored_path = os.path.join(CONSUMPTION_PHOTOS_DIR, stored_filename)
    photo_file.save(stored_path)
    consumed_on = datetime.now().date().isoformat()
    caption = request.form.get('caption', '').strip()

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        '''
        INSERT INTO consumption_photos (
            user_id, uploaded_by_user_id, caption, consumed_on, filename, original_filename
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (session['user_id'], session['user_id'], caption, consumed_on, stored_filename, original_filename)
    )
    photo_id = cursor.lastrowid
    db.commit()
    db.close()

    db = get_db()
    row = db.execute(
        '''
        SELECT p.id, p.user_id, p.uploaded_by_user_id, p.caption, p.consumed_on, p.filename, p.original_filename, p.created_at,
               u.username,
               0 as likes_count,
               0 as liked_by_me
        FROM consumption_photos p
        JOIN users u ON u.id = p.user_id
        WHERE p.id = ?
        ''',
        (photo_id,)
    ).fetchone()
    db.close()

    return jsonify({'success': True, 'photo': consumption_photo_to_dict(row)}), 201

@app.route('/api/consumption-photos/<int:photo_id>/file', methods=['GET'])
@require_auth
def get_consumption_photo_file(photo_id):
    db = get_db()
    row = db.execute('SELECT filename FROM consumption_photos WHERE id = ?', (photo_id,)).fetchone()
    db.close()

    if not row:
        return jsonify({'error': 'Photo not found'}), 404

    return send_from_directory(CONSUMPTION_PHOTOS_DIR, row['filename'])

@app.route('/api/consumption-photos/<int:photo_id>', methods=['DELETE'])
@require_auth
def delete_consumption_photo(photo_id):
    db = get_db()
    row = db.execute(
        'SELECT filename, uploaded_by_user_id FROM consumption_photos WHERE id = ?',
        (photo_id,)
    ).fetchone()
    if not row:
        db.close()
        return jsonify({'error': 'Photo not found'}), 404

    actor = db.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if not actor or (row['uploaded_by_user_id'] != session['user_id'] and actor['role'] != 'admin'):
        db.close()
        return jsonify({'error': 'Forbidden'}), 403

    db.execute('DELETE FROM consumption_photos WHERE id = ?', (photo_id,))
    db.commit()
    db.close()

    try:
        os.remove(os.path.join(CONSUMPTION_PHOTOS_DIR, row['filename']))
    except OSError:
        pass

    return jsonify({'success': True}), 200

@app.route('/api/consumption-photos/<int:photo_id>/like', methods=['POST'])
@require_auth
def like_consumption_photo(photo_id):
    db = get_db()
    # Check if photo exists
    photo = db.execute('SELECT id FROM consumption_photos WHERE id = ?', (photo_id,)).fetchone()
    if not photo:
        db.close()
        return jsonify({'error': 'Photo not found'}), 404
        
    # Check if already liked
    user_id = session['user_id']
    liked = db.execute('SELECT 1 FROM consumption_photo_likes WHERE photo_id = ? AND user_id = ?', (photo_id, user_id)).fetchone()
    
    if liked:
        # Unlike
        db.execute('DELETE FROM consumption_photo_likes WHERE photo_id = ? AND user_id = ?', (photo_id, user_id))
        action = 'unliked'
        liked_by_me = False
    else:
        # Like
        db.execute('INSERT INTO consumption_photo_likes (photo_id, user_id) VALUES (?, ?)', (photo_id, user_id))
        action = 'liked'
        liked_by_me = True
        
    db.commit()
    
    # Get updated count
    count_row = db.execute('SELECT COUNT(*) as likes_count FROM consumption_photo_likes WHERE photo_id = ?', (photo_id,)).fetchone()
    likes_count = count_row['likes_count']
    db.close()
    
    return jsonify({
        'success': True,
        'action': action,
        'likes_count': likes_count,
        'liked_by_me': liked_by_me
    }), 200

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
    session.permanent = True
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
    
    if not re.match(r'^[a-zA-Z0-9_\.\-]+$', username):
        return jsonify({'error': 'Username can only contain alphanumeric characters, dots, hyphens, and underscores'}), 400
    
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

    target_user_id = session['user_id']
    username_param = request.args.get('username')
    if username_param:
        if session.get('role') != 'admin' and username_param.strip().lower() != session.get('username'):
            return jsonify({'error': 'Forbidden'}), 403
        user = get_user_by_username(username_param.strip().lower())
        if not user:
            return jsonify({'error': 'User not found'}), 404
        target_user_id = user['id']

    db = get_db()
    if scope == 'all':
        checkins = db.execute(
            'SELECT * FROM checkins WHERE user_id = ? ORDER BY date DESC',
            (target_user_id,)
        ).fetchall()
    else:
        checkins = db.execute(
            'SELECT * FROM checkins WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date DESC',
            (target_user_id, range_start, range_end)
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

    if requested_date:
        try:
            req_date_obj = datetime.strptime(requested_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

        # Allow dates from 2 days ago up to 1 day in the future (relative to server time)
        # to accommodate timezone offsets up to 24 hours.
        days_diff = (req_date_obj - today_date).days
        if not (-2 <= days_diff <= 1):
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
