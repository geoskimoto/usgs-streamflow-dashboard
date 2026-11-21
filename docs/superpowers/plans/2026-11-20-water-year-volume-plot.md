# Water Year Volume Plot — Plan

Date: 2026-11-20 · Size: **Moderate** (new feature, existing app) · Status: **awaiting review**

## 1. Goal and non-goals

**Goal.** Add a fourth lazy-loaded card, "Water Year Volume", to the detail panel. It shows *observed* runoff volume for the selected station's current water year against the historical record, in two modes:

- **Cumulative** — volume since Oct 1, with percentile bands across historical water years.
- **Daily** — the volume that passed on each day, with the same bands as the Water Year Plot.

A card-local toggle switches the volume unit between **kaf** (thousand acre-feet) and **cfs-days**. It loads behind the existing "Load period-of-record analysis" button.

**Non-goals (v1).**
- No forecasts: NWRFC, resid-cast, EA-LSTM and blended traces are not drawn.
- No changes to the Water Year Plot, Annual Summary or Flow Duration Curve.
- No new cache on disk (parquet).
- No "current percentile rank" annotation. It is cheap to add later.
- No metric-volume units (m³, dam³).

## 2. Scale assumptions

The feature adds no new fetches. It reuses the full-history daily-mean load that Annual Summary and Flow Duration Curve already trigger, so the load profile is unchanged:

- Single-digit concurrent users.
- ~4,900 stations, of which only the selected one is computed.
- Roughly 10–100 years × 365 rows per station.

The extra compute is a groupby and a cumsum, so it is milliseconds. **Assumed, please confirm:** no change in expected user count or availability needs.

## 3. Requirements (specification for `test-writer`)

**Volume math** (`utils/water_year_volume.py`)

- **R1.** 1 cfs-day = 86,400 ft³ = 86400/43560 acre-ft (1.983471). kaf = cfs-days × 1.983471 / 1000. Both factors live in one module and nowhere else.
- **R2.** The daily-mean discharge in cfs on a day equals that day's volume in cfs-days. Daily volume in kaf = Q_cfs × 1.983471/1000.
- **R3.** Input in cms (Environment Canada stations; `unit` column) is converted to cfs through `utils/units.py` *before* any volume math. A cms-native series and its numerically equivalent cfs series give identical volumes.
- **R4.** The flow-unit toggle (cfs/cms) has **no effect** on volume values or labels. Only the card's own volume toggle does.

**Cumulative**

- **R5.** Per water year, cumulative volume is the running sum of daily volume from Oct 1, indexed by day of water year via `water_year_calculator.py`. No inline water-year logic.
- **R6.** Cumulative series are non-decreasing, and the value on the last day equals the sum of that year's daily volumes.
- **R7.** Water years run Oct 1–Sep 30. A date of Sep 30 belongs to the water year ending that day. Oct 1 belongs to the next. Leap-year day 366 is handled.
- **R8.** Percentile bands (the percentile set from `DEFAULT_PERCENTILES`, plus median) are computed per day of water year across **completed, sufficiently complete historical** water years. The current water year is excluded from its own bands.
- **R9.** Gap policy, explicit and logged:
  - A day with no observation contributes **no volume** and is **not interpolated**.
  - Each water year gets a `missing_days` count over its elapsed days.
  - A historical year with more than `WYV_MAX_MISSING_FRAC` (default 5%) of days missing is **excluded from the bands**.
  - Every exclusion and every gap in the current year is logged at INFO or WARNING with the site id and counts.
- **R10.** If the current water year has gaps, the plot shows an annotation such as "N missing days — cumulative volume is a lower bound". The traces still render.
- **R11.** If fewer than `WYV_MIN_YEARS` (default 10) qualifying historical years exist, the bands are omitted and the figure notes "Not enough complete years for percentile bands". The current-year trace still renders.

**Daily**

- **R12.** Daily-mode bands equal the existing per-day-of-WY flow percentile stats scaled by the volume factor. They are not recomputed independently. (Verify the stats cache is unit-native: convert to cfs first, then scale.)

**Figure**

