# UDAKO Champions League - Deployment & Architecture Guide

## Overview

**UDAKO CL** is a Progressive Web App (PWA) scoreboard application for tracking drink intake and calculating rankings. It combines a **Flask backend** with **Apache frontend**, both running in Docker containers on **TrueNAS SCALE**.

- **Frontend**: HTML5/CSS/JavaScript SPA served via Apache
- **Backend**: Flask REST API with SQLite database
- **Storage**: Persistent SQLite database in `/data/udako.db`
- **Access**: HTTPS via Cloudflare (https://udako.libertronics.org)

---

## Architecture

```
┌─────────────────────────────────────┐
│     Client (Browser/Mobile)         │
│      https://udako.libertronics.org │
└──────────────────┬──────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
    HTTPS/TLS          TrueNAS SCALE
    via Cloudflare   ┌──────────────────┐
        │            │  Docker Compose  │
        └────────────┤                  │
                     │  ┌────────────┐  │
                     │  │ httpd:80   │  │ (port 50995→80)
                     │  │ (Frontend) │  │
                     │  └─────┬──────┘  │
                     │        │         │
                     │   Proxy /api/*   │
                     │        │         │
                     │  ┌─────▼──────┐  │
                     │  │Flask:5000  │  │
                     │  │ (Backend)  │  │
                     │  └─────┬──────┘  │
                     │        │         │
                     │   ┌────▼─────┐   │
                     │   │SQLite DB  │   │
                     │   │/data/     │   │
                     │   │udako.db   │   │
                     │   └──────────┘   │
                     └──────────────────┘
```

---

## Deployment Steps

### 1. Prepare TrueNAS Dataset

```bash
# On TrueNAS via SSH, create dataset structure:
mkdir -p /mnt/immich/Jarno_app/udako/data
chmod 755 /mnt/immich/Jarno_app/udako/data
```

### 2. Copy Application Files

Run the deployment script:

```bash
./deploy.sh
```

This copies:
- `website.html` - Main SPA application
- `manifest.json` - PWA metadata
- `service-worker.js` - Offline caching
- `app.py` - Flask backend API
- `requirements.txt` - Python dependencies
- `Dockerfile.backend` - Backend container image
- `docker-compose.yaml` - Container orchestration
- `httpd-proxy.conf` - Apache reverse proxy config

### 3. Create Docker Container in TrueNAS SCALE

#### Option A: First Time Setup

1. Go to **TrueNAS SCALE** → **Applications** → **Launch Docker Image**
2. Select **Custom Docker Compose YAML**
3. Copy entire contents of `docker-compose.yaml`
4. Paste into the YAML editor
5. Set environment variables:
   - `SECRET_KEY`: Generate a random secure string (min 32 chars)
   - `FLASK_ENV`: `production`
6. Click **Save & Deploy**

#### Option B: Update Existing Container

1. **Applications** → **Installed Applications** → Find UDAKO app
2. Click **Edit** or **Update**
3. Replace Docker Compose YAML with new version from `docker-compose.yaml`
4. Apply changes

### 4. Verify Deployment

```bash
# Test Flask health check
curl http://127.0.0.1:5000/api/health
# Expected: {"status": "ok"}

# Test frontend
curl http://127.0.0.1:50995/website.html
# Should return HTML content

# Verify database created
ls -lh /mnt/immich/Jarno_app/udako/data/udako.db
# Should exist with default admin user
```

---

## Database Schema

### users table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT,              -- 'admin' or 'user'
    must_change_pw INTEGER, -- 1 if user must change password
    created_at TIMESTAMP
);
```

**Default Admin User**:
- Username: `admin`
- Password: `admin123`
- ⚠️ **Change immediately on first login!**

### checkins table
```sql
CREATE TABLE checkins (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    date TEXT,              -- YYYY-MM-DD
    nb INTEGER,             -- normal beer count
    sb INTEGER,             -- special beer count
    sh INTEGER,             -- shot count
    co INTEGER,             -- cocktail count
    jo INTEGER,             -- joint count
    created_at TIMESTAMP,
    UNIQUE(user_id, date)   -- Only one entry per user per day
);
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| POST | `/api/auth/login` | `{username, password}` | `{success, user}` |
| POST | `/api/auth/logout` | - | `{success}` |
| GET | `/api/auth/me` | - | `{user}` |
| POST | `/api/auth/change-password` | `{password}` | `{success}` |

### Check-ins (Authenticated)

| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| GET | `/api/checkins` | - | `{checkins: [...]}` |
| POST | `/api/checkins` | `{nb, sb, sh, co, jo}` | `{success}` |

### Admin Endpoints

| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| GET | `/api/users` | - | `{users: [...]}` |
| POST | `/api/users/add` | `{username, password}` | `{success}` |
| POST | `/api/users/reset-password` | `{username, password}` | `{success}` |
| POST | `/api/users/delete` | `{username}` | `{success}` |

### Public Endpoints

| Method | Endpoint | Response |
|--------|----------|----------|
| GET | `/api/scoreboard` | `{scoreboard: [{rank, username, score, days, avg, last_date}, ...]}` |
| GET | `/api/health` | `{status: "ok"}` |

---

## Score Calculation

Each item is converted to **standard beer equivalents** using these multipliers:

