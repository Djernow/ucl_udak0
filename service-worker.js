// UDAKO CL Service Worker
// Enables offline functionality and caching for PWA

const CACHE_NAME = 'udako-cl-v1';
const urlsToCache = [
  '/',
  '/website.html',
  '/manifest.json'
];

// ============================================================
// INSTALL EVENT
// ============================================================
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      // Cache essential files
      return Promise.all([
        cache.addAll(urlsToCache),
        self.skipWaiting()
      ]);
    })
  );
});

// ============================================================
// ACTIVATE EVENT
// ============================================================
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          // Delete old cache versions
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// ============================================================
// FETCH EVENT - Network first, fallback to cache
// ============================================================
self.addEventListener('fetch', event => {
  // Skip API calls and external resources
  if (event.request.url.includes('/api/') || 
      event.request.url.includes('cloudflare') ||
      event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Only cache successful responses
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }

        // Clone and cache
        const responseToCache = response.clone();
        caches.open(CACHE_NAME).then(cache => {
          cache.put(event.request, responseToCache);
        });

        return response;
      })
      .catch(() => {
        // Fallback to cache
        return caches.match(event.request).then(response => {
          return response || new Response('Offline - resource not available', {
            status: 503,
            statusText: 'Service Unavailable',
            headers: new Headers({
              'Content-Type': 'text/plain'
            })
          });
        });
      })
  );
});

// ============================================================
// NOTIFICATION CLICK
// ============================================================
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      if (clientList.length > 0) {
        return clientList[0].focus();
      }
      return clients.openWindow('/');
    })
  );
});