- **R13.** The current-year observed trace spans Oct 1 to the last observed day, never beyond. The x-axis shows the full water year, labelled as water-year dates, not calendar-year.
- **R14.** Axis titles and hover text carry the volume unit ("Cumulative volume (kaf)", "Daily volume (cfs-days)"). The mode and unit are reflected in the title.
- **R15.** Hover uses the same 4-significant-digit precision as the existing plots.
- **R16.** The figure goes through `plot_theme.apply_theme` for light and dark. It uses colorblind-safe colors from the theme, with no hard-coded colors.
- **R17.** Observed data is visually distinct from the percentile bands. The legend labels it "Observed".

**UI / lazy loading**

- **R18.** The card is hidden until a station is selected and "Load period-of-record analysis" is clicked. A new station selection resets it to hidden and unrendered.
- **R19.** The card contains a mode control (Cumulative | Daily) and a unit control (kaf | cfs-days). Defaults: Cumulative, kaf.
- **R20.** Switching mode or volume unit re-renders the card without a new full-history fetch. Within a short TTL, the same site returns the cached computation.
- **R21.** Toggling the cfs/cms control does **not** re-render this card.
- **R22.** Toggling dark mode re-renders the card in the new theme.
- **R23.** Every callback target and id used by the card exists in the static layout. The new ids are guarded by a layout-id test.

**Failure**

- **R24.** No data or an empty history shows a friendly alert, not a stack trace or a blank card.
- **R25.** A DataOps API error shows a friendly "could not load volume data" message. The error is logged with the site id only, with no tokens or URLs containing tokens.

## 4. Design

**New module `usgs_dashboard/utils/water_year_volume.py`** — pure functions, no Dash or Plotly:

- Constants for the factors (R1), plus `WYV_MAX_MISSING_FRAC` and `WYV_MIN_YEARS`.
- `daily_volume(df)`: to cfs via `units.convert_frame`, then volume per day.
- `water_year_volume_table(df)`: columns `water_year, day_of_wy, daily_cfs_days, cum_cfs_days`, with a per-year missing-day summary.
- `cumulative_bands(table, current_wy)`: percentile bands per day of WY (R8, R9, R11).

Canonical storage is always cfs-days. kaf is a display scale only, which is the same pattern `units.py` uses: "convert only at the display boundary".

**`data_manager.get_water_year_volume(site_id)`**:
- Calls `get_streamflow_data` and the module above.
- Returns the table, bands and gap summary.
- Keeps a small in-memory TTL cache keyed by `site_id` (R20).
- Daily bands come from `get_flow_statistics(display_unit='cfs')` scaled (R12).

**`viz_manager.create_water_year_volume_plot(site_id, vol, mode, vol_unit, dark)`**:
- A single new figure builder, using `_create_error_plot` for the failure path.
- It reuses the theme and hover-precision helpers. It does not copy the three existing water-year plot implementations, and it does not add a fourth.

**`app.py`** (lean callbacks):
- Static layout block `wyv-section` after `annual-summary-container`. It holds the mode and unit `RadioItems` and a `dcc.Graph`, wrapped in the same `dcc.Loading` spinner pattern.
- Callback 1: show or hide the section and reset on gauge change, driven by `annual-summary-requested`.
- Callback 2: Inputs `annual-summary-requested`, `wyv-mode`, `wyv-unit`, `dark-mode-store`. States `selected-gauge-store`, `gauges-store`, `chart-height-dropdown`, `plot-options-checklist`. It does not take `flow-unit-store` as an input (R21).
- Graph config and height follow `render_annual_summary`.

**Reused:** `water_year_calculator`, `units.convert_frame`, `plot_theme`, `DEFAULT_PERCENTILES`, the existing lazy-load store, `get_flow_statistics`.

## 5. Integration impact

- **Other projects:** none. No station-config handoff, tokens, metrics or SSO contract is touched.
- **Existing tests:** `test_layout_ids.py` and the unit-toggle tests are not modified. New ids are guarded by a new test file.
- **Env vars:** none new. The two thresholds are constants in `config.py`, not environment-driven.
- **Deploy:** standard dev → push → `git pull` as `streamflowdash` → restart. No new dependencies, nginx or systemd changes, and no cron or timer.
- **Docs:** update `CLAUDE.md` (architecture and data-flow lines) and `DISPLAY_BEHAVIOR_SPEC.md` (plot display behavior).