| Item | Multiplier | Equivalent |
|------|-----------|-----------|
| 🍺 Normal Beer | 1.0× | 1.0 std |
| 🍻 Special Beer | 1.5× | 1.5 std |
| 🥃 Shot | 0.75× | 0.75 std |
| 🍹 Cocktail | 1.25× | 1.25 std |
| 🚬 Joint | 2.0× | 2.0 std |

**Formula**: `Total = (nb × 1.0) + (sb × 1.5) + (sh × 0.75) + (co × 1.25) + (jo × 2.0)`

To change multipliers, edit the `MULT` object in `website.html` (top of `<script>` section).

---

## Features

### User Roles

**Admin**:
- View all users and full scoreboard
- Add/delete users
- Reset user passwords
- View check-in history

**User**:
- Submit daily check-ins
- View personal scoreboard rank
- View check-in history
- Change own password

### Daily Check-in

Users can log intake with category counters:
- Counter buttons (+ / −) for each item type
- Real-time equivalency calculation
- Saves one entry per user per day (updates if re-submitted)

### Scoreboard

**Public** — visible to all (no auth required):
- Ranks users by total score
- Shows total beer equivalents
- Days logged
- Average intake per day
- Last check-in date

**Admin View** — includes user management:
- Add new users (temporary password)
- Reset user passwords (forced change on next login)
- Delete users (cascades to delete their check-ins)
- View multiplier configuration

### PWA Installation

Install as native app on devices:

**Android (Chrome)**:
1. Open https://udako.libertronics.org
2. Menu → "Install app" (or prompted automatically)
3. Adds to home screen with icon

**iOS (Safari)**:
1. Open https://udako.libertronics.org
2. Share → Add to Home Screen
3. Appears as standalone app

**Desktop (Chrome/Edge)**:
1. Open https://udako.libertronics.org
2. Click install button in address bar
3. Installs to application menu

---

## Configuration

### Environment Variables

Set in TrueNAS Docker Compose environment section:

```yaml
environment:
  - FLASK_ENV=production         # Use 'development' for debugging
  - DATABASE_PATH=/data/udako.db # SQLite database location
  - SECRET_KEY=<secure_random>   # Session encryption (min 32 chars)
```

### Multipliers (Score Weights)

Edit in `website.html` script section:

```javascript
const MULT = {
  nb: 1.0,    // normal beer
  sb: 1.5,    // special beer
  sh: 0.75,   // shot
  co: 1.25,   // cocktail
  jo: 2.0     // joint
};
```

**Must sync manually between frontend and backend** if changing!

---

## Troubleshooting

### Flask API not responding

```bash
# Check container logs
docker logs <container_id>

# Test health endpoint
curl http://127.0.0.1:5000/api/health
```

### Database errors

```bash
# Verify database exists
ls -lh /mnt/immich/Jarno_app/udako/data/udako.db

# Check permissions
chmod 755 /mnt/immich/Jarno_app/udako/data
```

### Session/Login issues

- Clear browser cookies/cache
- Ensure `SECRET_KEY` is set
- Check browser security settings (SameSite cookies)

### 404 on `/website.html`

- Verify file copied to dataset
- Check Apache DirectoryIndex in proxy config
- Restart httpd container

### Proxy errors (`502 Bad Gateway`)

- Verify Flask backend running: `curl http://backend:5000/api/health`
- Check network connectivity between containers
- Verify docker network `udako-net` exists

---

## Backup & Recovery

### Backup Database

```bash
# On TrueNAS
cp /mnt/immich/Jarno_app/udako/data/udako.db \
   /mnt/immich/Jarno_app/udako/data/udako.db.backup
```

### Restore Database

```bash
# Stop containers
docker-compose down

# Restore backup
cp /mnt/immich/Jarno_app/udako/data/udako.db.backup \
   /mnt/immich/Jarno_app/udako/data/udako.db

# Restart
docker-compose up -d
```

---

## Security Notes

1. **Change default admin password immediately** (`admin123`)
2. **Use HTTPS** (Cloudflare TLS) for all production access
3. **Set SECRET_KEY** to random 32+ character string in production
4. **Database backup** — regularly backup `/data/udako.db`
5. **Session cookies** are HTTPONLY, SECURE, SAMESITE=Lax
6. **Password hashing** uses Werkzeug PBKDF2

---

## Maintenance

### Update Application

1. Update files on local machine
2. Run `./deploy.sh` to copy to dataset
3. Restart containers in TrueNAS

### Monitor Usage

- Check database size: `du -sh /mnt/immich/Jarno_app/udako/data/`
- View container logs for errors
- Monitor disk space for SQLite growth

### Clean Old Data

To archive/delete old check-ins:

```bash
# Connect to SQLite
sqlite3 /mnt/immich/Jarno_app/udako/data/udako.db

# Delete entries older than date
sqlite> DELETE FROM checkins WHERE date < '2023-01-01';
sqlite> VACUUM;
```

---

## Support & Debugging

**Enable Flask debug logs** (temporary):

Set `FLASK_ENV=development` in docker-compose.yaml and redeploy.

**Check API responses**:

```bash
# Login
curl -c cookies.txt -d '{"username":"admin","password":"admin123"}' \
  -H "Content-Type: application/json" \
  http://127.0.0.1:5000/api/auth/login

# Get scoreboard
curl -b cookies.txt http://127.0.0.1:5000/api/scoreboard
```

---

**Version**: 1.0  
**Last Updated**: 2024  
**Application**: UDAKO Champions League (UDAKO CL)
