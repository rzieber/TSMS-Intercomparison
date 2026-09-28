# Method differences: our analysis vs. TSMS draft report

Running log of every difference between `scripts/error/error-analysis.py` and
*TSMS_3D-PAWS_DATA_ANALYSIS_REPORT (2).pdf*. Neither side is assumed to be correct; the aim is to
understand each divergence and collect feedback for TSMS.

**Status key:** `Same` = methods agree · `Differs` = deliberate or known difference ·
`Open` = unresolved question/discrepancy · `Ours` = issue on our side to fix · `Feedback` = point to raise with TSMS

Report section/page references are to the draft PDF. Last updated 2026-09-28 (added G11–G16; WS2, WD5, WD2 updated for wind regimes; questions 6–7).

---

## General

| # | Topic | Report | Ours | Status |
|---|---|---|---|---|
| G1 | Difference sign | Difference = 3D-PAWS − TSMS (§3.2, p.3) | 3D-PAWS − TSMS (changed 2026-09-28; previously TSMS − 3D-PAWS) | Same |
| G2 | Temporal resolution | Minute-level paired observations for most stats (e.g. N ≈ 559k for TSMS00 wind dir, Table 8); daily/monthly for temporal and precip analyses (§3.6, §3.10) | Configurable `TIMESCALE`: hourly, daily, or point-for-point. All stats computed at that one resolution | Differs |
| G3 | Daily completeness criterion | Day kept only if ≥ 80% of 1,440 minute observations present (§3.6), used for daily-based analyses | **Since 2026-09-28:** same 80% rule, applied per instrument and per variable in cleaning (Phase 7), so it affects every timescale, not only daily analyses. The analysis also requires ≥ 80% of an hour's/day's minutes to be *paired* | Differs (stricter) |
| G4 | Input data / QC | Multi-stage QC: range, climatology, step, persistence, rolling MAD/z-score (61-pt window), spatial consistency vs. site median (§4, Table 1) | `data/cleaned/*final*.csv` from our own cleaning pipeline; different from the report's QC'd data | Differs / Open |
| G5 | Timestamps | UTC, no local-time conversion (§3.2, §3.6) | Not verified which timezone `data/cleaned` uses for TSMS vs. 3D-PAWS files | Open |
| G6 | Sensors compared | One sensor per variable: MCP9808 (temp), HTU21D (RH), BMP280 (pressure) (Table 1) | All sensors: `bmp2_temp`, `htu_temp`, `sth_temp`, `mcp9808`; `htu_hum`, `sth_hum`; `bmp2_pres` | Differs |
| G7 | Statistics reported | Mean/median bias, SD & IQR of differences, MAE, RMSE, Pearson r, R², regression, Taylor diagrams, descriptive stats of each series (mean, median, SD, IQR, min, max) (§3.1–3.5) | Mean/median bias, SD & IQR of differences, MAE, RMSE, SD of each series, Pearson r, Reliability/Inaccuracy. No R², regression, Taylor, or per-series median/IQR/min/max | Differs |
| G8 | Reliability / Inaccuracy; comparison with WMO uncertainty requirements | **No WMO comparison, by design.** It repeatedly states that its results "should not be interpreted ... as an assessment of compliance with WMO measurement performance requirements or measurement uncertainty" (§8 pressure; Bland–Altman; conclusions) and positions 3D-PAWS as "complementary" and in support of WMO "Early Warnings for All". The only tolerance-style numbers are % of pressure readings within 0.5 / 1.0 hPa (Fig. 8.7), not tied to WMO | `(1 − MAE / SD_TSMS) × 100`, our own metric, not linked to WMO values. `wmo_thresholds` (0.2 K, 3 %RH, 0.15 hPa, 5°, 0.5 m/s, 5%) are the WMO-No. 8 Annex 1.A *achievable* uncertainty column (confirmed 2026-09-28; *required* is stricter). **Since 2026-09-28 (PF-15):** "Reliability" removed; replaced by the WMO-No. 8 Annex 1.G Measurement Quality Classification (Class A–D) plus OSCAR application-area levels (`wmo-classification.xlsx`), reported as conservative, with Konya/Ankara wind flagged as siting-limited. This goes beyond the report | Differs |
| G9 | SHT sensor upgrade dates | Not mentioned | `sht_upgrade` dict defined but **unused**, so pre-/post-upgrade SHT data is mixed | Ours / Open |
| G10 | WMO thresholds | Not used | `wmo_thresholds` defined but only printed, not used in any statistic | Ours |
| G11 | HTU / humidity cleaning | Spatial consistency: flag 3D-PAWS readings that deviate from the site-level median of the 3D-PAWS stations by more than a variable-specific threshold, when ≥ 3 valid observations exist (§4.5). Threshold not stated | **Until 2026-09-28:** removed HTU readings > 3.5 from the TSMS reference (circular). **Now:** only readings that jump > 3.5 between consecutive minutes are checked. Humidity is removed if > 5 %RH from the closest other 3D-PAWS station at the site; `htu_temp` if > 2 °C from the median of the station's other temperature sensors. See [logic-changelog](logic-changelog.md) | Differs |
| G12 | Hampel / rolling outlier test | 61-point window; MAD score > 3.5 or \|z\| > 3.0 (§4.4). **Same zero-MAD flaw:** the modified z-score `0.6745·(x − med)/MAD` is undefined or infinite when MAD = 0, which is the normal case for quantized minute data in steady conditions. Measured on the Konya reference with the report's 61-row window, MAD = 0 for 73.6% of temperature, 78.1% of humidity, and 91.8% of pressure readings, and for 100% of precipitation readings. The wider window does **not** help (the 20-row figures are 72.9 / 79.7 / 93.9%). If a zero MAD produces an infinite score, the readings that sit in a MAD = 0 window but differ from the median would all be flagged: 12.4% of temperature, 17.4% of humidity, 16.1% of pressure, and every rain tip (see P3–P4). If instead flat windows are skipped, those readings are never tested. The report doesn't say whether a floor was used | 20-row window; Hampel (3 × 1.4826 × MAD) or \|z\| > 3; not applied to wind or rain. **Fixed 2026-09-28:** MAD floored at each column's resolution (`RESOLUTION_FLOOR`). Before the fix it removed 12–19% of reference and 3D-PAWS temp/RH/pressure | Differs / Feedback |
| G13 | Order of pairing and aggregation | Paired at minute level; daily values from ≥ 80%-complete days | **Since 2026-09-28:** paired at minute level first, then aggregated (≥ 80% paired minutes per hour/day). Previously each instrument was aggregated separately, then paired | Same |
| G14 | Stuck humidity sensors (TSMS03 SHT31D ~2 %RH, TSMS04 HTU21D 0 %RH, from 1 Dec 2024) | Not mentioned. Table 1's interval test (0–105 %RH) accepts both. Its humidity persistence test covers only 0 < RH ≤ 105, so a run of exact 0s wouldn't count. Its spatial check vs. the site median (§4.5) would give a median near 2 %RH while both fail, which flags the **working** station (TSMS05), not the failed ones | Removed as documented failures SF-01/SF-02 ([sensor-failures.md](sensor-failures.md)) | Open / Feedback |
| G15 | Rolling z-score in near-flat windows | \|z\| > 3.0 over a 61-point window (§4.4). **Same quantization flaw:** in a window that is almost constant, the std is tiny, so a single resolution step scores a large z (≈ 7.7 for one step in 61 identical values). On the Konya reference (61-row window) it flags 0.01% of temperature, 0.13% of humidity, and 0.10% of pressure readings, and 69–96% of those flags are within about one resolution step of the window mean. **Precipitation is much worse:** std = 0 in ~97% of windows, and an isolated tip among zeros is always \|z\| > 3. Report-style z-scoring alone flags 34% of rainy minutes and 35% of total rain at the Konya reference gauge, 25% / 24% at Adana, and 12% / 21% at Ankara. This is independent of the MAD issue in G12. The report doesn't say how std = 0 is handled | 20-row window; not applied to rain. **Fixed 2026-09-28:** std floored at each column's resolution (`RESOLUTION_FLOOR`), so a reading must be more than 3 steps from the window mean in flat conditions | Differs / Feedback |
| G16 | CHORDS column misalignment (SF-10) | Report doesn't say where its 3D-PAWS data came from. Its tables include TSMS02–05 and 08 for the whole study period, e.g. TSMS03 has 973 valid rain days and TSMS08 wind direction MAE 17.08°, both plausible, so it may have used a correctly labeled source or re-mapped the columns | Our data was mislabeled for TSMS02, 03, 04, 05, 08 during Jan–mid-Mar 2024 and Dec 2024 → end (every variable). Dec 2024+ is likely a copy-paste of a CHORDS batch under an older header; Jan–Mar 2024 is not, and is suspected to be a firmware/software change at 2024-03-11 00:00 UTC (SF-10). **Dec 2024+ fixed 2026-09-28** in `data/reformatted` (`data/cleaned` not yet regenerated); Jan–mid-Mar 2024 still open (PF-28) | Ours / Open |

