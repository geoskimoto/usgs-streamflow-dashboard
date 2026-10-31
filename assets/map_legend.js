/* Click handling for the rail map legend (#map-legend).

   The legend items are rendered by the clientside callback in app.py from the
   gauge-map figure's traces. Clicking one shows/hides its trace(s) on the live
   Plotly graph, the same behavior the built-in Plotly legend had. Delegated, so
   it survives the legend being re-rendered. */
document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('.legend-item') : null;
    if (!btn || !window.Plotly) { return; }
    var gd = document.querySelector('#gauge-map .js-plotly-plot');
    if (!gd || !btn.dataset.traces) { return; }
    var idx = btn.dataset.traces.split(',').map(Number);
    var turnOff = !btn.classList.contains('is-off');
    window.Plotly.restyle(gd, { visible: turnOff ? 'legendonly' : true }, idx);
    btn.classList.toggle('is-off', turnOff);
    btn.setAttribute('aria-pressed', turnOff ? 'false' : 'true');
});
