# Logic changelog

Running record of changes to our own analysis logic: what was wrong before each fix, what
changed, and how results were affected. Differences from the TSMS report are tracked separately
in [method-differences.md](method-differences.md).

Newest entries first. Each entry lists the files touched, the problem in detail, the fix, the
effect on results, and anything left open.

---


## 2026-09-29: Report-parity figures (every figure in the TSMS report, side by side with ours)

**Files:** `scripts/plotter/plot-gen-final.py` (new `report_fig_*` functions, registered as `report-fig-6.1` …
`report-fig-10.3`); `plots/report-comparison/` (side-by-sides, `ours/`, extracted `report-figures/`, README).

**Before (what was wrong):** we compared only the report's Tables 4 and 6–9. Its 32 figures had no counterpart,
so differences in method or data (e.g. the Konya reference) couldn't be seen.

**Change:**
- Each figure is recomputed with the report's period, sensors (MCP9808; SHT31D else HTU21D; BMP280) and wind height
  treatment (Hellmann to 2 m).
- It's shown next to the report's own image, which pypdf extracted from the PDF. N is in every legend.
- Method choices the report doesn't state are listed per figure in the README: daily aggregation for the scatters,
  local time for the diurnal plots, our own eligible-day rule for monthly means.

**What it showed:**
- Ankara and Adana reproduce closely.
- **The report's Konya reference in Fig 6.3 is 1–2 °C colder than the Konya reference file we received**, while
  its 3D-PAWS lines match ours. This is the likely source of the report's Konya bias (G17, TSMS question 1).
- Seven internal inconsistencies in the report, listed in the README and the companion deck. Among them:
  - Fig 10.1 vs 10.2 reference rain differs about 10×;
  - the diurnal plots are in local time although §3.6 says UTC;
  - the Konya reference wind looks unadjusted to 2 m.

## 2026-09-29: Report parity tables (one per report table) in `compare_with_report.py`

**Files:** `scripts/comparison/compare_with_report.py`; outputs `data/report-comparison/table-*.csv`,
`figure-10-2_p62_monthly-precipitation.csv`, `report-consistency-checks.csv`, `report-parity-tables.xlsx`.
Backup of the previous outputs: `data/archive/report-comparison-backup-09292026_[BEFORE-PARITY-TABLES]/`.

- **Before:** side-by-side only for Tables 4, 6, 6, 7, 8, 9, report sensor only, on `data/cleaned` as written
  (after our Step 7, which blanks every < 80% day). No completeness tables (Tables 2, 3), no Table 1,
  no Table 9 valid/wet days or report contingency counts.
- **Change:** new parity tables for Tables 1, 2, 3, 4, 6 (RH), 6 (pressure), 7, 8, 9 and Fig. 10.2 (text
  values), every 3D-PAWS sensor as its own row/column, report values beside ours. Minute-level values are
  "QC-valid": `data/cleaned` plus the minutes Step 7 removed only for daily completeness (restored from
  `*_outliers.csv`), because the report applies the 80% rule only to daily aggregation. Completeness also
  given "before QC removals". Wind speed adds a calm-excluded sensitivity row. `REPORT_COMPARISON_OUT`
  env var redirects output for dry runs.