## Wind speed

| # | Topic | Report | Ours | Status |
|---|---|---|---|---|
| WS1 | Height adjustment | Hellmann 10 m → 2 m on TSMS only; α = 0.30 Ankara, 0.35 Konya, 0.25 Adana (§3.8) | Same formula, exponents, and heights | Same |
| WS2 | Calm periods / wind regimes | Not stated. QC rule: "when wind speed is 0, wind direction cannot be 0" (Table 1). No split by wind strength | **Since 2026-09-28:** zero speeds kept for both instruments. Statistics reported for all winds and separately for *variable* (reference 10-m speed < 3.0 m/s, ~6 kt) and *non-variable* (≥ 3.0 m/s) winds, classified from the reference only. (Before: `_mask_calm` dropped any minute where either instrument read 0.) | Differs |
| WS3 | Aggregation | Minute-level pairs | Scalar mean of speed over the hour/day (non-calm minutes only) | Differs |
| WS4 | Anomalous 3D-PAWS speeds | Not discussed for these stations | TSMS03 bias ≈ −21 m/s, TSMS04 ≈ −6 m/s (before sign flip), r ≈ 0. Looks like a data/units problem in our cleaned 3D-PAWS files | Ours |

## Wind direction

| # | Topic | Report | Ours | Status |
|---|---|---|---|---|
| WD1 | Error metric | Absolute angular difference as minimum circular separation (§3.9) | Same for MAE and RMSE | Same |
| WD2 | Signed difference / bias | **None.** No direction bias, median bias, SD, or IQR reported; §3.2 doesn't say whether it applies to direction | Signed circular difference wrapped to [−180°, 180°), used for Mean/Median Bias, Bias SD, Bias IQR | Differs / Feedback |
| WD3 | Agreement thresholds | Median absolute error; % within ±22.5°, ±45°, ±90° (Table 8) | Not computed | Differs |
| WD4 | Averaging | Minute-level, no averaging | Speed-weighted vector mean for hourly/daily (added 2026-09-25; previously an arithmetic mean, which was wrong across 0°/360°) | Differs |
| WD5 | Calm / stale direction | Not stated. Their QC rule targets speed = 0 with dir = 0, which is how **TSMS** records calm (`0.0, 0.0` in reference files). 3D-PAWS records calm as speed 0 with the vane's last direction (e.g. `0.0, 255.0`), which that rule would **not** flag | Direction set to NaN wherever the same instrument's speed is 0, for both systems; the speed itself is kept | Open / Feedback |
| WD6 | Linear stats on angles | None | Pearson r, per-series SD, and Reliability computed on raw degrees. Not valid for circular data | Ours |
| WD7 | Results | Mean abs. error (minute-level): Ankara 45.6–48.1°, Konya 84.6–93.6°, Adana 17.1–17.7° | Point-for-point run (old code, 2026-09-23): Ankara 57.4–61.4°, Konya 55.3–87.9°, Adana 61.0–77.8°. Adana is the largest gap and the ranking is reversed | Open |

