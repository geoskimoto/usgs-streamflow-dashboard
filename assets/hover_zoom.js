/* Position the hover-zoom-panel near the cursor in real time.
   Runs at mousemove frequency (60fps) — no Dash round-trip involved.
   The Dash clientside callback controls show/hide and figure content;
   this script only handles x/y placement. */

(function () {
    var OFFSET = 14;   // px gap between cursor and panel edge

    document.addEventListener('mousemove', function (e) {
        var panel = document.getElementById('hover-zoom-panel');
        if (!panel || panel.style.display === 'none') return;

        var pw = panel.offsetWidth  || 480;
        var ph = panel.offsetHeight || 240;
        var vw = window.innerWidth;
        var vh = window.innerHeight;

        // Default: panel appears to the right and above the cursor
        var left = e.clientX + OFFSET;
        var top  = e.clientY - ph - OFFSET;

        // Flip right → left if panel would overflow right edge
        if (left + pw > vw - 8) {
            left = e.clientX - pw - OFFSET;
        }

        // Flip above → below if panel would overflow top edge
        if (top < 8) {
            top = e.clientY + OFFSET;
        }

        panel.style.left = left + 'px';
        panel.style.top  = top  + 'px';
    });
}());
