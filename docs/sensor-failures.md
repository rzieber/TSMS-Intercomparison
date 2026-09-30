# Sensor failure catalog

Running catalog of sensor failures and malfunctions found in the 3D-PAWS and TSMS data: what
failed, when, how it was identified, and how the data is handled. Changes to cleaning logic are
logged in [logic-changelog.md](logic-changelog.md). Differences from the TSMS report are in
[method-differences.md](method-differences.md).

**Status key:** `Removed` = excluded from `data/cleaned` · `Handled` = partly addressed by a
cleaning filter · `Open` = identified, not yet handled · `Suspected` = needs confirmation

Removals and flags are configured as rows in [station-events.csv](station-events.csv) (with the
catalog ID in `catalog_id`). QC Step 1 in `scripts/outliers/outlier-removal.py` applies them:
removals are logged in each station's `*_outliers.csv` with `outlier_type = station_event:<event>`,
and flagged periods go to `station_event_flags.csv`. Times are as recorded in the data files
(timezone not yet verified; see method-differences G5).

Last updated 2026-09-29 (SF-20, SF-21 from the maintenance logs; SF-22–26 from the persistence checks; SF-27, SF-28 from the neighbour check; SF-09, 17, 22, 26–28 corrected and SF-29–31 added from the diagnostic figures; confirmed failures encoded in station-events.csv).

---

## Summary

