# Map-first redesign — implementation plan

Branch: `design/map-first`. Visual reference: `Documentation/design/map-first-mock.html`
(static mock, example data; open in a browser). Scope: look, layout and theming only.
No changes to data_manager, adapters, stats cache, hover PNG generation or any API contract.

## Decisions (approved)
- Layout B: slim top bar, collapsible filter rail (left), full-height map, **right-side detail panel** with the water-year plot.
- Light + dark themes, light default (matches commit e692de1). Wave spinner kept, recolored by theme tokens.
- Fira Sans (UI) + Fira Code (numbers/IDs). Percentile colors: colorblind-safe orange/green/blue scale.
- Hover PNG tooltip stays; panel becomes a **light card in both themes** (PNGs are rendered with the light theme).

## Findings that shape the work
- Dark mode already exists: `dark-mode-btn` toggles `body.dark-mode` (clientside) and writes `dark-mode-store`,
  which the plot callbacks (app.py ~L1295, ~L1676, ~L1916) read. Keep this mechanism; do not add a second one.
- ~170 lines of inline CSS live in `app.index_string` (app.py ~L85-260), including all `body.dark-mode` rules.
  Move them into `assets/theme.css` as tokens, then delete the inline block.
- Callback IDs that must survive the restructure: sidebar-col, sidebar-toggle-btn, mobile-sidebar-btn,
  main-content-wrapper, gauge-map, multi-plot-container, annual-summary-container, history-buttons-row,
  gauge-info-content, percentile-date-picker, prev/next-date-btn, map-hover-panel (+ children),
  and every filter control id in filter_panel.py.
- `hover_zoom.js` owns map-hover-panel display/left/top; panel width (462) and heights are hard-coded there. Do not change.
- Emoji used as icons throughout (card headers, buttons); replace with inline SVG icons.

## Steps (one commit each, app run and checked after each)
1. **Tokens + fonts** — `assets/theme.css` with light/dark tokens keyed to `body.dark-mode`; Google Fonts; port the
   existing inline dark rules; remove the inline block. No layout change. Spinner colors -> tokens.
2. **Top bar** — replace `create_header()` hero and the button row with a 48px bar: title, date picker (-/+),
   updated indicator, Dashboard/Admin switch, theme toggle. Same component ids.
3. **Filter rail** — restyle `filter_panel.py` as flat sections (no card stack, no emoji); keep every control id.
   Collapse/expand reuses the existing sidebar callbacks.
4. **Map stage** — gauge-map fills the viewport height; floating count chip; style the plotly toolbar; percentile
   legend (with counts) in the rail.
5. **Right detail panel** — selected-gauge header + stats + range buttons + plot + forecast toggles in a right panel
   beside the map; collapses to a strip; bottom sheet below 860px. Existing history/annual-summary ids are moved, not renamed.
6. **Hover card** — light card styling for map-hover-panel in both themes; z-index above the detail panel.
7. **Plotly template** — light/dark figure templates driven by `dark-mode-store`; confirm contrast and colorblind-safe palettes.
8. **Pass** — responsive check (375 / 768 / 1024 / 1440), keyboard focus, reduced motion, run `pytest`.

## Tests
Existing suite must pass unchanged (tests are locked; failures get reported, not patched). Layout work adds a
smoke test that the layout tree still contains every required callback id (written separately from the implementation).

## Deploy
Dev tree is deployed only via the documented push-to-main + pull in `/home/streamflowdash/...` flow. Nothing is
deployed from this branch until reviewed.

## Status (2026-10-31)
Steps 1-8 implemented on `design/map-first`; not yet merged or deployed. Outcomes that differ from the plan:
- Dark basemap skipped by decision (tiles stay light in dark mode).
- Map percentile display regrouped to 5 classes (spec updated); non-percentile states keep their spec colors.
- Sidebar toggle labels and filter state labels lost their emoji (string edits inside two callbacks).
- Known leftovers: duplicate empty-state text in the detail panel (callback-owned); `create_sidebar()` is unused dead code
  from before the redesign; `viz_manager` figure height/margins still tuned for a wide plot area.
