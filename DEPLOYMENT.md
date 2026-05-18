# UDAKO Champions League — Deploy & Install Guide

Quick deployment for TrueNAS SCALE + Android PWA.

## TL;DR — Fast Deploy (5 minutes)

### On TrueNAS Host

```bash
# SSH into TrueNAS
ssh user@TRUENAS_IP

# Clone or download repo to TrueNAS
cd /tmp
git clone <your-repo-url> udako-cl
cd udako-cl

# Run deployment script
chmod +x deploy.sh
./deploy.sh

# Verify deployment
curl -i http://127.0.0.1:50995/
```

**Done!** Files are now served from your Docker container.

---

## File Structure

```
udako-cl/
├── website.html          # Main app (HTML + CSS + JS)
├── index.html           # (Auto-created symlink to website.html)
├── manifest.json        # PWA manifest (app metadata)
├── service-worker.js    # Offline caching
├── docker-compose.yaml  # Docker Compose config (Apache httpd)
├── deploy.sh           # Automated deployment script
├── site-deploy.yaml    # Kubernetes manifest (optional)
├── PWA_SETUP.md        # PWA installation guide
├── DEPLOYMENT.md       # This file
└── README.md           # Project overview
```

---

## Detailed Setup Steps

### 1. **Create TrueNAS Dataset** (if not already done)

```bash
ssh user@TRUENAS_IP
sudo mkdir -p /mnt/immich/Jarno_app/udako
sudo chown -R root:root /mnt/immich/Jarno_app/udako
sudo chmod -R 755 /mnt/immich/Jarno_app/udako
```

### 2. **Copy Files to Dataset**

**Option A: Using SCP (from your workstation)**
```bash
scp -r website.html manifest.json service-worker.js user@TRUENAS_IP:/mnt/immich/Jarno_app/udako/
```

**Option B: Using deployment script (on TrueNAS)**
```bash
ssh user@TRUENAS_IP
cd /tmp && git clone <your-repo-url> udako-cl && cd udako-cl
chmod +x deploy.sh && ./deploy.sh
```

**Option C: Manual copy on TrueNAS Shell**
```bash
cp /path/to/website.html /mnt/immich/Jarno_app/udako/
cp /path/to/manifest.json /mnt/immich/Jarno_app/udako/
cp /path/to/service-worker.js /mnt/immich/Jarno_app/udako/
```

### 3. **Set Permissions**

```bash
sudo chmod -R 755 /mnt/immich/Jarno_app/udako
sudo chown -R root:root /mnt/immich/Jarno_app/udako
echo "DirectoryIndex index.html" | sudo tee /mnt/immich/Jarno_app/udako/.htaccess
```

### 4. **Deploy Docker Container**

**Option A: TrueNAS Apps UI (Easiest)**
1. Apps → Launch Docker Image
2. Select "Custom Compose YAML"
3. Paste contents of `docker-compose.yaml`
4. Deploy

**Option B: Docker CLI (on TrueNAS)**
```bash
docker-compose -f docker-compose.yaml up -d
```

### 5. **Verify Deployment**

```bash
# Check container is running
docker ps | grep static-site

# Test locally
curl -i http://127.0.0.1:50995/
curl -i http://127.0.0.1:50995/index.html

# View container logs
docker logs static-site-1
```

---

## Android PWA Installation

Once deployed and accessible via HTTPS (Cloudflare handles this):

### Chrome Install (Recommended)
1. Open `https://udako.libertronics.org` on Android
2. Wait 2–3 seconds for the install prompt
3. Tap **"Install app"** → **"Install"**
4. App appears on home screen!

### Manual Add to Home Screen
1. Open `https://udako.libertronics.org` in Chrome
2. Tap **⋮ → "Add to Home screen"**
3. Confirm app name → **Add**

### iOS Safari
1. Open `https://udako.libertronics.org` in Safari
2. Tap **Share** (↗) → **"Add to Home Screen"**
3. Confirm → **Add**

