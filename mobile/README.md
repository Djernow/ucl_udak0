# UDAKO CL Mobile (Expo)

This React Native app uses the same API as the web app (`app.py`) and mirrors the main layout and tabs (Champions League, Europa League, Conference League, History, Statistics).

## Setup

1. Install dependencies:
   - `npm install`
2. Set the API base URL (server origin, no `/api` suffix):
   - `EXPO_PUBLIC_API_BASE=http://YOUR_SERVER:5000`
3. Optional: set the web URL (used by the "Open web" link):
   - `EXPO_PUBLIC_WEB_URL=https://YOUR_WEB_DOMAIN`
4. Start the app:
   - `npm run start`

## Notes

- The backend uses session cookies. The app calls the same `/api/*` endpoints as `website.html`.
- Make sure the Flask server is reachable from your device or emulator.
