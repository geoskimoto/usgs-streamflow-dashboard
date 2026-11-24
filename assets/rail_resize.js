/* Drag-to-resize for the filter rail (#sidebar-col). Mirrors panel_resize.js.

   The rail's right edge is the handle (a grip is drawn by `.sidebar-col::after` in theme.css).
   Width is set inline on the element (Dash never writes this element's `style`, only its className)
   and remembered in localStorage. Plotly graphs re-measure on a window `resize` event, so one is
   dispatched while dragging. Desktop layout only (>= 992px, matching the CSS); double-click resets. */
(function () {
    var KEY = 'filter-rail-width';
    var MIN_RAIL = 240, MAX_RAIL = 640, MIN_MAIN = 480, GRAB_PX = 10, DESKTOP = 992;
    var drag = null, raf = 0;

    function rail() { return document.getElementById('sidebar-col'); }
    function visible(r) { return r && window.innerWidth >= DESKTOP && r.offsetWidth > 0; }
    function clamp(px) {
        var max = Math.max(MIN_RAIL, Math.min(MAX_RAIL, window.innerWidth - MIN_MAIN));
        return Math.max(MIN_RAIL, Math.min(px, max));
    }
    function apply(px) {
        var r = rail();
        if (!r) { return; }
        if (px == null) { r.style.removeProperty('width'); r.style.removeProperty('max-width'); }
        else { var w = clamp(px) + 'px'; r.style.width = w; r.style.maxWidth = w; }
    }
    function notifyResize() {
        if (raf) { return; }
        raf = requestAnimationFrame(function () { raf = 0; window.dispatchEvent(new Event('resize')); });
    }
    function onHandle(e) {
        var r = rail();
        if (!visible(r)) { return false; }
        var b = r.getBoundingClientRect();
        return e.clientX <= b.right && b.right - e.clientX <= GRAB_PX &&
               e.clientY >= b.top && e.clientY <= b.bottom;
    }

    document.addEventListener('pointerdown', function (e) {
        if (e.button !== 0 || !onHandle(e)) { return; }
        drag = { id: e.pointerId };
        document.body.classList.add('is-col-resizing');
        e.preventDefault();
    });
    document.addEventListener('pointermove', function (e) {
        var r = rail();
        if (drag) {
            if (r) { apply(e.clientX - r.getBoundingClientRect().left); notifyResize(); }
        } else if (r) {
            r.classList.toggle('is-grab', onHandle(e));
        }
    });
    function end() {
        if (!drag) { return; }
        drag = null;
        var r = rail();
        if (r) { try { localStorage.setItem(KEY, String(Math.round(r.getBoundingClientRect().width))); } catch (err) {} }
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

    // Restore the saved width once the layout exists (Dash renders after DOMContentLoaded).
    var tries = 0;
    (function restore() {
        if (rail()) {
            try { var s = parseInt(localStorage.getItem(KEY), 10); if (s) { apply(s); } } catch (err) {}
            return;
        }
        if (tries++ < 50) { setTimeout(restore, 100); }
    })();
})();