**WD2 feedback:** absolute error alone can't separate a constant vane rotation from random
scatter. A signed mean/median would show a systematic orientation offset. The PI has ruled out
installation bias, so this is a question to confirm, not a claim. **Update 2026-09-28 (hourly,
split by regime):** at Adana, direction error *drops* in non-variable winds (MAE ≈ 10°, median
bias −3° to −6°), as expected when direction is well defined. At Ankara and Konya the signed
offset *grows* in non-variable winds: TSMS01 median bias +12.5° → +30.3°, TSMS02 +12.0° → +27.9°,
TSMS04 +73° → +110°, TSMS05 +62° → +102° (variable → non-variable). A bias that increases as the
wind steadies behaves like a systematic effect (orientation, local obstruction, or channelling at
2 m), not noise. It's worth raising with TSMS and the PI, and worth checking against the site
layouts. The size of the offset depends on the averaging method. For TSMS01's non-variable hours
it's +30° (speed-weighted hourly mean), +43° (minute by minute), or +66° (10-min vector averages
used for the wind roses), with a middle-50% spread of over 100°. In those hours 3D-PAWS also
reads 0.68 m/s vs. 2.23 m/s for the reference at 2 m, which fits sheltering or deflection at the
3D-PAWS mast rather than a rotated vane alone.

