# QC framework for 3D-PAWS and TSMS reference data

Proposed quality-control procedure for `scripts/outliers/outlier-removal.py`, for discussion with
the team. Each step has **one job**, runs in a fixed order, and logs what it changed and why.
Implementation status is tracked per step. Change history: [logic-changelog.md](logic-changelog.md).
Backlog item: [potential-fixes.md](potential-fixes.md) PF-35.

Last updated 2026-09-29 (Steps 0–7 implemented; Step 8 flag columns next).

---

## Key points

- **Remove only what's shown to be wrong; flag the rest.** Clear errors are removed: missing-value
  codes, impossible values, documented faults, logger zeros, stuck sensors, frozen loggers.
  Unusual readings are only flagged.
- **An unusual reading survives only if a neighbour saw it too.** For temperature, 61–95% of the
  flagged readings turn out to be real midday convection. The old filter was deleting them, at the
  reference too.
- **Steady offsets never decide anything.** Each instrument is compared with its own recent
  readings, so a shield warm bias or the Konya courtyard neither confirms nor removes data.
- **The reference can back up a 3D-PAWS reading but is never the reason one is removed.**
- **Wind and rain are never removed on statistics alone.** Wind is checked for jumps, stuck vanes
  and calm spells. Rain is checked day by day against the other gauges and kept with a flag
  (`tipping_flag`).
- **Limits were set from measured data,** and three planned values changed after measuring:
  - Humidity runs at 80% or above are exempt from the stuck-sensor check. The Adana reference sits
    at 99% for up to 20 h in fog, and Konya at 85–91% on freezing nights; both are real.
  - Pressure may stay flat for up to 3 h, not 2 h: genuine plateaus reach 2.6 h.
  - A vane counts as stuck only after at least 60 minutes of wind strong enough to turn it.

## Principles

These come from WMO-No. 8 (Vol. I Ch. 6 §6.7 and Table 6.7; Vol. III Ch. 1 §1.5; Vol. V Ch. 1).

1. **Flag suspect data; remove only data shown to be erroneous.** "In general, flag suspect values;
   flag and remove erroneous values" (Vol. I, Table 6.7). Every value ends with a status: *good*,
   *suspect*, or *failed*, plus the reason.
2. **Use independent evidence only.** A 3D-PAWS value is never removed for disagreeing with the
   TSMS reference, the instrument it's being compared against. Evidence comes from physical limits,
   the station's own other sensors, co-located 3D-PAWS stations, diagnostics, and site logs.
3. **Thresholds come from instrument specifications and site climatology,** not from the data's own
   statistical spread (which fails on quantized minute data; see Step 5).
4. **Auditable and reversible.** Raw data is never overwritten. Every change is logged with its
   original value, so any step can be undone or re-tuned.
5. **Order matters.** Cheap, certain checks come first and statistical ones later. Each step works on
   data that has passed the steps before it, so later steps aren't fooled by errors earlier steps
   would have caught.
6. **Ambiguous cases get human review** against maintenance logs. WMO calls this the "more
   subjective" second stage of precipitation QC.

## The steps