---

## Updating the App

To deploy new changes:

### Quick Update
```bash
# From your workstation
scp website.html user@TRUENAS_IP:/mnt/immich/Jarno_app/udako/

# Container automatically serves the updated file (no restart needed)
```

### Full Redeploy
```bash
ssh user@TRUENAS_IP
cd /path/to/repo
./deploy.sh

# Or manually restart container
docker restart static-site-1
```

### Users See New Version
- **Next visit:** New files auto-load
- **Force refresh:** `Ctrl+Shift+R` on web, uninstall/reinstall on Android
- **Manual cache clear:** Android Settings → Apps → UDAKO CL → Storage → Clear Cache

---

## Docker Compose Configuration

The `docker-compose.yaml` sets up:

```yaml
version: "3.9"
services:
  static-site:
    image: httpd:alpine          # Lightweight Apache
    restart: unless-stopped      # Auto-restart on failure
    ports:
      - "50995:80"              # Map host:container port
    volumes:
      - /mnt/immich/Jarno_app/udako:/usr/local/apache2/htdocs:ro
      # Read-only mount of your dataset
```

**To change:**
- **Port:** Edit `ports: - "XXXX:80"`
- **Dataset path:** Edit `volumes: - /new/path:/usr/local/apache2/htdocs:ro`
- **Image:** Change `image: httpd:latest` (or nginx, etc.)

---

## Troubleshooting

### **404 Error When Accessing Root**
- Create `.htaccess` with `DirectoryIndex index.html`
- Or rename `website.html` to `index.html`

### **Container Not Running**
```bash
docker ps -a | grep static-site
docker logs static-site-1
docker start static-site-1
```

### **Permission Denied on Files**
```bash
sudo chmod -R 755 /mnt/immich/Jarno_app/udako
sudo chown -R root:root /mnt/immich/Jarno_app/udako
```

### **Service Worker Not Registering**
- Ensure `/service-worker.js` is accessible
- Check browser console: F12 → Console → Look for service worker errors
- Verify HTTPS is working (required for service workers)

### **App Won't Install on Android**
- Ensure HTTPS (check Cloudflare)
- Wait 2–3 seconds for the install prompt
- Try clearing Chrome cache: Settings → Apps → Chrome → Storage → Clear Cache
- Use "Add to Home Screen" as fallback

### **Changes Don't Show on Android App**
1. Force refresh: `Ctrl+Shift+R`
2. Clear app cache: Settings → Apps → UDAKO CL → Storage → Clear Cache
3. Uninstall and reinstall the app

---

## Automated Updates (Optional)

Create a cron job to auto-pull and deploy from git:

```bash
# Edit crontab
crontab -e

# Add this line (runs every hour)
0 * * * * cd /path/to/repo && git pull && ./deploy.sh >> /var/log/udako-deploy.log 2>&1
```

---

## FAQ

**Q: Can I use Nginx instead of Apache?**  
A: Yes, change `image: httpd:alpine` to `image: nginx:alpine` in docker-compose.yaml. Nginx needs a slightly different config.

**Q: How do I add custom app icons?**  
A: Replace the inline SVG icons in `manifest.json` with real PNG files. See PWA_SETUP.md for details.

**Q: Will the app work offline?**  
A: Yes! The service worker caches all files on first visit. Check-in data uses browser `localStorage`, so it persists offline.

**Q: Can multiple users install the app?**  
A: Yes! Each device/user gets their own cache and local storage.

**Q: How do I backup user data?**  
A: Data is stored in each user's browser `localStorage`. Currently no backend—add a database if you need server-side backup.

---

## Support

For issues:
1. Check logs: `docker logs static-site-1`
2. Verify files: `ls -la /mnt/immich/Jarno_app/udako/`
3. Test directly: `curl -i http://127.0.0.1:50995/`
4. Check service worker: Browser DevTools → Application → Service Workers

---

**Ready to deploy? Run: `./deploy.sh` 🚀**
