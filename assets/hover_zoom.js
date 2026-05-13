/* Cursor tracking for map-hover-panel positioning.
   Stores live cursor coords in window._hoverCursor so the Dash
   clientside callback can read them synchronously when it fires.
   Also repositions the panel on every mousemove while it is visible. */

(function () {
    var OFFSET = 14;    // px gap between cursor tip and panel edge
    var PW     = 440;   // matches width in clientside callback
    var PH     = 340;   // worst-case height (info + PNG); pure-text case is smaller but safe

    window._hoverCursor = { x: 0, y: 0 };

    function positionPanel(cx, cy) {
        var panel = document.getElementById('map-hover-panel');
        if (!panel) return;

        var vw = window.innerWidth;
        var vh = window.innerHeight;

        var left = cx + OFFSET;
        var actualPH = panel.offsetHeight || PH;
        var top  = cy - Math.round(actualPH / 2);

        if (left + PW > vw - 8) { left = cx - PW - OFFSET; }
        if (top < 8)             { top  = 8; }
        if (top + actualPH > vh - 8) { top = vh - actualPH - 8; }

        panel.style.left = left + 'px';
        panel.style.top  = top  + 'px';
    }

    document.addEventListener('mousemove', function (e) {
        window._hoverCursor.x = e.clientX;
        window._hoverCursor.y = e.clientY;

        var panel = document.getElementById('map-hover-panel');
        if (panel && panel.style.display !== 'none') {
            positionPanel(e.clientX, e.clientY);
        }
    });

    /* Expose so the Dash clientside callback can call it directly. */
    window._positionHoverPanel = positionPanel;
}());