| Step | One job | Checks | Outcome | Status |
|---|---|---|---|---|
| **0. Structure** | Is the record well-formed? | Timestamps (sort, remove duplicates keeping the first); regular 1-min grid with empty rows for missing minutes; null markers (any value ≤ −990); column-layout guard | Null markers → missing (logged). Layout problems → **warning** for review | **Implemented 2026-09-29** |
| **1. Metadata & diagnostics** | Was the system known to be working? | Documented failures and exclusions (sensor-failures catalog); maintenance visits and sensor changes; firmware/CHORDS events; battery and power (`Battery Charge (%)`, Particle stations); logger resets | Failed (documented faults) or suspect (degraded conditions from site logs) | **Implemented 2026-09-29** ([station-events.csv](station-events.csv)); battery diagnostics unavailable |
| **2. Range** | Is the value possible here? | Instrument and physical limits; then climatological limits by site and month | Failed | Partly (fixed limits only; climatology planned, PF-39) |
| **3. Internal consistency** | Do this station's variables agree with each other? | Logger zeros: a humidity sensor at exactly 0 %RH in the same minute as a temperature sensor at exactly 0.0 °C (SF-17); rain vs. humidity | Failed (logger zeros), or suspect (rain with RH < 60%: flag only) | **Implemented 2026-09-29** |
| **4a. Step (rate of change)** | Is the change since the last minute plausible? | Minute-to-minute change per variable (TSMS Table 1 limits: 2 °C, 15 %RH, 0.5 hPa, 8 m/s, 5 mm) | Suspect (flag), confirmed or cleared by Step 6 | **Implemented 2026-09-29** (flags; the HTU-specific removal is unchanged) |
| **4b. Persistence** | Is the sensor still responding? | Flat lines: the same value for longer than a per-variable limit (WMO "minimum required variability"); frozen logger (all variables unchanged) | Failed | **Implemented 2026-09-29** |
| **5. Statistical outliers** | Is the value unusual for its local context? | Hampel (median/MAD) and z-score over a centred 21-minute window, with a minimum data share (60%) and a resolution floor | **Suspect (flag)**, confirmed or cleared by Step 6; readings in too-sparse windows are **untested** | **Implemented 2026-09-29** (flag only: see below) |
| **6. Spatial consistency** | Does it agree with co-located instruments? | Flagged readings (Steps 4a, 5) kept only if a co-located instrument shows the same event; calm runs vs. the other anemometers; rain days vs. the other gauges | Corroborated → good (kept, flagged); uncorroborated → failed; calm → failed; rain → flag | **Implemented 2026-09-29** (wind: flags only) |
| **7. Completeness** | Is there enough data to use the period? | A day's readings of a variable are kept only if ≥ 80% of its 1,440 minutes are valid | Failed (whole day, per variable) | Implemented |
| **8. Output** | What's each value's status? | One `<column>_flag` column per value column in `data/cleaned`: empty = good, otherwise the reasons | Only *failed* removed (blank value, reason in `*_outliers.csv`); **rain is flag-only** (`tipping_flag`) | **Implemented 2026-09-29** |

## Step-by-step explanation

### Step 0: Structure
- **Why a regular grid:** the rolling-window tests in Step 5 count *rows*. Without a row for every
  minute, a "20-point" window silently stretches across gaps. TSMS03 had rows for only 91% of its
  minutes, and its longest gap was 316 h. With a grid, 20 rows means 20 minutes, and gaps show up
  as empty cells rather than disappearing.
- **Why ≤ −990 for null markers:** the data uses `-999.99`, `-999.9`, `-999`, `-1000` (3D-PAWS) and
  `-9999` (TSMS). About 320,000 `bmp2_slp` values were also near −1005: sea-level pressures computed
  from a pressure marker. No measured variable here can go below −990.
- **Why the layout guard only warns:** a month whose median is implausible for its column (e.g.
  "rain" with a median of 13 mm/min) points to a column mix-up (SF-10). Fixing that needs a person,
  so the guard reports it rather than guessing.

### Step 1: Metadata and diagnostics
Information *about* the instrument, not its readings: known failures, maintenance, firmware or
database changes, power. It comes before value checks because it can explain whole periods at
once. A battery trending to zero is a Step 1 flag (degraded power). If it also causes stuck
readings, Step 4b catches those independently, and the two steps confirm each other.

**How it's implemented:** every known event is one row in [station-events.csv](station-events.csv)
(station, start, end, variables, action, event, catalog ID, source, notes), built from the January
2024 maintenance logs, the evaluation plan, and the sensor-failures catalog. The table is the single
place to add, change or remove a documented event; the code has no hard-coded dates. Each row has
one of three actions:

| Action | Used for | Effect |
|---|---|---|
| `remove` | Failures confirmed by a log *and* the data (e.g. SF-20: TSMS02 anemometer unplugged for 10 months, reading exactly 0) | Values blanked, logged with their original value |
| `flag` | Degraded conditions found at a visit (off-level or stuck buckets, pebbles in a funnel, a binding anemometer), and the visit days themselves | Values kept; the period is listed in `station_event_flags.csv` and becomes a flag in Step 8 |
| `note` | Sensor changes (HTU21D → SHT31D), software updates, conditions with no measurable effect | Printed only; sensor-change dates are where statistics should be split (PF-17) |

**Diagnostics:** the RPi stations (TSMS00–05) don't log battery or power data. The Particle
stations (TSMS06–08) have battery columns, but they're constant 0 or missing, so there's nothing
to test.

### Step 2: Range
Two layers: limits the instrument can physically report, then climatological limits for the site
and month (e.g. 45 °C is possible in Adana in July but not in Ankara in January). TSMS uses monthly
climatological limits for temperature, but the report doesn't give the values (question for TSMS).

