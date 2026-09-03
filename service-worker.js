// Fooball v0.4.4: temporary service-worker kill switch.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(
  caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k))))
    .then(() => self.registration.unregister())
    .then(() => self.clients.matchAll({type:'window'}))
    .then(clients => clients.forEach(c => c.navigate(c.url)))
));
self.addEventListener('fetch', event => {
  event.respondWith(fetch(event.request, {cache:'no-store'}));
});
