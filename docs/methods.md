# Methods: data provenance and processing notes

Draft methods text for reporting. It states what was done to the data and why, at a level
suitable for a methods section. Technical detail and evidence live in the linked documents
([sensor-failures.md](sensor-failures.md), [logic-changelog.md](logic-changelog.md),
[siting.md](siting.md)).

Last updated 2026-09-28.

---

## 1. Data sources

3D-PAWS observations come from two sources:

- **SD cards** stored on each station, from installation (Aug–Nov 2022) to the station visits of
  12–16 January 2024.
- **CHORDS** (cloud database) from those visits to 30 November 2025, retrieved as two downloads:
  one covering January 2024 – November 2025, and a second, separately exported batch covering
  1 December 2024 – 30 November 2025.

CHORDS retains only two years of data, so records before late 2024 can't be re-downloaded.

TSMS reference observations were provided by TSMS as a plain-text file. Reference instruments
(docs/TSMS Sensors.docx): wind speed Lastem DNA002 (1-min averages; gusts sampled every 6 s),
wind direction Lastem DNA011, temperature and humidity Rotronic MP101A, pressure Druck RPT200.
Precipitation at the Ankara reference is measured with an accumulation (weighing) gauge; the
Konya and Adana references and all 3D-PAWS stations use tipping-bucket gauges.

3D-PAWS sensors in this study (datasheets in `docs/datasheets/`; bare-component values, before
shield, siting, calibration and maintenance effects):

| Sensor | Variable | Datasheet accuracy | Other specs | Stations / period |
|---|---|---|---|---|
| BMP280 | Pressure, temperature | ±1.0 hPa absolute (0–65 °C), ±1.7 hPa (−20–0 °C); relative ±0.12 hPa; T ±1.0 °C (0–65 °C) | Drift ±1.0 hPa/yr; solder drift −0.5 to +2 hPa. Bosch min/max = ±3σ. T channel reads the die (cross-check only) | All nine, whole record |
| HTU21D | Humidity, temperature | ±2 %RH typ (20–80 %RH, 25 °C); T ±0.3 °C typ | Hysteresis ±1 %RH; drift 0.5 %RH/yr; τ63 5 s (10 s max) | TSMS00–08 to Jan 2024; kept at TSMS00, 01, 04, 07 |
| SHT31D | Humidity, temperature | ±2 %RH typ; T ±0.3 °C typ (10–55 °C) | Hysteresis 0.8 %RH; drift < 0.25 %RH/yr, T < 0.03 °C/yr; τ63 8 s; long exposure > 80 %RH can offset RH (+3 %RH after 60 h), recovering | TSMS02, 03, 05, 06, 08 from Jan 2024 |
| MCP9808 | Temperature | ±0.25 °C typ (−40–125 °C), ±0.5 °C max (−20–100 °C) | Resolution 0.0625 °C | All nine |
| Cups + SS451A Hall switch | Wind speed | No component spec. **SMN Argentina wind tunnel (6 units, 5–30 m/s):** linear (R² ≥ 0.998) but reads **10–13% low** vs. a Pitot reference; best fit factor 2.90 + 0.40 m/s offset vs. the firmware's 2.64 | 2 pulses/rev, calibration factor 2.64. **Start-up ≤ 1.2 m/s** (5 of 6 units responded at 1.0 m/s, one at 1.2 m/s; new units, field-aged not tested). RPi and Particle agree (0.055 m/s) | All nine |
| Vane + AS5600 magnetic encoder | Wind direction | No component spec (set by alignment and calibration) | 12-bit (0.09°); no starting threshold stated | All nine |
| Tipping bucket + SS451A | Rain | Single-rate calibration; < 5% error at 0.1–30 mm/h (2016–17 lab test) | 0.2 mm/tip | All nine |

