// Service Worker: macht die App offline nutzbar.
// Bei Änderung der CDN-Versionen in index.html: CDN_ASSETS anpassen und CACHE hochzählen.
const CACHE = 'lyrics-liste-v1';

const APP_SHELL = [
  './',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png'
];

const CDN_ASSETS = [
  'https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.9/babel.min.js'
];

self.addEventListener('install', event=>{
  event.waitUntil((async ()=>{
    const cache = await caches.open(CACHE);
    await cache.addAll(APP_SHELL);
    await cache.addAll(CDN_ASSETS.map(url=>new Request(url, {mode:'cors'})));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event=>{
  event.waitUntil((async ()=>{
    const keys = await caches.keys();
    await Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event=>{
  const req = event.request;
  if(req.method!=='GET') return;
  const url = new URL(req.url);

  // CDN-Bibliotheken: versionierte URLs, ändern sich nie → Cache zuerst
  if(CDN_ASSETS.includes(url.href)){
    event.respondWith(caches.match(req).then(hit=>hit || fetchAndCache(req)));
    return;
  }

  // Eigene Dateien: Netz zuerst (damit Updates sofort ankommen), offline aus dem Cache
  if(url.origin===self.location.origin){
    event.respondWith((async ()=>{
      try{
        return await fetchAndCache(req);
      }catch(e){
        const hit = await caches.match(req, {ignoreSearch:true});
        if(hit) return hit;
        if(req.mode==='navigate') return caches.match('./');
        throw e;
      }
    })());
  }
  // Alles andere (z.B. iTunes-Suche) geht normal ans Netz
});

async function fetchAndCache(req){
  const res = await fetch(req);
  if(res.ok && !res.redirected){
    const cache = await caches.open(CACHE);
    cache.put(req, res.clone());
  }
  return res;
}
