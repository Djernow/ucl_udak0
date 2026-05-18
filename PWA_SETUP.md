# UDAKO CL — PWA Setup & Android Installation

## What's New

Your website is now a **Progressive Web App (PWA)** — installable on Android, iOS, and desktop as a native-like app with offline support.

## Files Added

- **`manifest.json`** — App metadata (name, icons, theme colors, display mode)
- **`service-worker.js`** — Offline caching and app lifecycle management
- **Updated `website.html`** — Service worker registration + PWA meta tags

## Installation on Android

### Option 1: Chrome Install Prompt (Easiest)
1. Open `https://udako.libertronics.org` in Chrome on Android
2. Wait 2–3 seconds
3. Look for the **"Install app"** prompt at the bottom or in the menu (⋮ → "Install app")
4. Tap **Install**
5. App appears on your home screen as **UDAKO CL**!

### Option 2: Manual Add to Home Screen
1. Open `https://udako.libertronics.org` in Chrome
2. Tap **⋮ (menu)** → **"Add to Home screen"**
3. Confirm the app name and tap **Add**

### Option 3: Share & Install
1. Open in Chrome, tap **⋮** → **Share**
2. Select **"Add to Home screen"**

## What the App Does

✅ **Installable** — Works like a native app (no browser chrome)  
✅ **Offline Support** — Cached files load even without internet  
✅ **Works Online** — Real-time updates when connected  
✅ **Data Stored Locally** — Uses browser `localStorage` for check-ins  
✅ **Responsive** — Optimized for mobile, tablet, and desktop  

## Installation on iOS (Safari)

1. Open `https://udako.libertronics.org` in Safari
2. Tap **Share** (↗ icon)
3. Scroll and tap **"Add to Home Screen"**
4. Confirm and tap **Add**

## Installation on Desktop

### Chrome/Chromium
1. Visit `https://udako.libertronics.org`
2. Look for the **install icon** in the address bar (↓ + box)
3. Or: **⋮ → "Install app"**

### Edge
1. Visit the site
2. **⋮ → "Apps" → "Install this site as an app"**

## How Offline Works

The service worker caches the main files on first visit. After that:
- **Online:** App fetches fresh data (if available from backend)
- **Offline:** Cached HTML/CSS/JS load instantly; your check-in data (stored in `localStorage`) is always available

## Updating the App

When you update `website.html`, `manifest.json`, or `service-worker.js`:
1. Users will get the new version on their next visit
2. The old cache automatically clears
3. **Manually:** Users can clear app data in Android Settings → Apps → UDAKO CL → Storage → Clear Cache

## Testing Offline (Chrome DevTools)

1. Open DevTools (F12)
2. Go to **Application** → **Service Workers**
3. Check **"Offline"**
4. The app should still load from cache

## Troubleshooting

**App not installing?**
- Ensure you're on HTTPS (Cloudflare should handle this)
- Wait a few seconds; the install prompt takes time to appear
- Check browser console for service worker errors

**Changes not showing up?**
- Force refresh: `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)
- Clear app cache: Android Settings → Apps → UDAKO CL → Storage → Clear Cache
- Uninstall and reinstall the app

**Service Worker errors in console?**
- Check that `/service-worker.js` is accessible
- Verify `/manifest.json` loads without 404

## Files Needed on Server

Ensure your TrueNAS dataset has all these files:
```
/mnt/immich/Jarno_app/udako/
├── index.html
├── website.html (or index.html only)
├── manifest.json
├── service-worker.js
└── .htaccess (contains: DirectoryIndex index.html)
```

## Next Steps

1. **Upload files to TrueNAS:**
   - Copy `manifest.json` and `service-worker.js` to `/mnt/immich/Jarno_app/udako/`
   - Replace `website.html` with the updated version

2. **Test on Android:**
   - Open Chrome, visit `https://udako.libertronics.org`
   - Install the app from the prompt
   - Log in with admin/admin123 (or your credentials)

3. **Optional Enhancements:**
   - Add custom app icons (currently using SVG placeholders)
   - Add splash screens for iOS
   - Set up push notifications (requires backend setup)

---

**Let the games begin!** 🏆