Sources: BMP280 from the Bosch datasheet (BST-BMP280-DS001-26, as summarized in the 3D-PAWS sensor
specifications doc; the repo PDF is encrypted); SHT3x from the repo copy (v0.93, May 2015; the 2022 v7
datasheet gives ±0.2 °C); others from the repo PDFs and the 3D-PAWS manual. **Wind and rain have no
uncertainty spec** beyond the SMN tunnel tests (`docs/datasheets/3DPAWS_anemometer_test_report_EN.pdf`),
so the WMO class for those rests on the field comparison. The vane's starting threshold is untested. The 3D-PAWS team's uncertainty budgets (Annex 1.G Table 2 method) cover the **current** build
(SHT45, BMP581), not the sensors used here; a study-sensor budget is still to do (PF-42). The TSMS
reference sensor specifications are being compiled.

## 2. Correction of mislabeled CHORDS columns

In the January 2024 – November 2025 CHORDS files for stations TSMS02, TSMS03, TSMS04, TSMS05
and TSMS08, the data rows for two periods are in a different column order than the file header,
so values were assigned to the wrong variables when read by header. The stations are on both
Raspberry Pi (TSMS02–05) and Particle (TSMS08) dataloggers. TSMS00, TSMS01, TSMS06 and TSMS07
are unaffected.

**Period 1: 1 December 2024 – 30 November 2025.** Replaced with the separately exported CHORDS
batch for the same period, whose header is correct, matched by column name. At the four
unaffected stations this batch is identical to the original data in every column, which confirms
the correspondence.

**Period 2: start of the CHORDS record (12–16 January 2024) – 10 March 2024 23:59 UTC.** At all
five affected stations the column order changes at the same instant, 11 March 2024 00:00 UTC,
and never reverts. The cause is unknown; a datalogger firmware or software change, or a change in
CHORDS itself, is suspected. No correctly labeled copy of this period exists. Columns were
re-assigned by inference, using:

1. value ranges and signatures (e.g. compass-direction text, pressure and sea-level pressure
   magnitudes, rainfall's mostly-zero record, wind direction's 0–360° range);
2. co-occurring dropouts of readings from the same sensor chip (the BMP280 reports temperature
   and pressure; the SHT31D/HTU21D reports temperature and humidity);
3. the small, stable temperature offsets between each station's sensors, which carry across the
   11 March 2024 layout change.

After re-assignment, each variable's offset from the TSMS reference is consistent before and
after the layout change, and Konya rainfall agrees with the reference (e.g. 44.8–50.0 mm vs.
44.6 mm at the reference, 12 January – 10 March 2024).

**Why temperature is mostly Class D (checked 2026-09-29).** The earlier analysis's temperature errors were the same size
(MCP9808 RMSE 0.5–1.0 °C then, 0.43–0.99 °C now); what changed is the yardstick. Annex 1.G asks that 95% of 1-min
differences fall inside ±1.0 K for Class C, and an RMSE of 0.65 K already means a 95th percentile of ≈ 1.25 K. The
differences follow a day–night cycle, the signature of a naturally ventilated radiation shield: the median difference by
hour runs from −0.25 to +0.55 °C (TSMS00), −0.62 to +0.60 (TSMS04) and −0.20 to +0.80 (TSMS07). The mean bias stays
near zero, but the swing sets the tails: at TSMS07, 99% of night-time differences are within 1 K against 80% by day.
The 3D-PAWS team's own uncertainty budget (shield + environment ≈ 0.35 K each at k = 1) puts even a calibrated unit at
the Class C limit (1.0 K), so the result is what the shield physics predicts. Konya is worst (courtyard wall). A
timing offset contributes little (shifting 3D-PAWS by 2 min lowers the MAE by ≈ 3%). Humidity looked better in the
earlier analysis because its HTU21D filter compared against the reference and removed readings that disagreed.

**Suggested methods text:**

