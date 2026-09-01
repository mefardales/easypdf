/* Service worker for the easypdf.surf tools.
 *
 * It exists so the tools keep working with no connection: once a tool has
 * been opened, its page and the libraries it uses stay on the device. Nothing
 * is ever sent anywhere - this only caches what the browser already fetched.
 */
// Each language has its own worker, so each needs its own cache name AND its
// own prefix: cleaning up "everything that is not mine" would otherwise mean
// the Spanish app wiping the English one every time it started, and back.
var PREFIX = "easypdf-tools-es-";
var CACHE = PREFIX + "v1";

// The shell is small, so it is fetched up front; the styles and the script
// are shared by both languages and live under /tools/. The two PDF libraries
// are not precached: together they are close to two megabytes and most
// visitors only need one of them, so each is kept the first time a tool
// actually loads it.
var SHELL = [
  "./",
  "/tools/app.css",
  "/tools/app.js"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      // One request at a time and each on its own: cache.addAll() is all or
      // nothing, so a single slow or failed file left the cache empty and the
      // tools stopped working offline for no visible reason.
      return SHELL.reduce(function (chain, path) {
        return chain.then(function () {
          // "reload" skips the browser's own HTTP cache. Without it a server
          // that answers 304 Not Modified hands back a body-less response,
          // which cannot be stored, and the precache silently ends up empty.
          return fetch(new Request(path, { cache: "reload" }))
            .then(function (response) {
              if (response && response.ok) return cache.put(path, response);
            })
            .catch(function () { /* no connection on the first visit */ });
        });
      }, Promise.resolve());
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(names.map(function (name) {
        // Only this worker's own older versions.
        var mine = name.lastIndexOf(PREFIX, 0) === 0;
        return mine && name !== CACHE ? caches.delete(name) : null;
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;

  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Pages: try the network first so a new version is picked up, and fall back
  // to the cached copy when there is nothing to reach.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then(function (response) {
          var copy = response.clone();
          caches.open(CACHE).then(function (c) { c.put(request, copy); });
          return response;
        })
        .catch(function () {
          return caches.match(request).then(function (hit) {
            return hit || caches.match("./");
          });
        })
    );
    return;
  }

  // Everything else (styles, scripts, the libraries): cache first. They are
  // versioned by the cache name, so a new release replaces the lot.
  event.respondWith(
    caches.match(request).then(function (hit) {
      if (hit) return hit;
      return fetch(request).then(function (response) {
        if (response && response.status === 200 && response.type === "basic") {
          var copy = response.clone();
          caches.open(CACHE).then(function (c) { c.put(request, copy); });
        }
        return response;
      });
    })
  );
});
