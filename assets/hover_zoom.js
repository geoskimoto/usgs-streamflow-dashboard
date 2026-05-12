/* Cursor tracking for hover-zoom-panel positioning.
   Stores live cursor coords in window._hoverCursor so the Dash
   clientside callback can read them synchronously when it fires.
   Also repositions the panel on every mousemove if it is visible. */

(function () {
    var OFFSET = 14;    // px gap between cursor tip and panel edge
    var PW     = 480;   // matches CSS width in callback
    var PH     = 250;   // approximate panel height (figure 210 + header + padding)

    window._hoverCursor = { x: 0, y: 0 };

    function positionPanel(cx, cy) {
        var panel = document.getElementById('hover-zoom-panel');
        if (!panel) return;

        var vw = window.innerWidth;
        var vh = window.innerHeight;

        var left = cx + OFFSET;
        var top  = cy - PH - OFFSET;

        if (left + PW > vw - 8) { left = cx - PW - OFFSET; }
        if (top < 8)             { top  = cy + OFFSET; }

        panel.style.left = left + 'px';
        panel.style.top  = top  + 'px';
    }

    document.addEventListener('mousemove', function (e) {
        window._hoverCursor.x = e.clientX;
        window._hoverCursor.y = e.clientY;

        var panel = document.getElementById('hover-zoom-panel');
        if (panel && panel.style.display !== 'none') {
            positionPanel(e.clientX, e.clientY);
        }
    });

    /* Expose so the Dash clientside callback can call it directly. */
    window._positionHoverPanel = positionPanel;
}());