- **Effect:** the three original CSVs are byte-identical to before. Restoring the Step 7 minutes raises
  N by ≈ 1–2% for temperature/pressure and more for HTU21D humidity (TSMS00 696,858 → 1,124,946 vs. the
  report's 1,059,354); temperature/pressure biases move by ≤ 0.02 at Ankara/Adana, humidity more
  (TSMS00 −1.70 → −2.20 %RH, the report's −2.20). Findings in method-differences G25, WS5.

## 2026-09-29: Wind roses share one scale per site and show N; reference rain traced to the TSMS export

**Files:** `scripts/plotter/plot-gen-final.py` (`windrose`, new `_windrose_hourly`, `_windrose_site_scale`,
`_nice_scale`); docs.

**Wind roses.**
- **Before:** each 3D-PAWS/reference pair shared a radial scale, but the three regimes (all, variable,
  non-variable) and the three stations each had their own. The same ring meant different percentages
  on different roses. The legend gave hours, not N.
- **Change:** one scale per site, covering the largest sector of all 18 roses at the site (3 stations
  × 2 instruments × 3 regimes). The rings step in 1, 2, 2.5, 5 or 10% increments, at most 6 rings.
  Scales: Ankara and Konya 0–40%, Adana 0–50%. The legend shows `N = <hourly values drawn>` and the
  calm hours left out.

**Reference rain (SF-09, SF-31).**
- The two TSMS data deliveries differ **only in rain**; every other variable is 100% identical where
  they overlap (Oct 2022 – Dec 2024).
- **Ankara:** the newer export is exactly ×10 the earlier one from Q1 2023. The earlier export
  matches the 3D-PAWS gauges and the old Turkiye_Intercomparison analysis.
- **Adana:** the newer export adds 941 summer 0.1 mm minutes (the SF-31 small-amount days).
- **Konya:** agrees to 98.6%.
- Not yet acted on: whether to use the earlier export's rain through Dec 2024 is a decision for the
  user and TSMS (question 10).

## 2026-09-29: `plot-gen-final.py` restructured into named plot functions

**Files:** `scripts/plotter/plot-gen-final.py`

**Before (what was wrong):**
- One 1,866-line loop over stations, with 20 plot sections. You chose plots by commenting sections in
  and out.
- Sections depended on each other's side effects: the box plots only worked because an earlier
  section had set the date index.
- Several sections couldn't run on today's data:
  - pandas 3 removed `SettingWithCopyWarning`;
  - `bme2_hum` is gone, and the new `_flag` text columns are present;
  - `scatter-temp-sensors` used an undefined path.
- Paths only worked from the repo root.

**Change:**
- Each section is now a function, with its header as the docstring and its special logic kept.
  - Kept: Hellmann reduction, wind regimes from the reference, declinations, bias lists, per-sensor
    loops, file names and folders.
  - Alternatives kept as parameters (e.g. `regime`, `apply_declination` on the monthly wind roses).
- A registry of 20 named plots and a command line:
  - `python main.py plots --list`;
  - `python main.py plots windrose boxplots --stations TSMS06 --sites Adana`;
  - with no names, only `windrose` runs, as before.
- Data is loaded once per site, numeric columns only. A missing sensor column is skipped with a note,
  and a failing plot is reported without stopping the run. Uses the Agg backend.
- Fixes limited to what was needed to run: the pandas 3 warning, NaN-safe fits, and an explicit date
  index in the box plots. The difference plots' per-day loop became one merge; it matched the
  original on 90 sampled days.

**Verification:**
- Default wind roses for TSMS00 and TSMS02–05 are byte-identical to the previous output (30 PNGs).
- Every other plot ran on TSMS06 / Adana.
- The wind roses for all nine stations were then regenerated from the current `data/cleaned` (54 PNGs).
- The original script is the last committed version in git (`git show HEAD:scripts/plotter/plot-gen-final.py`).

**Open:** nine bugs in the original sections were reported and deliberately left as they were
(PF-45).

## 2026-09-29: `main.py` command center; splice backup path; downstream re-run

**Files:** `main.py` (rewritten), `scripts/error/error-analysis.py` (`--timescale` option),
`scripts/reformatting/splice_chords_dec2024.py`, `scripts/plotter/plot-gen-final.py` (refactor, see next entry).

**Before (what was wrong):**
- `main.py` was only a docstring. Every step was run by hand, and error-analysis's timescale was changed
  by editing the file.
- **Backups sat inside the live data folders.** The user has moved them to `data/archive/`.
- **The splice script would have corrupted a re-run.** It always rebuilds from
  `data/reformatted_backup_pre-chords-splice/`, treated as the untouched original. With that folder
  moved, a re-run would have copied the *already spliced* files in as the "original" and spliced them
  twice.

**Change:**
- **`main.py`** runs each step as a subcommand, from the repo root, and stops on the first failure:
  `status`, `reformat`, `splice`, `clean`, `analyze`, `compare`, `plots`, `failures`, `all`.
  - `clean` asks first, then backs up `data/cleaned` to
    `data/archive/cleaned-backup-<MMDDYYYY>_[BEFORE-<LABEL>]/` and verifies it byte for byte.
  - `analyze` and `compare` back up their outputs the same way.
- **The splice script** now reads its originals from `data/archive/reformatted_backup_pre-chords-splice/`.

**Downstream re-run on the 2026-09-29 station-events cleaning** (previous outputs in
`data/archive/analysis-backup-09292026_[BEFORE-REF-EVENTS-RERUN]/`):

| Result | Change |
|---|---|
| TSMS08 wind speed | Class B → A (N 138,792 → 82,747; RMSE 0.70 → 0.48 m/s), after its dead-anemometer periods were removed |
| TSMS06/07 wind speed | RMSE 0.44/0.42 → 0.37/0.35 m/s, after the Adana reference outage was removed |
| Ankara rain, flagged days excluded | Now **0 paired days** at TSMS00/01 and 16–108 at TSMS02. The whole reference record from March 2023 is flagged (SF-09) and the pre-visit gauge flags cover the earlier months |
| Konya rain, flagged days excluded | Loses 5–38 days (the watering period); CSI unchanged |

The Ankara row makes the "flagged days excluded" rain result empty there until the ×10 decision.

## 2026-09-29: Confirmed failures encoded as station events (incl. reference stations); `data/cleaned` re-run

**Files:**
- `scripts/outliers/outlier-removal.py`: Step 1 now also applies events to the site's TSMS reference, written as `REF-<site>` in `station-events.csv`. Reference flag columns carry `event:` flags, and `station_event_flags.csv` is de-duplicated.
- `docs/station-events.csv`: 14 new rows.
- `scripts/plotter/plot-sensor-failures.py`: new SF-29, SF-30, SF-31 figures; SF-28 rebuilt as watering and moved to the 3D-PAWS folder.

**Before (what was wrong):**
- **Station events couldn't target a reference station.** So the Adana reference outage (SF-26) and the Ankara ×10 rain (SF-09) had no documented handling.
- **Several confirmed failures were only partly handled** by the automatic checks:
  - TSMS01's stuck vane: 6,625 of ≈ 44,000 readings.
  - TSMS08's dead anemometer: 58,189 minutes of a fault spanning months.
- **Konya watering tips and TSMS02's dead gauge carried no flag.**

**Change (following the framework: confirmed non-rain failures removed, rain only flagged):**

| Action | Entry | What |
|---|---|---|
| Remove | SF-26 | Adana reference wind speed, 2025-08-09 14:00 → 2025-10-13 07:59 |
| Remove | SF-22 | TSMS01 wind direction, 2024-10-21 12:34 → 2024-11-21 12:25 |
| Remove | SF-27 | TSMS08 wind speed: 2023-04-29 → 2024-01-12; Jun–Oct 2024; the 0.7 m/s stuck spans in Jan–Feb 2024 |
| Flag | SF-09 | Ankara reference rain from 2023-03-06 (`rain_scaling_x10`; no ÷10 correction applied) |
| Flag | SF-29 | TSMS02 rain, 2023-03-31 → 2024-01-04 |
| Flag | SF-28 | Konya rain, 1 Jul – 2 Sep 2023 (TSMS03/04/05); Jul 2025 (TSMS05) |
| Note | SF-30 | TSMS01 anemometer reading low |

**Effect (vs. `data/archive/cleaned-backup-09292026_[BEFORE-REF-EVENTS]/`):**
- Wind speed removed: TSMS08 465,255 readings; Adana reference 94,600.
- Wind direction removed: TSMS01 35,760.
- Rain newly flagged: Ankara reference 1,437,575 readings (the whole period from 6 Mar 2023); TSMS02 368,033; TSMS03/04 ≈ 91,800 each; TSMS05 133,780.
- Nothing else changed.

**Open:**
- Downstream results (error-analysis, WMO classes, report comparison, wind roses) predate this run and need re-running.
- Team decisions still pending: Ankara ÷10 correction vs. exclusion; remove the watering tips or keep them flagged.

## 2026-09-29: Sensor-failure figures; catalog corrections

**Files:** new `scripts/plotter/plot-sensor-failures.py` (one function per failure; writes
`plots/diagnostics/*/README.md`); `docs/sensor-failures.md`.

**What the figures showed that we had wrong (each checked against the reformatted data):**

| Entry | Before | Corrected |
|---|---|---|
| SF-09 | Ankara reference rain inflated, perhaps weighing-gauge noise | A **×10 scaling error from 2023-03-06**. Wet-day ratio vs. TSMS00: 0.97 before, 9.96 after. The reporting step changes from 0.01 to 0.1 mm that day |
| SF-28 | Konya *reference* missed rain on 12 days | The reverse: **courtyard watering** tips all three Konya 3D-PAWS gauges at ≈ 10:00 UTC at ≈ 27% RH. The reference's 0.6 mm is right. The Step 6 dead-gauge rule flagged the wrong instrument |
| SF-26 | Suspected, mostly unconfirmed | A **reference anemometer outage**, 10 Aug – 12 Oct 2025 (≈ 100% zeros). The Step 6 calm check missed it, because Adana's 2 m winds are mostly below 1.5 m/s |
| SF-17 | Sep–Oct 2024 affected `sth_*` only | All TSMS06 sensors were zero, 35,743 minutes |
| SF-27 | 58,189 minutes | TSMS08 reads 0 in 90–100% of minutes in most months May 2023 – Oct 2024, plus a stuck 0.7 m/s in Jan–Feb 2024 |

Smaller corrections: SF-22 lasted a whole month; SF-23 is 25 runs on 22 days; SF-24 adds a fourth day; SF-25 lasted longer than QC removed.

New entries:
- SF-29: TSMS02 rain gauge dead during its anemometer outage.
- SF-30: TSMS01 anemometer reads ≈ 30% of TSMS00.

**Open (decisions pending; each needs a `data/cleaned` re-run):**
- Correct the Ankara reference rain (÷10 from 2023-03-06) or exclude it.
- Remove the Adana reference wind speed for 10 Aug – 12 Oct 2025.
- Remove or flag the Konya watering tips.
- Bound SF-22, SF-27 and SF-29 as station events.

## 2026-09-29: Rain reported at two wet-day thresholds and with/without flagged days; downstream re-run

**Files:**
- `scripts/comparison/compare_with_report.py` (new `WET_THRESHOLDS`; precipitation table now long-format).
- `scripts/error/error-analysis.py` (new WMO row `tipping (flagged days excluded)`; `sum_variables` extended).

**Before (what was wrong):**
- Rain was compared at the report's 0.2 mm wet-day threshold only, with every day counted.
- That included days where either gauge is known to be bad: TSMS05's junk months (SF-12), the Ankara
  reference's inflated totals (SF-09), and dead-gauge days.
- As a result the TSMS05 rain RMSE was 78 mm/day and its class D.

**Change:**
- The report comparison gives every combination of wet-day threshold (0.2 mm, 1.0 mm) × days (all,
  flagged days excluded). A day is excluded when either gauge has any flag that day.
- The WMO classification adds a flagged-days-excluded rain row per station.
- The report's own values sit beside the 0.2 mm / all-days rows.

**Effect (regenerated data):**
- **FAR at 1.0 mm:** 0.04–0.35, vs. 0.14–0.66 at 0.2 mm.
- **Adana reference:** ≈ 290 days with 0.2–1.0 mm that 3D-PAWS rarely registers (new lead,
  method-differences P10, TSMS question 15).
- **WMO rain class, flagged days excluded:**

  | Station | All days | Flagged days excluded |
  |---|---|---|
  | TSMS05 | D (RMSE 78.2 mm) | **B** (RMSE 1.26 mm) |
  | TSMS04 | D | C |
  | TSMS07 | D | C |
  | TSMS00–02 (Ankara) | D | D |

  Ankara stays D: its reference over-reads on most wet days (bias −21 to −23 mm/day), not only on the
  flagged ones (SF-09).

**Downstream re-run on the regenerated `data/cleaned`:**
- `data/error-analysis` hourly and daily statistics, and `wmo-classification.csv/.xlsx`. The previous
  files are in `data/archive/error-analysis-backup-09292026_[BEFORE-QC-FRAMEWORK]/`.
- `data/report-comparison/*.csv`.
- Wind roses in `plots/wind-roses/`.

## 2026-09-29: QC framework stage 6: Step 8 flag columns; statistical test dropped for wind

**`data/cleaned` regenerated 2026-09-29 with Steps 0–8.** The previous files are in
`data/archive/cleaned-backup-09292026_[BEFORE-QC-FRAMEWORK]/`. Every downstream result (error-analysis,
WMO classification, report comparison, plots) predates this and must be re-run.

**Files:** `scripts/outliers/outlier-removal.py`:
- New `add_flag_columns()`.
- Step 6a records which flags were corroborated.
- Wind removed from Step 5.
- The header phase list is updated.

**Before (what was wrong):**
1. **Flags lived only in side files** (`*_flags.csv`, `station_event_flags.csv`). The cleaned data didn't
   say which kept readings were suspect, so the analysis couldn't report rain with and without flagged
   periods.
2. **Statistical test on wind (added in stage 5).** At 11, 21 and 61 min alike it flagged about 1–3% of
   minutes (Adana), and 90–95% of 3D-PAWS speed flags were gusts the neighbours also saw. So wind was
   being marked "suspect" for being gusty. Before stage 5, wind had no statistical test at all.

**Change:**
- Every value column in the `*_final.csv` files gets `<column>_flag`: empty = good, otherwise the
  `;`-separated reasons (e.g. `tipping_flag`, `temperature_flag`). Codes:
  - `step`, `hampel`, `z_score`, each with `:corroborated` when Step 6 found a co-located witness;
  - `stat_untested`;
  - `rain_low_rh`, `rain_dead_gauge`, `rain_uncorroborated`;
  - Step 1 flag events as `event:<name>`.
- Removed readings stay blank, with the reason in `*_outliers.csv`.
- Wind QC is now the step test, stuck vane, calm check and documented events (decided with the
  window comparison above).

**Effect (test run, scratch):**
- Flagged readings per temperature sensor: 2,000–7,300, mostly `hampel:corroborated` (real convection)
  and `stat_untested`.
- Pressure: 200–4,200 per sensor, mostly `event:maintenance_visit` and `stat_untested`.
- Wind: about 1,400 per 3D-PAWS station (the visit day), plus TSMS07's pre-visit anemometer flag
  (`event:anemometer_binding`, ≈ 590,000 minutes).
- Rain: the degraded-gauge events flag TSMS00, 01, 06 and 07 from the start of the record to the
  January 2024 visit (≈ 590,000–740,000 minutes each).
- TSMS05 rain: 3,378 mm in total, 832 mm without flagged periods (the SF-12 junk months carry
  `rain_uncorroborated`).
- Ankara reference rain: 26,715 minutes `rain_uncorroborated` (SF-09).

**Open:**
- Error-analysis doesn't read the flag columns yet. Next: rain statistics with and without flags
  (PF-40 wet-day thresholds too).
- Whether the degraded-gauge flags should cover the whole pre-visit record (qc-framework question 9).

## 2026-09-29: QC framework stage 5: Step 6 neighbour check; Step 5 extended to wind; per-site processing

**Files:** `scripts/outliers/outlier-removal.py`:
- New constants `NEIGHBOUR_SHARE`, `NEIGHBOUR_LAG`, `NEIGHBOUR_GROUPS`, `CALM_RUN_MINUTES`, `CALM_NEIGHBOUR_SPEED`, `RAIN_EVENT_MM`, `RAIN_DRY_MM`.
- New functions `wrap180()`, `local_anomaly()`, `completeness_step()`; circular option in `stat_outliers()`.
- New outlier reasons `neighbour_uncorroborated`, `no_neighbour`, `anemometer_not_responding`, `reference_suspect_calm`.
- New flag reasons `rain_dead_gauge`, `rain_uncorroborated`.
- The main loop now stores each station's results after Step 5. Step 6, Step 7 (completeness) and the output run per site with all four instruments in memory.

**Before (what was wrong):**
1. **No neighbour check.** Only humidity had a site cross-check (Phase 5, HTU only). The step-test and statistical flags had nothing to confirm or clear them.
2. **Statistical tests skipped wind,** as requested: the 21-min window now applies to every variable except rain. Wind direction uses circular statistics and only minutes with the cups turning.
3. **Calm and dead gauges were never checked against the neighbours.** TSMS08's anemometer was reading 0 through summer 2023 while both neighbours had wind (SF-27). The Konya reference gauge recorded nothing on days the 3D-PAWS gauges got ≥ 5 mm (SF-28).
4. **The reference was cleaned three times,** once per station, and written three times.

**Change:**
- **Rule (agreed 2026-09-29):** a flagged reading is kept only if a co-located instrument shows the same event. Same sign, ≥ 50% of the deviation from its own 21-min median, within ±1 min. Uncorroborated flags are removed, whether contradicted or unverifiable.
- **Calm:** zero-speed runs ≥ 3 h are removed when ≥ 2 other 3D-PAWS anemometers read a median ≥ 1.5 m/s. The cups start at ≤ 1.2 m/s per SMN's tunnel tests.
- **Rain:** daily dead-gauge and uncorroborated days are flagged.
- The reference is processed once per site.

**Wind decided 2026-09-29: flags only** (`NEIGHBOUR_FLAG_ONLY`). Uncorroborated wind flags are kept, because the 10 m and 2 m anemometers can't vouch for each other's gusts. The wind rows below show what removal *would* have done.

**Effect (test run, scratch):**

| Group | Flags corroborated (kept) | Removed |
|---|---|---|
| Temperature, working sensors | 95–99% | the rest |
| HTU21D at TSMS00–02 (bit-switching) | 25–48% | 52–75% |
| Reference pressure, Ankara | 35 of 432 | 397 |
| Reference wind speed | 28–53% | 0.7–1.4% of all reference wind |
| 3D-PAWS wind direction | 31–82% | up to 2% of readings (TSMS00) |

Other changes:
- Calm minutes removed: TSMS08 58,189 (SF-27); Adana reference 213.
- Rain flags: TSMS05 976 mm on 4 days (SF-12); Ankara reference 583 mm on 19 days (SF-09).
- Dead-gauge days: TSMS01 26, TSMS02 21, TSMS08 13, Konya reference 12 (SF-28).

**Open:**
- Step 8: flag columns (`tipping_flag` etc.).

## 2026-09-29: QC framework stage 4: Step 5 statistical outliers (window, data share, MAD, flag-only)

**Files:** `scripts/outliers/outlier-removal.py`:
- New `stat_outliers()`, constants `STAT_WINDOW`, `STAT_MIN_SHARE`, `STAT_K`, `STAT_REMOVE`.
- Phase 6 replaced by Step 5; new flag reasons `hampel`, `z_score`, `stat_untested`.

**Before (what was wrong):**
1. **The Hampel MAD wasn't the Hampel MAD.** It took each reading's distance from *its own* rolling
   median, then a rolling median of those distances, so each distance was measured against a
   different centre. The standard MAD is the median of the window's distances from the *window's*
   median.
2. **The "centred" window was 20 wide,** so it ran 10 minutes back and 9 forward.
3. **A reading was judged with only half its window present** (`min_periods = 10`). A reading in a
   sparser window was silently skipped, so nothing recorded that it hadn't been tested.
4. **Readings flagged by both tests were logged twice** (as `z-score_contextual` and
   `hampel_contextual`), which inflated the removal counts.
5. **Every statistical flag was removed,** from the reference as well. We measured how many were real:
   for temperature, **61–95% of flags are corroborated** by a co-located instrument, meaning the same
   deviation, same sign, same minute:

   | Flagged series | Flags | Corroborated |
   |---|---|---|
   | Adana reference | 3,703 | 61% |
   | Adana MCP9808s | 1,932–2,438 | 90–95% |
   | Konya reference | 239 | 77% |
   | Konya MCP9808s | 1,531–1,983 | 69–93% |

   They cluster at 09–11 UTC, with a median deviation of 0.5 °C: midday convection, just above the
   0.44 °C Hampel cut-off (3 × 1.4826 × the 0.1 °C floor) in otherwise steady windows. So Phase 6 was
   deleting real weather.

**Change:**
- A 21-minute centred window (exactly 21 minutes, since Step 0's grid).
- At least 60% of the window present, else the reading is flagged `stat_untested`.
- Standard MAD × 1.4826, k = 3, floors unchanged.
- Each reading logged once (`hampel` takes precedence over `z_score`).
- **Outcome is a flag** (`STAT_REMOVE = False`); Step 6 will remove the flags no co-located
  instrument supports. Same columns as before (T, RH, pressure, SLP; not wind or rain).

Effect of the method change alone (same input, flags counted with removal on). The corrected test flags 12–71% fewer readings, depending on the sensor:

| Series | Before | After |
|---|---|---|
| Konya reference T | 510 | 242 |
| TSMS03 `sth_hum` | 17,809 | 8,354 |
| TSMS07 `htu_hum` | 24,419 | 6,989 |

**Effect on the cleaned data (test run, scratch):** valid readings **kept** that stage 3 had removed:
- 2,400–6,100 per temperature sensor per station;
- 10,000–47,000 per humidity sensor, mostly HTU21D;
- 27–82 for pressure;
- reference temperature 500 (Konya), 2,873 (Ankara), 4,194 (Adana).

The flags are in the `*_flags.csv` files.

**Open:** Step 6 (neighbour confirmation) is needed before `data/cleaned` is regenerated. Otherwise
the HTU21D bit-switching remnants that Phase 5 couldn't verify stay in as flags only.

## 2026-09-29: QC framework stage 3: internal consistency, step test, persistence

**Files:** `scripts/outliers/outlier-removal.py`:
- New constants `RAIN_RH_FLAG`, `STEP_LIMITS`, `PERSISTENCE_MINUTES`, `RH_PERSISTENCE_MAX`, `VANE_MOVING_SPEED`, `FREEZE_MINUTES`, `COLUMN_KIND`.
- New functions `run_lengths()`, `persistence_mask()`, `frozen_mask()`, `removal_log()`, `flag_log()`.
- New outlier reasons `logger_zeros`, `persistence`, `logger_frozen`.
- New flag reasons `rain_low_rh`, `step`, with new outputs `3DPAWS_<station>_<site>_flags.csv` and `TSMS_Reference_<site>_flags.csv`.

Step 3 runs before the HTU filter (Phase 5); Steps 4a and 4b run after it, before the statistical tests (Phase 6).

**Before (what was wrong):**
1. **No internal-consistency check.** TSMS06's logger zeros (SF-17: every T and RH sensor at exactly
   0.0 for ≈ 118,000 minutes) passed the range check (0 °C and 0% are "in range") and went into the
   statistics, worth about −20 °C and −63 %RH against the reference in those minutes.
2. **Step test only on the HTU21D.** Jumps in any other sensor, or in the reference, weren't looked at.
3. **No persistence test at all.** Stuck sensors passed every check, because a stuck value is in range
   and has zero spread, so the Hampel/z-score tests can't see it. Found once the test existed:
   - a **frozen record at the Ankara reference** on 25 mornings, Jun–Aug 2025 (SF-23);
   - the Ankara reference humidity stuck at 10% (SF-24) and its vane at 0° (SF-25);
   - TSMS01's vane at 0.0° (SF-22);
   - TSMS03 `bmp2_temp` stuck for 3 h;
   - several short stuck-vane runs.

**Measured before choosing limits** (reformatted data, nulls and range applied):
- 1-min changes on working sensors: 99.99th percentile ≤ 1.3 °C, 9 %RH, 0.4 hPa, 8 m/s. The HTU21D
  bit-switching gives changes of up to 77 °C / 74 %RH.
- **The proposed persistence limits needed two changes:**
  - **Humidity: "below 100%" → "below 80%".** The Adana reference sits at exactly 99% (its saturation
    reading) for up to 20 h in fog (103 runs). The Konya reference holds 85–91% for 4–8 h on freezing
    nights, which is saturation over ice.
  - **Pressure: 2 h → 3 h.** Genuine plateaus at the turning points of the daily cycle reach 2.6 h
    (Konya, Adana references).
- **Wind direction "unchanged 1 h with speed > 0" was too loose.** TSMS08 would have lost 24,362
  readings at a median speed of 0.7 m/s, where a still vane is plausible. The rule is now a run of
  identical directions containing ≥ 60 minutes of wind ≥ 1 m/s. The 1 m/s placeholder stands in for the
  vane's starting threshold until the datasheets arrive (PF-42).
- **Frozen logger needed "nonzero wind speed".** Without it, a calm, foggy night at the Adana
  reference (68 min at 99%, 0 m/s, 12.4 °C) would count as frozen. The 25 Ankara events all repeat
  speeds of 1.4–10.2 m/s.

**Change:**
- **Step 3.**
  - Logger zeros removed: exact 0 %RH together with exact 0.0 °C in the same minute; all exact zeros in that minute's T/RH columns.
  - Rain with RH < 60% flagged (each instrument's own humidity).
- **Step 4a.** Step test at the TSMS Table 1 limits (2 °C, 15 %RH, 0.5 hPa, 8 m/s, 5 mm) on every variable except wind direction and SLP. Flag only; both ends of a jump are flagged.
- **Step 4b.**
  - Persistence with the limits above.
  - Frozen logger: T, RH, pressure and a nonzero wind speed all unchanged ≥ 60 min, every column removed.
  - Applied to the 3D-PAWS stations and the reference.

**Effect (test run, output to scratch; `data/cleaned` not yet regenerated).** Valid readings removed
vs. the stage 2 output, including knock-on Phase 6/7 changes:

| File | Removed |
|---|---|
| TSMS06 | `sth_temp` 97,829, `sth_hum` 97,748, `bmp2_temp` 64,319, `mcp9808` 62,603 (SF-17); `wind_dir` 1,705 |
| TSMS01 | `wind_dir` 8,547 (SF-22) |
| TSMS08 | `wind_dir` 16,150 |
| TSMS03 | `wind_dir` 2,875; `bmp2_temp` 187 |
| TSMS02 | `wind_dir` 1,598 |
| TSMS07 | `wind_dir` 317 |
| Ankara reference | ≈ 5,100 per variable (frozen record, SF-23); humidity 9,641 (incl. SF-24); `avg_wind_dir` 7,785 (incl. SF-25) |
| TSMS00, 04, 05, Konya reference, Adana reference | none |

Flags (kept):
- Rain with RH < 60%: reference 40–248 mm per site; 3D-PAWS 52–253 mm per station, plus TSMS05's 2,312 mm of SF-12 junk.
- Step flags: dozens to hundreds per sensor, excluding the HTU21D. The HTU21D gets thousands at TSMS00–02, from bit-switching the Phase 5 filter couldn't verify.

**Open:**
- Step 6 must confirm or clear the step flags and judge long zero-speed runs (SF-26, Adana reference 2025).
- Step 8 turns the flags into columns (`tipping_flag`).
- The `VANE_MOVING_SPEED` and step limits should come from the datasheets (PF-42).

## 2026-09-29: QC framework stage 2: Step 1 "Metadata & diagnostics" from a station-events table

**Files:** `scripts/outliers/outlier-removal.py` (new `metadata_step()`, `event_mask()`,
`event_columns()`; `sensor_failures` dict and `failure_mask()` removed; the hard-coded TSMS04 and
TSMS08 rain removals deleted from Phase 4; outlier reason `sensor_failure` → `station_event`, logged
as `station_event:<event>`; new output `station_event_flags.csv`), new
[station-events.csv](station-events.csv). Sources: `docs/Maintenance-Logs/` (Jan 2024 visits) and
the evaluation plan.

**Before (what was wrong):**
1. **The maintenance logs weren't used at all.** Nothing in the pipeline knew about the visits,
   the sensor swaps, or the conditions the technicians found.
2. **TSMS02's anemometer was unplugged for ≈ 9.5 months and its zeros were kept as calm** (new
   SF-20). From 2023-03-31 12:17 to 2024-01-11 10:02, all 407,009 `wind_speed` readings are exactly
   0 while the Ankara reference median is 1.5 m/s. 0 m/s passes the range check and wind isn't
   tested statistically, so every zero went into the TSMS02 wind statistics as real calm.
3. **Documented removals were scattered:** two rain blocks with hard-coded dates inside Phase 4,
   plus an (empty) `sensor_failures` dict at the top of the script. You had to read code to learn
   what was excluded and why.
4. **No way to mark a period suspect without deleting it.** Degraded but not failed conditions
   (a stuck bucket, pebbles in a funnel) could only be ignored or removed.

**Change (Step 1, one job: was the system known to be working?):** runs after Step 0, before the
range check. Each row of `station-events.csv` is `remove` (blank and log), `flag` (keep; list the
period in `station_event_flags.csv` for Step 8's flag columns) or `note` (print only). A blank start
or end means the start or end of the record. The pre-pass that builds site humidity for the HTU
cross-check uses the same `remove` rows. Battery diagnostics aren't used: the RPi stations
(TSMS00–05) don't log them, and the Particle stations' battery columns are constant 0 or absent.

**Effect (test run, output to scratch; `data/cleaned` not yet regenerated):**
- TSMS02 `wind_speed`: 407,009 readings removed (SF-20); nothing else in TSMS02 changes.
- TSMS04 and TSMS08 rain: identical to before (1,551,944 and 1,509,532 valid readings; 850.0 and
  1,052.6 mm), confirming the moved rules behave the same.
- 14 flagged periods: the nine visit days (all variables), four degraded rain gauges before the
  visits (TSMS00, 01, 06, 07; ≈ 600,000–730,000 readings each), and the TSMS07 anemometer (SF-21).
- No other values change.

**Correction made during testing:** I first set the TSMS02 outage start to 2023-03-15 00:00, taken
from a count on already-cleaned data, where Phase 7 had blanked 2023-03-15. The reformatted data
shows the anemometer still working that morning (659 readings to 11:00 that track the reference,
r = 0.62). The start is now 2023-03-31 12:17, the first reading after the record gap.

**Open:** the flagged rain periods run from the start of the record because the logs only
describe the visit day. Step 6 (neighbour check) should bound when each problem began. TSMS01's
near-zero rain since 2023 (SF-16) may be its stuck bucket.

## 2026-09-29: QC framework stage 1: Step 0 "Structure" replaces Phases 1–2

**Files:** `scripts/outliers/outlier-removal.py` (new `structure_step()`, `NULL_MARKER_CEILING`,
`LAYOUT_RANGES`; old Phase 1 "nulls" and Phase 2 "time resets" removed; outlier reasons renamed
`null` → `null_marker`, `timestamp_reset` → `duplicate_timestamp`; new output
`structure_layout_warnings.csv`). Framework: [qc-framework.md](qc-framework.md).

**Before (what was wrong):**
1. **No regular time grid.** Missing minutes had no row, so rolling windows counted rows, not
   minutes. TSMS03 had rows for 91% of its minutes, with 46 gaps over an hour and the longest 316 h.
   A "20-point" window could span days. The gap infill (`func.fill_empty_rows`) ran only in the TSMS
   reformatter, and cleaning dropped rows afterwards without refilling them.
2. **The first row of every file was dropped** (PF-06): its time difference is `NaT`, and
   `NaT > 0` is False.
3. **"Timestamp resets" were really duplicates.** The data was sorted first, so only duplicate
   minutes remained "out of order", and which copy was kept depended on an unstable sort.
4. **Only `-999.99` was treated as a null marker** (PF-05). The data also uses `-999.9`, `-999.0`,
   `-1000.0` (3D-PAWS) and `-9999.0` (TSMS), plus ≈ 320,000 `bmp2_slp` values near −1005: SLPs
   computed from a pressure marker, because `func.calc_slp` masks only `-999.99`. These were removed
   later by the range check but logged as `threshold`.
5. **Every blank cell was logged as a `-999.99` null,** whether or not it had ever held that value.

**Change (Step 0, one job: is the record well-formed?):** parse and stable-sort timestamps; drop
duplicate minutes keeping the first in file order (logged); reindex onto a complete 1-min grid with
empty rows for missing minutes; turn any value ≤ −990 into missing, logged with its original value;
and a **column-layout guard** that writes a warning, without changing data, for any month whose
median is implausible for its column.

**Effect (test run, output to scratch; `data/cleaned` not yet regenerated, see PF-35):**
- Every file is now on a full grid (e.g. TSMS02 1,450,888 → 1,731,519 rows).
- The first row is kept everywhere.
- Valid-value counts change by tens to ≈ 1,400 per column (out of ≈ 1.5 M). The differences come
  from the Phase 6 20-row windows now spanning exactly 20 minutes near gaps.
- Null markers are logged with their true value (e.g. 720,557 at TSMS03).
- **The layout guard flagged 26 station-months, all sensor faults rather than column mix-ups:**
  TSMS06 pressure 0 hPa (Oct 2024, Mar–May 2025; the SF-17 logger zeros) and ≈ 670 hPa from Jun
  2025 (SF-14), and **TSMS07 pressure stuck at ≈ 500.1 hPa, May–Oct 2024 (new, SF-19)**. The Phase 3
  range check (870–1,084 hPa) already removes these values.

## 2026-09-28: WMO classification replaces "Reliability" (PF-15)

**Files:** `scripts/error/error-analysis.py` (Reliability section and `wmo_thresholds` removed; `_paired()`
takes a `freq` argument; new WMO classification section writing `wmo-classification.csv/.xlsx`)

**Before (what was wrong):** "Reliability" = `(1 − MAE / SD_TSMS) × 100` isn't a standard metric and has no
link to WMO requirements, even though it was meant for comparing against them. It rewards variables with a
large natural range: pressure scored ~75% with a 1 hPa MAE, while wind scored 0% even where it agreed
reasonably. The `wmo_thresholds` list it sat next to (0.2 K, 3 %RH, 0.15 hPa, 5°, 0.5 m/s, 5%) turned out to
be WMO-No. 8 Annex 1.A's *achievable* column, not the *required* one, and it was only ever printed.

**Change:** a two-tier WMO comparison, computed at the WMO averaging time for each measurand regardless of
`TIMESCALE`. Temperature, humidity and pressure use 1-min values ("instantaneous", Annex 1.A note 4); wind
uses 10-min means; rain uses daily totals on days either gauge records ≥ 0.2 mm. OSCAR NWP/hydrology rain
uses hourly totals, excluding dry-dry hours.
1. **Annex 1.G Measurement Quality Classification** (k = 2): Class A/B/C is met when ≥ 95% of pairs have
   |3D-PAWS − TSMS| within the class's target system uncertainty (relative targets for wind speed and
   rain are evaluated against the reference value); otherwise Class D. Also reported: bias, RMSE,
   U95 (95th percentile of |difference|), % within each class, and % within the Annex 1.A required
   and achievable values.
2. **OSCAR/Requirements** (k = 1 RMSE) for 2.2 High-Resolution NWP, 2.3 Nowcasting/VSRF, 2.9 Agricultural
   Meteorology, and 4.1 Hydrology: the level reached (goal / breakthrough / threshold / below threshold).
   Humidity (OSCAR uses specific humidity), pressure (no near-surface requirement found) and direction
   aren't compared in this tier.
3. **Siting note:** every Konya and Ankara wind row carries a siting-limited note (docs/siting.md). Konya's
   note says outright that the class is *not* a measure of sensor performance.

The "Reliability"/"Inaccuracy" columns and sheets are gone from the hourly/daily outputs. The four
statistics sections are now Difference, Accuracy and Precision, plus the separate WMO file.

**Effect (test run on current `data/cleaned`):**
- **Temperature:** mostly Class D at 1-min resolution (U95 ≈ 1.0–1.9 K; Class C needs 1.0 K). Best:
  TSMS08 `htu_temp`/`mcp9808` and TSMS07 `htu_temp` reach Class C. OSCAR: breakthrough for nowcasting and
  HR-NWP at almost every station (RMSE 0.4–1.0 K; TSMS08 `mcp9808` reaches goal).
- **Humidity:** mostly Class C. Konya HTU21D is Class D, consistent with the winter high bias (SF-04).
- **Pressure:** Class C at Konya and Adana-TSMS07; Class D at Ankara, where a ≈ 1.1–1.3 hPa bias
  dominates (a possible barometer height difference, PF-18).
- **Wind speed:** all winds Class A–C. Non-variable winds Class B–C. **Konya's Class A / OSCAR "goal"
  is an artifact of sheltered, weak winds** (flagged).
- **Wind direction:** Class D everywhere. Adana is best (RMSE ≈ 16–27° at 10 min; Class C needs 15° at 95%).
- **Rain:** Class C at TSMS03 and TSMS06, D elsewhere. Ankara's −27 mm/day bias traces to the reference
  (SF-09), and TSMS05 to its July 2025 spike (SF-12).
- **New issue:** TSMS06 records exactly 0.0 on all temperature/humidity sensors for most of Feb–May 2025,
  and on the SHT31D in Sep–Oct 2024 (SF-17). This inflates its RMSE (e.g. `mcp9808` 4.2 K vs. U95 1.5 K).

**Interpretation (see methods.md §6):** the classes are conservative. The differences include the TSMS
reference's own uncertainty and, at Konya and Ankara, siting effects, which WMO treats separately (Annex
1.D). So the class is a lower bound on what the 3D-PAWS sensors achieve.

**Open:** wind starting threshold (Annex 1.G) not yet estimated (PF-32); Eₙ score needs the reference
uncertainty (PF-33); OSCAR humidity via specific humidity (PF-34).

## 2026-09-28: Daily completeness check added (Phase 7); analysis pairs minutes before aggregating

**Files:** `scripts/outliers/outlier-removal.py` (new Phase 7, `DAILY_COMPLETENESS`, outlier reason
`daily_completeness`); `scripts/error/error-analysis.py` (`_agg_timescale` replaced by
`_paired()` / `_wind_availability()`, `PAIRED_COMPLETENESS`); `data/cleaned` (regenerated)

**Before (what was wrong):**
1. **No completeness rule.** A day with 10 valid minutes counted as much as a full day in daily
   statistics, and daily rain sums on partial days were too low. The TSMS report requires ≥ 80%
   of 1,440 minutes (§3.6).
2. **Aggregation before pairing.** `_agg_timescale` averaged (or summed) each instrument over
   whatever minutes *it* had, and the hourly/daily results were paired afterwards. If 3D-PAWS
   was missing the afternoon and TSMS wasn't, the 3D-PAWS daily mean covered only the cooler
   hours, and the difference was reported as sensor bias. The same applied to rain totals, and to
   wind direction, where each side's vector mean came from different minutes.

**Change:**
- **Phase 7 (cleaning):** after all other QC, for each instrument, variable and calendar day, if
  fewer than 80% of the day's 1,440 minutes have a valid value, that day's readings of that
  variable are removed and logged as `daily_completeness`. It applies to TSMS and 3D-PAWS alike,
  per variable.
- **Pairing (analysis):** each 3D-PAWS variable is inner-joined with its reference variable
  **at minute level** first. Only minutes where both report are kept, then those pairs are
  aggregated: mean; sum for rain; speed-weighted vector mean for direction, each instrument
  weighted by its own speed. An hour or day is kept only if ≥ 80% of its minutes are paired
  (`PAIRED_COMPLETENESS`). Two instruments can each pass Phase 7 and still share far fewer minutes.
- **Wind completeness** is judged on minutes where both instruments report a *wind speed*
  (zeros count). It's not judged on the regime-split or zero-speed-filtered values. A first
  version used the filtered values, which made nearly every day "incomplete" for non-variable
  winds (they need 80% of the day to be windy) and dropped any hour with calm minutes from
  direction statistics. That changed TSMS01's daily non-variable direction MAE from 66° to 108°,
  based on a handful of days. Fixed before adoption.
- Paired results are cached per (station, variable), so each pair is built once and shared by
  all four statistics sections.

**Effect:**
- **Phase 7 removals:** 1–3% of most columns, reference included (e.g. Konya reference 1.4% for
  every variable). The exception is the HTU21D at the Ankara stations: 30–40% of `htu_temp` /
  `htu_hum` at TSMS00, 01, 02, where the Phase 5 bit-switching filter left many days below 80%. Also
  TSMS04 `htu_hum` 11% and TSMS07 `htu_hum` 7.6%.
- **Pairing vs. old aggregation (same cleaned data, test runs):** temperature, humidity,
  pressure and wind speed are essentially unchanged (median |ΔMAE| 0.00; largest non-wind change
  TSMS01 rain, 1.1 mm/day daily). Wind direction improves where the two sides used to be averaged
  over different minutes, e.g. daily MAE TSMS08 26.6° → 17.0°, TSMS07 17.5° → 13.0°.
- `data/error-analysis` and `plots/` are stale until re-run.

**Open:** a daily or hourly *regime* value can rest on very few minutes (e.g. an hour with 3
non-variable minutes). No minimum is imposed. Reporting N per regime (PF-12, PF-26) would make
that visible.

## 2026-09-28: Jan–Mar 2024 CHORDS rows re-mapped; TSMS04 temperatures excluded (SF-10, part 2)

**Files:** `scripts/reformatting/splice_chords_dec2024.py` (new `early_2024_maps`,
`remap_early_2024()`, SD/CHORDS boundary detection); `data/reformatted` (rewritten from the
untouched originals in `data/reformatted_backup_pre-chords-splice/`); `data/cleaned`
(regenerated); new `docs/methods.md`

**Before (what was wrong):** from the start of the CHORDS record (12–16 Jan 2024) to
2024-03-11 00:00 UTC, the raw rows at TSMS02, 03, 04, 05 and 08 are in a different column order
than the file header. This is **not** a copy-paste (user): the switch happens at the same instant
at all five stations, on both Raspberry Pi and Particle loggers, which suggests a firmware,
software, or CHORDS change. So in `data/reformatted` every variable was mislabeled for about
8 weeks at five stations, e.g. TSMS03 "rain" = a temperature (93,644 mm in Jan 2024). The period
can't be re-downloaded: CHORDS keeps only 2 years.

**Change:** those CHORDS rows are rebuilt from the raw file using a per-station mapping (header
label → true variable). The mapping was inferred from value signatures, same-chip dropouts, and
inter-sensor temperature offsets; see sensor-failures SF-10 for the full table and evidence. The
SD-card rows, which were correctly labeled, aren't touched. The boundary is found from the
first drop in the source row index, because the reformatter wrote the SD part and then the
CHORDS part. A first attempt at finding the boundary by value matching was wrong: an MCP9808 at
≈ 0 °C on a cold night looks like a wind speed of 0.

**TSMS04 temperatures excluded (SF-15):** its three temperature columns in this window can't be
assigned to HTU21D / BMP280 / MCP9808 with confidence, so `htu_temp`, `bmp2_temp` and `mcp9808`
are written as missing for 2024-01-12 09:10 → 2024-03-10 20:31. All other TSMS04 variables are
kept. The rationale and suggested methods text are in `docs/methods.md` §3.

**Verification:** each sensor's offset from the reference is consistent before and after the
switch (e.g. TSMS03 BMP/MCP/SHT +1.3/+1.1/+1.0 °C before vs. +1.2/+1.1/+1.0 after), and Konya
rain agrees with the reference (44.8–50.0 vs. 44.6 mm). Full table in SF-10. TSMS08's large
re-mapped rain totals fall almost entirely (7,943 of 7,959 mm) on dates Phase 4 already removes.

**Effect:** `data/cleaned` regenerated 2026-09-28 (all 12 files back at the top level of
`data/cleaned`). Monthly 3D-PAWS rain is now within a plausible range everywhere: the
10⁴–10⁶ mm months are gone. Remaining rain problems are real gauge issues (SF-11, SF-12, SF-16)
and the Ankara reference (SF-09). TSMS04 `htu_temp`/`bmp2_temp`/`mcp9808` are empty for the
excluded window, and its `htu_hum` and `tipping` are kept. `data/error-analysis` and `plots/` are stale.

**Open:** sensitivity run with and without the recovered windows (PF-31, methods.md §4). Ask
TSMS whether they saw and handled this (method-differences question 6).

## 2026-09-28: Dec 2024 → Nov 2025 replaced with the correctly labeled CHORDS batch (SF-10, part 1)

**Files:** new `scripts/reformatting/splice_chords_dec2024.py`; `data/reformatted/station_TSMS0*/TSMS0*_Nov22-Nov25.csv`
(rewritten; originals in `data/reformatted_backup_pre-chords-splice/`); `scripts/outliers/outlier-removal.py`
(`sensor_failures` emptied); `main.py` (workflow step 1b)

**Before (what was wrong):** the Jan 2024 → Nov 2025 CHORDS csv for each station was assembled by
pasting a later CHORDS batch under the header of an earlier one (the user's explanation for the Dec 2024
portion; the separate Jan–Mar 2024 misalignment is *not* a copy-paste, see sensor-failures SF-10). The pasted
batch used a different column order, and `final_paws_reformatter.py` reads columns by header name.
So from 2024-12-01, every value at TSMS02, 03, 04, 05 and 08 was stored under the wrong variable name
in `data/reformatted`, and from there in `data/cleaned` and every statistic. Examples:
- TSMS03 "rain" was HTU21D temperature, giving ≈ 0.5–1 million mm per month (SF-05).
- TSMS03 "wind_speed" was humidity, and TSMS04's was visible light (SF-08).
- TSMS03 "humidity" was UV (SF-01), and TSMS04 "humidity" was rain (SF-02). Earlier today both
  were cataloged as sensor failures and removed.

**Change:** for each station, rows from 2024-11-30 23:59 on (the batch's first timestamp after the
1-minute shift) are replaced with the Dec 2024 → Nov 2025 batch in
`data/raw/3D-PAWS/Dec-2024_Nov-2025/`, mapped **by column name**. It follows the reformatter's
conventions:
- timestamps floored to the minute, then shifted back 1 minute
- CHORDS's "HTU21D" columns go to `sth_*` on upgraded stations (TSMS02, 03, 05, 06, 08) and to
  `htu_*` on the others, chosen from what each station used in Oct–Nov 2024
- SLP is approximated with `func.calc_slp` at Adana, which has no SLP column

The SF-01/SF-02 removals were deleted from `sensor_failures`. After the splice they would have
removed real humidity.

**Verification:**
- At TSMS00, 01, 06 and 07, which were never scrambled, the new Dec 2024+ data is **100% identical**
  to the old data in every column. That confirms the name mapping and the 1-minute shift.
- At the formerly scrambled stations, Dec 2024+ medians are now physically consistent. Konya
  temperatures agree across TSMS03/04/05 (≈ 15 °C), humidity is ≈ 50 %RH (reference median 49), and
  pressure agrees at ≈ 899 hPa.
- Konya monthly rain now tracks the reference. Dec 2024–Nov 2025: reference 259 mm vs. TSMS03 256 mm.

**Effect:** row counts per station changed slightly: 30–70 fewer rows in the replaced period,
because the old file had duplicate timestamps. One TSMS05 row with no timestamp was dropped.
`data/cleaned` and all downstream outputs are now stale and need regenerating.

**Open:**
1. **Jan → mid-Mar 2024 is still mislabeled** at TSMS02, 03, 04, 05, 08 (PF-28). Only TSMS08's
   early-2024 rows follow the Dec-batch column order. Reading them that way gives MCP9808 within
   0.00 °C of the reference (r = 0.998). TSMS03/05 have the compass field in the same position but
   a different order of the other columns, and TSMS02/04 use yet another layout.
2. With correct labels, new real-data issues show up: SF-11 to SF-14 in the failure catalog.
3. `final_paws_reformatter.py` still reads its CHORDS input from a path outside the repo that no
   longer exists. Folding the splice into the reformatter would make the pipeline reproducible.

## 2026-09-28: Wind split into variable / non-variable regimes by the reference; calm filter replaced

**Files:** `scripts/error/error-analysis.py` (new wind section before aggregation; `_mask_calm`
removed; wind variables for each regime), `scripts/plotter/plot-gen-final.py` (complete-record
wind-rose block rewritten; wind constants moved to the top of the file)

**Before (analysis):** `_mask_calm` (2026-09-25) set speed **and** direction to NaN whenever
*either* instrument read 0 m/s, separately for each instrument. That had two problems:
1. **It filtered on the instrument under test.** A minute where the reference shows wind but
   the 3D-PAWS cup reads 0 (stalled cup, starting threshold) is a genuine 3D-PAWS error. It was
   thrown away, so wind-speed statistics couldn't show the failure.
2. **It mixed all wind conditions together.** Direction agreement in light, variable winds is
   inherently poor (vanes wander, and direction barely exists at near-zero speed). Averaging it
   with steady winds hid how the vane performs when direction is well defined.

**Before (plots):** the wind roses dropped 3D-PAWS minutes with speed 0. The "non-variable"
option (commented out) applied `>= 3.0 m/s` to **each instrument's own speed**: 3D-PAWS
`wind_speed` at 2 m and TSMS `avg_wind_speed` at 10 m. So the two roses of a "non-variable"
comparison were built from different hours. Also:
- The file named `*_variable_winds_*` actually contained **all** winds.
- The TSMS rose for a site was saved to the same file for each of that site's three stations,
  so it was overwritten twice, each time with a different station's date range.

**Change:**
- **Regimes come from the reference only.** Each minute is classified by the reference's
  unadjusted 10-m `avg_wind_speed`. It's *non-variable* at ≥ 3.0 m/s (~6 kt; the cutoff the
  wind-rose plots already used) and *variable* below that. 3D-PAWS minutes with no reference
  minute get no regime. They still count toward the all-winds statistics.