> For stations TSMS02–TSMS05 and TSMS08, CHORDS records from 12–16 January to 10 March 2024
> and from 1 December 2024 onward were delivered with columns out of order relative to the file
> header. The December 2024 – November 2025 period was replaced with a separately exported,
> correctly labeled CHORDS batch. For January – March 2024, for which no correctly labeled copy
> exists, variables were re-assigned from their value characteristics, co-occurring sensor
> dropouts, and inter-sensor temperature offsets, and verified against the TSMS reference.

## 3. Exclusion: TSMS04 temperature, 12 January – 10 March 2024

At TSMS04, three columns in period 2 are clearly air temperatures, but which column belongs to
which sensor (HTU21D, BMP280, MCP9808) can't be determined reliably:

- all three drop out only together, so the chip-dropout test can't separate them;
- a ~13-hour data gap around the 11 March 2024 layout change prevents a continuity check;
- the offset and diurnal-pattern evidence favours one assignment only weakly.

Assigning them anyway would risk attributing one sensor's behaviour (e.g. the BMP280's
enclosure warming) to another in the sensor-specific statistics, and such an error couldn't be
detected downstream. The three temperature series for **TSMS04, 12 January 2024 09:10 –
10 March 2024 20:31** are therefore **excluded from the analysis** (written as missing). This
covers about 58 days of three sensors at one of nine stations. TSMS04's other variables for the
period (rainfall, wind, pressure, humidity) are identified with confidence and retained. The raw
values are preserved in the raw CHORDS file.

**Why temperature is mostly Class D (checked 2026-09-29).** The earlier analysis's temperature errors were the same size
(MCP9808 RMSE 0.5–1.0 °C then, 0.43–0.99 °C now); what changed is the yardstick. Annex 1.G asks that 95% of 1-min
differences fall inside ±1.0 K for Class C, and an RMSE of 0.65 K already means a 95th percentile of ≈ 1.25 K. The
differences follow a day–night cycle, the signature of a naturally ventilated radiation shield: the median difference by
hour runs from −0.25 to +0.55 °C (TSMS00), −0.62 to +0.60 (TSMS04) and −0.20 to +0.80 (TSMS07). The mean bias stays
near zero, but the swing sets the tails: at TSMS07, 99% of night-time differences are within 1 K against 80% by day.
The 3D-PAWS team's own uncertainty budget (shield + environment ≈ 0.35 K each at k = 1) puts even a calibrated unit at
the Class C limit (1.0 K), so the result is what the shield physics predicts. Konya is worst (courtyard wall). A
timing offset contributes little (shifting 3D-PAWS by 2 min lowers the MAE by ≈ 3%). Humidity looked better in the
earlier analysis because its HTU21D filter compared against the reference and removed readings that disagreed.

**Suggested methods text:**

> TSMS04 temperature data from 12 January to 10 March 2024 were excluded because a change in
> the datalogger's column order made it impossible to establish which sensor each temperature
> series came from.

## 4. Recovered data and sensitivity

The period-2 data at TSMS02, TSMS03, TSMS05 and TSMS08 (and TSMS04's non-temperature
variables) is **recovered by inference**, not taken from a correctly labeled source. The evidence
is strong, but to be transparent, results should be checked with and without these windows:

| Station | Recovered window (data timestamps) |
|---|---|
| TSMS02 | 2024-01-16 11:36 – 2024-03-10 23:58 |
| TSMS03 | 2024-01-12 09:34 – 2024-03-10 20:28 |
| TSMS04 | 2024-01-12 09:10 – 2024-03-10 20:31 (temperatures excluded) |
| TSMS05 | 2024-01-12 09:43 – 2024-03-10 20:37 |
| TSMS08 | 2024-01-15 09:21 – 2024-03-10 23:58 |

The sensitivity run is tracked as potential-fixes PF-31.

## 5. Completeness and pairing

- **Daily completeness (per instrument):** after quality control, a variable's readings for a
  calendar day (UTC) are retained only if at least 80% of the day's 1,440 minutes have a valid
  value. This matches the TSMS report's criterion, but it's applied to all analyses, not only
  daily ones.