### Step 3: Internal consistency
Checks between variables at the same station.
- **Logger zeros (removed):** a humidity sensor reading exactly 0 %RH in the same minute as a
  temperature sensor reading exactly 0.0 °C. That's the logger writing zeros, not a measurement:
  real air here never has 0% humidity, and 0 °C on its own is common in winter, so neither alone is
  enough. Every exact 0 in that minute's temperature and humidity columns is removed. It finds the
  TSMS06 fault (SF-17: 118,032 minutes) and 7 minutes at TSMS08, and nothing anywhere else.
- **Rain with RH < 60% (flagged only).** TSMS removes it. We keep it because real showers can start
  before the humidity sensor responds: the rule would remove 2–8% of reference rain and 22% of
  TSMS03's, including rain on days with ≥ 5 mm. It does usefully flag junk: 2,312 of TSMS05's
  3,404 mm (its SF-12 months).
- **Not separate checks:** dewpoint ≤ temperature is guaranteed once RH ≤ 100% (Step 2); a stuck vane
  under turning cups is Step 4b; direction at zero speed isn't an error (it's set to missing in the
  analysis).

### Step 4a: Step test (rate of change)
A minute-to-minute change larger than the variable plausibly makes. We use the TSMS limits (2 °C,
15 %RH, 0.5 hPa, 8 m/s, 5 mm) so both analyses test the same thing. On working sensors the 99.99th
percentile of the 1-min change is ≤ 1.3 °C, 9 %RH, 0.4 hPa and 8 m/s, so these catch only unusual
jumps. A step on its own is only *suspect*: real events (a gust front, sunrise on the sensor) can
cause fast changes, so readings are **flagged** and Step 6 decides. If the neighbours saw the same
change, the reading stays. Wind direction isn't step-tested (it swings naturally), nor is SLP (it's
derived from pressure). The HTU21D bit-switching filter stays as a separate removal, since that
fault is known and confirmed within the station.

### Step 4b: Persistence
A sensor stuck on one value, or a logger repeating its last record. We measured every flat-line
run in the data before setting the limits. They depend on the variable, because some steady
conditions are real:

| Variable | Limit (removed if reached) | Why (measured on this data) |
|---|---|---|
| Temperature | 3 h unchanged | No working sensor holds 0.1 °C for 3 h |
| Humidity | 3 h unchanged, **only below 80%** | Real plateaus sit at the sensor's saturation value (Adana reference: 99% for up to 20 h in fog) and, below freezing, at saturation over ice (Konya reference: 85–91% for 4–8 h on winter nights). Below 80% a 3 h plateau is a fault (Ankara reference stuck at 10%, SF-24) |
| Pressure | 3 h unchanged | Genuine plateaus at the turning points of the daily pressure cycle last up to 2.6 h (Konya, Adana references); 2 h would remove real data |
| Wind direction | Unchanged through a run with ≥ 60 min of wind ≥ 1 m/s | The wind was strong enough to turn the vane and it didn't. In lighter wind a still vane is real (starting threshold; 1 m/s is a placeholder until the datasheets arrive, PF-42) |
| **Frozen logger** | Temperature, humidity, pressure and a **nonzero** wind speed all unchanged ≥ 60 min | Catches a logger repeating its last record: the Ankara reference on 25 summer-2025 mornings (SF-23). A calm, foggy night can hold everything else still (Adana reference, 68 min at 0 m/s and 99%), which is why a nonzero speed is required |
| Wind speed | Not tested here | Calm is real; long zero runs are judged against the neighbours in Step 6 (e.g. the Adana reference in 2025, SF-26) |
| Rain | **Not applied** | Zero is rain's normal state; dead gauges are found in Step 6 instead |

TSMS uses 100 consecutive repeats for temperature, humidity and pressure with no exemptions
(method-differences G21). On the Adana reference that would remove 50,065 humidity readings, mostly
fog plateaus.

### Step 5: Statistical outliers
A Hampel filter (distance from the local median in units of the local MAD) and a z-score over a
centred window. Safeguards:
- **Resolution floor:** without it, steady periods give MAD = 0 and every one-step change is
  flagged. Before this fix, the filter removed 12–19% of valid data.
- **A window of real minutes:** Step 0 puts every file on a 1-min grid, so 21 rows are exactly 21
  minutes (10 before, 10 after). Before that, a "20-row" window could span days across a gap.
