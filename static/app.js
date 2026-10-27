/* OnePath web app: small client-side helpers (NiceGUI renders the pages). */
// Calls back once the page (rendered by Vue after this script) has an element matching the selector.
const whenPresent = (selector, callback) => {
  const found = () => document.querySelector(selector);
  if (found()) return callback(found());
  const watcher = new MutationObserver(() => { if (found()) { watcher.disconnect(); callback(found()); } });
  watcher.observe(document.documentElement, {childList: true, subtree: true});
  setTimeout(() => watcher.disconnect(), 15000);
};

// External links open outside the app (in the Safari web app: in Safari).
document.addEventListener('click', e => {
  const a = e.target.closest && e.target.closest('a[href^="http"]');
  if (a && a.host !== location.host) { a.target = '_blank'; a.rel = 'noopener'; }
}, true);

// «Назад»: the previous screen of this app when there is one, otherwise the link's own target.
document.addEventListener('click', e => {
  const back = e.target.closest && e.target.closest('.js-back');
  if (back && document.referrer.startsWith(location.origin) && history.length > 1) { e.preventDefault(); history.back(); }
});

// A thin line at the top while the next screen loads (html.nav-pending in app.css): the installed iPhone app
// shows no loading indicator of its own, and a screen takes a round trip to the server. Links of this app,
// and, where the browser has the Navigation API, navigations started by the server (ui.navigate).
// Not for downloads (ui.download clicks a temporary <a download>), new tabs, or changes within the page
// (history.replaceState in the library); and it goes away by itself if no screen comes after all.
let pendingTimer = 0;
const settled = () => { clearTimeout(pendingTimer); document.documentElement.classList.remove('nav-pending'); };
const pending = () => {
  document.documentElement.classList.add('nav-pending');
  clearTimeout(pendingTimer);
  pendingTimer = setTimeout(settled, 15000);
};
document.addEventListener('click', e => {
  const a = e.target.closest && e.target.closest('a[href]');
  if (!a || a.target === '_blank' || a.hasAttribute('download') || e.metaKey || e.ctrlKey || e.shiftKey) return;
  const url = new URL(a.href, location.href);
  if (url.origin === location.origin && !(url.pathname === location.pathname && url.search === location.search)) pending();
});
if (window.navigation) {
  navigation.addEventListener('navigate', e => { if (!e.destination.sameDocument && e.downloadRequest === null) pending(); });
}
addEventListener('pageshow', settled);  // a page restored by «Назад» from the browser's cache
document.addEventListener('visibilitychange', () => { if (document.hidden) settled(); });

// The tab bar's three sections are one page (core/ui/tabs.py): a tap shows another section right here, at once and
// with an animation (app.css), keeping the address, «Назад» and each section's scroll position; the server only
// redraws what changed since (tab_shown). A tap on the current section scrolls it to the top.
(() => {
  const SECTIONS = {'/': 'opps', '/mine': 'mine', '/settings': 'settings'};
  const scrolls = {};
  const shownTab = () => { const on = document.querySelector('.tab-screen.on'); return on && on.dataset.tab; };
  const show = tab => {
    const next = document.querySelector(`.tab-screen[data-tab="${tab}"]`), now = document.querySelector('.tab-screen.on');
    if (!next || next === now) return;
    if (now) { scrolls[now.dataset.tab] = scrollY; now.classList.remove('on'); }
    next.classList.add('on');
    for (const link of document.querySelectorAll('.tabbar .tab')) {
      const on = link.dataset.tab === tab;
      link.classList.toggle('active', on);
      if (on) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
      if (on && link.dataset.title) document.title = link.dataset.title;
    }
    scrollTo(0, scrolls[tab] || 0);
    if (window.emitEvent) emitEvent('tab_shown', {tab});
  };
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[href]');
    if (!a || a.target === '_blank' || e.metaKey || e.ctrlKey || e.shiftKey || !document.querySelector('.tab-screen')) return;
    const url = new URL(a.href, location.href);
    const tab = url.origin === location.origin && !url.search && SECTIONS[url.pathname];
    if (!tab || !document.querySelector(`.tab-screen[data-tab="${tab}"]`)) return;
    e.preventDefault();
    e.stopImmediatePropagation();  // nothing loads, so no loading line
    if (tab === shownTab()) return scrollTo({top: 0, behavior: 'smooth'});
    show(tab);
    history.pushState(null, '', url.pathname);
  }, true);
  addEventListener('popstate', () => { if (SECTIONS[location.pathname] && document.querySelector('.tab-screen')) show(SECTIONS[location.pathname]); });
  whenPresent('.tab-screen', () => { history.scrollRestoration = 'manual'; });  // the sections keep their own positions
})();

// iOS applies :active (the tap feedback in app.css) only when the page listens to touches.
document.addEventListener('touchstart', () => {}, {passive: true});

// iOS keeps fixed elements under the on-screen keyboard: track its height as --kb and raise the pill.
if (window.visualViewport) {
  const vv = window.visualViewport;
  const update = () => {
    const kb = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
    document.documentElement.style.setProperty('--kb', kb + 'px');
    document.body.classList.toggle('kb-open', kb > 80);
  };
  vv.addEventListener('resize', update);
  vv.addEventListener('scroll', update);
}
