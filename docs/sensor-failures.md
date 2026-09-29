# Sensor failure catalog

Running catalog of sensor failures and malfunctions found in the 3D-PAWS and TSMS data: what
failed, when, how it was identified, and how the data is handled. Changes to cleaning logic are
logged in [logic-changelog.md](logic-changelog.md). Differences from the TSMS report are in
[method-differences.md](method-differences.md).

**Status key:** `Removed` = excluded from `data/cleaned` · `Handled` = partly addressed by a
cleaning filter · `Open` = identified, not yet handled · `Suspected` = needs confirmation

Removals are configured in `sensor_failures` at the top of
`scripts/outliers/outlier-removal.py`. They're applied in Phase 4 and logged in each station's
`*_outliers.csv` with `outlier_type = sensor_failure`. Times are as recorded in the data files
(timezone not yet verified; see method-differences G5).

Last updated 2026-09-28 (SF-10 fixed for both periods; SF-01, 02 fixed; SF-11 to SF-15 added).

---

## Summary

| ID | Station | Sensor / column | Failure | Period | Status |
|---|---|---|---|---|---|
| SF-01 | TSMS03 (Konya) | ~~SHT31D / `sth_hum`~~ | **Reclassified 2026-09-28: not a sensor failure.** The "humidity" is the UV sensor (SI1145_UV) under the wrong label (SF-10) | 2024-12-01 00:00 → end of `sth_hum` record | **Fixed 2026-09-28** (splice); removal deleted |
| SF-02 | TSMS04 (Konya) | ~~HTU21D / `htu_hum`~~ | **Reclassified 2026-09-28: not a sensor failure.** The "humidity" is the precipitation column under the wrong label (SF-10) | 2024-11-30 23:59 → end of record | **Fixed 2026-09-28** (splice); removal deleted |
| SF-03 | TSMS00–04 | HTU21D / `htu_temp`, `htu_hum` | "Bit-switching": temperature and humidity values swap at 1–4 min intervals | Hours to ~2 months at a time, pre-upgrade | Handled |
| SF-04 | Konya HTU21Ds (TSMS03–05) | HTU21D / `htu_hum` | Reads +8 to +13 %RH high in winter, ~0 in summer | Every winter, Oct–May | Open |
| SF-05 | TSMS02, 03, 04, 05, 08 | ~~Tipping bucket~~ / `tipping` | Implausible rainfall (≈ 47,600 to 2.2 million mm/yr). **Root cause 2026-09-28: SF-10** (the "rain" column holds temperature, humidity, wind, or light values) | Jan–Mar 2024 and Dec 2024 → end | Dec 2024+ fixed 2026-09-28 (Konya rain now tracks the reference); Jan–Mar 2024 open |
| SF-06 | TSMS02 (Ankara) | SHT31D / `sth_hum` | Large low bias (−25 %RH vs. reference) | Post-upgrade | Suspected |
| SF-07 | TSMS06 (Adana) | SHT31D / `sth_hum` | Low bias (−8 %RH vs. reference) | Post-upgrade | Suspected |
| SF-08 | TSMS03, TSMS04 | ~~Anemometer~~ / `wind_speed` | Speeds far above reference (bias ≈ 21 and 6 m/s), r ≈ 0. **Root cause 2026-09-28: SF-10** (e.g. TSMS03's "wind_speed" is HTU21D humidity from Dec 2024, TSMS04's is visible light) | Jan–Mar 2024 and Dec 2024 → end | Dec 2024+ fixed 2026-09-28; Jan–Mar 2024 open |
| SF-09 | Ankara TSMS reference | Rain gauge / `total_rainfall` | ≈ 3,500 mm/yr with 1-min spikes up to 31.5 mm; hundreds of mm in many months from Mar 2023 (e.g. 979 mm May 2023 vs. 84 mm at TSMS00) but plausible in others. Separate pipeline from SF-10 (TSMS text file). **Lead (2026-09-28):** Ankara's reference uses an **accumulation (weighing) gauge**, while Konya, Adana and all 3D-PAWS use tipping buckets. If 1-min rain is derived from differences in accumulated weight, sensor noise and baseline shifts (WMO-No. 8 Vol. I Ch. 6) counted as positive increments would inflate totals | Intermittent, Mar 2023 → end | Suspected |
| SF-10 | TSMS02, 03, 04, 05, 08 | **All columns** (data pipeline, not a sensor) | CHORDS export column misalignment: data rows are in a different column order than the file header, so every variable is mislabeled | CHORDS start (12–16 Jan 2024) → 2024-03-10 23:59 UTC, and 2024-12-01 → end of record | **Fixed 2026-09-28** (`splice_chords_dec2024.py`): Dec 2024+ from the correctly labeled batch; Jan–Mar 2024 re-mapped by inference (except SF-15) |
| SF-15 | TSMS04 (Konya) | HTU21D, BMP280, MCP9808 temperatures | Sensor identity of the three temperature columns can't be established in the re-mapped Jan–Mar 2024 window (SF-10) | 2024-01-12 09:10 → 2024-03-10 20:31 | **Excluded** (written as missing in `data/reformatted`); see [methods.md](methods.md) §3 |
| SF-16 | Several 3D-PAWS gauges | Tipping bucket / `tipping` | Months of near-zero rain while the reference and neighbouring gauges record rain (possible clogging, a stuck bucket, or a connection fault). From the 2026-09-28 cleaned data: TSMS03 0–1 mm/month Apr–Sep 2024 (Konya reference 12–63); TSMS08 0–1 mm Apr–Sep 2024 (Adana ref 14–92); TSMS01 0–7 mm for most of 2023–2024; TSMS02 0 mm Aug–Oct 2024 and Feb–Mar 2025; TSMS00 0 mm Jun–Nov 2025. Overlaps SF-11 (TSMS04 from Apr 2025) | See description | Suspected; not yet bounded or removed |
| SF-17 | TSMS06 (Adana) | All temperature and humidity sensors (`mcp9808`, `bmp2_temp`, `sth_temp`, `sth_hum`) | Exactly 0.0 on all sensors at once (a logger writing zeros, not readings). 0 °C passes range checks. Median difference vs. reference −19.6 °C / −63 %RH in those minutes | Feb–May 2025 (all sensors, ≈ 60,000 min); Sep–Oct 2024 (`sth_*` only, ≈ 35,000 min) | Suspected; not yet removed. Candidate for `sensor_failures` or an automatic all-zero check (PF-22) |
| SF-18 | TSMS04 (Konya) | BMP280 / `bmp2_pres` | Pressure bias vs. reference drifts from ≈ +1.5 hPa (Q4 2022) to ≈ −1.6 hPa (mid-2024 onward); TSMS03 and TSMS05 drift much less. Suggests sensor drift or a calibration change | Gradual, 2022 → 2024, then stable | Suspected |
| SF-11 | TSMS04 (Konya) | Tipping bucket / `tipping` | Isolated 1-min values of 37–39 mm (not physical; Phase 3 removes > 32), and almost no rain recorded from Apr 2025 (0–3 mm/month vs. 20–49 mm at the reference and TSMS03/05) | Apr 2025 → end | Suspected |
| SF-12 | TSMS05 (Konya) | Tipping bucket / `tipping` | Monthly totals of 2,108 mm (Jul 2025) and 314 mm (Nov 2025) vs. 20 / 25 mm at the reference; other months track the reference | Jul 2025, Nov 2025 | Suspected |
| SF-13 | TSMS01 (Ankara) | BMP280 / `bmp2_temp` | Dec 2024+ median 4.5 °C vs. ≈ 14 °C for the station's other temperature sensors | Dec 2024 → end (not yet bounded) | Suspected |
| SF-14 | TSMS06, TSMS08 (Adana) | BMP280 / `bmp2_pres` | TSMS06 Dec 2024+ median 673 hPa (Adana ≈ 1010); TSMS08 mostly `-999.9`, a null marker Phase 1 doesn't recognise (it handles `-999.99`) | Dec 2024 → end (not yet bounded) | Suspected |

Previously handled in code before this catalog (Phase 4 of `outlier-removal.py`): TSMS04
fabrication test tips (start of record → 2022-08-31), TSMS08 rainfall from a suspected faulty
connector or tampering (seven date ranges, 2023-04 to 2024-03), and month-specific manual
threshold removals for several temperature and pressure sensors (`station_rules`).

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
