# UDAKO CL - Deployment Complete ✅

## Project Files Created

Your UDAKO Champions League application is fully configured for deployment to TrueNAS SCALE. Here's what's been created:

### **Frontend (Web Application)**
- **website.html** (36 KB)
  - Full Progressive Web App (PWA) with API integration
  - User login with forced password change on first login
  - Daily check-in interface with counters for 5 drink categories
  - Real-time scoreboard with rankings, stats, and filtering
  - Admin panel for user management
  - Supports offline access via service worker
  - Dark theme with UDAKO CL branding (#e8c84a gold, #0f0f11 dark background)

- **manifest.json**
  - PWA metadata for app installation on Android/iOS/Desktop
  - Branding: "UDAKO champions league" / "UDAKO CL"
  - Standalone display mode, portrait orientation

- **service-worker.js**
  - Offline caching strategy (network-first with fallback)
  - Cache versioning for updates
  - Skips API calls to preserve real-time functionality

### **Backend (Flask REST API)**
- **app.py** (422 lines)
  - SQLite database with users and check-ins tables
  - Session-based authentication (secure cookies)
  - User roles: admin and user
  - Default admin: username=`admin`, password=`admin123`
  - Complete REST API:
    - Authentication: /api/auth/login, logout, change-password
    - User management (admin): /api/users/add, reset-password, delete
    - Check-ins (user): /api/checkins (POST/GET)
    - Scoreboard (public): /api/scoreboard with rankings
  - Password hashing with Werkzeug PBKDF2
  - Score calculation: nb=1.0×, sb=1.5×, sh=0.75×, co=1.25×, jo=2.0×

- **requirements.txt**
  - Flask==2.3.3
  - Werkzeug==2.3.7

### **Deployment Configuration**
- **docker-compose.yaml**
  - Orchestrates httpd (frontend) and Flask (backend) services
  - Flask runs on port 5000 internally, httpd on 50995→80
  - Mounted volumes for persistent database storage
  - Network bridge for container communication
  - Environment variables: FLASK_ENV, DATABASE_PATH, SECRET_KEY

- **Dockerfile.backend**
  - Alpine Python 3.11 base image
  - Installs Flask dependencies
  - Exposes port 5000
  - Ensures /data directory for SQLite database

- **httpd-proxy.conf**
  - Apache reverse proxy configuration
  - Routes /api/* requests to Flask backend
  - SPA routing support (non-existent files → website.html)
  - DirectoryIndex set to website.html

- **deploy.sh**
  - Automated deployment script for TrueNAS
  - Copies all files to dataset at /mnt/immich/Jarno_app/udako/
  - Sets correct permissions (755 for directories, 644 for files)
  - Outputs next deployment steps

### **Documentation**
- **DEPLOYMENT_GUIDE.md** (150+ lines)
  - Complete architecture diagram
  - Step-by-step deployment instructions for TrueNAS SCALE
  - Database schema explanation
  - All API endpoints with request/response examples
  - Score calculation formula
  - Features overview (roles, daily check-in, scoreboard, PWA)
  - Troubleshooting guide
  - Backup/recovery procedures
  - Security notes

---

## 🚀 Quick Start (TrueNAS SCALE)

### 1. **Copy Files to Dataset**
```bash
./deploy.sh
```

### 2. **Create Docker Container**
- TrueNAS SCALE → Applications → Launch Docker Image
- Select "Custom Docker Compose YAML"
- Paste contents of `docker-compose.yaml`
- Set `SECRET_KEY` to random 32+ character string
- Save and deploy

### 3. **Access Application**
- **Local**: http://127.0.0.1:50995/
- **Production**: https://udako.libertronics.org/ (via Cloudflare)
- **Default Admin**: username=`admin`, password=`admin123`

---

## 📊 Architecture Summary

```
Client Browser/Mobile (HTTPS via Cloudflare)
         ↓
    Port 50995 (TrueNAS)
         ↓
  ┌──────────────┐
  │   httpd      │ (Apache with reverse proxy)
  │   :80        │
  └──────┬───────┘
         │
    ┌────┴─────┐
    ↓          ↓
Website.html  /api/* requests
(Frontend)       ↓
            ┌─────────────┐
            │ Flask:5000  │ (Backend API)
            │   :5000     │
            └─────┬───────┘
                  ↓
          ┌──────────────┐
          │  SQLite DB   │
          │ /data/udako  │
          │     .db      │
          └──────────────┘
```

---

## 🔑 Key Features Implemented

✅ Progressive Web App (PWA) for mobile installation
✅ Session-based authentication with password hashing
✅ Daily drink intake tracking with 5 categories
✅ Real-time scoreboard with rankings and stats
✅ Admin user management panel
✅ Forced password change on first login
✅ Offline-capable (service worker caching)
✅ Dark theme with UDAKO CL branding
✅ REST API with complete CRUD operations
✅ SQLite database with schema versioning
✅ Docker containerization for easy deployment
✅ Apache reverse proxy for seamless frontend-backend communication

---

## 📝 Configuration

### Change Drink Multipliers
Edit in `website.html` (top of `<script>` section):
```javascript
const MULT = {
  nb: 1.0,    // normal beer
  sb: 1.5,    // special beer
  sh: 0.75,   // shot
  co: 1.25,   // cocktail
  jo: 2.0     // joint
};
```

### Database Persistence
Database stored at `/mnt/immich/Jarno_app/udako/data/udako.db`
- Automatically created on first backend startup
- Default admin user created if DB empty
- Persists between container restarts (mounted volume)

### Security
- Passwords hashed with Werkzeug PBKDF2
- Session cookies: HTTPONLY, SECURE, SAMESITE=Lax
- Admin-only endpoints protected with role decorators
- **Change default admin password immediately after first login!**

---

## 🛠️ Troubleshooting

### Flask API Not Responding
```bash
curl http://127.0.0.1:5000/api/health
```

### Check Logs
```bash
docker logs <container_id>
```

### Verify Database
```bash
ls -lh /mnt/immich/Jarno_app/udako/data/udako.db
```

### Proxy Errors (502)
- Ensure Flask backend is running
- Verify Docker network connectivity
- Check `httpd-proxy.conf` is mounted correctly

---

## 📦 Files Summary

| File | Size | Purpose |
|------|------|---------|
| website.html | 36 KB | Main SPA with API integration |
| app.py | 13 KB | Flask backend with all endpoints |
| docker-compose.yaml | 1.4 KB | Container orchestration |
| Dockerfile.backend | 270 B | Flask container image spec |
| httpd-proxy.conf | 1.1 KB | Apache reverse proxy config |
| manifest.json | 2 KB | PWA metadata |
| service-worker.js | 2 KB | Offline caching logic |
| requirements.txt | 29 B | Python dependencies |
| deploy.sh | 3 KB | Deployment automation |
| DEPLOYMENT_GUIDE.md | 8 KB | Complete documentation |

---

## ✨ Next Steps

1. **Run deploy.sh** to copy files to TrueNAS dataset
2. **Create Docker container** using docker-compose.yaml in TrueNAS SCALE
3. **Access application** at http://127.0.0.1:50995/
4. **Log in** with admin / admin123
5. **Change admin password** immediately
6. **Add users** via admin panel
7. **Start tracking drinks!** 🍺

---

**Version**: 1.0  
**Status**: ✅ Ready for Production  
**Last Updated**: 2024