**WD5 hypothesis:** if the report kept 3D-PAWS calm minutes with a stale direction while
dropping TSMS calm minutes, that would add spurious direction errors in the report's numbers.
It's worth asking TSMS how 3D-PAWS calm records were handled.

## Precipitation

| # | Topic | Report | Ours | Status |
|---|---|---|---|---|
| P1 | Zero / dry periods | Kept. Dry–dry days are Correct Negatives in the contingency table (Table 9) | Time steps where both gauges read 0 are **excluded** from bias, MAE, RMSE, SD, r, and reliability | Differs |
| P2 | Metrics | Monthly totals: Bias and R² (§3.10, Fig. 10.2). Daily wet/non-wet (≥ 0.2 mm/day): POD, FAR, CSI (Table 9) | Per-timestep bias, MAE, RMSE, SD, r, reliability on hourly/daily sums. No monthly totals, no contingency scores | Differs |
| P3 | QC outlier test on precip | Rolling 61-pt MAD (> 3.5) / z-score (> 3.0) applied to "all meteorological variables" (§4.4, Fig. 4.1). Not stated whether used on precip or on reference data. If it was, the z-score part alone removes 12–34% of reference rainy minutes (21–35% of total rain); see G15 | None applied | Open / Feedback |
| P4 | Effect of P3 if applied | — | Simulated on our cleaned 1-min data: removes 73–95% of rainy minutes (Adana ref wet days 459 → 53; Konya ref 264 → 12; TSMS06 201 → 27; TSMS00 241 → 10). Mostly-zero windows give MAD = 0, so every tip gets flagged | Feedback |
| P5 | Reference wet-day counts | Implied reference wet days (Hits + Misses): Adana ≈ 80, Konya ≈ 180, Ankara ≈ 76–104 over ~870–1,050 paired days | Raw reference, ≥ 0.2 mm, 80%-complete days: Adana 459 / 1,179, Konya 264 / 1,181 | Open / Feedback |
| P6 | 3D-PAWS wet-day counts | TSMS06: 190 (Table 9) | Raw TSMS06: 201 | Same (roughly) |
| P7 | Reference vs. 3D-PAWS annual totals | Monthly figures only (not machine-readable) | Raw data, both gauges clean: Adana ref ≈ 500 mm/yr vs. TSMS06 ≈ 532, TSMS07 ≈ 447 mm/yr | Open |
| P8 | Our 3D-PAWS `tipping` data | — | Was implausible at TSMS02, 03, 04, 05, 08 (≈ 47,600 to 2.2 million mm/yr). **Resolved 2026-09-28:** caused by the CHORDS column mislabeling (SF-10), now fixed for both periods; monthly totals in the regenerated `data/cleaned` are in a plausible range. Remaining rain issues are genuine gauge problems, cataloged as SF-11, SF-12, SF-16 | Resolved |
| P9 | Our Ankara reference data | — | ≈ 3,500 mm/yr with 1-min spikes up to 31.5 mm. Implausible | Ours |

