self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.map(function (key) { return caches.delete(key); }));
      })
      .then(function () { return self.registration.unregister(); })
      .then(function () {
        return self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      })
      .then(function (clients) {
        clients.forEach(function (client) {
          if (client.url) client.navigate(client.url);
        });
      })
  );
});

self.addEventListener('fetch', function () {
  // Retired service worker intentionally does not intercept requests.
});