- **Pairing:** 3D-PAWS and reference observations are matched by timestamp at 1-minute
  resolution before any aggregation. Hourly and daily values are computed from the paired
  minutes only (mean; sum for precipitation; speed-weighted vector mean for wind direction), and
  a period is retained only if at least 80% of its minutes are paired. For wind variables, a
  minute counts as paired when both anemometers report a speed.

**Why temperature is mostly Class D (checked 2026-09-29).** The earlier analysis's temperature errors were the same size
(MCP9808 RMSE 0.5–1.0 °C then, 0.43–0.99 °C now); what changed is the yardstick. Annex 1.G asks that 95% of 1-min
differences fall inside ±1.0 K for Class C, and an RMSE of 0.65 K already means a 95th percentile of ≈ 1.25 K. The
differences follow a day–night cycle, the signature of a naturally ventilated radiation shield: the median difference by
hour runs from −0.25 to +0.55 °C (TSMS00), −0.62 to +0.60 (TSMS04) and −0.20 to +0.80 (TSMS07). The mean bias stays
near zero, but the swing sets the tails: at TSMS07, 99% of night-time differences are within 1 K against 80% by day.
The 3D-PAWS team's own uncertainty budget (shield + environment ≈ 0.35 K each at k = 1) puts even a calibrated unit at
the Class C limit (1.0 K), so the result is what the shield physics predicts. Konya is worst (courtyard wall). A
timing offset contributes little (shifting 3D-PAWS by 2 min lowers the MAE by ≈ 3%). Humidity looked better in the
earlier analysis because its HTU21D filter compared against the reference and removed readings that disagreed.

**Suggested methods text:**

> Observations were quality controlled at 1-minute resolution, and days with fewer than 80% of
> valid 1-minute observations for a variable were excluded. 3D-PAWS and TSMS observations were
> paired by timestamp at 1-minute resolution, and hourly and daily values were computed from
> paired observations only, retaining periods with at least 80% paired minutes.

## 6. Comparison with WMO requirements

3D-PAWS is positioned as a **baseline-tier** network in the sense of the *Vision for the WMO
Integrated Global Observing System in 2040* (Ch. 1, p. 7): between the *reference* tier (highest
performance, calibrated, with uncertainty estimates) and the *comprehensive* tier (little
management, no QC), a baseline network is managed, quality-controlled and WIGOS-metadata
compliant (docs/3D-PAWS as a Baseline Tier Observing Network.pdf). Vision 2040 notes that users
choose observations by tier and application: for the onset of severe weather, "timeliness and
spatial and temporal resolution are more important than low uncertainty of measurements", while
long-term trend monitoring may need a reference network.

Two complementary WMO frameworks are used. Neither is a claim that 3D-PAWS is reference-grade.
Both describe fitness for purpose as a complementary network (WMO-No. 8 Vol. III, Ch. 1, Annex 1.A:
low-cost AWSs "may have their place in a tiered network").

1. **Measurement Quality Classification** (WMO-No. 8 Vol. I, Ch. 1, Annex 1.G): Class A/B/C (aligned
   with OSCAR goal / breakthrough / threshold) or D. A class is achieved when at least 95% of paired
   differences lie within its target system uncertainty (k = 2). Annex 1.A required and achievable
   uncertainties are reported alongside for context.
2. **Application-specific requirements** (WMO OSCAR/Requirements): the RMSE of paired differences (k =
   1) is compared with the goal / breakthrough / threshold levels for high-resolution NWP,
   nowcasting / very-short-range forecasting, agricultural meteorology, and hydrology.

Comparisons use the WMO averaging times: 1-min values for temperature, humidity and pressure;
10-min means for wind; daily totals for precipitation (hourly for NWP and hydrology), excluding
periods when both gauges are dry.

