/* Drag-to-resize for the detail panel (#detail-panel) beside the map.

   The panel's left edge is the handle (a grip is drawn by `.detail-panel::before` in theme.css),
   so no DOM is injected into the Dash-managed layout. Width is stored in the CSS variable
   `--detail-w` on #workspace (consumed by the grid in theme.css) and remembered in localStorage.
   Plotly graphs only re-measure on a window `resize` event, so one is dispatched while dragging.
   Wide layout only (>= 1200px, matching the CSS); double-click the handle to reset. */
(function () {
    var KEY = 'detail-panel-width';
    var MIN_PANEL = 360, MIN_MAP = 320, GRAB_PX = 10, WIDE = 1200;
    var drag = null, raf = 0;

    function ws() { return document.getElementById('workspace'); }
    function panel() { return document.getElementById('detail-panel'); }
    function isWide() { return window.innerWidth >= WIDE; }
    function collapsed() { var w = ws(); return !w || w.classList.contains('panel-collapsed'); }

    function clamp(px) {
        var w = ws();
        var max = w ? w.getBoundingClientRect().width - MIN_MAP - 16 : px;
        return Math.max(MIN_PANEL, Math.min(px, Math.max(MIN_PANEL, max)));
    }
    function apply(px) {
        var w = ws();
        if (!w) { return; }
        if (px == null) { w.style.removeProperty('--detail-w'); }
        else { w.style.setProperty('--detail-w', clamp(px) + 'px'); }
    }
    function notifyResize() {
        if (raf) { return; }
        raf = requestAnimationFrame(function () { raf = 0; window.dispatchEvent(new Event('resize')); });
    }
    function onHandle(e) {
        var p = panel();
        if (!p || !isWide() || collapsed()) { return false; }
        var r = p.getBoundingClientRect();
        return e.clientX >= r.left && e.clientX - r.left <= GRAB_PX &&
               e.clientY >= r.top && e.clientY <= r.bottom;
    }

    document.addEventListener('pointerdown', function (e) {
        if (e.button !== 0 || !onHandle(e)) { return; }
        drag = { id: e.pointerId };
        ws().classList.add('is-resizing');
        document.body.classList.add('is-col-resizing');
        e.preventDefault();
    });
    document.addEventListener('pointermove', function (e) {
        if (!drag) { return; }
        var w = ws();
        if (!w) { return; }
        apply(w.getBoundingClientRect().right - e.clientX);
        notifyResize();
    });
    function end() {
        if (!drag) { return; }
        drag = null;
        var w = ws();
        if (w) {
            w.classList.remove('is-resizing');
            try { localStorage.setItem(KEY, String(Math.round(panel().getBoundingClientRect().width))); } catch (err) {}
        }
        document.body.classList.remove('is-col-resizing');
        window.dispatchEvent(new Event('resize'));
    }
    document.addEventListener('pointerup', end);
    document.addEventListener('pointercancel', end);

    document.addEventListener('dblclick', function (e) {
        if (!onHandle(e)) { return; }
        apply(null);
        try { localStorage.removeItem(KEY); } catch (err) {}
        window.dispatchEvent(new Event('resize'));
    });

    // Cursor feedback over the handle.
    document.addEventListener('pointermove', function (e) {
        if (drag) { return; }
        var p = panel();
        if (p) { p.classList.toggle('is-grab', onHandle(e)); }
    });

    // Restore the saved width once the layout exists (Dash renders after DOMContentLoaded).
    var tries = 0;
    (function restore() {
        if (ws()) {
            try { var s = parseInt(localStorage.getItem(KEY), 10); if (s) { apply(s); } } catch (err) {}
            return;
        }
        if (tries++ < 50) { setTimeout(restore, 100); }
    })();
})();
