const CACHE_NAME = 'flexa-shell-v67';
const MEDIA_CACHE_NAME = 'flexa-media-v1';
const CORE_ASSETS = [
  './',
  './index.html',
  './tokens.css',
  './ui-kit.css',
  './style.css',
  './texts.js',
  './muscles.js',
  './athlete_profile.js',
  './analytics.js',
  './ui_components.js',
  './app.js',
  './manifest.json',
  './img/logo.svg',
  './data.json',
  './content/config.json',
  './content/overrides.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(CORE_ASSETS).catch(() => {})).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME && k !== MEDIA_CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes('/api/')) return;

  // Cache-first for static heavy media (exercises SVG, photos, uploaded covers, audio)
  if (url.pathname.includes('/img/') || url.pathname.includes('/audio/') || url.pathname.includes('/content/uploads/')) {
    event.respondWith(
      caches.open(MEDIA_CACHE_NAME).then(mediaCache =>
        mediaCache.match(req).then(hit => {
          if (hit) return hit;
          return fetch(req).then(res => {
            if (res && res.ok && res.status === 200) {
              const cp = res.clone();
              mediaCache.put(req, cp).catch(() => {});
            }
            return res;
          });
        })
      ).catch(() => caches.match(req, { ignoreSearch: true }).then(hit => hit || Response.error()))
    );
    return;
  }

  // Network-first for HTML, JS, CSS, JSON so updates appear immediately online while still working offline
  event.respondWith(
    fetch(req).then(res => {
      if (res && res.ok) {
        const cp = res.clone();
        caches.open(CACHE_NAME).then(c => c.put(req, cp)).catch(() => {});
      }
      return res;
    }).catch(() => caches.match(req, { ignoreSearch: true }).then(hit => hit || Response.error()))
  );
});
