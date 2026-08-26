/* Cursor tracking and visibility control for #map-hover-panel.

   THIS FILE IS THE SOLE OWNER of the panel's display/left/top.

   Do not add a Dash callback that writes #map-hover-panel's `style` prop.
   React's style diff compares each key against its own previous *virtual*
   value and never reads the DOM, so once this file sets display:none
   imperatively, a React update that still carries display:'block' is a
   no-op and the panel stays stuck hidden until an unrelated round-trip
   resets React's virtual value. Two writers to one property is the bug.
   All static panel chrome (position/width/background/border/…) is set once
   in the Dash layout and never updated after mount. */

(function () {
    var OFFSET  = 14;    // px gap between cursor tip and panel edge
    var PW      = 462;   // must match the panel width set in the Dash layout
    var PH_PNG  = 357;   // panel height when the PNG thumbnail is shown
    var PH_TEXT = 116;   // panel height, info text only

    var lastH = PH_PNG;        // expected height of the panel as last rendered
    var hoverEventsBound = false;

    window._hoverCursor = { x: 0, y: 0 };
    window._hoverActive = false;   // true while the cursor is over a map marker

    function panelEl() {
        return document.getElementById('map-hover-panel');
    }

    function positionPanel(cx, cy, forcedH) {
        var panel = panelEl();
        if (!panel) return;

        var vw = window.innerWidth;
        var vh = window.innerHeight;
        var h  = forcedH || panel.offsetHeight || lastH;

        var left = cx + OFFSET;
        var top  = cy - Math.round(h / 2);

        if (left + PW > vw - 8)  { left = cx - PW - OFFSET; }
        if (left < 8)            { left = 8; }
        if (top < 8)             { top  = 8; }
        if (top + h > vh - 8)    { top  = vh - h - 8; }

        panel.style.left = left + 'px';
        panel.style.top  = top  + 'px';
    }

    /* Called by the Dash clientside callback once station content has arrived.
       Ignores a response that landed after the cursor already left the marker.
       Height is taken from has_png rather than measured: React applies the
       image style after this function returns, so offsetHeight is stale here. */
    function showHoverPanel(storeData) {
        if (hoverEventsBound && !window._hoverActive) return;

        var panel = panelEl();
        if (!panel) return;

        lastH = (storeData && storeData.has_png) ? PH_PNG : PH_TEXT;
        positionPanel(window._hoverCursor.x, window._hoverCursor.y, lastH);
        panel.style.display = 'block';
    }

    /* force=true for the synchronous unhover path. Without force this ignores a
       stale {show:false} response that arrived after the cursor moved onto a
       new marker, which would otherwise blank a panel that should be visible. */
    function hideHoverPanel(force) {
        if (!force && window._hoverActive) return;

        var panel = panelEl();
        if (panel) panel.style.display = 'none';
    }

    document.addEventListener('mousemove', function (e) {
        window._hoverCursor.x = e.clientX;
        window._hoverCursor.y = e.clientY;

        var panel = panelEl();
        if (panel && panel.style.display !== 'none') {
            positionPanel(e.clientX, e.clientY);
        }
    });

    /* plotly_hover/plotly_unhover must be bound on the inner .js-plotly-plot
       graph div — the outer Dash wrapper (#gauge-map) is a plain DOM element
       with no .on(). The graph div is replaced whenever the Graph component
       remounts, so re-check periodically and re-bind; the guard flag lives on
       the element itself and therefore disappears with it. */
    function bindHoverHandlers() {
        var mapEl = document.getElementById('gauge-map');
        if (!mapEl) return;

        if (!mapEl._hoverPanelLeaveBound) {
            mapEl._hoverPanelLeaveBound = true;
            mapEl.addEventListener('mouseleave', function () {
                window._hoverActive = false;
                hideHoverPanel(true);
            });
        }

        var gd = mapEl.querySelector('.js-plotly-plot');
        if (gd && typeof gd.on === 'function' && !gd._hoverPanelBound) {
            gd._hoverPanelBound = true;
            gd.on('plotly_hover', function () {
                window._hoverActive = true;
            });
            gd.on('plotly_unhover', function () {
                window._hoverActive = false;
                hideHoverPanel(true);
            });
            hoverEventsBound = true;
        }
    }
    bindHoverHandlers();
    setInterval(bindHoverHandlers, 1000);

    window._positionHoverPanel = positionPanel;
    window._showHoverPanel     = showHoverPanel;
    window._hideHoverPanel     = hideHoverPanel;
}());
