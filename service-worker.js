// Service worker — MVR Prompteur d'accords
// Permet l'utilisation hors-ligne après le premier chargement (utile en répétition/concert sans wifi)

// IMPORTANT : incrémenter ce numéro à chaque déploiement d'une nouvelle version.
// C'est ce qui permet au navigateur de détecter qu'un nouveau Service Worker
// existe (le fichier service-worker.js a changé) et de proposer la mise à jour.
const APP_VERSION = '2';
const CACHE_NAME = 'mvr-cache-v' + APP_VERSION;
const ASSETS = [
  './index.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-192.png',
  './icon-maskable-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  // Pas de skipWaiting() automatique ici : on laisse le nouveau Service Worker
  // "en attente" (waiting) jusqu'à ce que l'utilisateur confirme la mise à jour
  // via la bannière dans la page (voir index.html). Ça évite qu'une nouvelle
  // version s'active silencieusement pendant qu'un concert est en cours.
});

// Permet à la page de déclencher l'activation immédiate du nouveau worker
// quand l'utilisateur clique sur "Mettre à jour" dans la bannière.
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Stratégie : cache d'abord, puis réseau (et mise à jour silencieuse du cache)
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => cached); // hors-ligne : retombe sur le cache

      return cached || networkFetch;
    })
  );
});
