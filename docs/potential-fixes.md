# Potential fixes

Backlog of improvements that have been identified but not implemented, or were deliberately
deferred. When one is implemented, move the details into [logic-changelog.md](logic-changelog.md)
and mark it **Done** here, with the date. Related docs: [method-differences.md](method-differences.md)
(differences from the TSMS report) and [sensor-failures.md](sensor-failures.md) (failure catalog).

**Priority:** `High` = changes results materially · `Medium` = improves correctness or
comparability · `Low` = cleanup / nice to have

Last updated 2026-09-29 (PF-44 to PF-48 added: report §3.1/3.4/3.6 statistics still missing; PL-09
updated and PL-12/PL-13 added for §3.7 pressure follow-ups).

---

## Summary

| ID | Area | Idea | Priority | Status |
|---|---|---|---|---|
| PF-01 | Cleaning, Phase 6 | Set the Hampel/z-score floor at the sensor's noise level instead of its resolution | Low | Deferred. Evidence 2026-09-29: with the resolution floor, 61–95% of temperature flags are real convective fluctuations. Handled by making Step 5 flag-only; a noise-level floor would reduce the flag count |
| PF-02 | Cleaning, Phase 6 | Use time-based rolling windows (e.g. `'20min'`) with a minimum data share (≥ 60%); readings in too-sparse windows become "untested", not flagged. Current data isn't on a regular grid (TSMS03: 91% of minutes present, longest gap 316 h), so a "20-row" window can span days | Medium | **Done 2026-09-29** (PF-35 stage 4: 21-min centred window on the Step 0 grid, ≥ 60% present or 'untested') |
| PF-03 | Cleaning, Phase 5 | Flag the middle of multi-minute bit-switching runs, not just their edges | Medium | Open |
| PF-04 | Cleaning, Phase 5 | Apply Phase 4 manual removals to neighbour humidity in the pre-pass | Low | Open |
| PF-05 | Cleaning, Phase 1 | Treat `-1000.0`, `-999.9` (TSMS08 pressure) and `-999.0` (TSMS06 wind_dir) as null markers alongside `-999.99` | Low | **Done 2026-09-29** (Step 0: any value ≤ −990 is a null marker, incl. SLPs derived from a marker) |
| PF-06 | Cleaning, Phase 2 | Stop dropping the first row of every file | Low | **Done 2026-09-29** (Step 0 keeps the first row) |
| PF-07 | Cleaning, Phase 3 | Realistic per-minute rain limit (32 mm/min is close to the world record) | High | Open |
| PF-08 | Data | Fix or re-clean `tipping` for TSMS02, 03, 04, 05, 08 and Ankara reference rain | High | **3D-PAWS part done 2026-09-28** (root cause SF-10, fixed via PF-28). Still open: Ankara reference (SF-09); gauge-level issues SF-11/12/16 |
| PF-09 | Analysis | Pair readings at minute level *before* aggregating; add the 80% daily completeness rule | High | **Done 2026-09-28** (Phase 7 + minute-level pairing) |
| PF-10 | Analysis, wind | Define calm from the reference only; restrict direction comparisons to reference speed above ~1 m/s | High | **Done 2026-09-28** (variable / non-variable regimes at 3.0 m/s) |
| PF-11 | Analysis, wind dir | Replace linear stats on direction with circular SD / circular correlation in the precision block (`error-analysis.py` `pearsonr`/`np.std` on raw angles); add median abs. error and % within ±22.5°/45°/90° | Medium | Open |
| PF-12 | Analysis | Report N (paired count) per row; round r to 2–3 decimals | Medium | Open |
| PF-13 | Analysis | Pearson r on de-seasonalized data (remove diurnal and annual cycles) | Medium | Open |
| PF-14 | Analysis | Relabel sections: systematic error (bias), random error (SD/IQR of differences), total error (MAE/RMSE) | Low | Open |
| PF-15 | Analysis | Replace "Reliability" with a WMO-No. 8 **Annex 1.G Measurement Quality Classification** (Class A/B/C/D) per station/sensor/variable, from the bias and 95th percentile of \|difference\| at WMO averaging times (1 min T/RH/p; 10 min wind; daily rain); show Annex 1.A required/achievable for context; state it's conservative (differences include siting and reference uncertainty); add wind starting threshold. Confirmed: `wmo_thresholds` = Annex 1.A *achievable* column | Medium | **Done 2026-09-28** (`wmo-classification.csv/.xlsx`) |
| PF-16 | Analysis, precip | Totals-based comparison (ratio of totals, cumulative curves), wet/dry contingency, keep dry periods | High | Open |
| PF-17 | Analysis | Use `sht_upgrade` to split HTU vs. SHT periods | Medium | Open |
| PF-18 | Analysis, pressure | Correct for barometer height difference (~0.12 hPa per m) before calling a bias sensor error | Medium | Open |
| PF-19 | Analysis, wind speed | Sensitivity run with and without the Hellmann height correction | Low | Open |
| PF-20 | Investigation | TSMS03/04 wind speed anomaly (SF-08), `sth_hum` biases at TSMS02/06 (SF-06/07), TSMS04 precursor on 29–30 Nov 2024 | Medium | Open |
| PF-21 | Investigation | Is `bmp2_temp` an air temperature, or enclosure temperature? | Low | Open |
| PF-22 | Cleaning | Persistence ("minimum required variability", WMO-No. 8 Vol. III Ch. 1) per variable, plus a simultaneous-exact-zeros check across chips (SF-17). Rain excluded: zero runs are its normal state | Medium | **Done 2026-09-29** (stage 3; limits adjusted after measuring, see qc-framework.md Step 4b) |
| PF-23 | Plots, wind | Monthly wind-rose block (commented out) still filters each instrument on its own speed | Low | Open |
| PF-24 | Plots, wind | Hourly speed in the wind roses is the vector-mean speed, which reads low in variable winds; `_vectorial_wind_average` also returns NaN if any minute is NaN | Medium | Open |
| PF-25 | Analysis, wind | Regime threshold uses the reference's 10-m speed; consider 2-m (Hellmann-adjusted) speed or a sensitivity check | Low | Open |
| PF-26 | Analysis, wind | Report N per regime; non-variable winds are only 3–18% of minutes. Since pairing, a regime's hourly/daily value can rest on very few minutes; consider a minimum | Medium | Open |
| PF-27 | Investigation, wind | Ankara/Konya: 3D-PAWS much weaker and rotated in non-variable winds (TSMS01: 0.68 vs. 2.23 m/s, +30° to +66°). Figure: [figures/tsms01-nonvariable-windrose-vs-reference.png](figures/tsms01-nonvariable-windrose-vs-reference.png) | High | **Closed 2026-09-28: known siting limitation** (Konya courtyard/brick wall, Ankara hill), documented in [siting.md](siting.md) |
| PF-28 | Data pipeline | Re-map CHORDS columns for misaligned periods (SF-10), rebuild `data/reformatted` → `data/cleaned`, remove the SF-01/SF-02 removals | **Critical** | **Done 2026-09-28**: Dec 2024+ spliced, Jan–Mar 2024 re-mapped (TSMS04 temperatures excluded, SF-15), `data/cleaned` regenerated |
| PF-32 | Analysis, wind | Estimate the anemometer starting threshold (Annex 1.G: ≤ 0.5 / 1.0 / 2.5 m/s), e.g. the lowest reference speed at which the 3D-PAWS cup reports > 0 in most minutes (Adana only) | Medium | Open |
| PF-33 | Analysis | Eₙ score (Vol. V Ch. 4 §2.4): needs the reference instruments' expanded uncertainty. Models now known (Lastem DNA002/DNA011, Rotronic MP101A, Druck RPT200; `docs/TSMS Sensors.docx`): look up datasheets for a type-B estimate; calibration certificates make it rigorous | Medium | Open (ask TSMS for calibration records) |
| PF-34 | Analysis | OSCAR tier for humidity: convert both instruments' RH (with T, p) to specific humidity and compare with OSCAR PBL requirements | Low | Open |
| PF-35 | Cleaning | **Restructure QC into single-purpose steps** (below), each logged separately; output good/suspect/failed with a reason; remove only "failed"; rain flag-only (`tipping_flag`) | High | In progress: stage 1 (Step 0 Structure), stage 2 (Step 1 Metadata, [station-events.csv](station-events.csv)) and stage 3 (Steps 3, 4a, 4b) stage 4 (Step 5), stage 5 (Steps 6–7) and stage 6 (Step 8 flag columns) implemented 2026-09-29. **`data/cleaned` regenerated 2026-09-29** (previous files in `data/archive/cleaned-backup-09292026_[BEFORE-QC-FRAMEWORK]/`). **Remaining:** re-run error-analysis, WMO classification, report comparison and plots; error-analysis to read the flag columns (rain with/without flags). Full description for the team: [qc-framework.md](qc-framework.md) |
| PF-36 | Cleaning | Step (rate-of-change) test for **all** variables, per-variable limits (instrument spec / climatology), not just the HTU | Medium | **Done 2026-09-29** as flags (TSMS Table 1 limits); per-sensor limits from datasheets later (PF-42) |
| PF-37 | Cleaning | Neighbour (spatial) check for all variables; mark a 3D-PAWS station suspect when it departs from the other two; mark the **reference** suspect only for gross, event-level disagreements (e.g. reference dry while ≥ 2 3D-PAWS gauges record > X mm), never for systematic biases (common-mode shields/siting). Reference-suspect pairs are excluded from the comparison and reported to TSMS | Medium | **Done 2026-09-29** (PF-35 stage 5: flag corroboration, calm runs, rain days; wind flags kept as flags) |
| PF-38 | Cleaning | Diagnostics step: documented failures/exclusions, maintenance and firmware events, battery/power (`Battery Charge (%)` in the Particle files), logger resets. Non-measurement information only; separate from persistence | Medium | **Done 2026-09-29** (events table from the Jan 2024 maintenance logs; battery columns unusable: RPi stations don't log them, Particle columns are constant 0 or absent) |
| PF-39 | Cleaning | Review TSMS's climatological limits ("varies by month", values not given): extract Table 1, compare with ours (fixed ±50 °C), adopt site/month limits where defensible | Medium | Open |
| PF-40 | Analysis, rain | Wet-day threshold: report 1.0 mm (ETCCDI R1mm convention) as the headline and 0.2 mm for report parity. At 1.0 mm Konya FAR 0.56–0.66 → 0.25–0.35, CSI 0.30–0.39 → 0.50–0.69 | Medium | **Done 2026-09-29** in `compare_with_report.py` (both thresholds × all days / flagged days excluded → `data/report-comparison/precipitation.csv`; results in method-differences P10). Still to add to error-analysis/WMO rain classification |
| PF-41 | Cleaning, rain | Rain vs. RH consistency as a **flag**, not a removal (TSMS removes rain at RH < 60%: 2–8% of reference rain, 22% of TSMS03's; real rain days affected) | Low | **Done 2026-09-29** (Step 3 flag, `*_flags.csv`; becomes `tipping_flag` in Step 8) |
| PF-42 | Analysis, WMO | **Characterize the 3D-PAWS sensors too, not only the reference.** Collect the manufacturer datasheets for every 3D-PAWS sensor used in the study (BMP280, HTU21D, SHT31D, MCP9808, SI1145; anemometer, vane and tipping-bucket models) and record the stated accuracy, resolution, range and response time per variable. Uses: (1) report each sensor's specified uncertainty next to its achieved Annex 1.G class and Annex 1.A required/achievable values, so it's clear whether a result is instrument-limited or siting/shield-limited; (2) the Eₙ score (PF-33) needs *both* instruments' uncertainties; (3) step-test limits, noise floors (PF-01) and resolution floors from specifications instead of the data alone | High | **In progress:** 3D-PAWS datasheets received 2026-09-29 (`docs/datasheets/`; specs tabulated in methods.md §1). Still open: (a) TSMS reference datasheets (being compiled); (b) an Annex 1.G Table 2 uncertainty budget for the *study* sensors (BMP280, HTU21D, SHT31D, MCP9808): the team's budgets are for the current SHT45/BMP581 build; (c) cups: start-up ≤ 1.2 m/s from the SMN tunnel tests (used for `CALM_NEIGHBOUR_SPEED`); vane: no starting threshold, so `VANE_MOVING_SPEED` = 1.0 m/s (a 3D-PAWS reading, ≈ 1.5 m/s true wind on SMN's fit) stays a reasoned placeholder; (d) add datasheet accuracy next to the achieved class in `wmo-classification.csv` |
| PF-43 | Analysis, wind | **Wind-speed calibration sensitivity.** SMN Argentina's tunnel tests find the 3D-PAWS cups read 10–13% low (fit: factor 2.90 + 0.40 m/s when pulses are counted, vs. the firmware's 2.64). Re-run the wind-speed statistics and WMO classes with that correction as a sensitivity case, and say in the report that part of the negative 3D-PAWS speed bias is instrumental, not just the 2 m height and siting. The study's anemometers weren't tunnel-tested (unit IDs unknown), and SMN's units were new | Medium | Open |
| PF-44 | Diagnostics, TSMS06 | **Dig into TSMS06's diagnostic data around the SF-17 logger zeros.** Both SF-17 periods (Sep–Oct 2024, `sth_*` only; Feb–May 2025, all sensors) come from the CHORDS download, not the SD cards, and a bug has been noticed in the CHORDS database, so the zeros may be a database artefact rather than a logger fault. TSMS06 is a Particle station and logs station metadata (battery %, charge, etc.). Check those columns in the raw CHORDS files over both periods: do battery/charge values, logger resets or gaps coincide with the zeros? Note: an earlier quick look found TSMS06's `bpc` and `Battery Charge (%)` columns constant 0, which may itself be the CHORDS bug; worth checking against any SD-card copy | Medium | Open (added 2026-09-29) |
| PF-45 | Plots | **Bugs in the original plot sections**, found in the 2026-09-29 refactor of `plot-gen-final.py` and kept as they were (logic retained on purpose). (1) `histograms`: the reference file name tests `'3DPAWS-TSMS00'` (hyphen), never true, so every reference histogram is named `TSMS-Adana_*`. (2) `scatter-vs-ref`: the file name has no sensor, so each temperature/humidity sensor overwrites the last. (3) `rain-monthly-bars`: total = `cumsum[-1] - cumsum[0]` drops each month's first minute. (4) `scatter-temp-sensors`: the bmp-vs-htu trend line is fitted against `htu_temp`. (5) `windrose-monthly`: hard-coded Hellmann 0.14 (not per site); non-variable wind from each instrument's own speed, not the reference's (unlike the complete-record roses and error-analysis); the TSMS calm filter is overwritten by the ≥ 3 m/s filter; `wind_dir_true` computed but unused; variable-wind TSMS file names omit the site. (6) Box plots for wind and rain (commented out) reuse `combined_pres_df`. (7) `site-rain-daily-bars`: stray space in file names. (8) Headers: `diff-humidity` says MONTHLY but is complete-record; `site-rain-monthly-bars` says daily. (9) `timeseries-temp-sensors`, `scatter-temp-sensors` omit `sth_temp` | Low | Open (fix before using those plots in a report) |
| PF-44 | Analysis, §3.1 | Per-series descriptive stats (median, IQR, min, max) for each raw series (3D-PAWS and TSMS separately), not just of the difference (G7). Open question: does min/max mean anything here, or is it just recording the most extreme weather of the record rather than sensor performance? | Medium | Open |
| PF-45 | Analysis, §3.4 | Add R² and the OLS regression line (slope/intercept, 3D-PAWS vs. TSMS) alongside Pearson r in the precision block (G7). N per comparison is PF-12; paired-only comparison (never compare a value against a missing counterpart) is already enforced by `_paired`/PF-09 | Medium | Open |
| PF-46 | Analysis | Generalize `TIMESCALE` (currently one global choice: hourly / daily / point-for-point) into a per-analysis aggregation framework so any variable can be assessed at whatever timescale suits it — this matters most for rain, where sub-daily accumulation timing changes the picture | Medium | Open |
| PF-47 | Analysis | Completeness threshold is a flat 80% at every timescale (PF-09). A hint of real weather changes less within an hour than within a day, so a lower bar (60–70%?) may be defensible at finer resolutions. Needs a sensitivity check (how much do the stats move as the threshold changes?) before picking numbers, not a guess | Medium | Open |
| PF-48 | Analysis, §3.6 | Monthly statistics from eligible daily means (≥ 80% complete), matching the report's approach to longer-term behaviour. Open question: does a monthly mean-of-daily-means represent the month well, or would min/max (extremes) say more — especially for rain, where the daily mean isn't the policy-relevant number, totals/extremes are | Medium | Open |
| PF-31 | Analysis | Sensitivity run: key statistics with and without the inferred Jan–Mar 2024 windows ([methods.md](methods.md) §4) | Medium | Open |
| PF-30 | Data pipeline | Fold the Dec 2024 splice into `final_paws_reformatter.py`, whose CHORDS input path points outside the repo and no longer exists | Medium | Open |
| PF-29 | Documentation | Add site descriptions, photos, sensor heights, and obstruction distances to `siting.md` | Low | Open |

---

## PF-01: Floor at the sensor's noise level instead of its resolution

**Context:** on 2026-09-28 the Hampel MAD and the z-score std were floored at each column's
recording resolution (`RESOLUTION_FLOOR` in `outlier-removal.py`). That fixes the zero-MAD /
near-zero-std problem: a single resolution step can no longer be flagged.

**Idea:** a sensor's reading fluctuates by more than one resolution step even when the air is
perfectly steady, because of electronic noise and small real fluctuations. If the floor were set
at that *noise level* (the typical minute-to-minute scatter in steady conditions) rather than
the resolution, the filters would flag only readings that stand out from the sensor's own normal
jitter. Some readings still flagged with the resolution floor look like genuine short
fluctuations, e.g. daytime `mcp9808` values of `15.0, 15.25, 15.31, 15.0, 14.62` °C at TSMS00.

**How it could be done:** for each column, estimate noise from stable periods: the MAD (or
std) of first differences at night with low wind, or the lower percentiles of the rolling MAD
where it's non-zero. Use that value, or a multiple of it, as the floor.

**Why deferred:** needs a noise-characterization study per sensor, and possibly per period, since
resolution changed between the SD-card and CHORDS eras. The resolution floor already removes the
bulk of the false positives (12–19% → under 0.7% for non-HTU series). *Decision 2026-09-28:
stick with the resolution floor for now.*

## PF-02: Time-based rolling windows

Phase 6 windows are 20 **rows**. Across data gaps, 20 rows can span hours, and the median/MAD
then compare readings from very different conditions. Pandas supports time windows on a
DatetimeIndex (`rolling('20min', center=True)`), which would keep the window at 20 minutes of
real time. The same applies to the report's 61-point window.

## PF-03: Middle of bit-switching runs

The Phase 5 step test flags a reading when it jumps from the minute before or after. In a run
like good, bad, bad, bad, good, only the first and last bad readings are next to a jump. The
middle one isn't flagged. Options: flag everything between an up-jump and the matching
down-jump, or apply the site cross-check to every reading during periods with frequent jumps.

## PF-04: Neighbour humidity skips Phase 4 removals

The humidity pre-pass applies null/range checks, step-suspect removal, and documented sensor
failures, but not the month-specific `station_rules` removals (e.g. TSMS06–08 `htu_hum`). A
manually removed neighbour value can still vouch for a reading.

## PF-05: `-1000.0` null sentinel

TSMS04's raw file contains `-1000.0` values (e.g. just before SF-02). Phase 1 recognizes only
`-999.99`, so these are removed later by the Phase 3 range check and logged as `threshold`
instead of `null`. The data outcome is the same, but outlier statistics are mislabelled.

## PF-06: Phase 2 drops the first row

`time_diff` is `NaT` for the first row, and `NaT > Timedelta(0)` is False, so the first row of
every file is dropped as if it were a timestamp reset. Fix: keep rows where `time_diff` is `NaT`.

## PF-07 / PF-08: Rain limit and broken `tipping` data

The Phase 3 upper limit of 32 mm/min lets through stuck or counter-style values: TSMS02, 03, 04,
05, 08 show ≈ 47,600 to 2.2 million mm/yr, and the Ankara reference has 1-min spikes up to
31.5 mm. A realistic per-minute limit, plus finding where the implausible values come from
(counters not converted to per-minute amounts?), is needed before any rainfall statistic is
usable. See SF-05, SF-09.

## PF-09: Pair first, then aggregate

`_agg_timescale` averages or sums each station over whatever minutes it has, and pairs the results
afterwards. If one station is missing part of a day, its daily value covers different hours than
the other's. That's a sampling difference, not a sensor difference, and it's severe for rain
sums. Fix: inner-join the minute data first, keep only minutes where both have values, then
aggregate. Add the 80% completeness rule the report uses. (method-differences G3, G13)

## PF-10: Calm defined from the reference (Done 2026-09-28)

*Implemented as variable / non-variable regimes classified by the reference's 10-m speed
(3.0 m/s). Zero-speed directions are removed, zero speeds kept. See the changelog. The ~1 m/s
direction cutoff wasn't adopted separately; the variable regime covers it.*

`_mask_calm` (2026-09-25) dropped a minute when **either** instrument reads 0 m/s. That discards
minutes where the reference shows wind but the 3D-PAWS cup is stalled, which is exactly the
failure a comparison should expose. Define calm from the reference only. For speed, keep 3D-PAWS
zeros. For direction, compare only when the reference speed is above ~1 m/s (vanes are
unreliable in light wind). (method-differences WS2)

## PF-11 to PF-16: Analysis statistics

- **PF-11:** Pearson r, per-series SD, and Reliability treat wind direction as a linear
  variable. Use circular statistics, and add the report's median absolute direction error and
  within-threshold percentages for direct comparison (WD3, WD6).

  **Diagnosis (2026-09-29):** the bug is isolated to the precision block
  (`error-analysis.py` lines 360–366): `pearsonr(tsms, paws)` and `np.std(paws, ddof=1)` /
  `np.std(tsms, ddof=1)` run directly on the raw stored angles, with no wraparound handling.
  The bias-diff and MAE/RMSE blocks are already circular-safe (`((paws - tsms) + 180) % 360 - 180`
  at line 242; `np.minimum(np.abs(raw_diff), 360 - np.abs(raw_diff))` at line 302) — those
  don't need to change.

  Re-encoding the stored columns from `[0, 360)` to `[-180, 180)` is **not** a general fix for
  the precision block: it only relocates the discontinuity from the 0°/360° seam to the
  180°/-180° seam. It would happen to fix stations whose prevailing wind clusters near north
  (e.g. oscillating 350°↔10°, which currently reads as huge fake variance and garbage
  correlation), but reintroduces the identical bug for any station/period where wind clusters
  near south, and doesn't help at all for bimodal wind (plausible at Konya, given the siting
  issues in [siting.md](siting.md)). The real fix has to be independent of the linear
  encoding: circular mean/SD from the resultant vector length of `(sin θ, cos θ)`, and a
  circular correlation coefficient (Jammalamadaka–Sarma) in place of Pearson on raw angles.
- **PF-12:** every row should show how many paired readings it's based on. r rounded to one
  decimal makes 0.95 and 1.0 look the same.
- **PF-13:** daily temperature at co-located stations correlates at ~1.0 because both follow the
  seasons. Correlate anomalies to measure sensor agreement.
- **PF-14:** the current "Accuracy (systematic errors)" and "Precision" labels don't match what
  MAE/RMSE and per-series SD measure.
- **PF-15:** "Reliability" (1 − MAE/SD_ref) is non-standard and rewards high-variance variables.
  A WMO-tolerance hit rate is standard; check thresholds against WMO-No. 8.
- **PF-16:** per-timestep rain statistics mostly measure tip timing. Excluding dry-dry periods
  also differs from the report (P1, P2).

## PF-44 to PF-48: TSMS report parity — statistics still missing (2026-09-29)

Cross-checked against the report's §3.1–3.7 (see also G7, method-differences.md). §3.2's
mean/median bias, bias SD, and bias IQR are **already** produced (`error-analysis.py`'s
difference table, `df_difference`) and already applied to wind direction as a signed circular
difference (WD2) — nothing to add there. §3.5's Taylor diagrams are already tracked as PL-10
(Low priority, matches "figure-for-figure parity only"). The gaps below are the rest:

- **PF-44 (§3.1, descriptive stats):** the analysis only ever describes the *difference* between
  instruments, never each series on its own. Add median, IQR, min, and max for each raw series
  (3D-PAWS and TSMS separately). Whether min/max are meaningful is worth deciding as a team: for
  most variables they just record the most extreme weather during the record (a fact about the
  climate, not the sensor), so they may belong in methods/context rather than in an accuracy
  table — unless one series' min/max is implausible relative to the other's, which would be a QC
  signal.
- **PF-45 (§3.4, R² / regression / paired-only):** add R² and the OLS regression line (3D-PAWS as
  a function of TSMS) next to Pearson r. N per comparison is already tracked as PF-12. The
  paired-only requirement (never let an unmatched reading bias a stat in either direction) is
  already how `_paired` and the PF-09 minute-level join work — this just confirms nothing new is
  needed on that front.
- **PF-46 to PF-48 (§3.6, temporal aggregation):** three related gaps.
  - **PF-46:** `TIMESCALE` in `error-analysis.py` is one global setting (hourly / daily /
    point-for-point) applied to every variable. Rain in particular needs its own judgment about
    aggregation — a sub-daily view can matter even when a coarser one is right for temperature or
    pressure. Generalize so each analysis can pick its own timescale rather than sharing one.
  - **PF-47:** the 80% completeness rule (PF-09) is applied the same way regardless of the
    aggregation window. An hour has less time for real weather to change than a day does, so a
    stricter or looser bar could be defensible at different timescales — but that should be
    decided from a sensitivity check (does the resulting statistic actually move much between,
    say, 60%, 70%, and 80%?), not picked by feel.
  - **PF-48:** the report assesses longer-term behaviour from *eligible daily means* rolled up to
    monthly. Before copying that: does a monthly mean-of-daily-means actually represent typical
    daily behaviour well, or would monthly min/max (extremes) say more? This matters most for
    rain, where a "typical day's mean" isn't the number anyone cares about — totals and extremes
    are.

## PF-17 to PF-21

- **PF-17:** `sht_upgrade` is defined but unused, so HTU and SHT periods are mixed in the same
  statistics.
- **PF-18:** station pressure drops ~0.12 hPa per metre. TSMS00's −1 hPa bias would match about
  8 m of height difference. Check barometer heights.
- **PF-19:** the Hellmann exponents are estimates. Report how much wind-speed results depend
  on them.
- **PF-20:** see [sensor-failures.md](sensor-failures.md) SF-06 to SF-08 and the SF-02 precursor.
- **PF-21:** if the BMP280 sits inside the enclosure, `bmp2_temp` isn't an air temperature. The
  report uses only the MCP9808.

## PF-22: Automatic detection of persistent failures

SF-01 and SF-02 passed every filter because they don't jump. They had to be found by eye and
removed by hand. Possible checks: long runs of an identical value (e.g. > 6 h of exactly 0.0 %RH),
or physically impossible values sustained over time (RH < 5% for hours in Konya winter). Note that the
report's persistence test excludes 0 %RH from its range, and a site-median check fails when
most stations fail together (method-differences G14).

## PF-23 to PF-26: Wind follow-ups (2026-09-28)

- **PF-23:** the commented-out MONTHLY RECORDS wind-rose block in `plot-gen-final.py` still
  applies `>= 3.0` to each instrument's own speed. If it's revived, give it the same
  reference-based classification as the complete-record block.
- **PF-24:** `func._vectorial_wind_average` returns the speed of the *mean vector*. When
  directions vary within the 10-min window, that's lower than the mean speed, so light,
  variable winds land in lower speed bins. The analysis uses the scalar mean speed. It also uses
  `np.mean`, so a single NaN minute makes the whole hour NaN (the new rose block drops NaN
  minutes first).
- **PF-25:** the 6-kt convention and the plotting code both refer to the reference's 10-m
  speed, which is what's used. At 2 m, 3.0 m/s at 10 m corresponds to ≈ 1.7–2.0 m/s depending on
  the Hellmann exponent. A sensitivity run at other thresholds (e.g. 2 and 4 m/s) would show how
  much the regime results depend on the cutoff.
- **PF-26:** non-variable winds are 17.8% of reference minutes at Ankara, 6.0% at Adana, and
  3.3% at Konya. Regime statistics for Konya rest on few hours, so N needs to be in the output
  (see PF-12).

## PF-28: Re-map CHORDS columns (SF-10)

The Jan 2024 – Nov 2025 CHORDS exports for TSMS02, 03, 04, 05 and 08 have data rows whose column
order differs from the header during 2024-01-01 → ~mid-Mar 2024 and 2024-12-01 → end. See
[sensor-failures.md](sensor-failures.md) SF-10. Options, roughly in order of reliability:

1. **Dec 2024 → Nov 2025:** use the correctly labeled second download
   (`data/raw/3D-PAWS/Dec-2024_Nov-2025/Calibration_Instrument-{n+2}_*.csv`) instead of the
   Jan24–Nov25 file for that period. It matches the misaligned file value-for-value at the same
   timestamps (100% matches after re-mapping), so it contains the same data, correctly labeled.
   Note: `final_paws_reformatter.py` currently doesn't read this folder at all. Its CHORDS input
   path (`data_origin_partII`) points outside the repo.
2. **Jan → mid-Mar 2024:** no correctly labeled copy is in the repo. Either re-download that
   window from CHORDS (checking the headers), or detect the order per row. The compass field's
   position identifies which layout a row uses, and the Dec 2024 mapping gives the column
   permutation for the "position 4 / 7 / 9" layouts. That should be checked per station, because
   the Jan–Feb 2024 layout (e.g. TSMS02 position 8) isn't always the same as the Dec 2024 one.
3. **Guard rail for the future:** in the reformatter, check each row's compass-field position
   (or value ranges per column) against the header and fail loudly on a mismatch, rather than
   silently mislabeling.

After re-mapping: regenerate `data/reformatted` and `data/cleaned`, then remove the SF-01 and
SF-02 entries from `sensor_failures` in `outlier-removal.py`, and re-check SF-05 and SF-08.

### PF-28 status (2026-09-28)

**Done:** Dec 2024 → Nov 2025 (option 1 above), via `scripts/reformatting/splice_chords_dec2024.py`.

**Remaining, Jan → ~mid-Mar 2024** (tested by reading the early-2024 raw rows with the Dec-batch
column order and comparing MCP9808 with the reference temperature):

| Station | Early-2024 layout (compass position) | Dec-batch order works? |
|---|---|---|
| TSMS08 | 9 / 15, same as Dec batch | **Yes.** MCP9808 − ref median 0.00 °C, r = 0.998, pressure 1,017 hPa |
| TSMS03, TSMS05 | 4, same compass position, but the other columns differ | No (MCP9808 comes out ≈ 260–900 °C) |
| TSMS02 | 8 | No, a different layout |
| TSMS04 | 4 (Dec batch: 7) | No, a different layout |

Options: (a) ~~re-download Jan–Mar 2024 from CHORDS~~ **not possible** (CHORDS keeps only 2 years);
(b) infer each station's early-2024 column permutation, then verify as above; (c) exclude
Jan 1 → Mar 10 2024 at these five stations.

**Update 2026-09-28:** the switch is exactly 2024-03-11 00:00 UTC at all five stations, and a full
mapping has been inferred for each (option b). See [sensor-failures.md](sensor-failures.md)
SF-10, "Jan 1 → Mar 10 2024". Confidence is high for TSMS02, 03, 05, 08 and medium for TSMS04's
temperature sensors. Next step: apply it (extend the splice script to re-map these rows by
position before 2024-03-11 00:00 UTC), verify against the reference and neighbours, then
regenerate `data/cleaned`.

## PF-15: WMO framing (sources reviewed 2026-09-28)

Sources in `docs/`: WMO-No. 8 Vol. I (2024), Vol. III (2024), Vol. V (2023).

- **Vol. I, Ch. 1, Annex 1.A** (pp. 25–34): operational measurement uncertainty. *Required*
  (column 5, general operational use): T 0.1 K, RH 1%, p 0.1 hPa, wind speed 0.5 m/s (≤ 5 m/s) /
  10%, direction 5°, daily rain 0.1 mm (≤ 5 mm) / 2%. *Achievable* (column 8, practical aid): T
  0.2 K, RH 3% (solid-state), p 0.15 hPa, direction 5°, daily rain larger of 5% or 0.1 mm.
  Uncertainties at 95% (k = 2), and residual bias should be small relative to them (note 5).
  Mode: "instantaneous" = 1-min average (note 4); wind = 2 and/or 10-min averages; rain = totals.
- **Vol. I, Ch. 1, Annex 1.G** (pp. 81–87): Measurement Quality Classification Scheme. Classes
  A/B/C aligned with OSCAR goal/breakthrough/threshold, D = worse or unknown. Purpose: fitness for
  a given application, "not ... which measurements are good or bad" (§2.2). Combined with the
  Annex 1.D siting classes. Table 1 targets (k = 2): T 0.2/0.6/1.0 K; RH 2/5/10%; p 0.2/1.0/2.0 hPa;
  wind speed 1 m/s or 5% / 2 m/s or 10% / 5 m/s or 15%; starting threshold ≤ 0.5/1.0/2.5 m/s;
  direction 5/10/15°; daily rain 1 mm or 2% / 3 mm or 5% / 5 mm or 10%.
- **Vol. I, Ch. 1, Annex 1.D:** siting classifications. Use in [siting.md](siting.md) to give Konya
  and Ankara a formal siting class.
- **Vol. III, Ch. 1, Annex 1.A** ("Low-cost AWS", pp. 30–33): 3D-PAWS fits the "compact AWS"
  category. "Low-cost AWSs may have their place in a tiered network and can provide significant
  value if their performance and operating limitations are understood."
- **Vol. V, Ch. 4:** testing, calibration and intercomparison. §2.4 defines the Eₙ score
  (difference divided by the combined k = 2 uncertainty of participant and reference) for formal
  evaluation; §6.2 covers field-intercomparison data analysis.

- **OSCAR/Requirements** (https://space.oscar.wmo.int/observingrequirements): extract in
  [oscar-requirements.md](oscar-requirements.md). Uncertainty is RMSE at 68% (k = 1), with goal /
  breakthrough / threshold per application area, plus horizontal resolution, observing cycle,
  and timeliness. Candidate application areas for 3D-PAWS: 2.2 High-Resolution NWP, 2.3
  Nowcasting / Very Short-Range Forecasting, 2.9 Agricultural Meteorology, 4.1 Hydrological
  Forecasting. No near-surface pressure variable was found in OSCAR.

**Plan:** two tiers.
1. **General:** Annex 1.G class (k = 2), as below. It's conservative, because it's based on the
   strictest application areas for T, p and rain.
2. **Application-specific:** for each chosen OSCAR application area, compare the 3D-PAWS
   **RMSE** (k = 1, already computed) and bias against that area's goal / breakthrough /
   threshold, at a matching observing cycle. Note the horizontal-resolution benefit of a dense
   network separately.

For each station/sensor/variable, compute the bias and U95 (95th percentile of
|3D-PAWS − TSMS|) at the Annex 1.A averaging time, assign the Annex 1.G class, and list Annex 1.A
required/achievable values for context. Report it as conservative: the differences include
siting (Annex 1.D, separate in the WMO scheme) and the reference's own uncertainty. This goes
beyond the TSMS report, which makes no WMO comparison (method-differences G8).

## Plot backlog (2026-09-28)

Suggested additions to `scripts/plotter/plot-gen-final.py`, ranked by value. Report figure
numbers in brackets.

| ID | Plot | Why | Priority |
|---|---|---|---|
| PL-01 | Daily cycle of the **bias** by site (hour of day; median + IQR band), T and RH; plus a month × hour bias heatmap per sensor [report 6.9, 7.5, 8.3 show values, not bias] | Radiation-shield heating/cooling, Konya courtyard effects, HTU winter bias (SF-04) | High |
| PL-02 | Temperature bias binned by reference wind speed and by SI1145 VIS (sunlight proxy) | Separates shield effects from sensor error | High |
| PL-03 | Cumulative rainfall per site, all four gauges on one axis (double-mass style) [10.1, 10.2 are monthly totals] | Shows SF-09, SF-11, SF-12, SF-16 in one figure per site | High |
| PL-04 | CDF of \|3D-PAWS − TSMS\| for every variable, with Annex 1.G Class A/B/C limits marked [8.7 does pressure only] | Visual version of the WMO classification (95% crossing = class) | High |
| PL-05 | Wind: speed ratio and direction error binned by reference speed | Starting threshold (PF-32), sheltering at Konya/Ankara, justifies the 3 m/s regime split | Medium |
| PL-06 | Data-availability timeline: station × month % valid minutes per variable, with excluded / recovered / failure periods shaded | Supports methods (what was kept, removed, recovered) | Medium |
| PL-07 | POD / FAR / CSI, ours vs. the report [10.3], at 0.2 and 1.0 mm (PF-40) | Rain comparison in one chart | Medium |
| PL-08 | Pressure bias over time (monthly median + IQR) | Shows TSMS04 drift (SF-18); cleaner than the current difference time series | Medium |
| PL-09 | Bland–Altman for pressure [8.5], and extend to T and RH | Report only has this for pressure; nothing implemented on our side yet for any variable (checked `plot-gen-final.py`, 2026-09-29) | Low |
| PL-10 | Taylor diagrams [6.8] | Only for figure-for-figure parity; adds little beyond the tables | Low |
| PL-11 | Replace raw-value box / violin / histogram plots (redundant) with distributions of the **differences** [6.5–6.7, 8.2] | Less redundancy; shows error, not climate | Low |
| PL-12 | Seasonal (month-of-year) bias distribution, per variable — extends PL-01's diurnal cycle to the annual one | Report §3.7 does this for pressure; useful anywhere a sensor's error might drift with temperature/season (HTU winter bias, SF-04) | Medium |
| PL-13 | Bias vs. ambient temperature, binned or scatter, for pressure (report §3.7) and humidity (HTU21D's RH output is itself temperature-compensated, so its bias could show the same dependence) | Distinguishes a sensor's own temperature-compensation error from shield/siting effects (PL-02 covers the latter) | Medium |

### PL-09, PL-12, PL-13: report §3.7 pressure follow-ups (2026-09-29)

The report's §3.7 pressure section uses Bland–Altman plots (fig. 8.5), seasonal bias
distributions, temperature-dependent bias analysis, and a CDF of absolute pressure error (fig.
8.7, already generalized to every variable as PL-04). Checked `plot-gen-final.py`: none of
Bland–Altman, seasonal bias, or temperature-dependent bias are implemented for *any* variable yet
(not just missing for T/RH as the old PL-09 wording implied) — so PL-09 is now pressure-first,
parity-with-the-report, and T/RH is the extension beyond it. PL-13 (bias vs. temperature) applies
to humidity too: the HTU21D's RH output is itself temperature-compensated internally, so the same
kind of dependence the report is checking for pressure could show up there as well, separately
from the shield-heating effect PL-02 already covers.

## Presentation deliverables (planned after the cleaning and analysis fixes)

Built from the regenerated statistics and plots. Both are in the same order and numbered to match.

| ID | Deliverable | Audience | Content |
|---|---|---|---|
| PD-01 | **Speaker notes** (private artifact) | Presenter only | Section-by-section talking points keyed to each numbered visual: the point to make, supporting numbers, caveats (e.g. siting, SF-17, recovered windows), likely questions and answers, and what's still outstanding. Replaces the text-heavy "TSMS Report Cross-Check" page as the presenter's guide **Built 2026-09-29** for the 30 Sep meeting (24 slides): https://claude.ai/artifact/6fPq8mwbLfNGE8L7taikos |
| PD-02 | **Visuals deck** (artifact, or PDF if preferred) | Team | One plot or table per section, a short caption or 2–4 bullets, no paragraphs. Same order and numbering as PD-01 **Built 2026-09-29** for the 30 Sep meeting (24 slides): https://claude.ai/artifact/LK8mFFbYucu4ZZF3BZnVXy |

Order (draft): takeaways → **cleaning practice: the detailed step table and explanations from
[qc-framework.md](qc-framework.md), including the questions for the team to weigh in on** → agreement (bias dot plots, wind-direction table) → Konya gap →
rainfall (wet days at 0.2 and 1.0 mm, cumulative curves PL-03, POD/FAR/CSI PL-07) → CHORDS column
fix (before/after) → QC flaw (removal table) → WMO framing (class grid, error CDFs PL-04) → siting
(wind error vs. speed PL-05) → questions for TSMS → next steps.