- **Directions recorded at zero speed are removed, speeds are not.** For each instrument,
  direction is set to NaN when that instrument's own speed is 0. 3D-PAWS reports the vane's last
  position, and TSMS reports 0°, so neither is a direction. Zero speeds are kept as real
  measurements.
- **The analysis reports all winds plus each regime.** New variables `wind_speed_variable`,
  `wind_speed_nonvariable`, `wind_dir_variable`, `wind_dir_nonvariable` appear alongside
  `wind_speed` and `wind_dir`. Regime columns are built at minute level, then aggregated
  (speed-weighted vector mean for direction, as before). So an hourly "non-variable" value
  averages only the non-variable minutes in that hour.
- **Plots:** each hour (10-min vector average over (:50, :00]) is classified by the reference's
  10-min mean 10-m speed. For each regime (all / variable / non-variable), the 3D-PAWS and TSMS
  roses use **the same hours**, i.e. hours both report, and share one radial scale. Hours with a
  vector-mean speed of 0 are calm. They have no direction, so they're reported as "calm %" in the
  legend rather than drawn. The old code's `atan2(0, 0)` would have put them at 180° (south). Output:
  `plots/wind-roses/<station>/<station>_{all,variable,nonvariable}_winds_[10-MIN-AVG].png` and
  `TSMS-Reference_<site>_{all,variable,nonvariable}_winds_[10-MIN-AVG].png` in the same folder
  (one TSMS rose per station, for that station's hours).

**Effect (hourly, test run on current cleaned data):**
- Share of reference minutes that are non-variable: Ankara 17.8%, Adana 6.0%, Konya 3.3%.
- **Wind speed:** the variable-regime numbers are close to the all-winds numbers. In
  non-variable winds, 3D-PAWS reads clearly low at several stations (median bias −1.5 m/s
  TSMS01, −2.2 TSMS08, −1.0 TSMS05, −0.4 at TSMS06/07).
- **Wind direction:** Adana improves in non-variable winds (MAE 9.9–10.5° vs. 11.5–16.8°
  variable). **Ankara and Konya get worse**, with a larger, consistent signed offset: TSMS01
  median bias +12.5° (variable) → +30.3° (non-variable), TSMS04 +73° → +110°, TSMS05 +62° → +102°.
  A bias that grows when direction is well defined looks systematic (orientation or siting), not
  random scatter. See method-differences WD2.
- The all-winds `wind_dir` numbers are unchanged from before. With speed-weighted averaging, a
  zero-speed minute already carried no weight.

**Plot check (TSMS01, non-variable hours, test render):** the reference rose points NNE–NE, and
the 3D-PAWS rose for the same 3,610 hours points E–S, with every hour in the 0–2 m/s bin. Hour
by hour, the median offset (3D-PAWS − reference) is +66° (middle 50%: +8° to +116°) from the
rose's 10-min vector averages, +43° from individual minutes, and +30° from the analysis's
speed-weighted hourly means. The methods weight minutes differently, so the size of the offset
depends on the method, but it's large and positive in all of them. In the same hours the 3D-PAWS
median speed is 0.68 m/s vs. 2.23 m/s for the reference adjusted to 2 m. A weaker wind *and* a
rotated direction at the 3D-PAWS mast is the signature of local sheltering or deflection by an
obstruction. That's a hypothesis to check against the site layout.

**Plot layout:** legends are placed beside the rose instead of over it (they covered the S-W
label), and the figures are saved with `bbox_inches="tight"`.

**Also fixed:** the wind-rose block called
`warnings.simplefilter(..., pd.errors.SettingWithCopyWarning)`. That warning class was removed
in pandas 3 (the venv has 3.0.6), so the plot script crashed at that line before drawing
anything. The line was removed. Two commented-out blocks still contain it.

**Also fixed:** `error-analysis.py` read `data/cleaned` with `rglob`, i.e. recursively, so
backup folders inside `data/cleaned` were read as extra copies of every station. With three
backups present, every station/variable row appeared 3×, and the Excel export failed. It now
reads only top-level `*_final.csv` files. The same fix was made in
`scripts/workshop-2025/rainfall_2-2024.py`.

**Open:** see potential-fixes PF-10 (done), PF-23 (monthly wind roses still use per-instrument
filtering), PF-24 (the plots' hourly speed is the vector-mean speed, which reads low in variable
winds), PF-25 (10-m vs. 2-m reference speed for the threshold).

## 2026-09-28: Rolling z-score given a standard-deviation floor (Phase 6)

**Files:** `scripts/outliers/outlier-removal.py` (`MAD_FLOOR` renamed `RESOLUTION_FLOOR` and
now used for both tests; rolling std clipped in both Phase 6 loops)

**How the z-score works:** for each reading `x`, Phase 6 takes the same centred 20-row window
and computes its mean and standard deviation (std). The z-score is `(x − mean) / std`, the
number of standard deviations `x` sits from the window average. It's flagged when `|z| > 3`.

**Before (what was wrong):** the same quantization problem as the Hampel filter, in a milder
form. A window of exactly identical values has std = 0; the old code replaced 0 with NaN, so those
windows were skipped. But a window that's *almost* flat, e.g. 19 readings of 15.0 °C and one
of 15.1 °C, has a tiny std (≈ 0.022 °C). That single 0.1 °C step gets `z ≈ 4.3` and is
flagged. So the z-score was removing one-resolution-step readings in near-steady conditions.
Once the MAD floor was in place, the z-score became the main remaining source of removals in the
reference: 0.06–0.16% of readings, vs. Hampel's 0.00–0.04%. On the Konya reference, 82–99% of the
readings it flagged were within about one resolution step of the window mean.

**Change:** the rolling std is clipped from below at the same per-column resolution as the MAD
(`RESOLUTION_FLOOR`) instead of turning 0 into NaN. A reading must now be more than 3
resolution steps from the window mean to be flagged in a flat window (0.3 °C, 0.3 hPa,
3 %RH for the reference). When the std is already above the floor, nothing changes. Exactly
flat windows no longer drop out of the test. A reading equal to the flat value simply scores
z = 0.

**Status:** `data/cleaned` regenerated 2026-09-28 with this fix, together with the MAD floor and
the sensor-failure removals. Error-analysis outputs have **not** been re-run yet.

**Effect (full run; share of each file's readings removed by the z-score, before → after):**

| Group | Before | After |
|---|---|---|
| TSMS reference temp / RH / pressure (all 3 sites) | 0.04–0.19% | 0.00–0.02% |
| 3D-PAWS pressure (`bmp2_pres`, `bmp2_slp`) | 0.003–0.19% | 0.000–0.002% |
| 3D-PAWS `mcp9808` | 0.01–0.45% | 0.00–0.15% |
| 3D-PAWS `bmp2_temp`, `sth_temp` | 0.01–0.04% | 0.00–0.03% |
| 3D-PAWS `htu_temp` | 0.00–0.33% | 0.00–0.31% |
| 3D-PAWS `htu_hum`, `sth_hum` | 0.003–0.18% | 0.003–0.18% (unchanged) |

The HTU columns barely change. What the z-score removes there is large deviations
(bit-switching spikes), not quantization steps. The Adana pressure series, which had the most
one-step flags (0.14–0.19%), drop to ≈ 0.

## 2026-09-28: Hampel filter given a MAD floor (Phase 6)

**Files:** `scripts/outliers/outlier-removal.py` (new `MAD_FLOOR` table, later renamed
`RESOLUTION_FLOOR`; MAD clipped in both Phase 6 loops)

**Status:** `data/cleaned` regenerated 2026-09-28 with this fix (in the same run as the z-score
std floor below). Error-analysis outputs not yet re-run.

**Full-run result (share of each file's readings removed by Hampel, before → after):**

| Group | Before | After |
|---|---|---|
| TSMS reference temp / RH / pressure (all 3 sites) | 12.0–15.6% | 0.00–0.25% |
| 3D-PAWS `bmp2_pres`, `bmp2_slp` | 1.3–16.4% | 0.00–0.04% |
| 3D-PAWS `mcp9808` | 7.8–14.7% | 0.19–0.62% |
| 3D-PAWS `bmp2_temp`, `sth_temp` | 2.9–11.8% | 0.06–0.33% |
| 3D-PAWS `htu_temp` | 0.8–12.0% | 0.06–1.84% |
| 3D-PAWS `htu_hum`, `sth_hum` | 0.3–4.8% | 0.17–2.07% |

(These are from a test run with only the MAD floor; z-score removals were unchanged there at
0.00–0.45%, before the std floor was added.) The HTU columns keep the highest Hampel rates
(up to ~2% at TSMS00/01), which is consistent with residual bit-switching spikes (SF-03) rather
than quantization.

**How the filter works:** for every reading `x`, Phase 6 looks at a centred window of 20 rows
around it and computes:
- `med`, the median of the window
- `MAD`, the *median absolute deviation*: the median of `|xᵢ − med|` over the window, i.e. the
  typical distance of a reading from the median
- the threshold, `3 × 1.4826 × MAD`. For normally distributed data, 1.4826 × MAD estimates the
  standard deviation, so this is a robust "3 sigma" rule.

`x` is flagged when `|x − med| > threshold`. Median and MAD are used instead of mean and
standard deviation because a single spike barely moves them.

**Before (what was wrong):** data is recorded in discrete steps (0.1 °C, 0.1 hPa, 1 %RH for
the reference). When conditions are steady, most readings in a 20-minute window are identical,
so more than half the deviations `|xᵢ − med|` are exactly 0 and **MAD = 0**. The threshold
becomes 0, and *any* reading that differs from the median at all, even by one resolution step,
is flagged as an outlier.

Example: a window of reference temperatures `[15.0 × 14, 15.1 × 6]` has median 15.0 and
MAD 0. Every one of the six 15.1 °C readings is flagged, though a 0.1 °C change is the smallest
change the instrument can report.

Measured on raw minute data (replaying Phase 6):

| Series | Readings where MAD = 0 | Hampel removals |
|---|---|---|
| Konya reference temperature | 72.9% | 15.56% |
| Konya reference humidity | 79.7% | 14.73% |
| Konya reference pressure | 93.9% | 13.39% |
| TSMS00 `mcp9808` | 38.1% | 12.33% |
| TSMS06 `mcp9808` | 55.1% | 13.18% |
| TSMS06 `bmp2_pres` | 87.3% | 19.12% |

The readings removed had a median deviation of 0.06 °C from the window median (TSMS00
`mcp9808`), i.e. one resolution step. They were real data, not outliers. This removed 12–19%
of every major series, reference included, concentrated in the calmest, most stable periods.
That biases the remaining data toward changing conditions.

**Change:** MAD is clipped from below at the coarsest resolution each column is recorded at
(`MAD_FLOOR`, now `RESOLUTION_FLOOR`): 0.1 for all 3D-PAWS temperature/humidity/pressure columns and for reference
temperature/pressure, and 1.0 %RH for reference humidity. The threshold therefore never drops
below `3 × 1.4826 × resolution` ≈ 4.4 resolution steps (0.44 °C, 0.44 hPa, 4.4 %RH for the
reference). When MAD is already above the floor, the filter behaves exactly as before.

**Effect (replay on raw data, before → after):**

| Series | Hampel removals |
|---|---|
| Konya reference temperature | 15.56% → 0.04% |
| Konya reference humidity | 14.73% → 0.01% |
| Konya reference pressure | 13.39% → 0.00% |
| TSMS00 `mcp9808` | 12.33% → 0.35% |
| TSMS06 `mcp9808` | 13.18% → 0.21% |
| TSMS06 `bmp2_pres` | 19.12% → 0.01% |

The readings still flagged at TSMS00 `mcp9808` deviate 0.50–1.15 °C from the window median
(10th–90th percentile).

**Open:**
1. ~~The rolling z-score has a milder version of the same problem.~~ Fixed in the next entry
   (std floor).
2. **Some remaining flags may be real.** Several readings still flagged in daytime (e.g.
   `15.0, 15.25, 15.31, 15.0, 14.62`) look like real turbulent temperature fluctuations rather
   than spikes. Decision (2026-09-28): keep the floor at the resolution for now. Setting it at the
   sensor's noise level is logged in [potential-fixes.md](potential-fixes.md) (PF-01).
3. **The window counts rows, not minutes.** Across data gaps, a 20-row window can cover hours
   (PF-02).

## 2026-09-28: Documented sensor-failure periods removed in full

**Files:** `scripts/outliers/outlier-removal.py` (new `sensor_failures` config, `failure_mask()`,
Phase 4 removal block, humidity pre-pass), `docs/sensor-failures.md` (new catalog)

**Before:** no way to remove a known failure period other than hard-coded one-off blocks (like
the TSMS04 and TSMS08 rainfall removals). Two humidity failures passed every filter:
- TSMS03 `sth_hum` stuck near 1–4 %RH from 2024-12-01 (catalog SF-01)
- TSMS04 `htu_hum` stuck at exactly 0.0 %RH from 2024-11-30 23:59 (SF-02)

Neither jumps, so the Phase 5 step test didn't flag them, and the range checks accept 0–4 %RH.
They also leaked into the Phase 5 **site cross-check**: the failed stations were used as
"neighbours" for the other Konya stations. When both TSMS03 and TSMS04 were failing, a
suspect TSMS05 reading had no plausible neighbour, so it was measured against values near 0 and
removed even when correct.

**Change:** a single `sensor_failures` table lists (column, start, end, catalog id) per station,
with `end = None` meaning through the end of the record. It's applied in two places:
1. **Phase 4:** readings in the period are set to NaN, logged with
   `outlier_type = sensor_failure`, and a count is printed.
2. **Humidity pre-pass:** failed periods are blanked before a station's humidity is used to
   cross-check its neighbours.

Periods were set from the minute data. Each start is the first bad minute after the last
normal reading. Neither sensor recovers, so both run to the end of the record. Full evidence is
in `docs/sensor-failures.md`.

**Effect:** `data/cleaned` regenerated 2026-09-28. Removed 57,826 TSMS03 `sth_hum` readings
(SF-01) and 481,243 TSMS04 `htu_hum` readings (SF-02). Neither column has any data from the
onset onward. Last kept readings: TSMS03 2024-11-30 23:58, TSMS04 2024-11-30 23:57.

**Open:** the TSMS04 precursor on 29–30 Nov 2024 (bit-switching-like values) isn't removed.
`-1000.0` values in the TSMS04 raw file are a second null sentinel that Phase 1 doesn't
recognise.

## 2026-09-28: HTU cleaning no longer uses the TSMS reference (Phase 5)

**Files:** `scripts/outliers/outlier-removal.py` (new `step_suspect()`, humidity pre-pass,
Phase 5 rewritten, new thresholds and outlier reasons)

**Status:** `data/cleaned` regenerated with this change on 2026-09-28 (the user kept a backup of
the previous version). Error-analysis outputs in `data/error-analysis` predate it and need a
re-run. Diagnostic plot of the Konya failure:
`plots/diagnostics/konya-humidity-dec2024-failure.png`.

**Before:** Phase 5 merged each 3D-PAWS station with the TSMS reference and deleted every
`htu_temp` reading more than 3.5 °C from TSMS, and every `htu_hum` reading more than 3.5 %RH
from TSMS. That is circular: the instrument under test was cleaned with the instrument it is
being compared against, so every disagreement larger than 3.5 was removed before the
comparison was made. Consequences:
- **Humidity statistics were artificially good.** Every station's `htu_hum` came out with
  MAE ≈ 1.6–1.9 %RH and 0% of minutes off by more than 10 %RH, no matter how the sensor
  actually behaved.
- **Large amounts of real data were deleted.** Only 19–60% of `htu_hum` readings survived
  (TSMS04: 272,888 of ~1.46 million; TSMS07: 429,504 of ~1.5 million). Deletions were
  concentrated in winter, when the HTU reads high (see Effect), so the surviving data was
  also seasonally biased.
- **A genuine sensor behaviour was hidden.** The HTU21D reads high in humid, cold months.
  That shows up only in the removed data.
- **`sth_hum` was never filtered at all,** even though it is also a humidity sensor.
- Smaller issues: the header comment said ">10 °C or >10%" while the thresholds were 3.5, and
  humidity removals were logged as `htu_trend_switch`, which described a different mechanism.

**Change:** a reading is *suspect* if it jumps by more than 3.5 °C (`htu_temp`) or 3.5 %RH
(`htu_hum`, `sth_hum`) from the reading exactly one minute before or after. Both ends of a
jump are flagged, and gaps longer than a minute don't count as jumps. Each suspect reading is
then checked against independent 3D-PAWS sensors only:
- **Humidity:** each station runs only one humidity sensor at a time (HTU before the Jan 2024
  upgrade, SHT after), so the check uses the *other two 3D-PAWS stations at the same site*. A
  suspect reading is removed if it is more than **5 %RH** from the closest neighbouring
  station. 5 %RH is about twice the normal station-to-station spread (median 1.8–3.3 %RH).
  Neighbour humidity comes from a pre-pass that applies null/range checks and drops the
  neighbours' own suspect readings, so a noisy neighbour can't vouch for a noisy reading.
- **`htu_temp`:** checked against the median of the same station's `bmp2_temp`, `mcp9808`,
  and `sth_temp`. Removed if more than **2.0 °C** away. These sensors normally agree within
  0.1–0.9 °C (90th percentile), while flagged readings are off by up to ~36 °C.
- **Nothing to check against:** suspect readings are removed anyway and logged separately
  (`hum_step_unverified`, `temp_step_unverified`) so they can be counted or restored.

New outlier reasons: `hum_step_site_check`, `hum_step_unverified`, `temp_step_station_check`,
`temp_step_unverified`. `htu_trend_switch` is no longer used.

**Effect (test run; error vs. TSMS reference, measured only to evaluate the cleaning):**

| Station | Column | Readings kept (old → new) | MAE old → new | % minutes off > 10 (old → new) |
|---|---|---|---|---|
| TSMS00 | htu_hum | 912,951 → 1,228,019 | 1.71 → 3.66 | 0.00 → 3.00 |
| TSMS03 | htu_hum | 213,705 → 650,834 | 1.71 → 6.55 | 0.00 → 22.11 |
| TSMS04 | htu_hum | 272,888 → 1,425,282 | 1.68 → 22.39 | 0.00 → 54.77 |
| TSMS07 | htu_hum | 429,504 → 1,436,703 | 1.92 → 5.35 | 0.00 → 4.30 |
| TSMS00 | htu_temp | 1,313,419 → 1,314,541 | 0.59 → 0.61 | 0.00 → 0.07 |
| TSMS04 | htu_temp | 1,407,230 → 1,455,559 | 0.72 → 0.96 | 0.00 → 0.81 |

- `htu_temp`: bit-switching is still caught (168,707 readings removed at TSMS00 and 118,193
  at TSMS01, nearly all confirmed by the station's other sensors). The error barely changes,
  which suggests the old filter wasn't hiding much for temperature.
- `htu_hum`: errors rise because real sensor error is no longer deleted. At Konya the HTU
  reads **+8 to +13 %RH in winter and ~0 in summer**, every year. That's a genuine finding and
  should stay in the data.
- `sth_hum`: now filtered, but little changes (0.1–1% removed).

**Open:**
1. **Persistent humidity failures aren't caught.** TSMS04's HTU21D drops to 0 %RH on
   30 Nov 2024 and stays there through Nov 2025 (median 0 vs. reference 49). TSMS03's SHT31D
   sits near 2 %RH with brief daily spikes from 1 Dec 2024 until its record ends on
   28 Apr 2025 (median 2 vs. reference 76). TSMS05 is unaffected. In both, 100% of minutes are
   off by more than 10 %RH. A step test
   can't detect a steady failure. The site check can't be applied to all readings either: with
   two of three Konya stations failing together, a majority-based check would flag the one
   good station. Options: documented manual removal (Phase 4 style) or a failure-period list.
2. **Middle readings of bad runs are missed.** Bit-switching runs longer than one minute
   (good, bad, bad, bad, good) only flag the edges of the run.
3. **Neighbour humidity skips Phase 4 manual removals** (e.g. TSMS06–08 `htu_hum` removals),
   so a manually removed neighbour value could still vouch for a reading.
4. **`sth_hum` has large biases of its own:** TSMS02 −25 %RH (55% of minutes off by more than
   10) and TSMS06 −8 %RH. These need investigation.
5. Found while reading the code, not fixed: Phase 2 drops the first row of every file. For
   that row, `time_diff` is `NaT`, and `NaT > 0` evaluates as False.

## 2026-09-28: Difference Analysis section added; Bias moved out of Accuracy

**Files:** `scripts/error/error-analysis.py`

**Before:** differences were summarized only by a single mean "Bias" column in the Accuracy
section. There was no median, spread, or IQR of the differences, so a few large outliers could
drag the mean with nothing to show it.

**Change:** new *Difference Analysis* section, placed before Accuracy, reporting Mean Bias,
Median Bias, Bias Standard Deviation (ddof = 1), and Bias Interquartile Range (Q3 − Q1) of
3D-PAWS − TSMS. Wind direction uses the signed circular difference wrapped to [−180°, 180°).
Precipitation drops time steps where both gauges read 0, as the other sections do. The old
Accuracy "Bias" column was removed because it was identical to Mean Bias. Accuracy now holds
MAE and RMSE only.

**Effect:** four new columns and workbook sheets. Mean vs. median gaps expose outlier-driven
biases. For example, at TSMS06 (hourly), `sth_hum` has Mean Bias −7.7 vs. Median 0.4, and
`bmp2_temp` has Mean −0.5 vs. Median +0.6 with SD 4.9 but IQR 0.6.

**Open:** SD and IQR of wrapped direction differences are only meaningful when most
differences are well inside ±180°. A circular SD would be more robust.

## 2026-09-28: Bias sign flipped to 3D-PAWS − TSMS

**Files:** `scripts/error/error-analysis.py` (Accuracy section, plus the commented `paws_corrected` line)

**Before:** bias was computed as TSMS − 3D-PAWS, so a positive bias meant 3D-PAWS read *low*.
That is the opposite of the usual "instrument under test minus reference" convention.

**Change:** all signed differences are now 3D-PAWS − TSMS. A positive bias means 3D-PAWS reads high.

**Effect:** every Bias value changes sign (e.g. TSMS06 wind_dir +2.5° → −2.5°). MAE, RMSE,
r, and Reliability are unchanged. Output files generated before this date use the old sign.

## 2026-09-25: Output filenames dropped `_[NO-WIND-CORRECTION]`

**Files:** `scripts/error/error-analysis.py`

**Before:** outputs were named `*-statistical-analysis_[NO-WIND-CORRECTION]`, referring to a
wind-direction bias / magnetic-declination correction that the PI has since ruled out.

**Change:** now `daily-`, `hourly-`, and `point-for-point-statistical-analysis` (.csv and .xlsx).
Old files were moved by hand to `data/error-analysis/original-before-fixes/`.

## 2026-09-25: Dead wind-bias code removed

**Files:** `scripts/error/error-analysis.py`

**Before:** a commented-out `_vectorial_wind_average` function and a commented-out block
estimating a per-site wind direction/speed installation bias. The PI ruled out the
installation-bias hypothesis. The block also called the function under the wrong name
(`vectorial_wind_average` instead of `_vectorial_wind_average`), so it would not have run.

**Change:** both removed. `magnetic_declinations` and the commented `paws_corrected` lines were
kept on purpose in case declination correction comes up again.

## 2026-09-25: `TIMESCALE` casing broke output filenames

**Files:** `scripts/error/error-analysis.py`

**Before:** filename selection compared `TIMESCALE == 'H'`. After `TIMESCALE` was changed to
`'h'` (pandas' newer alias), hourly results would have been saved as
`point-for-point-statistical-analysis`, silently overwriting or mislabeling files.

**Change:** comparison is now case-insensitive (`str(TIMESCALE).upper()`).

## 2026-09-25: Calm-wind filtering moved before aggregation and made consistent

**Files:** `scripts/error/error-analysis.py` (`_mask_calm`; removed `> 0` filters in three sections)

**Before:**
1. Zero-speed records were filtered differently in different sections. Accuracy and
   Precision filtered calm only for *wind direction*, while Reliability filtered it for both
   speed and direction. Wind-speed Bias/MAE/RMSE/SD/r were therefore computed on a different
   set of records than wind-speed Reliability.
2. The filter (`speed > 0`) ran *after* hourly/daily aggregation, so it removed only periods
   whose **average** speed was 0, i.e. fully calm hours or days. Individual calm minutes stayed
   in the averages, dragging mean speeds down and adding meaningless directions to direction
   averages.

**Change:** `_mask_calm` sets speed and direction to NaN for every reading with speed ≤ 0,
separately for TSMS and 3D-PAWS, **before** aggregation. The three post-aggregation `> 0`
filters were removed, so all sections see the same wind records.

**Effect:** wind-speed statistics now exclude calm minutes everywhere (mean speeds rise for both
instruments). Combined with the vector-averaging fix below, daily results changed substantially.

**Open (found in review, 2026-09-28): this fix is itself flawed.** It drops a minute when
*either* instrument reads 0. A minute where TSMS reads 1.5 m/s and a stalled 3D-PAWS cup reads 0
is a genuine 3D-PAWS failure, and it gets discarded. That hides the anemometer's starting-threshold
behaviour. The planned replacement defines calm from the reference only: keep zeros for speed,
and require reference speed above ~1 m/s for direction comparisons.

## 2026-09-25: Wind direction averaged as a vector, not arithmetically

**Files:** `scripts/error/error-analysis.py` (`_agg_timescale`, `wind_pairs`)

**Before:** `_agg_timescale` averaged `avg_wind_dir` and `wind_dir` with a plain arithmetic
`'mean'`. Direction is circular, so the mean of 350° and 10° came out as 180° (due south)
instead of 0° (north). Any hour or day with winds on both sides of north got a direction pointing
the opposite way. This corrupted every hourly and daily wind-direction statistic: bias, MAE,
RMSE, SD, r, and reliability. Point-for-point results were not affected.

**Change:** each direction is split into speed-weighted components, `u = speed·sin(θ)` and
`v = speed·cos(θ)`. The components are averaged over the hour/day, and the direction is
recovered as `atan2(ū, v̄) mod 360`, rounded to avoid 359.9999° showing up for north. Speed
is still a plain scalar mean.

**Effect (daily, before → after):**

| Station | wind_dir MAE | wind_dir Reliability |
|---|---|---|
| TSMS00 | 54.3° → 55.6° | 0.0 → 36.8 |
| TSMS06 | 87.7° → 13.3° | 0.0 → 48.6 |
| TSMS07 | 89.7° → 18.0° | 0.0 → 47.2 |
| TSMS08 | 99.9° → 29.1° | 0.0 → 33.3 |

**Note:** the hourly files in `original-before-fixes/` were produced *after* this fix (at 12:49,
between the fix and an accidental editor revert at 12:50). They are not a true "before".

**Open:** speed-weighted vs. unit-vector averaging is a choice. Speed-weighting lets strong-wind
minutes dominate the average direction.

## 2026-09-23: Output rows sorted unstably; Excel workbook added

**Files:** `scripts/error/error-analysis.py`

**Before:** rows were sorted by station number only, using a non-stable sort, so the order of
variables within a station came out arbitrary (e.g. TSMS01's rows were reversed).

**Change:** rows are sorted by station number, then by variable in `variable_mapper` order.
Added an `.xlsx` workbook with one sheet per statistic (variables × stations) plus an
"All Stations" sheet. The CSV is still written. Added `openpyxl` to `requirements.txt`.
