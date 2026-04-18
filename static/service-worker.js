// Service Worker - Desregistrar service workers previos
// Este archivo existe para evitar errores 404 si el navegador tiene un SW registrado previamente

self.addEventListener('install', function(event) {
    // Forzar la activación inmediata
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    // Tomar control de todas las páginas inmediatamente
    event.waitUntil(
        // Limpiar cachés antiguos
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    return caches.delete(cacheName);
                })
            );
        }).then(function() {
            // Desregistrar este service worker
            return self.registration.unregister();
        })
    );
});