| ID | Station | Sensor / column | Failure | Period | Status |
|---|---|---|---|---|---|
| SF-01 | TSMS03 (Konya) | ~~SHT31D / `sth_hum`~~ | **Reclassified 2026-09-28: not a sensor failure.** The "humidity" is the UV sensor (SI1145_UV) under the wrong label (SF-10) | 2024-12-01 00:00 → end of `sth_hum` record | **Fixed 2026-09-28** (splice); removal deleted |
| SF-02 | TSMS04 (Konya) | ~~HTU21D / `htu_hum`~~ | **Reclassified 2026-09-28: not a sensor failure.** The "humidity" is the precipitation column under the wrong label (SF-10) | 2024-11-30 23:59 → end of record | **Fixed 2026-09-28** (splice); removal deleted |
| SF-03 | TSMS00–04 | HTU21D / `htu_temp`, `htu_hum` | "Bit-switching": temperature and humidity values swap at 1–4 min intervals | Hours to ~2 months at a time, pre-upgrade | Handled |
| SF-04 | Konya HTU21Ds (TSMS03–05) | HTU21D / `htu_hum` | Reads +8 to +13 %RH high in winter, ~0 in summer: 4–6× the datasheet ±2 %RH (20–80 %RH), so not a sensor tolerance effect | Every winter, Oct–May | Open |
| SF-05 | TSMS02, 03, 04, 05, 08 | ~~Tipping bucket~~ / `tipping` | Implausible rainfall (≈ 47,600 to 2.2 million mm/yr). **Root cause 2026-09-28: SF-10** (the "rain" column holds temperature, humidity, wind, or light values) | Jan–Mar 2024 and Dec 2024 → end | Dec 2024+ fixed 2026-09-28 (Konya rain now tracks the reference); Jan–Mar 2024 open |
| SF-06 | TSMS02 (Ankara) | SHT31D / `sth_hum` | Large low bias (−25 %RH vs. reference) | Post-upgrade | Suspected |
| SF-07 | TSMS06 (Adana) | SHT31D / `sth_hum` | Low bias (−8 %RH vs. reference) | Post-upgrade | Suspected |
| SF-08 | TSMS03, TSMS04 | ~~Anemometer~~ / `wind_speed` | Speeds far above reference (bias ≈ 21 and 6 m/s), r ≈ 0. **Root cause 2026-09-28: SF-10** (e.g. TSMS03's "wind_speed" is HTU21D humidity from Dec 2024, TSMS04's is visible light) | Jan–Mar 2024 and Dec 2024 → end | Dec 2024+ fixed 2026-09-28; Jan–Mar 2024 open |
| SF-09 | Ankara TSMS reference | Rain gauge / `total_rainfall` | ≈ 3,500 mm/yr with 1-min spikes up to 31.5 mm; hundreds of mm in many months from Mar 2023 (e.g. 979 mm May 2023 vs. 84 mm at TSMS00) but plausible in others. Separate pipeline from SF-10 (TSMS text file). **Lead (2026-09-28):** Ankara's reference uses an **accumulation (weighing) gauge**, while Konya, Adana and all 3D-PAWS use tipping buckets. If 1-min rain is derived from differences in accumulated weight, sensor noise and baseline shifts (WMO-No. 8 Vol. I Ch. 6) counted as positive increments would inflate totals **Update 2026-09-29: a ×10 scaling error, not gauge noise.** Wet-day ratio reference ÷ TSMS00 is 0.97 before 2023-03-06 and 9.96 after (126 wet days); totals after that date 11,253 mm vs. 833 mm. The same day the reference's reporting step changes from 0.01 mm to exactly 0.1 mm (last finer value 2023-03-06 04:21; duplicate timestamps around 02:02 suggest a logger change). Dividing by 10 tracks the 3D-PAWS gauges | 2023-03-06 → end | **Confirmed; flagged** from 2023-03-06 (station-events `rain_scaling_x10`, every reference rain value carries the flag). Correction (÷10) or exclusion is a team decision |
| SF-10 | TSMS02, 03, 04, 05, 08 | **All columns** (data pipeline, not a sensor) | CHORDS export column misalignment: data rows are in a different column order than the file header, so every variable is mislabeled | CHORDS start (12–16 Jan 2024) → 2024-03-10 23:59 UTC, and 2024-12-01 → end of record | **Fixed 2026-09-28** (`splice_chords_dec2024.py`): Dec 2024+ from the correctly labeled batch; Jan–Mar 2024 re-mapped by inference (except SF-15) |
| SF-15 | TSMS04 (Konya) | HTU21D, BMP280, MCP9808 temperatures | Sensor identity of the three temperature columns can't be established in the re-mapped Jan–Mar 2024 window (SF-10) | 2024-01-12 09:10 → 2024-03-10 20:31 | **Excluded** (written as missing in `data/reformatted`); see [methods.md](methods.md) §3 |
| SF-16 | Several 3D-PAWS gauges | Tipping bucket / `tipping` | Months of near-zero rain while the reference and neighbouring gauges record rain (possible clogging, a stuck bucket, or a connection fault). From the 2026-09-28 cleaned data: TSMS03 0–1 mm/month Apr–Sep 2024 (Konya reference 12–63); TSMS08 0–1 mm Apr–Sep 2024 (Adana ref 14–92); TSMS01 0–7 mm for most of 2023–2024; TSMS02 0 mm Aug–Oct 2024 and Feb–Mar 2025; TSMS00 0 mm Jun–Nov 2025. Overlaps SF-11 (TSMS04 from Apr 2025) | See description | Suspected; not yet bounded or removed |
| SF-17 | TSMS06 (Adana) | All temperature and humidity sensors (`mcp9808`, `bmp2_temp`, `sth_temp`, `sth_hum`) | Exactly 0.0 on all sensors at once (a logger writing zeros, not readings). 0 °C passes range checks. Median difference vs. reference −19.6 °C / −63 %RH in those minutes | Feb–May 2025 (all sensors, ≈ 60,000 min); 2024-09-26 14:20 → 2024-10-21 23:05 (**all sensors**, 35,743 min; corrected 2026-09-29, was listed as `sth_*` only) | **Both periods come from the CHORDS download, not the SD cards; a CHORDS database bug is suspected, so this may be a data-pipeline artefact (PF-44: check TSMS06's battery/diagnostic metadata).** **Removed** (QC Step 3 "logger zeros", 2026-09-29): any minute where a humidity sensor reads exactly 0 %RH and a temperature sensor exactly 0.0 °C; 118,032 minutes, 400,115 readings. Elsewhere this combination occurs in 7 minutes (TSMS08) |
| SF-18 | TSMS04 (Konya) | BMP280 / `bmp2_pres` | Pressure bias vs. reference drifts from ≈ +1.5 hPa (Q4 2022) to ≈ −1.6 hPa (mid-2024 onward); TSMS03 and TSMS05 drift much less. Suggests sensor drift or a calibration change. ≈ 3.1 hPa over ≈ 1.75 yr ≈ 1.8 hPa/yr, beyond the BMP280's ±1.0 hPa/yr drift spec | Gradual, 2022 → 2024, then stable | Suspected |
| SF-19 | TSMS07 (Adana) | BMP280 / `bmp2_pres`, `bmp2_slp` | Pressure stuck at ≈ 500.1 hPa (SLP ≈ 502.9) for six months; Adana is ≈ 1,010 hPa. Found by the Step 0 layout guard (2026-09-29); removed by the range check (870–1,084 hPa) | May → Oct 2024 | Suspected (BMP280 fault or logger issue) |
| SF-11 | TSMS04 (Konya) | Tipping bucket / `tipping` | Isolated 1-min values of 37–39 mm (not physical; Phase 3 removes > 32), and almost no rain recorded from Apr 2025 (0–3 mm/month vs. 20–49 mm at the reference and TSMS03/05) | Apr 2025 → end | Suspected |
| SF-12 | TSMS05 (Konya) | Tipping bucket / `tipping` | Monthly totals of 2,108 mm (Jul 2025) and 314 mm (Nov 2025) vs. 20 / 25 mm at the reference; other months track the reference | Jul 2025, Nov 2025 | Suspected |
| SF-13 | TSMS01 (Ankara) | BMP280 / `bmp2_temp` | Dec 2024+ median 4.5 °C vs. ≈ 14 °C for the station's other temperature sensors | Dec 2024 → end (not yet bounded) | Suspected |
| SF-14 | TSMS06, TSMS08 (Adana) | BMP280 / `bmp2_pres` | TSMS06: 0 hPa in Oct 2024 and Mar–May 2025 (the SF-17 logger zeros) and ≈ 670 hPa (SLP ≈ 664–678) from Jun 2025 (Adana ≈ 1,010 hPa). TSMS08 mostly `-999.9` (now treated as missing, Step 0). Found by the Step 0 layout guard (2026-09-29); removed by the range check | TSMS06: Oct 2024; Mar 2025 → end | Suspected (TSMS06 pressure failed from Jun 2025) |
| SF-20 | TSMS02 (Ankara) | Cup anemometer / `wind_speed` | **Disconnected.** The anemometer developed a short circuit that tripped the RPi, so it was unplugged (Ankara maintenance log, 2024-01-17). `wind_speed` is exactly 0 for all 407,009 readings while the reference median is 1.5 m/s (62% of minutes > 1 m/s). The vane kept working | 2023-03-31 12:17 → 2024-01-11 10:02 (last working reading 2023-03-15 11:00, then a record gap; first nonzero 2024-01-11 10:03) | **Removed** (Step 1); `wind_dir` kept |
| SF-21 | TSMS00, 01, 06, 07 | Tipping buckets / `tipping`; TSMS07 anemometer | Conditions found at the Jan 2024 visits: TSMS00 gauge significantly off level and possibly stuck on one side; TSMS01 bucket possibly stuck; TSMS06 two ~5 mm pebbles in the funnel orifice; TSMS07 funnel screens missing; TSMS07 anemometer binding (corroded bearing, rotor replaced) | Start unknown → visit day (2024-01-17 Ankara, 2024-01-15 Adana) | **Flagged** (Step 1), not removed: the logs show degraded conditions, not failed data. Bounding the start is Step 6's job (neighbour rain / wind comparison) |
| SF-22 | TSMS01 (Ankara) | Wind vane / `wind_dir` | Reads exactly 0.0° almost every minute from 2024-10-21 to 2024-11-21 while the cups turn; 0.0° is 44,314 of its readings overall, 20× its next most common value | Oct 2024 → Nov 2024 | **Removed** 2024-10-21 12:34 → 2024-11-21 12:25 (station-events `vane_stuck_at_0`, 2026-09-29; previously only 6,625 windy readings) |
| SF-23 | **Ankara TSMS reference** | Logger (all variables) | **Frozen record:** temperature, humidity, pressure, wind speed (1.4–10.2 m/s) and direction all repeat the same values for 65–236 min, in 25 runs on 22 days (19 Jul and 8 Aug have two), mostly starting 05:51–06:18 UTC, some 08:03–10:04; first on 2025-06-30 | Jun–Aug 2025 | **Removed** (Step 4b "logger_frozen"; 2,875 minutes). Feedback for TSMS |
| SF-24 | **Ankara TSMS reference** | Humidity (Rotronic MP101A) / `humidity` | Flat at exactly 10% for 5–9 h on summer afternoons while temperature changes: looks like a reporting floor | 2023-08-15, 2023-08-16 (221 min), 2024-06-23, 2024-06-24 | **Removed** (Step 4b persistence; 1,475 readings). Feedback for TSMS |
| SF-25 | **Ankara TSMS reference** | Wind vane (Lastem DNA011) / `avg_wind_dir` | Reads 0° for 643 min while the reference speed is ≈ 2.8 m/s (until 07:39 on 11 Jun, and again from 11:26; QC removed only up to 06:20) | Jun 2025 (10–11 Jun) | **Removed** (Step 4b). Feedback for TSMS |
| SF-26 | **Adana TSMS reference** | Anemometer (Lastem DNA002) / `avg_wind_speed` | **Outage:** exactly 0 m/s in ≈ 100% of minutes from 2025-08-10 to 2025-10-12 (at most 54 nonzero minutes a day; single zero runs up to ≈ 7 days); ≈ 1.9 m/s daily mean in July; recovers 13 Oct. The Step 6 calm check removed only 213 min because the 2 m 3D-PAWS winds at Adana are mostly below 1.5 m/s | 2025-08-10 → 2025-10-12 | **Removed** 2025-08-09 14:00 → 2025-10-13 07:59 (station-events `anemometer_outage`, 2026-09-29) |
| SF-27 | TSMS08 (Adana) | Cup anemometer / `wind_speed` | **Not responding:** runs of exactly 0 m/s ≥ 3 h while both other Adana 3D-PAWS anemometers read a median ≥ 1.5 m/s (above the cups' ≤ 1.2 m/s start-up, SMN tunnel tests). Concentrated May–Sep 2023 (46,300 of 58,189 minutes), with more in summer 2024. The evaluation plan says TSMS08's cup mechanism was replaced in January 2024; its median speed is 0.3 m/s vs. 0.9 at TSMS06/07 Figures (2026-09-29): TSMS08 reads 0 in 93–100% of minutes May–Dec 2023 and 90–100% Jun–Oct 2024, so the removed minutes (neighbours windy) are only part of the fault; after the Jan 2024 visit it also sits at an almost constant ≈ 0.7 m/s for days (17–27 Jan, 8–9 Feb, 15–18 Feb 2024), a second stuck value | May 2023 → Oct 2024 | **Removed** (2026-09-29, station-events): 2023-04-29 → 2024-01-12 and Jun–Oct 2024 (90–100% zeros), plus the 0.7 m/s stuck spans 16–28 Jan, 8–11 Feb, 14–19 Feb 2024. Apr–May 2024 (63–76% zeros) left to the Step 6 calm check. Check the replaced unit's magnet |
| SF-28 | **Konya 3D-PAWS gauges** (TSMS03, 04, 05), not the reference | Tipping buckets / `tipping` | **Courtyard watering, not missed rain (corrected 2026-09-29).** In Jul–Aug 2023 all three gauges tip most days at ≈ 09:50–10:00 UTC (and ≈ 13:50) while the reference humidity is ≈ 27% (median at the tips) and the stations' own humidity agrees; the reference records 0.6 mm in the two months, TSMS03/04/05 record 83 / 139 / 104 mm. Step 6 flagged the *reference* as a dead gauge on 12 days, the wrong way round | Mainly Jul–Aug 2023 (other dry seasons to check) | **Flagged** `courtyard_watering` 1 Jul – 2 Sep 2023 at TSMS03/04/05 and Jul 2025 at TSMS05 (suspected; 55 watering-like tips in the SF-12 month). The reference's false `rain_dead_gauge` flags remain in the flag file (the neighbour rule can't tell); tips also carry `rain_low_rh` |
| SF-29 | TSMS02 (Ankara) | Tipping bucket / `tipping` | **No rain recorded** during its anemometer outage: 7 tips from 2023-03-31 12:17 to 2024-01-04 (397,770 valid readings), while TSMS00/01 record rain. Same period as SF-20, so possibly the same disconnected harness | 2023-03-31 → 2024-01-04 | **Flagged** `rain_gauge_dead` 2023-03-31 12:17 → 2024-01-04 (station-events, 2026-09-29) |
| SF-30 | TSMS01 (Ankara) | Cup anemometer / `wind_speed` | **Reads ≈ 30% of TSMS00:** median ratio TSMS01 ÷ TSMS00 when TSMS00 > 1 m/s is 0.28 (2023), 0.26 (2024), 0.30 (2025), 0.45 (2022), for stations ≈ 10 m apart (TSMS02 ÷ TSMS00 is ≈ 0.5–0.9 over the same minutes). SMN found a misplaced magnet halves the reading | 2023 → end | Suspected; noted in station-events (`anemometer_low_reading`), not removed. Check the unit (magnet, bearing) |
| SF-31 | **Adana TSMS reference** | Rain gauge / `total_rainfall` | **Many days with 0.2–1.0 mm** that the 3D-PAWS gauges don't record: 290 of its 429 wet days (≥ 0.2 mm) are below 1 mm. They peak in the dry summer: 73 of 92 days in Jul–Sep 2023 and 60 in Jul–Sep 2024, fading in 2025. Likely dew or condensation counted as rain. Explains most of Adana's low POD at 0.2 mm | Mainly summers 2023 and 2024 | Suspected; not flagged. TSMS question 15 |

Previously handled in code before this catalog: TSMS04 fabrication test tips (start of record →
2022-08-31) and TSMS08 rainfall from a suspected faulty connector or tampering (seven date ranges,
2023-04 to 2024-03). Since 2026-09-29 both are rows in [station-events.csv](station-events.csv),
applied in Step 1. Month-specific manual threshold removals for several temperature and pressure
sensors are still in Phase 4 (`station_rules`).

---

## SF-01: TSMS03 SHT31D humidity stuck low

- **Station / sensor:** TSMS03, Konya. SHT31D (`sth_hum`), installed at the 2024-01-12 upgrade.
- **Removed period:** 2024-12-01 00:00:00 through the end of the record. The last `sth_hum`
  reading in the raw data is 2025-04-28 07:35. There's no `sth_hum` data in Feb–Mar 2025. The
  station's other sensors (e.g. `mcp9808`) keep reporting through 2025-11-30.
- **What happened:** the last normal reading is 90.7 %RH at 2024-11-30 23:58. At 2024-12-01
  00:00 the value drops to 1.0 %RH and stays near 1–4 %RH, with a brief rise each day (to
  20–100 %RH) that doesn't track the reference. Over the removed period the median is
  2 %RH vs. a reference median of 76 %RH. Only 1.9% of minutes are within 5 %RH of the
  reference, and those are coincidental crossings during the daily spikes. Raw values above
  100 (up to 256) also appear in April 2025.
- **How identified:** 2026-09-28, after the reference-based HTU filter was removed (see the
  changelog). Monthly comparison against the TSMS reference and the other Konya stations. TSMS05
  tracks the reference throughout, so the site's air wasn't unusually dry.
- **Why removed in full:** the sensor never returns to plausible values, and the low readings
  change slowly, so step and outlier filters can't separate good minutes from bad ones.
- **Evidence:** [figures/konya-humidity-dec2024-failure.png](figures/konya-humidity-dec2024-failure.png)
- **Readings removed:** 57,826, logged with `outlier_type = sensor_failure` in
  `data/cleaned/3DPAWS_TSMS03_Konya_outliers.csv`. The last kept reading is 2024-11-30 23:58.

## SF-02: TSMS04 HTU21D humidity stuck at 0

- **Station / sensor:** TSMS04, Konya. HTU21D (`htu_hum`). TSMS04 is one of the 3D-PAWS
  reference stations that was never upgraded.
- **Removed period:** 2024-11-30 23:59:00 through the end of the record (2025-11-30 23:58).
- **What happened:** from 2024-11-30 23:59, every `htu_hum` reading is exactly 0.0 %RH for the
  rest of the record, 12 months. No reading in the cleaned data after onset is above 0. The
  reference median over the same period is 49 %RH.
- **Possible precursor (not removed):** on 29–30 Nov 2024 the HTU readings are sparse and include
  values around 25–30 %RH interleaved with values around 97–100 %RH. That fits the SF-03
  bit-switching pattern. The raw file also contains `-1000.0` values just before onset. Phase 1
  handles only `-999.99`, so these are caught by the Phase 3 range check but logged as
  `threshold` rather than `null`. This should be reviewed.
- **How identified:** same as SF-01.
- **Readings removed:** 481,243, logged with `outlier_type = sensor_failure` in
  `data/cleaned/3DPAWS_TSMS04_Konya_outliers.csv`. The last kept reading is 2024-11-30 23:57.
- **Why removed in full:** a constant 0 is physically impossible for outdoor air and gives no
  information. Its values don't jump, so no step or outlier filter catches it.
- **Evidence:** [figures/konya-humidity-dec2024-failure.png](figures/konya-humidity-dec2024-failure.png)

### SF-01 and SF-02 started at the same time (resolved: SF-10)

Both "failures" begin within one minute of each other (2024-11-30 23:59 and 2024-12-01 00:00),
at two stations, on two different sensor models. **Resolved 2026-09-28:** the shared cause is
the change in CHORDS row column order on 2024-12-01 (SF-10). Neither humidity sensor failed.
TSMS03's "humidity" is its UV sensor and TSMS04's is its precipitation column. TSMS05 only
*looked* unaffected: after the reordering, its real humidity happens to sit in the column
labeled `sth31d_humidity`, but its other columns are scrambled too (e.g. its "rain" is visible
light). The SF-01/SF-02 removals stay in place until the SF-10 fix re-maps the columns. At that
point they should be deleted from `sensor_failures`, since the underlying sensors are probably
fine.

## SF-03: HTU21D bit-switching (TSMS00–TSMS04)

Documented in the Phase 4 notes of `outlier-removal.py`: temperature readings would toggle
between valid temperatures and humidity values (and vice versa) at 1–4 minute intervals, for
stretches of a few hours up to two months. Handled since 2026-09-28 by the Phase 5 step test plus
co-located sensor checks (see changelog). **Known gaps:** only the edges of multi-minute bad runs
are flagged, and a steady failure like SF-02 isn't caught.

## SF-04: Konya HTU21D reads high in winter

At Konya the HTU reads +8 to +13 %RH above the reference in winter (Oct–May) and close to 0 in
summer, every year of the record. It looks like steady sensor behaviour at high humidity and
cold temperatures, not noise, so it's **kept in the data** as a genuine result. The old
reference-based filter was hiding it by deleting 30–70% of winter readings. Worth checking
whether the Ankara and Adana HTUs show the same pattern.

## SF-05 to SF-09

Identified during the 2026-09-28 review. Not yet investigated in detail. See the figures in the
summary table and [method-differences.md](method-differences.md) (P8, P9, WS4).

---

## SF-10: CHORDS export column misalignment (data pipeline)

**What:** the raw CHORDS files in `data/raw/3D-PAWS/Jan-2024_Nov-2025/station_TSMS0n/`
(`Calibration_Inst{n+2}_Jan24-Nov25.csv`) have one header row, but **the column order of the data
rows changes over time**. Wherever the row order differs from the header, reading the file by
header (as `final_paws_reformatter.py` does with `pd.read_csv`) assigns every value to the wrong
variable. It's not a sensor problem: the sensors recorded correctly, and the values are just
labeled wrong.

**How it was found (2026-09-28):**
1. TSMS03's "rain" in Feb 2024 changed smoothly by ~0.1 per minute in the 13–20 range. It
   correlated at r = 0.999 with both `sth_temp` and `wind_speed`, so `wind_speed` was holding a
   temperature too.
2. Tracking the position of the compass-direction text field (`N`, `SE`, …) in each row, month by
   month, shows where row order matches the header:

| Station | Header compass position | Rows match header | Rows in a different order |
|---|---|---|---|
| TSMS00, 01, 06, 07 | n/a | whole record (TSMS01/07 checked on Feb 2025 only) | none found |
| TSMS02 | 13 | ~Mar 2024 → Nov 2024 | Jan–Feb 2024 (position 8); Dec 2024 → end (position 4) |
| TSMS03 | 8 | ~Mar 2024 → Nov 2024 | Jan–Feb 2024 and Dec 2024 → end (position 4) |
| TSMS04 | 10 | ~Mar 2024 → Nov 2024 | Jan–Feb 2024 (position 4); Dec 2024 → end (position 7) |
| TSMS05 | 8 | ~Mar 2024 → Nov 2024 | Jan–Feb 2024 and Dec 2024 → end (position 4) |
| TSMS08 | 7 (and 13) | ~Mar 2024 → Nov 2024 | Jan–Feb 2024 and Dec 2024 → end (position 9, 15) |

March 2024 is a transition month with both orders present.

3. The **second CHORDS download** in `data/raw/3D-PAWS/Dec-2024_Nov-2025/`
   (`Calibration_Instrument-{n+2}_2024-12-01_2025-11-30.csv`) has descriptive, correct headers
   and overlaps from 2024-12-01. Matching values at identical timestamps gives the true identity
   of each mislabeled column. Examples (Dec 2024, 100% of readings match):

| Station | Labeled as | Actually |
|---|---|---|
| TSMS03 | `sth31d_humidity` | SI1145_UV, so SF-01 is UV, not humidity |
| TSMS04 | `htu21d_humidity` | precipitation, so SF-02 is mostly-zero rain, not stuck humidity |
| TSMS03 | `rain` | HTU21D temperature |
| TSMS08 | `rain` | HTU21D humidity |
| TSMS03 | `wind_speed` | HTU21D humidity |
| TSMS04 | `wind_speed` | SI1145 visible light |

In Feb 2025, TSMS00, 06 and 07 match column-for-column, and TSMS01 matches except for empty BMP
columns. TSMS03, 04, 05 and 08 are scrambled in every column.

**Consequences:** during the misaligned periods, **every variable** at TSMS02, 03, 04, 05 and 08
in `data/cleaned`, and every statistic built from it, is wrong: temperature, humidity, pressure,
wind, and rain. That includes the Konya wind results, the implausible rain totals (SF-05), the
TSMS03/04 wind-speed anomaly (SF-08), and the two "humidity failures" (SF-01, SF-02). The
2026-09-28 SF-01/SF-02 removals only blank two columns. The rest of those rows are still
mislabeled.

**Cause: two separate events, both unconfirmed.**

1. **Dec 2024 → Nov 2025.** Likely a copy-paste (user, 2026-09-28): the latest CHORDS batch was
   pasted under the header of the file that held the earlier data, and CHORDS had delivered it
   in a different column order. Supporting evidence: the pasted rows follow the Dec 2024 batch's
   own header order exactly.
2. **Jan 1 → Mar 10 2024. Not a copy-paste** (user, 2026-09-28). This data was pulled from CHORDS
   the same way as the rest of the Jan 2024 → Nov 2025 record. The suspected cause is a software
   or firmware malfunction or update that changed the order in which fields were sent, stored,
   or exported. Evidence:
   - The layout switches at **the same timestamp, 2024-03-11 00:00 UTC**, at all five affected
     stations and never switches back. A change at the same instant on five separate stations
     points to something shared or pushed remotely, not to independent faults.
   - **It isn't specific to one logger type.** TSMS02, 03, 04, 05 run on Raspberry Pi
     dataloggers and TSMS08 on a Particle datalogger, and all five are affected. TSMS00 and
     TSMS01 (Raspberry Pi) and TSMS06 and TSMS07 (Particle) are not.
   - **It isn't tied to the Jan 2024 SHT31D upgrade.** TSMS04 wasn't upgraded but is affected;
     TSMS06 was upgraded but isn't. The upgrade dates (12–17 Jan 2024) also don't match the
     switch date.
   - The affected layouts differ between stations (TSMS03/05 share one; TSMS02, TSMS04 and
     TSMS08 each have their own). So the fields weren't shifted uniformly; each station's order
     was permuted differently.
   - **Candidates to check:** (a) the CHORDS instrument configuration: if variables were
     re-created or reordered on the server around 2024-03-11, exports before and after could list
     fields in different orders; (b) datalogger firmware or software updates pushed around
     2024-03-10/11; (c) a CHORDS ingest or export bug. The CHORDS admin history and the
     logger update logs are the places to look.

**Fix, part 1 (2026-09-28):** `scripts/reformatting/splice_chords_dec2024.py` replaces 2024-11-30
23:59 → end in `data/reformatted` with the correctly labeled Dec 2024 → Nov 2025 batch, mapped by
column name. It's verified by a 100% match at the four unaffected stations. See the changelog.

**Still open (PF-28):** Jan → mid-Mar 2024. Only TSMS08's early-2024 rows follow the Dec-batch
order. TSMS03/05 and TSMS02/04 use other layouts. Also relevant to the TSMS report if TSMS received
the same pasted file (method-differences G16).

### Jan 1 → Mar 10 2024: switch time and inferred column mapping (2026-09-28)

This period can't be re-downloaded: CHORDS keeps only 2 years of data. The raw rows are intact,
just mislabeled, so the data can be recovered by re-mapping columns.

**Switch time.** Every affected station changes layout exactly once, at the paste boundary
**2024-03-11 00:00 UTC**. Rows before are in the pasted batch's order; rows from then on match the
header. There's no alternation in March.

| Station | Last row in the pasted order | First row in the header order |
|---|---|---|
| TSMS02 | 2024-03-10 23:59:13 | 2024-03-11 00:00:14 |
| TSMS03 | 2024-03-10 20:29:14 | 2024-03-11 09:50:13 (≈ 13 h gap, no rows) |
| TSMS04 | 2024-03-10 20:32:18 | 2024-03-11 09:53:09 (≈ 13 h gap) |
| TSMS05 | 2024-03-10 20:38:14 | 2024-03-11 09:53:13 (≈ 13 h gap) |
| TSMS08 | 2024-03-10 23:59:53 | 2024-03-11 00:00:53 |

**Mapping (header label → true variable), 2024-01-01 → 2024-03-10.** Non-temperature columns
were identified from value signatures: compass letters; SLP ≈ 1,015–1,030 hPa; station pressure
≈ 900 hPa at Konya and ≈ 915–920 hPa at Ankara; rain mostly 0; wind direction 0–360; humidity
30–100%; SI1145 VIS ≈ 260 / IR ≈ 253 / UV ≈ 2–3. TSMS02's non-temperature mapping was
worked out by the user and confirmed by these checks.

| Header label | TSMS02 | TSMS03 & TSMS05 | TSMS04 | TSMS08 |
|---|---|---|---|---|
| col 1 | `rain` → **bmp_temp** | `bmp_temp` → rain | `htu21d_temp` → rain | `bmp_temp` → bmp_temp |
| col 2 | `wind_speed` → **mcp9808** | `mcp9808` → wind_speed | `bmp_temp` → wind_speed | `mcp9808` → mcp9808 |
| col 3 | `bmp_temp` → bmp_slp | `bmp_slp` → wind_direction | `mcp9808` → wind_direction | `bmp_pressure` → **sht31d_temp** |
| col 4 | `mcp9808` → bmp_pressure | `bmp_pressure` → compass | `htu21d_humidity` → compass | `rain` → sht31d_humidity |
| col 5 | `bmp_slp` → rain | `rain` → **bmp_temp** | `bmp_slp` → **htu21d_temp** | `wind_speed` → bmp_pressure |
| col 6 | `bmp_pressure` → wind_speed | `wind_speed` → **mcp9808** | `bmp_pressure` → **bmp_temp** | `wind_direction` → rain |
| col 7 | `si1145_vis` → wind_direction | `wind_direction` → bmp_slp | `rain` → **mcp9808** | `wind_direction_compass_dir` → wind_speed |
| col 8 | `si1145_ir` → compass | `wind_direction_compass_dir` → bmp_pressure | `wind_speed` → htu21d_humidity | `wg` → wind_direction |
| col 9 | `si1145_uv` → si1145_vis | `si1145_vis` → si1145_vis | `wind_direction` → bmp_slp | `wgd` → compass |
| col 10 | `sth31d_temp` → si1145_ir | `si1145_ir` → si1145_ir | `wind_direction_compass_dir` → bmp_pressure | `si1145_vis` → wg |
| col 11 | `sth31d_humidity` → si1145_uv | `si1145_uv` → si1145_uv | `si1145_vis` → si1145_vis | `si1145_ir` → wgd |
| col 12 | `wind_direction` → **sth31d_temp** | `sth31d_temp` → **sth31d_temp** | `si1145_ir` → si1145_ir | `si1145_uv` → si1145_vis |
| col 13 | `wind_direction_compass_dir` → sth31d_humidity | `sth31d_humidity` → sth31d_humidity | `si1145_uv` → si1145_uv | `wgd_compass_dir` → si1145_ir |
| col 14 | n/a | n/a | n/a | `sht31d_temp` → si1145_uv |
| col 15 | n/a | n/a | n/a | `sht31d_humidity` → wgd_compass_dir |

TSMS08's pasted order is the same as its Dec 2024 batch order (verified: MCP9808 vs. reference
temperature median difference 0.00 °C, r = 0.998).

**How the three temperature sensors were told apart** (bold cells above):
1. **Chip dropouts.** The BMP280 reports temperature and pressure, and the SHT31D (or HTU21D)
   reports temperature and humidity. When a chip drops out, all its readings go missing
   together. After the switch, this pattern holds exactly: e.g. TSMS02 `bmp_temp` is missing in
   10,457 of 10,457 pressure-missing minutes, and `sth31d_temp` in 11,802 of 11,802
   humidity-missing minutes. Before the switch it identifies the SHT31D at TSMS02 (2,833/2,833),
   TSMS03 (482 ⊂ 2,019), TSMS05 (2,725 ⊂ 3,048), and TSMS08 (45/45), and the BMP280 at TSMS02
   (257/257).
2. **Stable offsets between sensors.** Each station's sensors differ by a small, stable amount,
   and that amount carries across the switch. TSMS03: 0 / −0.12 / −0.25 °C before vs. 0 / −0.10 /
   −0.23 after (BMP / MCP / SHT). TSMS05: 0 / +0.05 / −0.27 vs. 0 / +0.08 / −0.24. TSMS02: the
   MCP9808 reads +0.16 warmer both before and after, and continues the MCP9808's values across
   midnight. TSMS08: 0 / −0.26 / −0.18 vs. 0 / −0.27 / −0.18.
3. **TSMS04 (least certain):** its three temperatures only ever drop out with the pressure, so
   test 1 can't separate them. Offsets relative to the HTU: +0.43 / +0.14 before vs. +0.37 / +0.12
   after (BMP / MCP). The daily profile of the pairwise differences also ranks this assignment
   first (mean r = 0.48, next best 0.31). No HTU bit-switching occurs in this window, so that
   signature couldn't be used. Confidence: medium.

Resolution can't be used as a test: all three read to 0.1 °C in this period.

### Jan–Mar 2024 re-mapping applied (2026-09-28)

`splice_chords_dec2024.py` rebuilds the CHORDS rows from the start of each station's CHORDS
record (after its SD-card record ends) to the last row before 2024-03-11 00:00 UTC, using the
mapping above. The SD-card/CHORDS boundary is found from the row index, since the SD and CHORDS
parts carry their own source index. Rows replaced: TSMS02 42,592; TSMS03 82,668; TSMS04 82,555;
TSMS05 82,690; TSMS08 78,354.

**Verification:** each sensor's median offset from the TSMS reference, before the switch vs.
11 Mar – 10 Apr 2024 (after):

| Station | BMP280 | MCP9808 | SHT31D | RH | Pressure |
|---|---|---|---|---|---|
| TSMS02 | −0.20 / −0.30 °C | −0.10 / 0.00 | −0.2 / −0.2 | −0.9 / −0.2 % | +1.8 / +1.0 hPa |
| TSMS03 | +1.30 / +1.20 | +1.10 / +1.10 | +1.0 / +1.0 | +2.8 / +2.0 | +0.9 / +0.6 |
| TSMS05 | +1.20 / +1.20 | +1.20 / +1.20 | +0.9 / +0.9 | +2.5 / +1.5 | +0.2 / 0.0 |
| TSMS08 | +0.20 / +0.20 | 0.00 / 0.00 | +0.1 / 0.0 | −1.1 / −1.5 | +0.9 / +0.9 |

Rain, CHORDS start → 10 Mar 2024: TSMS03 50.0, TSMS04 44.8, TSMS05 47.0 mm vs. Konya reference
44.6 mm. TSMS08's re-mapped rain is 7,959 mm, but 7,943 mm of it falls on dates already removed
in Phase 4 (the suspected faulty connector / tampering), so the genuine TSMS08 gauge problem shows
up in the correctly mapped data too.

---

## SF-20: TSMS02 anemometer disconnected (Mar 2023 – Jan 2024)

**Source:** Ankara maintenance log, 2024-01-17: the anemometer on station 2 "had developed a short
circuit" that was tripping the Raspberry Pi, "so it had been disconnected". The base was replaced at
the visit.

**Evidence in the data:** the last working reading is 2023-03-15 11:00 (that morning's 659 readings
track the reference, r = 0.62). The record then has a gap until 2023-03-31 12:17. From there,
`wind_speed` is exactly 0.0 in every one of 407,009 readings until 2024-01-11 10:02; the first
nonzero reading after the outage is at 10:03. Over the same period, the **Ankara reference** had a
median of 1.5 m/s, and 62% of its minutes were above 1 m/s. `wind_dir` kept varying (34,465
distinct values), consistent with a working vane and an unplugged anemometer.

**Handling:** `wind_speed` removed for the period (Step 1, `station_event:anemometer_disconnected`).
`wind_dir` is kept, but with speed missing it drops out of the speed-weighted direction averages and
the variable/non-variable regime split, which uses the reference speed and therefore still works.

**Before this fix:** the zeros passed every check (0 m/s is in range, and Phase 6 doesn't test wind),
so TSMS02 counted ≈ 9.5 months of false calm. That lowered its mean speed and inflated its speed
bias, and the Step 0 grid shows the zeros weren't gaps.

**Why it wasn't caught automatically:** calm is a real state, so the persistence rule for wind speed
(qc-framework.md, Step 4b) only marks zeros suspect when the reference or neighbours show wind. That
rule would have flagged this period; the maintenance log confirms it as a failure.

## SF-21: Degraded conditions found at the January 2024 visits

From the Ankara (2024-01-17) and Adana (2024-01-15) maintenance logs. Station mapping: Ankara
stations 0/1/2 = TSMS00/01/02; Adana stations 1/2/3 = TSMS06/07/08.

| Station | Condition | Possible effect |
|---|---|---|
| TSMS00 | Rain gauge significantly off level; may have been stuck on one side; dirty | Under-catch or no tips |
| TSMS01 | One side of the bucket much dirtier than the other (stuck); level slightly off | Under-catch or no tips |
| TSMS06 | Two ~5 mm pebbles stuck in the funnel orifice | Reduced or delayed catch |
| TSMS07 | Horizontal and vertical screens missing; bucket very dirty | Debris clogging |
| TSMS07 | Anemometer binding (corroded bearing); rotor replaced | Low speeds; raised starting threshold |

**Handling:** flagged, not removed (Step 1). The logs describe the state on the visit day, not when
it started, so the flag runs from the start of the record. Step 6 (neighbour check) is where the
start gets bounded: e.g. TSMS01's near-zero rain since 2023 (SF-16) may be this stuck bucket.

**Also from the logs, no data action:**
- TSMS05: radiation shield assembled with an open leaf in place of the closed leaf. No detectable
  effect: its pre-visit temperature offset from the reference matches TSMS03 (median +0.35 °C both).
- Konya: the router needed regular reboots to keep the Wi-Fi links up (gaps, not bad values). It was
  replaced on 2024-01-12.
- Ankara: RPi software updated on all three stations on 2024-01-17. Only TSMS02 shows the SF-10
  layout switch on 2024-03-11, so that update is unlikely to be its cause.
- TSMS08: the evaluation plan says its cup anemometer mechanism was replaced; the Adana log mentions
  only station 2 (TSMS07). The condition before replacement isn't described.

## SF-22 to SF-26: found by the QC stage 3 persistence checks (2026-09-29)

These came out of measuring flat-line runs before setting the Step 4b limits (see
[qc-framework.md](qc-framework.md) and the stage 3 changelog entry).

- **SF-23 (Ankara reference frozen logger)** is the clearest. On 25 mornings in June–August 2025,
  starting at 05:51–06:18 UTC, *every* variable repeats its previous value for 65–236 minutes,
  including wind speeds of 1.4–10.2 m/s, which never hold exactly steady in real wind. Several
  periods end at 08:00–08:01 UTC. This looks like the logger or transmission repeating the last
  record, not measurements. No 3D-PAWS station and no other reference shows this pattern; the only
  other candidate (Adana reference, 2022-12-14, 68 min) is a calm, foggy night with 0 m/s and is kept.
- **SF-24 and SF-25** are single-sensor flat lines at the Ankara reference (humidity at exactly 10%,
  vane at exactly 0°) in conditions where the value should move.
- **SF-26** is a candidate, not a finding yet: long zero-speed runs are normal at Adana at night
  (the 3D-PAWS neighbours agree through 2024), but in 2025 the neighbours often show wind during
  them. It needs the Step 6 neighbour logic before anything is marked.
- **SF-22 (TSMS01 vane)** reads exactly 0.0°, the typical value of a disconnected or failed
  potentiometer vane. Only runs with enough wind are removed automatically.
- **Also removed by Step 4b, not given IDs:** TSMS03 `bmp2_temp` stuck at 7.6 °C for 187 min
  (2024-12-05); TSMS03 vane at 0.0° during its October 2022 fault; TSMS02 vane at 0.0° in January
  2024 (around the visit); short stuck-vane runs at TSMS06, 07 and 08. The TSMS03 HTU21D stuck at
  −46.85 °C for 77 h (Oct 2022) is already removed by Phase 4 (`station_rules`).

## SF-26 to SF-31: what the diagnostic figures showed (2026-09-29)

Building a figure for every failure meant looking at each one at full resolution. Every
statement below was checked against the reformatted minute data.

**SF-09, Ankara reference rain ×10.** On wet days, reference ÷ TSMS00 is 0.97 before 6 March 2023
and 9.96 after (126 wet days). Reference totals after that date are 11,253 mm vs. TSMS00's 833 mm.

On the same day the reporting step changes:
- the last value finer than 0.1 mm is at 2023-03-06 04:21;
- from 11 March every value is a multiple of 0.1 mm;
- duplicate timestamps around 02:02 on 6 March suggest a logger change.

Divided by 10 it tracks the 3D-PAWS gauges (figures SF-09, SF-29). This is a scaling error, not
weighing-gauge noise. It's flagged, not corrected: that's a team decision, and ideally TSMS confirms it.

**SF-26, Adana reference anemometer outage.** The last normal hour is 2025-08-09 13:00 UTC. The
anemometer then reads exactly 0 m/s in ≈ 100% of minutes until 2025-10-13 08:00; the July daily mean
was ≈ 1.9 m/s. The Step 6 calm check missed it: Adana's 2 m 3D-PAWS winds are mostly below 1.5 m/s,
so two neighbours rarely clear the bar together. It's now a documented `remove` event.

**SF-28, Konya courtyard watering (reversed).** In Jul–Aug 2023 all three Konya gauges tip on dry
days, mostly at 09:50–10:00 UTC and ≈ 13:50, at a median reference humidity of 27% (the stations'
own sensors agree). The reference recorded 0.6 mm in those two months; TSMS03/04/05 recorded 83,
139 and 104 mm. That's a watering schedule landing in the 3D-PAWS gauges.

The Step 6 dead-gauge rule flagged the *reference* on 12 days because it assumes one gauge fails
while the others are right; here one cause hit all three 3D-PAWS gauges. The same signature appears
at TSMS05 in July 2025, the month of its SF-12 junk rain (2,108 mm). The rain-vs-humidity flag
(`rain_low_rh`) catches these tips.

**SF-29, TSMS02 rain gauge dead.** 7 tips from 2023-03-31 12:17 to 2024-01-04, exactly the span
of its unplugged anemometer (SF-20). Possibly the same disconnected harness or connector; ask
whoever serviced it.

**SF-30, TSMS01 anemometer low.** Over minutes when TSMS00 reads > 1 m/s, TSMS01 reads a monthly
median of 0.24–0.35 of TSMS00 from 2023 (0.4–0.5 in late 2022), 10 m away; TSMS02 reads 0.5–0.9.
Hourly means in 2024 lie far below the 1:1 line and are nearly proportional, which points to an
instrument fault rather than siting. SMN found a misplaced magnet halves the reading. Not removed,
because it still tracks the wind; check the unit.

**SF-31, Adana reference small amounts.** 290 of the reference's 429 wet days at the 0.2 mm
threshold carry 0.2–1.0 mm; the 3D-PAWS gauges record far fewer such days. They cluster in the dry
summers (73 of 92 days in Jul–Sep 2023, 60 in Jul–Sep 2024), so they're likely dew or condensation,
not rain. This is most of why Adana's POD is low at 0.2 mm and recovers at 1.0 mm.

## Figures

Diagnostic figures for SF-09, 17, 20–31 are in `plots/diagnostics/3dpaws-sensor-failure/` and
`plots/diagnostics/tsms-sensor-failure/`, each with a README of captions. They're made by
`scripts/plotter/plot-sensor-failures.py` from the reformatted (pre-QC) minute data. `plots/` is
gitignored.
