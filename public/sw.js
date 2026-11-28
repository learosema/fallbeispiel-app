const CACHE = "xabcde-v30";
// Clips heißen nach ihrem Inhalt (Hash) und ändern sich nie: eigener Cache, übersteht App-Updates
const AUDIO_CACHE = "xabcde-audio";
const ASSETS = ["./", "index.html", "info.html", "spicker.html", "loesungen.html", "training.html", "zusammenarbeit.html", "style.css", "app.js", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png", "apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE && k !== AUDIO_CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});
// Nur eigene GET-Requests cachen; API-Aufrufe gehen immer direkt ans Netz.
self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  if (url.pathname.startsWith("/audio/")) {
    // Range-Anfragen (Safari) nicht aus dem Cache bedienen – die gehen direkt ans Netz
    if (req.headers.has("range")) return;
    e.respondWith(
      caches.open(AUDIO_CACHE).then((c) => c.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok && res.status === 200) c.put(req, res.clone());
        return res;
      })))
    );
    return;
  }
  e.respondWith(
    fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy));
      return res;
    }).catch(() => caches.match(req))
  );
});
