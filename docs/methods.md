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

TSMS reference observations were provided by TSMS as a plain-text file. Precipitation at the
Ankara reference is measured with an accumulation (weighing) gauge; the Konya and Adana
references and all 3D-PAWS stations use tipping-bucket gauges.

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

**Suggested methods text:**

> Observations were quality controlled at 1-minute resolution, and days with fewer than 80% of
> valid 1-minute observations for a variable were excluded. 3D-PAWS and TSMS observations were
> paired by timestamp at 1-minute resolution, and hourly and daily values were computed from
> paired observations only, retaining periods with at least 80% paired minutes.

## 6. Comparison with WMO requirements

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

**Suggested methods text:**

> Agreement with WMO requirements was assessed using the Measurement Quality Classification of
> WMO-No. 8 (Vol. I, Annex 1.G) and the application-specific requirements of WMO OSCAR, at the
> averaging times specified in WMO-No. 8 Annex 1.A. Because differences from the co-located
> reference include the reference's own uncertainty and siting effects, the resulting classes are
> conservative estimates of 3D-PAWS performance. Wind results at Konya and Ankara are dominated by
> station siting and are reported for completeness only.

## 7. Other documented exclusions and limitations

- **Sensor and data issues:** see [sensor-failures.md](sensor-failures.md).
- **Siting:** 2-m wind at Konya (courtyard next to a brick wall) and Ankara (nearby hill) is not
  representative; see [siting.md](siting.md).
- **Cleaning logic changes:** see [logic-changelog.md](logic-changelog.md).