- **Minimum data share:** at least 60% of the window (13 of 21 minutes) must be present. Otherwise
  the reading is **untested** rather than judged against a few neighbours. That's 0.1–0.3% of readings,
  except the HTU21Ds at TSMS00–02 (6–10%, the gaps left by their bit-switching filter).
- **Standard Hampel MAD:** the median of the window's distances from the window's own median.
- **Window width:** 21 minutes, not TSMS's 61. Measured on the Konya reference, the 61-point window
  flags ≈ 25× more, and 68% of those flags are real events also seen at the 3D-PAWS neighbours.

**Outcome: flag, not removal.** We checked whether flagged readings were errors. For temperature, 61–95% of
flags (reference and MCP9808s, Konya and Adana) show the same deviation, same sign, at a co-located
instrument in the same minute. They cluster at 09–11 UTC: midday convection makes 1-min temperature
swing by about 0.5 °C, just over the Hampel cut-off in otherwise steady windows. Being statistically
unusual isn't evidence of error, so Step 6 removes a flag only when no co-located instrument
supports it. (`STAT_REMOVE` switches back to removal.)

**Not applied to rain or wind.** Rain: an isolated tip among zeros always "fails", so rain is
checked at event level in Step 6. Wind (decided 2026-09-29, after testing it): 1-min wind is gusty
and heavy-tailed. At 11, 21 and 61 minutes alike the test flags about 1–3% of minutes, and 90–95% of
the 3D-PAWS wind-speed flags are gusts the neighbours also saw. Wind QC is the step test, the
stuck-vane check, the calm check against the neighbours, and documented events, as WMO describes.

### Step 6: Spatial consistency
The three 3D-PAWS stations at each site are within ~10 m of each other and of the reference. All
four instruments are checked together, per site, after Steps 0–5.

**6a. Flagged readings need a co-located witness.** A reading flagged by the step test or the
statistical test is compared with every other instrument measuring the same variable at the site:
the other 3D-PAWS stations, the other chips in the same shield, and the reference.
- **Corroborated → kept** (flag stays, marked corroborated). Another instrument's deviation from
  *its own* 21-min median has the same sign and at least half the size, within ±1 minute. Real
  events (convection, gust fronts, showers) are seen by several instruments.
- **Not corroborated → removed**, whether the neighbours disagree or are missing. An unusual value
  that no other instrument supports can't be justified.
- **Systematic differences don't count either way.** Comparing each instrument's deviation from its
  own local median means a shield warm bias, the Konya courtyard or a calibration offset neither
  confirms nor condemns anything. Three agreeing 3D-PAWS stations never outvote the reference on a
  bias.
- **The reference can confirm a 3D-PAWS reading but never condemns one.** With no corroboration a
  flagged reading is removed either way, so the reference's disagreement is never the reason. The
  reference's own flags are judged the same way, by the 3D-PAWS stations.

**6b. Calm runs.** A run of exactly 0 m/s lasting ≥ 3 h is removed when at least two *other* 3D-PAWS
anemometers at the site read a median ≥ 1.5 m/s over it. SMN Argentina's tunnel tests put the cups'
start-up at ≤ 1.2 m/s, so sustained neighbour readings above 1.5 m/s mean the air was moving fast
enough to turn any working cup. Only 3D-PAWS neighbours are used, since they're at the same 2 m
height. This found TSMS08's anemometer not responding in summer 2023 (SF-27).

**6c. Rain, daily totals (flag only).** A gauge with no rain while at least two other gauges each
record ≥ 5 mm is a *dead-gauge day*. A gauge with ≥ 5 mm while all the others (at least two) record
< 0.2 mm is an *uncorroborated day*. Both are flags, never removals, for the 3D-PAWS gauges and the
reference alike. They catch TSMS05's junk months (976 mm, SF-12), the Ankara reference's inflated
totals (583 mm on 19 days, SF-09) and TSMS01's stuck bucket (26 days). **Caveat found 2026-09-29:** the
12 Konya reference "dead-gauge" days are the reverse: courtyard watering tipping all three 3D-PAWS
gauges at ≈ 10:00 UTC in dry weather (SF-28). A rule that trusts two agreeing gauges fails when
one cause hits them all. The `rain_low_rh` flag does catch those tips (≈ 27% RH).