**Interpretation.** The paired differences include the uncertainty of the TSMS reference and, where
siting differs, representativeness effects, which the WMO scheme treats separately (Annex 1.D).
The reported classes are therefore conservative (lower bounds on 3D-PAWS performance). Wind results
at Konya (courtyard next to a brick wall) and Ankara (nearby hill) reflect siting and aren't
interpreted as sensor performance. At Konya, the sheltered, weak winds make absolute errors small, so
high classes there are an artifact.

**Why temperature is mostly Class D (checked 2026-09-29).** The earlier analysis's temperature errors were the same size
(MCP9808 RMSE 0.5–1.0 °C then, 0.43–0.99 °C now); what changed is the yardstick. Annex 1.G asks that 95% of 1-min
differences fall inside ±1.0 K for Class C, and an RMSE of 0.65 K already means a 95th percentile of ≈ 1.25 K. The
differences follow a day–night cycle, the signature of a naturally ventilated radiation shield: the median difference by
hour runs from −0.25 to +0.55 °C (TSMS00), −0.62 to +0.60 (TSMS04) and −0.20 to +0.80 (TSMS07). The mean bias stays
near zero, but the swing sets the tails: at TSMS07, 99% of night-time differences are within 1 K against 80% by day.
The 3D-PAWS team's own uncertainty budget (shield + environment ≈ 0.35 K each at k = 1) puts even a calibrated unit at
the Class C limit (1.0 K), so the result is what the shield physics predicts. Konya is worst (courtyard wall). A
timing offset contributes little (shifting 3D-PAWS by 2 min lowers the MAE by ≈ 3%). Humidity looked better in the
earlier analysis because its HTU21D filter compared against the reference and removed readings that disagreed.

**Suggested methods text:**

> Agreement with WMO requirements was assessed using the Measurement Quality Classification of
> WMO-No. 8 (Vol. I, Annex 1.G) and the application-specific requirements of WMO OSCAR, at the
> averaging times specified in WMO-No. 8 Annex 1.A. Because differences from the co-located
> reference include the reference's own uncertainty and siting effects, the resulting classes are
> conservative estimates of 3D-PAWS performance. Wind results at Konya and Ankara are dominated by
> station siting and are reported for completeness only.

## 7. Other documented exclusions and limitations

- **Reference data quality:** the QC is applied to the TSMS reference as well, using only the
  reference's own record (it is never judged against 3D-PAWS in these steps). Persistence checks
  removed a frozen record at the Ankara reference on 25 mornings in summer 2025 (SF-23) and two
  stuck sensors there (SF-24, SF-25). These are reported to TSMS.
- **Maintenance metadata (QC Step 1):** events from the January 2024 site visits (Konya 12 Jan,
  Adana 15 Jan, Ankara 17 Jan; logs in `docs/Maintenance-Logs/`) and the evaluation plan are
  encoded in [station-events.csv](station-events.csv). Log station numbers map to IDs as: Ankara
  0/1/2 = TSMS00/01/02, Konya 1/2/3 = TSMS03/04/05, Adana 1/2/3 = TSMS06/07/08. One period is
  removed: TSMS02 wind speed, 31 Mar 2023 – 11 Jan 2024 (anemometer disconnected; SF-20).
  Degraded rain gauges and the TSMS07 anemometer before the visits are flagged, not removed
  (SF-21). HTU21D → SHT31D upgrades (TSMS02, 03, 05, 06, 08) mark where sensor statistics change
  instrument. TSMS00, 01, 04, 07 kept their original sensors as the 3D-PAWS benchmarks.

- **Sensor and data issues:** see [sensor-failures.md](sensor-failures.md).
- **Siting:** 2-m wind at Konya (courtyard next to a brick wall) and Ankara (nearby hill) is not
  representative; see [siting.md](siting.md).
- **Cleaning logic changes:** see [logic-changelog.md](logic-changelog.md).
