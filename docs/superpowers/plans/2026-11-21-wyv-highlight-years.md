# Water Year Volume: highlighted years — Plan

Date: 2026-11-21 · Size: **Moderate (small)** · Follows `2026-11-20-water-year-volume-plot.md`

## Goal / non-goals
**Goal.** Years typed into the sidebar's "Years to highlight" box also appear in the Water Year Volume card (both modes), drawn like the Water Year Plot's highlighted years but with thinner lines.
**Non-goals.** No change to the Water Year Plot, no new fetch, no forecasts, no new sidebar control.

## Requirements
- **H1.** `create_water_year_volume_plot(site_id, vol, mode, vol_unit, dark, highlight_years=None)`: the new argument is optional; with None/empty the output is identical to today.
- **H2.** For each highlighted year present in `vol['table']` (and not the current water year, which is already the "Observed" trace) add one trace named `WY <year>`: cumulative mode plots `cum_cfs_days`, daily mode `daily_cfs_days`, scaled to `vol_unit`, with x on the same reference water-year dates as the Observed trace (aligned by day of water year).
- **H3.** Highlight lines are thinner than the Water Year Plot's highlight width (3) and thinner than the Observed line: width exactly 1.75.
- **H4.** A year's colour is `HIGHLIGHT_YEAR_COLORS[highlight_years.index(year) % len(HIGHLIGHT_YEAR_COLORS)]`, the same palette and index rule the Water Year Plot uses. `HIGHLIGHT_YEAR_COLORS` lives in `utils/config.py`; the Water Year Plot's palette equals it.
- **H5.** Years absent from the table, duplicates, the current water year, and non-integer entries are ignored without error and add no trace. Legend order follows the input order.
- **H6.** Hover uses the same 4-significant-digit format, carries the volume unit (and not the other one) and the year.
- **H7.** Trace order: bands, then highlighted years, then Observed last (on top).
- **H8.** A highlighted year with missing days is named `WY <year> (<n> missing days)` (`1 missing day` singular), using `vol['summary']`; no suffix when complete. Missing days are never interpolated: daily gaps stay gaps.
- **H9.** `app.parse_highlight_years(text)` returns the ints from a comma/space separated string (`"2025, 2024 ,x,2023"` -> `[2025, 2024, 2023]`; empty/None -> `[]`). `update_multi_plots` uses the same helper (behavior unchanged).
- **H10.** `render_water_year_volume` takes `highlight-years-input.value` as an additional **Input**, appended as the last optional parameter (`highlight_text=None`) so the existing 9-argument call signature still works. It builds the list as the Water Year Plot does (parsed years, then the current water year appended if absent) and passes it to the builder. Typing years re-renders the card without a refetch (the per-site cache serves it).

## Design
- `utils/config.py`: `HIGHLIGHT_YEAR_COLORS` (the Water Year Plot's existing 8 colours); the Water Year Plot's inline list at viz_manager.py:805 is replaced by the constant (same values, no behavior change). The older inline list at :380 is left alone.
- `viz_manager.create_water_year_volume_plot`: extra optional arg and one helper that adds the traces.
- `app.py`: `parse_highlight_years` helper; flat-form callback decorator for `render_water_year_volume` so the new Input can be declared last.
- Colours are the Water Year Plot's (not colour-blind-safe) on purpose, so a year keeps its colour across both plots.

## Tests
Small: builder tests (H1-H8) and helper/callback tests (H9-H10) in `tests/test_wyv_highlight.py`. No existing test is edited.

## Rollout
Standard deploy; no new dependencies. Rollback is `git revert`.
