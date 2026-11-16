const CACHE_NAME = 'flexa-shell-v46';
const CORE_ASSETS = [
  './',
  './index.html',
  './style.css',
  './texts.js',
  './muscles.js',
  './athlete_profile.js',
  './app.js',
  './manifest.json',
  './img/logo.svg',
  './data.json',
  './content/config.json',
  './content/overrides.json',
  './content/texts.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(CORE_ASSETS).catch(() => {})).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes('/api/')) return;

  // Cache-first for static heavy media (exercises SVG, photos, audio)
  if (url.pathname.includes('/img/') || url.pathname.includes('/audio/')) {
    event.respondWith(
      caches.match(req).then(hit => hit || fetch(req).then(res => {
        if (res && res.ok) {
          const cp = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(req, cp)).catch(() => {});
        }
        return res;
      }))
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
    }).catch(() => caches.match(req, { ignoreSearch: true }))
  );
});
