// EventDeck VR service worker (M6 PWA対応)
// 方針: アプリシェルをキャッシュしつつ、API・ページはネットワーク優先。
// オフライン時はキャッシュ済みのシェルにフォールバックする。
const CACHE_NAME = "eventdeck-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // API・非GETはキャッシュしない (常にネットワーク)
  if (event.request.method !== "GET" || url.pathname.startsWith("/api/")) {
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // 静的アセットはキャッシュを更新しておく
        if (response.ok && (url.pathname.startsWith("/assets/") || SHELL.includes(url.pathname))) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() =>
        caches.match(event.request).then((cached) => cached ?? caches.match("/"))
      )
  );
});