**P3–P5 feedback:** the report's reference gauges show far fewer wet days than the raw
reference data, while its 3D-PAWS wet-day counts are close to raw. That fits QC removing real
rain from the reference, which would inflate the report's FAR (0.61–0.72 at every station) by
counting correct 3D-PAWS detections as false alarms. This needs confirmation from TSMS:
(1) was the MAD/z-score test applied to precipitation? (2) was it applied to the reference
gauges? (3) how do the QC'd reference daily totals compare with TSMS's official daily totals?

---

## Questions for TSMS

1. Was the rolling MAD/z-score outlier test applied to minute-level precipitation, and to the reference gauges? (P3–P5) How is MAD = 0 handled (a floor, skipping the window, or dividing by zero)? What fraction of each variable did the test remove? (G12)
2. How were 3D-PAWS calm records (speed 0 with a non-zero, stale direction) handled? (WD5)
3. Was any signed wind-direction bias computed? Is a systematic vane offset ruled out by measurement or by assumption? (WD2)
4. Which timezone are the raw TSMS and 3D-PAWS minute files in, before conversion to UTC? (G5)
5. Can we get the QC'd minute-level dataset behind Tables 8 and 9, so we can reproduce the Adana wind-direction and reference wet-day numbers? (WD7, P5)
6. Which 3D-PAWS data source did the report use for Jan 2024 – Nov 2025, and was the CHORDS column-order change handled? (G16) This could also explain part of the gap between our and their wind-direction results (WD7). Specifically:
   - Did TSMS notice that at TSMS02, 03, 04, 05 and 08 the column order changes at **2024-03-11 00:00 UTC** (Jan–Mar 2024 rows out of header order) and again from **2024-12-01**?
   - If so, how were the columns re-assigned, and in particular how were **TSMS04's three temperature sensors** (HTU21D, BMP280, MCP9808) told apart for 12 Jan – 10 Mar 2024? We could not do so reliably and excluded them (methods.md §3).
   - If not, the report's statistics for these five stations include mislabeled data for those periods (e.g. "rain" that is actually a temperature). Table 9's valid-day and wet-day counts for TSMS03–05 should be checked with this in mind.
7. The Konya (courtyard next to a brick wall) and Ankara (nearby hill) siting limits 2-m wind comparisons. Does the report want to state this explicitly? (see [siting.md](siting.md))
8. **Reference instrument uncertainty:** which instrument models are used at each TSMS reference station (temperature, humidity, pressure, wind, precipitation), and are calibration certificates or intervals available? This is needed for a formal Eₙ comparison (WMO-No. 8 Vol. V Ch. 4) and would sharpen the WMO classification (PF-33).
9. **Ankara precipitation:** the Ankara reference uses an accumulation (weighing) gauge. How is the 1-min `total_rainfall` derived from it, and are negative/noise increments filtered? Ankara reference totals are several times the 3D-PAWS totals in many months (SF-09).

## Our to-do items

Moved to [potential-fixes.md](potential-fixes.md), which is the single backlog for fixes on our side
(e.g. G3/G13 → PF-09, WS2 → PF-10, WD3/WD6 → PF-11, P8/P9 → PF-07/PF-08, G9 → PF-17, G10 → PF-15).