**Measured effect (all sites, test run):**
- Temperature: 95–99% of flags on working sensors are corroborated and kept.
- HTU21D bit-switching remnants: 70–75% contradicted and removed.
- Reference pressure: 394 of Ankara's 432 flags are uncorroborated spikes, removed.

**Wind: flags only (decided 2026-09-29).** For wind the neighbours aren't comparable: 10 m reference
vs. 2 m 3D-PAWS, courtyard and hill siting, and 1-min gusts that don't line up between instruments
ten metres apart. So step and statistical flags on wind speed and direction stay in the data as
flags and are never removed by 6a. Removing them would have taken out 0.3–1.4% of reference wind.
Calm runs (6b), stuck vanes (Step 4b) and documented events still remove wind data.

### Step 7: Completeness
After all other steps, a day is kept for a variable only if ≥ 80% of its minutes are valid (the
report's rule). The analysis also requires ≥ 80% of an hour's or day's minutes to be *paired*
between the two instruments.

### Step 8: Output
Removed readings are blank in `data/cleaned`, with the original value and reason in
`*_outliers.csv`. Every value column gets a `<column>_flag` column (e.g. `tipping_flag`,
`temperature_flag`): empty means good; otherwise it lists the reasons, separated by `;`:

| Flag | Meaning |
|---|---|
| `step:corroborated`, `hampel:corroborated`, `z_score:corroborated` | Unusual, but a co-located instrument saw the same event (e.g. midday convection): real weather, kept |
| `step` (wind only) | A wind jump nobody could confirm; kept because anemometers here can't vouch for each other's gusts |
| `stat_untested` | Too little data around it for the statistical test |
| `rain_low_rh` | Rain while the station's humidity was below 60% |
| `rain_dead_gauge`, `rain_uncorroborated` | The gauge's day disagrees with at least two other gauges at the site |
| `event:<name>` | A documented condition from station-events.csv (e.g. `event:rain_gauge_degraded`, `event:maintenance_visit`) |

The analysis reports rain with and without flagged periods, and can drop any flag class it chooses.

## Questions for the team

Each question notes what the code does now, so the team can confirm it or change it.

1. **Flags vs. removal.** *Current:* step and statistical flags are kept only if a co-located
   instrument saw the same event; otherwise removed. Wind and rain flags are never removed. Agreed?
2. **Persistence limits.** *Current:* 3 h for temperature, humidity below 80%, and pressure; wind
   direction when a run holds ≥ 60 min of wind ≥ 1 m/s; frozen logger ≥ 60 min. Measuring the data
   moved pressure from the proposed 2 h to 3 h and the humidity exemption from "below 100%" to
   "below 80%". Reasonable?
3. **Step-test limits.** *Current:* the TSMS Table 1 values (2 °C, 15 %RH, 0.5 hPa, 8 m/s, 5 mm), as
   flags. Keep them, or derive per-sensor limits from the datasheets?
4. **Rain dead-gauge rule.** *Current:* a day is flagged when the gauge has < 0.2 mm while ≥ 2 other
   gauges at the site have ≥ 5 mm, or ≥ 5 mm while all the others have < 0.2 mm. Same rule for the
   reference. Are 5 mm and daily totals right?
5. **Climatological limits.** *Open:* use TSMS's monthly limits if they share them, or derive our own
   from the reference record?
6. **Wet-day threshold.** *Planned:* report both 0.2 mm (report parity) and 1.0 mm (ETCCDI R1mm). Is
   1.0 mm right for the headline?
7. **Rain vs. humidity.** *Current:* rain with RH < 60% is flagged, not removed (TSMS removes it). Is
   the flag worth keeping? New evidence: it catches the Konya watering tips (SF-28, ≈ 27% RH), which the
   neighbour rule got backwards. Should the Konya dry-season watering tips be removed?
8. **Diagnostics and logs.** *Open:* maintenance logs exist for the January 2024 visits only. Were
   there other visits or known outages (2022–2023, 2024–2025)? Does CHORDS keep logger resets or
   firmware versions?
9. **Site-log conditions.** *Current:* stuck or clogged gauges found at a visit are flagged from the
   start of the record to the visit, so "rain without flags" drops all pre-visit rain at TSMS00, 01,
   06 and 07. Keep that, or bound each problem's start from the dead-gauge days and remove only those?
10. **Statistical outliers as flags.** *Decided 2026-09-29:* Step 5 flags; Step 6 keeps a flag only if
    a neighbour corroborates it (61–95% of temperature flags are real convection). Not applied to wind
    or rain.
