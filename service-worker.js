// Service worker — MVR Prompteur d'accords
// Permet l'utilisation hors-ligne après le premier chargement (utile en répétition/concert sans wifi)

// IMPORTANT : incrémenter ce numéro à chaque déploiement d'une nouvelle version.
// C'est ce qui permet au navigateur de détecter qu'un nouveau Service Worker
// existe (le fichier service-worker.js a changé) et de proposer la mise à jour.
const APP_VERSION = '109';
const CACHE_NAME = 'mvr-cache-v' + APP_VERSION;
// Un seul fichier à mettre en cache : manifest + icônes sont encodés en
// base64 DIRECTEMENT dans index.html (voir le commentaire en tête de ce
// fichier) — il n'existe PAS de manifest.json ni de icon-*.png séparés sur
// le serveur. Les lister ici faisait échouer cache.addAll() en entier
// (un seul 404 fait tout échouer), cassant l'installation du service worker
// sur tout nouvel appareil ("impossible de se connecter").
const ASSETS = [
  './index.html'
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