## 6. Security and data

- Station-level public hydrology data, with no user data and no PII.
- Logs carry site ids and counts only.
- No secrets are touched.

## 7. Failure behavior

- R24 and R25: a Bootstrap alert in the card, e.g. "Water year volume couldn't be loaded for this station. Try again in a moment."
- A failure never breaks the other three period-of-record cards, because the callback is independent.

## 8. Test plan

Tests are written **before** implementation by the `test-writer` agent from Section 3. Implementation never edits them.

- **Unit** (`tests/test_water_year_volume.py`): R1–R3, R5–R9, R11, R12, plus leap years and the Sep 30 / Oct 1 boundary.
- **Property** (hypothesis, if installed; otherwise parametrized randoms):
  - cumulative is monotone and ends at the sum of daily volumes;
  - kaf = cfs-days × constant for random series;
  - cms-native and cfs-equivalent inputs agree;
  - gaps never create volume.
- **Figure** (`tests/test_viz_water_year_volume.py`): R13–R17, R10 and R11 annotations, and the empty and error figures. This follows the pattern of `test_unit_toggle_viz.py`.
- **Layout and callback** (`tests/test_wyv_layout.py`): R18–R23, including that new ids exist and that cfs/cms does not trigger the card.
- **Integration** (mocked): R24 and R25 using a failing adapter. Live API runs only under `RUN_INTEGRATION_TESTS=1`.
- **Mutation:** an independent `mutation-evaluator` run after implementation, against `water_year_volume.py` and the figure builder.
- **Hydrology review:** `hydro-data-scientist` checks the gap policy, the band method (percentiles of cumulative curves across years), the unit factor, regulated-flow caveats and the current-year exclusion.
- **Manual visual check:** run locally with the SSO stub, as per `CLAUDE.md`, in light and dark mode on one cfs and one cms station.

## 9. Steps (each independently committable)

1. `test:` the `test-writer` agent writes the four test files from Section 3, all failing. Review and lock them.
2. `feat:` `utils/water_year_volume.py` — constants, daily and cumulative math, gap summary, bands. Done when the unit and property tests pass.
3. `feat:` `data_manager.get_water_year_volume` with TTL cache and daily-band scaling. Done when the data-manager tests pass.
4. `feat:` `viz_manager.create_water_year_volume_plot`. Done when the figure tests pass.
5. `feat:` layout block and the two callbacks in `app.py`. Done when the layout and callback tests pass, plus a manual visual check in both themes.
6. `docs:` update `CLAUDE.md` and `DISPLAY_BEHAVIOR_SPEC.md`.
7. `test:` the mutation evaluator and hydro review run. Report plausible versus correct. Fixes only after confirming with you.
8. `deploy:` push, pull as `streamflowdash`, restart, tail the logs.

## 10. Rollout and rollback

- Deploy as in `CLAUDE.md`.
- Rollback is `git revert` of the feat commits, then pull and restart. There is no schema, cache or config state to unwind.
- The card is additive and lazy, so a defect cannot affect the other plots.

## 11. Risks and open questions (default in bold)

1. **Gap threshold:** exclude historical years with more than 5% missing days from the bands? Default **5%**.
2. **Minimum years for bands:** **10**.
3. **Missing day in the current year:** contributes zero and is flagged as a lower bound, rather than interpolated. Default **flag, don't fill**.
4. **Daily-mode bands:** scale the existing flow stats rather than recompute (R12). Default **scale**. To be confirmed against the stats cache during step 3.
5. **Cache:** in-memory TTL per site (default **5 min**, matching `DATAOPS_CACHE_TTL`), with no parquet in v1. A parquet cache can come later if full-history loads prove slow.
6. **Theme re-render:** the card re-renders on dark-mode change (R22). The Annual Summary card currently reads the theme as State only, so it may not. That is out of scope, but I'll flag it.
7. **Regulated or partial-record stations:** bands from different regimes can mislead. Out of scope for v1. The hydro review may recommend a caveat in the hover or footnote.
