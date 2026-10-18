const CACHE_NAME = "meteo-pwa-v3";
const STATIC_ASSETS = [
  "/meteo/",
  "/meteo/analisis",
  "/meteo/static/styles.css",
  "/meteo/static/app.js",
  "/meteo/static/favicon.ico",
  "/meteo/static/icon-192.png",
  "/meteo/static/icon-512.png",
  "/meteo/static/icon.svg",
  "/meteo/manifest.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k !== CACHE_NAME ? caches.delete(k) : null)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  // Los endpoints /api/* se consultan en vivo a la estacion meteorologica
  if (event.request.url.includes("/api/")) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});