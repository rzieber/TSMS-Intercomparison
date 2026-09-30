"""
Data filter. Creates final csv's as well as outlier csv's. Contains plot gen logic.

Requires station_TSMS00 -> 08 folder struct, with the complete records for TSMS and 3D-PAWS within each folder
within the data_origin directory. Alongside the station_TSMS00 -> 08 folders, have a folder for each site.
Note:   The subfolders for station_TSMS00 -> 08 are generated automatically.
        The subfolders for sites Ankara, Konya, and Adana are NOT generated automatically.

The data_destination pathway doesn't require this, just list the full pathname where you want things stored.

Pre-pass: 3D-PAWS humidity from every station, for the Phase 5 site cross-check
Step 0: Structure -- timestamps, regular 1-min grid, null markers (<= -990), column-layout guard
Step 1: Metadata & diagnostics -- documented station events (docs/station-events.csv): remove / flag / note
Phase 3 (Step 2): Range -- instrument and physical limits
Phase 4: Manual removal of identified special cases (station_rules)
Step 3: Internal consistency -- logger zeros removed; rain with RH < 60% flagged
Phase 5: HTU21D bit-switching filter (step test + co-located 3D-PAWS sensors; no reference data)
Step 4a: Step test, all variables (flag only; confirmed or cleared by the neighbour check, Step 6)
Step 4b: Persistence -- flat-lined sensors and frozen loggers removed
Step 5: Statistical outliers -- centred 21-min Hampel and z-score, >= 60% data share or 'untested'; flag only (Step 6 decides)
Step 6: Spatial consistency, per site -- flags kept only if a co-located instrument shows the same event; calm and rain
        checked against the neighbouring gauges and anemometers
Step 7: Daily completeness (a variable's day is removed if < 80% of its minutes are valid)
Step 8: Output -- '<column>_flag' columns (empty = good; reasons ';'-separated), e.g. tipping_flag

Change history and rationale: docs/logic-changelog.md. Failure catalog: docs/sensor-failures.md.

How to use this script:
    The outlier removal logic in the first portion of this script is to remain uncommented.
    The plot generating scripts which follow the outlier removal portion should have only the 1 logic block uncommented.
    Each section of plot gen logic is separated by a header. The following is an example:
        =============================================================================================================================
        Create a time series plot of the 3D PAWS station data versus the TSMS reference station. MONTHLY RECORDS
        =============================================================================================================================
"""

import os
import sys
import pandas as pd
import warnings
import numpy as np
from pathlib import Path
from numpy.lib.stride_tricks import sliding_window_view


data_origin = r"data/reformatted/"
data_destination = r"data/cleaned/"

outlier_reasons = [
    "null_marker", "duplicate_timestamp", "threshold", "manual_removal", "htu_trend_switch", "z-score_contextual",
    "hampel_contextual", "hum_step_site_check", "hum_step_unverified", "temp_step_station_check",
    "temp_step_unverified", "station_event", "daily_completeness", "logger_zeros", "persistence", "logger_frozen",
    "neighbour_uncorroborated", "no_neighbour", "anemometer_not_responding", "reference_suspect_calm"
]
# Flags (values kept, written to the *_flags.csv files; Step 8 turns them into flag columns)
flag_reasons = ["rain_low_rh", "step", "hampel", "z_score", "stat_untested", "rain_dead_gauge", "rain_uncorroborated"]

# Step 1: documented station events (maintenance logs, sensor-failures catalog, known bad periods), one row per
# event: station, start, end, variables, action, event, catalog_id, source, notes. station is a 3D-PAWS id (TSMS00-08)
# or a TSMS reference as REF-<site> (REF-Ankara, REF-Konya, REF-Adana). A blank start/end means the
# start/end of the record; variables is a space-separated list of 3D-PAWS columns, or "all".
#   remove -> values set to NaN and logged as "station_event:<event>" (documented failures)
#   flag   -> values kept; the period is written to station_event_flags.csv (suspect; flag columns come in Step 8)
#   note   -> printed only (sensor changes, software updates, conditions with no detectable effect)
# (SF-01/SF-02 were dropped on 2026-09-28: mislabeled CHORDS columns, SF-10, fixed in data/reformatted.)
STATION_EVENTS = "docs/station-events.csv"
station_events = pd.read_csv(STATION_EVENTS, dtype=str).fillna("")
assert set(station_events['action']) <= {"remove", "flag", "note"}, "station-events.csv: unknown action"

# Step 3 (internal consistency)
RAIN_RH_FLAG = 60               # %RH; rain in a minute with lower humidity is flagged (TSMS removes it; we only flag)

# Step 4a (step test): maximum change between consecutive minutes before a reading is flagged. Same values as the
# TSMS report (Table 1). On working sensors the 99.99th percentile of the 1-min change is <= 1.3 °C, 9 %RH,
# 0.4 hPa and 8 m/s, so these catch only unusual jumps. Wind direction isn't step-tested (turbulence).
STEP_LIMITS = {"t": 2.0, "h": 15.0, "p": 0.5, "ws": 8.0, "r": 5.0}

# Step 4b (persistence, WMO "minimum required variability"): a run of identical consecutive readings at least this
# long (minutes) is removed. Measured on this data (see logic-changelog 2026-09-29, stage 3):
#   - pressure: genuine plateaus at the turning points of the daily pressure cycle last up to ~2.6 h at 0.1 hPa, so 3 h
#   - humidity: only below RH_PERSISTENCE_MAX. Real plateaus sit at the sensor's saturation value (Adana reference 99%
#     for up to 20 h in fog) and, below freezing, at saturation over ice (Konya reference 85-91% for 4-8 h)
#   - wind direction: a run of identical directions is removed if it contains >= 60 minutes of wind >= VANE_MOVING_SPEED,
#     i.e. the wind was strong enough to turn the vane and it didn't (e.g. TSMS01 reading exactly 0.0 deg for 18 days).
#     Unchanged directions in lighter wind are real: the vane has a starting threshold.
#   - wind speed: not tested here (calm is real; zeros are judged against neighbours in Step 6); rain: never
PERSISTENCE_MINUTES = {"t": 180, "h": 180, "p": 180, "wd": 60}
RH_PERSISTENCE_MAX = 80
VANE_MOVING_SPEED = 1.0         # m/s as read by 3D-PAWS; ~1.5 m/s true wind on SMN Argentina's tunnel fit (3D-PAWS reads
                                # 10-13% low, +0.4 m/s offset), above every tested cup's start-up (<= 1.2 m/s). The vane's own
                                # starting threshold is untested, so this stays a reasoned placeholder (PF-42)
# Frozen logger: temperature, humidity, pressure and a NONZERO wind speed all unchanged for this long (e.g. the Ankara
# reference repeating its last record for 1-4 h on 25 summer-2025 mornings); every value in the run is removed.
# A nonzero speed is required because calm, foggy nights can hold everything else still (Adana reference, 2022-12-14:
# 99% RH, 0 m/s, 12.4 °C for 68 min).
FREEZE_MINUTES = 60

COLUMN_KIND = {
    "temperature": "t", "bmp2_temp": "t", "htu_temp": "t", "sth_temp": "t", "mcp9808": "t",
    "humidity": "h", "htu_hum": "h", "sth_hum": "h",
    "actual_pressure": "p", "sea_level_pressure": "p", "bmp2_pres": "p", "bmp2_slp": "p",
    "avg_wind_speed": "ws", "wind_speed": "ws", "avg_wind_dir": "wd", "wind_dir": "wd",
    "total_rainfall": "r", "tipping": "r",
}

# Phase 7: a day's readings of a variable are kept only if at least this share of its 1,440 minutes are valid
# (same criterion as the TSMS report, section 3.6). The analysis additionally requires 80% of minutes to be PAIRED.
DAILY_COMPLETENESS = 0.8

# Thresholds for the HTU21D "bit-switching" filter (Phase 5)
TEMP_THRESHOLD = 3.5            # °C, jump between consecutive minutes that makes an htu_temp reading suspect
HUM_THRESHOLD = 3.5             # %RH, jump between consecutive minutes that makes an htu_hum/sth_hum reading suspect
TEMP_STATION_THRESHOLD = 2.0    # °C, max distance of a suspect htu_temp from the station's other temperature sensors
HUM_SITE_THRESHOLD = 5.0        # %RH, max distance of a suspect humidity reading from the closest 3D-PAWS station at the site

# Step 5 (statistical outliers). The data is on a regular 1-min grid (Step 0), so a 21-row window is exactly 21 minutes,
# centred (10 before, 10 after). A reading is tested only if at least STAT_MIN_SHARE of its window is present; otherwise
# it's 'untested' (flagged as such), not judged against a handful of neighbours.
# STAT_REMOVE = False: flags only. Measured 2026-09-29: 61-95% of temperature flags are corroborated by a co-located
# instrument at the same minute (midday convection), so statistical unusualness alone isn't evidence of error. The
# neighbour check (Step 6) removes the flags no co-located instrument supports.
STAT_WINDOW = 21
STAT_MIN_SHARE = 0.6
STAT_K = 3.0
STAT_REMOVE = False

# Minimum MAD (Hampel) and minimum rolling std (z-score) for Step 5: the coarsest resolution each column
# is recorded at. Without a floor, a flat or near-flat window gives MAD = 0 / a tiny std, and a reading that
# differs from its neighbours by a single resolution step is flagged as an outlier.
# 3D-PAWS: 0.01 (SD-card era) or 0.1 (CHORDS era); MCP9808 0.0625 or 0.1. See docs/potential-fixes.md (noise floor).
RESOLUTION_FLOOR = {
    "temperature": 0.1, "humidity": 1.0, "actual_pressure": 0.1, "sea_level_pressure": 0.1,     # TSMS reference
    "bmp2_temp": 0.1, "htu_temp": 0.1, "sth_temp": 0.1, "mcp9808": 0.1,                          # 3D-PAWS
    "bme2_hum": 0.1, "htu_hum": 0.1, "sth_hum": 0.1, "bmp2_pres": 0.1, "bmp2_slp": 0.1,
    "avg_wind_speed": 0.1, "wind_speed": 0.1, "avg_wind_dir": 1.0, "wind_dir": 1.0                # wind (both)
}

# Step 6 (spatial consistency). All four instruments at a site are within ~10 m of each other.
# A flagged reading (step test, Hampel, z-score) is kept only if a co-located instrument shows the same event: its own
# deviation from its 21-min median has the same sign and at least NEIGHBOUR_SHARE of the size, within +/-1 minute.
# Deviations from each instrument's own local median are compared, so systematic offsets between instruments (shield,
# siting, calibration) neither confirm nor condemn anything. Uncorroborated flags are removed, whether the neighbours
# disagree or are missing: an unusual value no other instrument supports can't be justified. The reference can confirm
# a 3D-PAWS reading but is never the reason one is removed (a reading with no corroboration goes either way).
NEIGHBOUR_SHARE = 0.5
# Wind flags are never removed by 6a (decided 2026-09-29): the 10 m reference and 2 m 3D-PAWS anemometers (courtyard at
# Konya, hill at Ankara) can't vouch for each other's 1-min gusts, so an uncorroborated wind flag isn't evidence of error.
# Calm runs (6b), stuck vanes (Step 4b) and documented events still remove wind data.
NEIGHBOUR_FLAG_ONLY = {"wind_speed", "wind_dir"}
NEIGHBOUR_LAG = 1               # minutes either side
NEIGHBOUR_GROUPS = {            # variable group: (3D-PAWS columns, reference column, circular)
    "temperature": (["bmp2_temp", "htu_temp", "sth_temp", "mcp9808"], "temperature", False),
    "humidity":    (["htu_hum", "sth_hum"], "humidity", False),
    "pressure":    (["bmp2_pres"], "actual_pressure", False),
    "slp":         (["bmp2_slp"], "sea_level_pressure", False),
    "wind_speed":  (["wind_speed"], "avg_wind_speed", False),
    "wind_dir":    (["wind_dir"], "avg_wind_dir", True),
}
# Calm: a run of exactly 0 m/s >= CALM_RUN_MINUTES is removed when at least two other 3D-PAWS anemometers at the site have
# a median speed >= CALM_NEIGHBOUR_SPEED over the run. SMN Argentina's wind-tunnel tests (docs/datasheets/
# 3DPAWS_anemometer_test_report_EN.pdf) found the cups start at <= 1.2 m/s, so sustained neighbour readings above 1.5 m/s
# mean the air was moving fast enough to turn any working anemometer. Only 3D-PAWS neighbours are used (same 2 m height).
CALM_RUN_MINUTES = 180
CALM_NEIGHBOUR_SPEED = 1.5
# Rain (flag only, daily totals): a gauge recording nothing while >= 2 other gauges at the site each record
# >= RAIN_EVENT_MM is flagged 'rain_dead_gauge'; a gauge recording >= RAIN_EVENT_MM while every other gauge (>= 2)
# records < RAIN_DRY_MM is flagged 'rain_uncorroborated'.
RAIN_EVENT_MM = 5.0
RAIN_DRY_MM = 0.2

site_stations = {
    "Ankara":   ["TSMS00", "TSMS01", "TSMS02"],
    "Konya":    ["TSMS03", "TSMS04", "TSMS05"],
    "Adana":    ["TSMS06", "TSMS07", "TSMS08"]
}

station_variables = [ 
    "temperature", "humidity", "actual_pressure", "sea_level_pressure", "wind", "total_rainfall"
]
variable_mapper = { # TSMS : 3DPAWS
    "temperature":["bmp2_temp", "htu_temp", "sth_temp", "mcp9808"],
    "humidity":["bme2_hum", "htu_hum", "sth_hum"],
    "actual_pressure":["bmp2_pres"],
    "sea_level_pressure":["bmp2_slp"],
    "avg_wind_dir":["wind_dir"],
    "avg_wind_speed":["wind_speed"], 
    "total_rainfall":["tipping"]
}
station_directories = [
    "station_TSMS00/", "station_TSMS01/", "station_TSMS02/",   
    "station_TSMS03/", "station_TSMS04/", "station_TSMS05/",
    "station_TSMS06/", "station_TSMS07/", "station_TSMS08/"
]

station_files = [] # list of lists of filenames under each station directory [[TSMS00 files], [TSMS01 files], [TSMS02 files]...]
for station in station_directories:
    station_files.append(sorted([f for f in os.listdir(data_origin + station) # sorted by filename
                                    if os.path.isfile(os.path.join(data_origin + station, f)) and f != ".DS_Store"]))
    
# -------------------------------------------------------------------------------------------------------------------------------

def coerce_non_timestamp_columns_to_numeric(df, timestamp_col='date'):
    non_ts_cols = [c for c in df.columns if c != timestamp_col]
    df[non_ts_cols] = df[non_ts_cols].apply(pd.to_numeric, errors='coerce')
    return df


def step_suspect(s:pd.Series, threshold):
    """
    Flag readings that jump by more than threshold from the reading exactly one minute before or after.
    s must have a sorted, unique DatetimeIndex. Both ends of a jump are flagged, since either could be the bad one.
    """
    t = s.index.to_series()
    one_min = pd.Timedelta('1min')
    jump_prev = (s.diff().abs() > threshold) & (t.diff() == one_min)
    jump_next = ((s.shift(-1) - s).abs() > threshold) & ((t.shift(-1) - t) == one_min)
    return (jump_prev | jump_next) & s.notna()


def run_lengths(s:pd.Series):
    """Length of the run of identical consecutive readings each reading belongs to (missing readings: 0, and they break runs).
    s must be on the regular 1-min grid."""
    v = s.to_numpy(dtype=float)
    brk = np.r_[True, (v[1:] != v[:-1]) | np.isnan(v[1:]) | np.isnan(v[:-1])]
    g = np.cumsum(brk)
    L = np.bincount(g)[g]
    return pd.Series(np.where(np.isnan(v), 0, L), index=s.index)


def persistence_mask(df:pd.DataFrame, col:str, speed_col:str):
    """Step 4b: True for readings in a flat-line run longer than the column's persistence limit."""
    kind = COLUMN_KIND[col]
    s = df[col]
    if kind == "wd":                                         # minutes of wind strong enough to turn the vane, per run
        v = s.to_numpy(dtype=float)
        g = np.cumsum(np.r_[True, (v[1:] != v[:-1]) | np.isnan(v[1:]) | np.isnan(v[:-1])])
        windy = np.bincount(g, weights=(df[speed_col] >= VANE_MOVING_SPEED).to_numpy(dtype=float))[g]
        return pd.Series((windy >= PERSISTENCE_MINUTES[kind]) & ~np.isnan(v), index=s.index)
    mask = run_lengths(s) >= PERSISTENCE_MINUTES[kind]
    if kind == "h": mask &= s < RH_PERSISTENCE_MAX           # saturation plateaus are real
    return mask


def frozen_mask(df:pd.DataFrame, cols:list):
    """Step 4b: True for minutes in a run where every column in cols is unchanged (and present) for >= FREEZE_MINUTES
    and the last column (wind speed) is nonzero."""
    x = df[cols].to_numpy(dtype=float)
    present = ~np.isnan(x).any(axis=1)
    same = np.r_[False, (x[1:] == x[:-1]).all(axis=1) & present[1:] & present[:-1]]
    g = np.cumsum(~same)                                     # a run starts at every minute that differs from the one before
    L = np.bincount(g)[g]
    return pd.Series((L >= FREEZE_MINUTES) & present & (x[:, -1] > 0), index=df.index)


def wrap180(x):
    """Signed angle difference in degrees, in [-180, 180)."""
    return (x + 180.0) % 360.0 - 180.0


def stat_outliers(s:pd.Series, floor:float, window:int=STAT_WINDOW, min_share:float=STAT_MIN_SHARE, k:float=STAT_K,
                  chunk:int=200_000, circular:bool=False):
    """
    Step 5: centred rolling z-score and Hampel test on a regular 1-min series. The Hampel MAD is the median of the
    window's absolute deviations from the window's own median (standard definition), scaled by 1.4826; MAD and std are
    floored at the column's resolution. Returns boolean arrays (z, hampel, untested).
    circular=True (wind direction): the centre is the window's mean direction and deviations are signed angle
    differences, so 359 and 1 degree are 2 degrees apart.
    """
    v = s.to_numpy(dtype=float); n = len(v); h = window // 2
    W = sliding_window_view(np.pad(v, (h, h), constant_values=np.nan), window)
    need = int(np.ceil(min_share * window))
    z, hm, unt = np.zeros(n, bool), np.zeros(n, bool), np.zeros(n, bool)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)   # all-missing windows
        for a in range(0, n, chunk):
            w, x = W[a:a+chunk], v[a:a+chunk]
            cnt = np.sum(~np.isnan(w), axis=1)
            ok = (cnt >= need) & ~np.isnan(x)
            if circular:
                r = np.deg2rad(w)
                centre = np.rad2deg(np.arctan2(np.nanmean(np.sin(r), axis=1), np.nanmean(np.cos(r), axis=1)))
                dev_w = wrap180(w - centre[:, None]); dev_x = wrap180(x - centre)
                mad = np.maximum(np.nanmedian(np.abs(dev_w), axis=1), floor)
                std = np.maximum(np.nanstd(dev_w, axis=1, ddof=1), floor)
                z[a:a+chunk] = ok & (np.abs(dev_x) / std > k)
                hm[a:a+chunk] = ok & (np.abs(dev_x) > k * 1.4826 * mad)
            else:
                med = np.nanmedian(w, axis=1)
                mad = np.maximum(np.nanmedian(np.abs(w - med[:, None]), axis=1), floor)
                std = np.maximum(np.nanstd(w, axis=1, ddof=1), floor)
                z[a:a+chunk] = ok & (np.abs(x - np.nanmean(w, axis=1)) / std > k)
                hm[a:a+chunk] = ok & (np.abs(x - med) > k * 1.4826 * mad)
            unt[a:a+chunk] = (cnt < need) & ~np.isnan(x)
    return z, hm, unt


def local_anomaly(s:pd.Series, circular:bool=False):
    """Deviation of each reading from its centred 21-min median (circular: from the window's mean direction)."""
    roll = dict(window=STAT_WINDOW, center=True, min_periods=int(np.ceil(STAT_MIN_SHARE * STAT_WINDOW)))
    if circular:
        r = np.deg2rad(s)
        centre = np.rad2deg(np.arctan2(np.sin(r).rolling(**roll).mean(), np.cos(r).rolling(**roll).mean()))
        return wrap180(s - centre)
    return s - s.rolling(**roll).median()


def add_flag_columns(frame:pd.DataFrame, flags:list, corroborated:dict, value_cols:list, station:str=None):
    """
    Step 8: one '<col>_flag' column per value column. Empty = good; otherwise the reasons, ';'-separated:
    step / hampel / z_score (with ':corroborated' when Step 6 found a co-located instrument showing the same event;
    uncorroborated ones were removed, except wind), stat_untested, the rain flags, and Step 1 events as 'event:<name>'.
    Removed readings are blank values (reason in *_outliers.csv), so they carry no flag.
    """
    fl = pd.concat(flags, ignore_index=True)
    pos_of = pd.Index(frame['date'])
    text = {c: np.full(len(frame), '', dtype=object) for c in value_cols}

    def add(col, pos, label):
        pos = pos[pos >= 0]
        if not len(pos): return
        cur = text[col][pos]
        text[col][pos] = np.where(cur == '', label, cur + ';' + label)

    for (col, reason), g in fl[fl['column_name'].isin(value_cols)].groupby(['column_name', 'flag_type']):
        dates = pd.DatetimeIndex(g['date'].drop_duplicates())
        if reason in (flag_reasons[1], flag_reasons[2], flag_reasons[3]):
            ok = dates.isin(corroborated.get(col, pd.DatetimeIndex([])))
            add(col, pos_of.get_indexer(dates[ok]), f"{reason}:corroborated")
            add(col, pos_of.get_indexer(dates[~ok]), reason)
        else:
            add(col, pos_of.get_indexer(dates), reason)
    if station is not None:                           # Step 1 'flag' events (maintenance visits, degraded conditions)
        for _, ev in station_events[(station_events['station'] == station) & (station_events['action'] == 'flag')].iterrows():
            mask = event_mask(frame['date'], ev['start'], ev['end']).to_numpy()
            for col in event_columns(ev, value_cols):
                add(col, np.flatnonzero(mask), f"event:{ev['event']}")
    for c in value_cols:
        text[c][frame[c].isna().to_numpy()] = ''
        frame[c + '_flag'] = text[c]
    return frame


def completeness_step(frame:pd.DataFrame, columns:list):
    """Step 7: blank a variable's day if < DAILY_COMPLETENESS of its 1,440 minutes are valid. Returns the removal log."""
    logs = []
    day = pd.to_datetime(frame['date']).dt.floor('D')
    for col in columns:
        if col not in frame.columns: continue
        valid_per_day = frame[col].notna().groupby(day).transform('sum')
        incomplete = (valid_per_day < DAILY_COMPLETENESS * 1440) & frame[col].notna()
        if not incomplete.any(): continue
        logs.append(removal_log(frame, incomplete, col, outlier_reasons[12]))
        frame.loc[incomplete, col] = np.nan
    return pd.concat(logs, ignore_index=True) if logs else None


def removal_log(df:pd.DataFrame, mask:pd.Series, col:str, reason:str):
    hit = mask & df[col].notna()
    return pd.DataFrame({'date': df.loc[hit, 'date'], 'column_name': col, 'original_value': df.loc[hit, col], 'outlier_type': reason})


def flag_log(df:pd.DataFrame, mask:pd.Series, col:str, reason:str):
    hit = mask & df[col].notna()
    return pd.DataFrame({'date': df.loc[hit, 'date'], 'column_name': col, 'value': df.loc[hit, col], 'flag_type': reason})


NULL_MARKER_CEILING = -990     # any value <= this is a missing-value marker (-999.99, -999.9, -999, -1000, -9999, and
                                # SLPs derived from a pressure marker, e.g. -1005.4); no measured variable here goes this low

LAYOUT_RANGES = {   # plausible monthly MEDIAN per column; a month outside it suggests a column-layout problem (SF-10)
    'temperature': (-40, 50), 'humidity': (0, 100), 'actual_pressure': (600, 1100), 'sea_level_pressure': (900, 1100),
    'avg_wind_dir': (0, 360), 'avg_wind_speed': (0, 30), 'total_rainfall': (0, 0.5),
    'bmp2_temp': (-40, 50), 'htu_temp': (-40, 50), 'sth_temp': (-40, 50), 'mcp9808': (-40, 50),
    'bme2_hum': (0, 100), 'htu_hum': (0, 100), 'sth_hum': (0, 100), 'bmp2_pres': (600, 1100), 'bmp2_slp': (900, 1100),
    'wind_dir': (0, 360), 'wind_speed': (0, 30), 'tipping': (0, 0.5),
}


def structure_step(df:pd.DataFrame, value_cols:list, label:str):
    """
    Step 0 -- Structure: is the record well-formed? (docs/potential-fixes.md PF-35)
        1. Timestamps: parse, sort (stable), drop duplicate minutes keeping the first in file order.
        2. Regular 1-min grid: every minute from first to last gets a row; missing minutes stay empty (NaN).
        3. Null markers: values <= NULL_MARKER_CEILING become NaN (logged with their original value).
        4. Column-layout guard: warn (don't change data) when a month's median falls outside LAYOUT_RANGES.
    Returns the structured frame (with a 'date' column), a log of changed values, and a list of layout warnings.
    """
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date', kind='stable')
    for col in value_cols: df[col] = pd.to_numeric(df[col], errors='coerce')

    logs = []
    dup = df['date'].duplicated(keep='first')
    if dup.any():
        logs.append(pd.DataFrame({'date': df.loc[dup, 'date'], 'column_name': 'date', 'original_value': np.nan,
                                  'outlier_type': outlier_reasons[1]}))
    df = df[~dup].set_index('date')

    full_index = pd.date_range(df.index.min().floor('min'), df.index.max().floor('min'), freq='1min', name='date')
    df = df.reindex(full_index)

    for col in value_cols:
        marker = df[col] <= NULL_MARKER_CEILING
        if marker.any():
            logs.append(pd.DataFrame({'date': df.index[marker], 'column_name': col,
                                      'original_value': df.loc[marker, col].to_numpy(), 'outlier_type': outlier_reasons[0]}))
            df.loc[marker, col] = np.nan

    layout_warnings = []
    for col in value_cols:
        if col not in LAYOUT_RANGES: continue
        lo, hi = LAYOUT_RANGES[col]
        monthly = df[col].resample('MS').agg(['median', 'count'])
        bad = monthly[(monthly['count'] >= 1000) & ((monthly['median'] < lo) | (monthly['median'] > hi))]
        for month, row in bad.iterrows():
            layout_warnings.append({'file': label, 'column': col, 'month': month.strftime('%Y-%m'),
                                    'median': round(row['median'], 2), 'expected': f"{lo} to {hi}"})

    df = df.reset_index()
    df['year_month'] = df['date'].dt.to_period('M')
    df['year_month_day'] = df['date'].dt.to_period('D')
    df['year_month_day_hour'] = df['date'].dt.to_period('h')
    log = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame(columns=['date', 'column_name', 'original_value', 'outlier_type'])
    return df, log, layout_warnings


def event_mask(dates:pd.Series, start, end):
    """True for dates inside an event period (a blank start/end: from the start / to the end of the record)."""
    mask = pd.Series(True, index=dates.index)
    if start: mask &= dates >= pd.Timestamp(start)
    if end: mask &= dates <= pd.Timestamp(end)
    return mask


def event_columns(event, value_cols:list):
    """The columns an event applies to ("all" = every value column)."""
    if event['variables'].strip() == "all": return list(value_cols)
    cols = event['variables'].split()
    unknown = set(cols) - set(value_cols)
    assert not unknown, f"station-events.csv: unknown column(s) {unknown} for {event['station']}"
    return cols


def metadata_step(df:pd.DataFrame, station:str, value_cols:list):
    """
    Step 1: apply the station's documented events. Returns the data with 'remove' periods blanked, the removal
    log, and one row per 'flag' event with the number of non-missing readings it covers.
    """
    logs, flags = [], []
    for _, ev in station_events[station_events['station'] == station].iterrows():
        cols = event_columns(ev, value_cols)
        mask = event_mask(df['date'], ev['start'], ev['end'])
        period = f"{ev['start'] or 'record start'} -> {ev['end'] or 'record end'}"
        tag = f" [{ev['catalog_id']}]" if ev['catalog_id'] else ""
        n = int(df.loc[mask, cols].notna().sum().sum())

        if ev['action'] == "remove":
            for col in cols:
                hit = mask & df[col].notna()
                logs.append(pd.DataFrame({'date': df.loc[hit, 'date'], 'column_name': col,
                                          'original_value': df.loc[hit, col],
                                          'outlier_type': f"{outlier_reasons[11]}:{ev['event']}"}))
                df.loc[mask, col] = np.nan
            print(f"\tREMOVE {ev['event']}{tag}: {' '.join(cols) if ev['variables'] != 'all' else 'all'} {period} ({n:,} readings)")
        elif ev['action'] == "flag":
            flags.append({'station': station, 'start': ev['start'] or str(df['date'].iloc[0]),
                          'end': ev['end'] or str(df['date'].iloc[-1]), 'variables': ev['variables'],
                          'event': ev['event'], 'catalog_id': ev['catalog_id'], 'readings': n, 'notes': ev['notes']})
            print(f"\tFLAG   {ev['event']}{tag}: {ev['variables']} {period} ({n:,} readings kept, flagged)")
        else:
            print(f"\tNOTE   {ev['event']}: {ev['variables']} from {ev['start'] or 'record start'}"
                  f"{' to ' + ev['end'] if ev['end'] else ''}")

    log = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame(columns=['date', 'column_name', 'original_value', 'outlier_type'])
    return df, log, flags


"""
=============================================================================================================================
Pre-pass: humidity from every 3D-PAWS station, used as the site cross-check in Phase 5.
Each station runs one humidity sensor at a time (HTU21D before the SHT31D upgrade, SHT31D after), so the
two columns are combined. Only null/range checks are applied here, and step-suspect readings are removed so a
noisy neighbour can't vouch for a noisy reading.
=============================================================================================================================
"""
print("Pre-pass: loading 3D-PAWS humidity for site cross-checks.")
site_humidity = {}  # station -> humidity series indexed by date, suspect readings removed

for station_dir, files in zip(station_directories, station_files):
    paws_file = [f for f in files if f.startswith("TSMS")][0]
    hum = pd.read_csv(
        data_origin+station_dir+paws_file,
        usecols=lambda c: c.strip() in ['date', 'htu_hum', 'sth_hum'],
        low_memory=False
    )
    hum.columns = hum.columns.str.strip()
    hum['date'] = pd.to_datetime(hum['date'])
    hum = hum.sort_values('date').drop_duplicates('date', keep='first').set_index('date')

    removals = station_events[(station_events['station'] == station_dir[8:14]) & (station_events['action'] == "remove")]
    sensors = []
    for col in ['htu_hum', 'sth_hum']:
        h = pd.to_numeric(hum[col], errors='coerce')
        h = h.where((h >= 0) & (h <= 100))  # also removes -999.99 nulls
        for _, ev in removals.iterrows():  # a failed sensor can't vouch for its neighbours
            if ev['variables'] == "all" or col in ev['variables'].split():
                h = h.where(~event_mask(h.index.to_series(), ev['start'], ev['end']))
        sensors.append(h.where(~step_suspect(h, HUM_THRESHOLD)))

    site_humidity[station_dir[8:14]] = sensors[0].combine_first(sensors[1])


layout_warnings_all = []     # Step 0 column-layout guard, written to data_destination/structure_layout_warnings.csv
site_data = {}               # site -> reference and station results after Steps 0-5, for Step 6 (all instruments at once)
event_flags_all = []         # Step 1 flagged periods, written to data_destination/station_event_flags.csv

for i in range(len(station_directories)):
    print("\n----------------------")
    paws_df = tsms_df = None
    """
    =============================================================================================================================
    Create the 3D PAWS and TSMS dataframes.
    =============================================================================================================================
    """
    for file in station_files[i]:
        if file.startswith("TSMS"): # 3D-PAWS records start w/ 'TSMS', TSMS ref. records start w/ the site name
            paws_df = pd.read_csv( 
                            data_origin+station_directories[i]+file,
                            header=0,
                            low_memory=False
                        )
            paws_df.columns = paws_df.columns.str.strip()

            paws_df['date'] = pd.to_datetime(paws_df['date'])
            
            paws_df = paws_df[['date', 'bmp2_temp', 'htu_temp', 'sth_temp', 'mcp9808', 'bme2_hum', 'htu_hum', 'sth_hum', 
                               'bmp2_pres', 'bmp2_slp', 'wind_dir', 'wind_speed', 'tipping']]
            
            paws_df = coerce_non_timestamp_columns_to_numeric(paws_df)
            
            paws_df['year_month'] =             paws_df['date'].dt.to_period('M')
            paws_df['year_month_day'] =         paws_df['date'].dt.to_period('D')
            paws_df['year_month_day_hour'] =    paws_df['date'].dt.to_period('h')
            
            paws_df.set_index('date', inplace=True)

        else:
            tsms_df = pd.read_csv(
                            data_origin+station_directories[i]+file,
                            header=0,
                            low_memory=False
                        )
            tsms_df.columns = tsms_df.columns.str.strip()

            tsms_df['date'] = pd.to_datetime(tsms_df['date'])

            tsms_df = tsms_df[['date', 'temperature', 'humidity', 'actual_pressure', 'sea_level_pressure', 
                                'avg_wind_dir', 'avg_wind_speed', 'total_rainfall']]
            
            tsms_df['year_month'] =             tsms_df['date'].dt.to_period('M')
            tsms_df['year_month_day'] =         tsms_df['date'].dt.to_period('D')
            tsms_df['year_month_day_hour'] =    tsms_df['date'].dt.to_period('h')

            tsms_df.set_index('date', inplace=True) 

    warnings.filterwarnings(
        "ignore", 
        category=FutureWarning, 
        message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated."
    )

    
    """
    =============================================================================================================================
    =============================================================================================================================
    =============================================================================================================================
                Eliminate outliers from the dataset and store in separate dataframe for each station.
            Creates a FILTERED dataframe, where all cells containing an outlier have been replaced with np.nan
    =============================================================================================================================
    =============================================================================================================================
    =============================================================================================================================
    """
    
    paws_outliers = pd.DataFrame(columns=['date', 'column_name', 'original_value', 'outlier_type'])
    tsms_outliers = pd.DataFrame(columns=['date', 'column_name', 'original_value', 'outlier_type'])
    paws_flags = [pd.DataFrame(columns=['date', 'column_name', 'value', 'flag_type'])]   # suspect values, kept
    tsms_flags = [pd.DataFrame(columns=['date', 'column_name', 'value', 'flag_type'])]
    
    print()
    print("Starting outlier removal for ", station_directories[i][8:14])

    """
    =============================================================================================================================
    Step 0: Structure -- timestamps, regular 1-min grid, null markers, column-layout guard (see structure_step)
    =============================================================================================================================
    """
    print("Step 0: Structure (timestamps, 1-min grid, null markers, layout guard).")
    station = station_directories[i][8:14]
    paws_cols = ['bmp2_temp', 'htu_temp', 'sth_temp', 'mcp9808', 'bme2_hum', 'htu_hum', 'sth_hum',
                 'bmp2_pres', 'bmp2_slp', 'wind_dir', 'wind_speed', 'tipping']
    tsms_cols = ['temperature', 'humidity', 'actual_pressure', 'sea_level_pressure', 'avg_wind_dir', 'avg_wind_speed', 'total_rainfall']

    paws_df_FILTERED, log, warn_paws = structure_step(paws_df.reset_index()[['date'] + paws_cols], paws_cols, f"3DPAWS_{station}")
    paws_outliers = pd.concat([paws_outliers, log], ignore_index=True)
    tsms_df_FILTERED, log, warn_tsms = structure_step(tsms_df.reset_index()[['date'] + tsms_cols], tsms_cols, f"TSMS_reference ({station} site)")
    tsms_outliers = pd.concat([tsms_outliers, log], ignore_index=True)

    for w in warn_paws + warn_tsms:
        print(f"\t[LAYOUT WARNING] {w['file']} {w['column']} {w['month']}: monthly median {w['median']} (expected {w['expected']})")
    layout_warnings_all.extend(warn_paws + warn_tsms)
    print(f"\t3D-PAWS: {len(paws_df_FILTERED):,} minutes on the grid; TSMS: {len(tsms_df_FILTERED):,}")


    """
    =============================================================================================================================
    Step 1: Metadata & diagnostics -- documented station events from docs/station-events.csv (see metadata_step).
    Battery/power diagnostics aren't used: the RPi stations (TSMS00-05) don't log them, and on the Particle stations
    (TSMS06-08) the battery columns are constant 0 or absent.
    =============================================================================================================================
    """
    print("Step 1: Metadata & diagnostics (documented station events).")
    paws_df_FILTERED, log, flags = metadata_step(paws_df_FILTERED, station, paws_cols)
    paws_outliers = pd.concat([paws_outliers, log], ignore_index=True)
    event_flags_all.extend(flags)
    ref_id = "REF-" + ("Ankara" if i in [0,1,2] else "Konya" if i in [3,4,5] else "Adana")
    tsms_df_FILTERED, log, flags = metadata_step(tsms_df_FILTERED, ref_id, tsms_cols)   # the site's reference
    tsms_outliers = pd.concat([tsms_outliers, log], ignore_index=True)
    event_flags_all.extend(flags)


    """
    =============================================================================================================================
    Phase 3: Filter out unrealistic values
    =============================================================================================================================
    """
    print(f"Phase 3: Filtering out unrealistic values.") 

    for variable in variable_mapper:                                # Filtering TSMS --------------------------------------------
        existing_nulls = tsms_df_FILTERED[variable].isnull()        # Create a mask for existing nulls before applying the filter
        
        if variable == "temperature":
            mask_temp = (tsms_df_FILTERED[variable] > 50) | (tsms_df_FILTERED[variable] < -50)
            tsms_df_FILTERED.loc[mask_temp, variable] = np.nan
        elif variable == "humidity":
            mask_hum = (tsms_df_FILTERED[variable] > 100) | (tsms_df_FILTERED[variable] < 0)
            tsms_df_FILTERED.loc[mask_hum, variable] = np.nan
        elif variable == "actual_pressure" or variable == "sea_level_pressure":
            mask_pres = (tsms_df_FILTERED[variable] > 1084) | (tsms_df_FILTERED[variable] < 870)
            tsms_df_FILTERED.loc[mask_pres, variable] = np.nan
        elif variable == "avg_wind_speed":
            mask_wndspd = (tsms_df_FILTERED[variable] > 100) | (tsms_df_FILTERED[variable] < 0)
            tsms_df_FILTERED.loc[mask_wndspd, variable] = np.nan
        elif variable == "avg_wind_dir":
            mask_wnddir = (tsms_df_FILTERED[variable] > 360) | (tsms_df_FILTERED[variable] < 0)
            tsms_df_FILTERED.loc[mask_wnddir, variable] = np.nan
        elif variable == "total_rainfall":
            mask_rain = (tsms_df_FILTERED[variable] > 32) | (tsms_df_FILTERED[variable] < 0)
            tsms_df_FILTERED.loc[mask_rain, variable] = np.nan
        else:
            print(f"[ERROR]: {variable} not found in dataframe.")
            sys.exit(-1)
        
        new_nulls = tsms_df_FILTERED[variable].isnull() & ~existing_nulls   # Create a mask for new nulls after applying the filter
        
        outliers_to_add = pd.DataFrame({                                    # Add new nulls to the outlier dataframe
            'date': tsms_df_FILTERED.loc[new_nulls, 'date'],
            'column_name': variable,
            'original_value': tsms_df_FILTERED.loc[new_nulls, variable],
            'outlier_type': outlier_reasons[2]
        })
        tsms_outliers = pd.concat([tsms_outliers, outliers_to_add], ignore_index=True)
        
        outliers_to_add = None
        new_nulls = None

        for var in variable_mapper[variable]:               # Filtering PAWS ----------------------------------------------------
            existing_nulls = paws_df_FILTERED[var].isnull()

            if var == "bmp2_temp" or var == "htu_temp" or var == "sth_temp" or var == "mcp9808":
                mask_temp = (paws_df_FILTERED[var] > 50) | (paws_df_FILTERED[var] < -50)
                paws_df_FILTERED.loc[mask_temp, var] = np.nan
            elif var == "htu_hum" or var == 'sth_hum' or var == "bme2_hum":
                mask_hum = (paws_df_FILTERED[var] > 100) | (paws_df_FILTERED[var] < 0)
                paws_df_FILTERED.loc[mask_hum, var] = np.nan
            elif var == "bmp2_pres" or var == "bmp2_slp":
                mask_pres = (paws_df_FILTERED[var] > 1084) | (paws_df_FILTERED[var] < 870)
                paws_df_FILTERED.loc[mask_pres, var] = np.nan
            elif var == "wind_speed":
                paws_df_FILTERED[var] = pd.to_numeric(paws_df_FILTERED[var], errors='coerce')
                mask_wndspd = (paws_df_FILTERED[var] > 100) | (paws_df_FILTERED[var] < 0)
                paws_df_FILTERED.loc[mask_wndspd, var] = np.nan
            elif var == "wind_dir":
                mask_wnddir = (paws_df_FILTERED[var] > 360) | (paws_df_FILTERED[var] < 0)
                paws_df_FILTERED.loc[mask_wnddir, var] = np.nan
            elif var == "tipping":
                mask_rain = (paws_df_FILTERED[var] > 32) | (paws_df_FILTERED[var] < 0)
                paws_df_FILTERED.loc[mask_rain, var] = np.nan
            else:
                print("Error with ", var)
            
            new_nulls = paws_df_FILTERED[var].isnull() & ~existing_nulls  
            
            outliers_to_add = pd.DataFrame({               
                'date': paws_df_FILTERED.loc[new_nulls, 'date'],
                'column_name': var,
                'original_value': paws_df_FILTERED.loc[new_nulls, var],
                'outlier_type': outlier_reasons[2]
            })
            paws_outliers = pd.concat([paws_outliers, outliers_to_add], ignore_index=True)


    import operator as o
    """
    ============================================================================================================================
    Phase 4: Manual removal of known outliers.
    ============================================================================================================================
    """
    print(f"Phase 4: Manual removal of known outliers (see Phase 4 in code for notes).") 

    """
    NOTE: The outliers specified in the station_rules variable fall exclusively under these categories:
            - test data generated during the fabrication process
            - erroneous spikes (e.g. random false zero's) which weren't removed during the statistical 
                outlier cleaning sweep

        The 2 other removals of erroneous rainfall data that used to follow station_rules (faulty connection,
        TSMS08; fabrication test data, TSMS04) are now documented events applied in Step 1.

        IMPORTANT:
        Not removed from the final dataset includes erroneous HTU temperature and r. humidity data.
        The HTU was observed in stations TSMS00 -> TSMS04 to suffer from a "bit-switching" issue, 
        where the temperature trend would toggle between valid temperature readings and erroneous 
        r. humidity readings at 1 -> 4 minute intervals. The same is true of the r. humidity trend --
        valid r. humidity readings would be interspersed with erroneous temperature data. 
        Timescales on the order of a few hours up to 2 months would be continuously affected by this 
        sensor malfunction. Unfortunately due to time constraints, this data could not be removed.
        (Update 2026-09-28: Phase 5 now removes much of this with a step test checked against co-located
        3D-PAWS sensors -- see docs/sensor-failures.md SF-03 for what it still misses.)

        A signal processing approach is proposed for future cleaning attempts. Complications arise 
        given the nature of the rate at which the "bit-switching" noise occurs -- because the rate 
        of noise is similar to the sampling rate of the weather stations, standard signal processing 
        techniques will run the risk of causing aliasing.
    """

    df = paws_df_FILTERED

    station_rules = {
        "TSMS00" : { 
            'bmp2_temp': [([pd.Period('2023-02')], o.gt, 16)],
            'htu_temp': [([pd.Period('2023-02')], o.gt, 16)],
            'mcp9808': [([pd.Period('2023-02')], o.gt, 16)],
            'bmp2_pres': [([pd.Period('2022-08')], o.gt, 1050)],
            'bmp2_slp': [([pd.Period('2022-08'), pd.Period('2022-09')], o.lt, 980)]
        },
        "TSMS01": {},
        "TSMS02": { 
            'bmp2_temp': [([pd.Period('2024-02')], o.gt, 20)],
            'bmp2_pres': [([pd.Period('2024-02')], o.gt, 930)],
            'bmp2_slp': [([pd.Period('2024-02')], o.lt, 1015)]
        },
        "TSMS03": { 
            'htu_temp': [([pd.Period('2022-10')], o.lt, -30)],
            'bmp2_slp': [([pd.Period('2024-06')], o.lt, 980)]
        },
        "TSMS04": {},
        "TSMS05": {
            'bmp2_temp': [([pd.Period('2024-01')], o.gt, 17)],
            'mcp9808': [([pd.Period('2024-01')], o.gt, 17)]
        },
        "TSMS06": {
            'bmp2_temp': [
                ([pd.Period('2024-01')], o.gt, 25),
                ([pd.Period('2024-01')], o.lt, 1),
                ([pd.Period('2024-09'), pd.Period('2024-10')], o.lt, 5)
            ],
            'htu_temp': [([pd.Period('2024-09'), pd.Period('2024-10')], o.lt, 5)],
            'mcp9808': [([pd.Period('2024-09'), pd.Period('2024-10')], o.lt, 5)],
            'htu_hum': [([pd.Period('2024-09'), pd.Period('2024-10')], o.lt, 5)]
        },
        "TSMS07": {
            'bmp2_temp': [
                ([pd.Period('2022-10')], lambda s, _: s.notna(), None),
                ([pd.Period('2024-09'), pd.Period('2024-10')], o.lt, 5)
            ],
            'htu_temp': [([pd.Period('2022-10')], lambda s, _: s.notna(), None)],
            'mcp9808': [([pd.Period('2022-10')], lambda s, _: s.notna(), None)],
            'htu_hum': [([pd.Period('2022-10')], lambda s, _: s.notna(), None)],
            'bmp2_pres': [
                ([pd.Period('2022-10')], lambda s, _: s.notna(), None),
                ([pd.Period('2022-11')], o.lt, 1000)
            ],
            'bmp2_slp': [
                ([pd.Period('2022-10')], lambda s, _: s.notna(), None),
                ([pd.Period('2022-11')], o.lt, 1000)
            ]
        },
        "TSMS08": {
            'bmp2_temp': [
                (None, lambda df: df['date'].between('2022-10-01','2022-11-05'), None),
                ([pd.Period('2024-10')], o.lt, 5)
            ],
            'htu_temp': [
                (None, lambda df: df['date'].between('2022-10-01','2022-11-05'), None),
                ([pd.Period('2024-01')], o.lt, 1)
            ],
            'mcp9808': [
                (None, lambda df: df['date'].between('2022-10-01','2022-11-05'), None)
            ],
            'htu_hum': [
                (None, lambda df: df['date'].between('2022-10-01','2022-11-05'), None),
                ([pd.Period('2024-01')], o.lt, 1)
            ],
            'bmp2_pres': [
                (None, lambda df: df['date'].between('2022-10-01','2022-11-05'), None),
                ([pd.Period('2022-11')], o.lt, 980)
            ],
            'bmp2_slp': [
                (None, lambda df: df['date'].between('2022-10-01','2022-11-05'), None),
                ([pd.Period('2022-11')], o.lt, 980)
            ]
        }
    }

    station = station_directories[i][8:14]
    cleanup = station_rules.get(station)

    for sensor, rules in cleanup.items():
        df[sensor] = pd.to_numeric(df[sensor], errors="coerce")
        existing_nulls = df[sensor].isna()
        original = df[sensor].copy()

        for months, cmpfunc, thresh in rules:
            if months is None:
                mask = cmpfunc(df)
            else:
                mask_period = df["year_month"].isin(months)

                if thresh is None:
                    mask_value = original.notna()
                else:
                    mask_value = cmpfunc(original, thresh)

                mask = mask_period & mask_value

            new_null = mask & ~existing_nulls
            if new_null.any():
                to_log = original.loc[new_null]
                paws_outliers = pd.concat([
                    paws_outliers,
                    pd.DataFrame({
                        "date":           df.loc[new_null, "date"],
                        "column_name":    sensor,
                        "original_value": to_log,
                        "outlier_type":   outlier_reasons[3],
                    })
                ], ignore_index=True)

                df.loc[mask, sensor] = np.nan
                existing_nulls |= mask

    # The TSMS04 fabrication-test rain and TSMS08 faulty-connector rain removals that were here are now rows in
    # docs/station-events.csv (Step 1).


    """
    ============================================================================================================================
    Step 3: Internal consistency -- do this station's variables agree with each other?
      - Logger zeros (failed): a humidity sensor reading exactly 0 %RH in the same minute as a temperature sensor reading
        exactly 0.0 °C is the logger writing zeros, not a measurement (SF-17, TSMS06). Every exact 0 in the station's
        temperature and humidity columns in that minute is removed. 0 °C on its own is common and is not touched.
      - Rain with RH < RAIN_RH_FLAG (suspect, flagged only). TSMS removes these; real showers can start before the
        humidity sensor responds, so we keep them and report rain with and without the flag.
      - Not needed as separate checks: dewpoint <= temperature (implied by RH <= 100, Step 2); a stuck vane under a
        turning cup (Step 4b); wind direction at zero speed (set to missing in the analysis, not an error).
    ============================================================================================================================
    """
    print("Step 3: Internal consistency (logger zeros; rain vs. humidity).")
    temp_cols, hum_cols = ['bmp2_temp', 'htu_temp', 'sth_temp', 'mcp9808'], ['htu_hum', 'sth_hum']
    zeros = (paws_df_FILTERED[hum_cols] == 0).any(axis=1) & (paws_df_FILTERED[temp_cols] == 0).any(axis=1)
    n_zero = 0
    for col in temp_cols + hum_cols:
        mask = zeros & (paws_df_FILTERED[col] == 0)
        n_zero += int(mask.sum())
        paws_outliers = pd.concat([paws_outliers, removal_log(paws_df_FILTERED, mask, col, outlier_reasons[13])], ignore_index=True)
        paws_df_FILTERED.loc[mask, col] = np.nan
    print(f"\tLogger zeros: {int(zeros.sum()):,} minutes, {n_zero:,} readings removed")

    paws_rh = paws_df_FILTERED['sth_hum'].combine_first(paws_df_FILTERED['htu_hum'])
    for df_, rain, rh, flags, label in [(paws_df_FILTERED, 'tipping', paws_rh, paws_flags, '3D-PAWS'),
                                        (tsms_df_FILTERED, 'total_rainfall', tsms_df_FILTERED['humidity'], tsms_flags, 'TSMS')]:
        mask = (df_[rain] > 0) & (rh < RAIN_RH_FLAG)
        flags.append(flag_log(df_, mask, rain, flag_reasons[0]))
        print(f"\tRain with RH < {RAIN_RH_FLAG}% ({label}): {int(mask.sum()):,} minutes, "
              f"{df_.loc[mask, rain].sum():.1f} of {df_[rain].sum():.1f} mm flagged")


    """
    ============================================================================================================================
    Phase 5: Filter HTU21D "bit-switching" noise without using the TSMS reference.
        A reading is suspect when it jumps by more than TEMP_THRESHOLD / HUM_THRESHOLD from the reading one minute
        before or after. Suspect readings are then checked against independent 3D-PAWS sensors:
            - humidity:     the other 3D-PAWS stations at the same site (each station has only one humidity sensor)
            - htu_temp:     the median of the same station's other temperature sensors (bmp2_temp, mcp9808, sth_temp)
        A suspect reading is removed if it disagrees with the check, or if there is nothing to check it against
        (logged under a separate *_unverified reason so these can be counted or restored).
    ============================================================================================================================
    """
    print("Phase 5: Filtering HTU noise using step test and co-located 3D-PAWS sensors.")

    station = station_directories[i][8:14]
    site = next(k for k, v in site_stations.items() if station in v)
    paws_indexed = paws_df_FILTERED.set_index('date')     # same row order as paws_df_FILTERED

    neighbours = pd.concat([site_humidity[s] for s in site_stations[site] if s != station], axis=1, sort=True)
    station_temps = paws_indexed[['bmp2_temp', 'mcp9808', 'sth_temp']].median(axis=1)

    phase5_checks = []  # (column, confirmed mask, unverified mask, confirmed reason, unverified reason)

    for col in ['htu_hum', 'sth_hum']:
        h = paws_indexed[col]
        suspect = step_suspect(h, HUM_THRESHOLD)
        nb = neighbours.reindex(h.index)
        has_nb = nb.notna().any(axis=1)
        dev = nb.sub(h, axis=0).abs().min(axis=1)   # distance to the closest neighbouring station
        phase5_checks.append((
            col, suspect & has_nb & (dev > HUM_SITE_THRESHOLD), suspect & ~has_nb,
            outlier_reasons[7], outlier_reasons[8]
        ))

    t = paws_indexed['htu_temp']
    suspect = step_suspect(t, TEMP_THRESHOLD)
    has_ref = station_temps.notna()
    dev = (t - station_temps).abs()
    phase5_checks.append((
        'htu_temp', suspect & has_ref & (dev > TEMP_STATION_THRESHOLD), suspect & ~has_ref,
        outlier_reasons[9], outlier_reasons[10]
    ))

    for col, confirmed, unverified, confirmed_reason, unverified_reason in phase5_checks:
        for mask, reason in [(confirmed, confirmed_reason), (unverified, unverified_reason)]:
            if not mask.any(): continue
            outliers_to_add = pd.DataFrame({
                'date': mask.index[mask],
                'column_name': col,
                'original_value': paws_indexed.loc[mask, col].to_numpy(),
                'outlier_type': reason
            })
            paws_outliers = pd.concat([paws_outliers, outliers_to_add], ignore_index=True)
            paws_df_FILTERED.loc[mask.to_numpy(), col] = np.nan

    
    """
    =============================================================================================================================
    Step 4a: Step test (rate of change) on every variable except wind direction. Flag only: a jump can be a real event
    (a gust front, sun on the shield), so the neighbour check (Step 6) decides. Both ends of a jump are flagged.
    Step 4b: Persistence. Flat-lined sensors (per-column limits) and frozen loggers (all variables unchanged) are removed.
    =============================================================================================================================
    """
    print("Step 4a: Step test (flag only).")
    for df_, cols, flags, label in [(paws_df_FILTERED, paws_cols, paws_flags, '3D-PAWS'), (tsms_df_FILTERED, tsms_cols, tsms_flags, 'TSMS')]:
        indexed = df_.set_index('date')
        counts = {}
        for col in cols:
            kind = COLUMN_KIND.get(col)
            if kind not in STEP_LIMITS or col in ('bmp2_slp', 'sea_level_pressure'): continue   # SLP is derived from pressure
            mask = pd.Series(step_suspect(indexed[col], STEP_LIMITS[kind]).to_numpy(), index=df_.index)
            flags.append(flag_log(df_, mask, col, flag_reasons[1]))
            counts[col] = int(mask.sum())
        print(f"\t{label}: " + ", ".join(f"{c} {n:,}" for c, n in counts.items()))

    print("Step 4b: Persistence (flat lines, frozen logger).")
    for df_, cols, speed_col, freeze_cols, label in [
            (paws_df_FILTERED, paws_cols, 'wind_speed', ['mcp9808', 'hum', 'bmp2_pres', 'wind_speed'], '3D-PAWS'),
            (tsms_df_FILTERED, tsms_cols, 'avg_wind_speed', ['temperature', 'humidity', 'actual_pressure', 'avg_wind_speed'], 'TSMS')]:
        logs, counts = [], {}
        # frozen logger first: judged on the untouched values, then every column in the run is removed
        work = df_.assign(hum=df_['sth_hum'].combine_first(df_['htu_hum'])) if label == '3D-PAWS' else df_
        frozen = frozen_mask(work, freeze_cols)
        for col in cols:
            logs.append(removal_log(df_, frozen, col, outlier_reasons[15]))
        if frozen.any():
            runs_ = (frozen != frozen.shift()).cumsum()[frozen]
            print(f"\t{label}: frozen logger in {runs_.nunique()} period(s), {int(frozen.sum()):,} minutes")
        for col in cols:
            if COLUMN_KIND.get(col) not in PERSISTENCE_MINUTES: continue
            mask = persistence_mask(df_, col, speed_col) & ~frozen
            counts[col] = int(mask.sum())
            logs.append(removal_log(df_, mask, col, outlier_reasons[14]))
            df_.loc[mask, col] = np.nan
        df_.loc[frozen, cols] = np.nan
        log = pd.concat(logs, ignore_index=True)
        if label == '3D-PAWS': paws_outliers = pd.concat([paws_outliers, log], ignore_index=True)
        else:                  tsms_outliers = pd.concat([tsms_outliers, log], ignore_index=True)
        print(f"\t{label}: " + ", ".join(f"{c} {n:,}" for c, n in counts.items() if n))


    """
    =============================================================================================================================
    Step 5: Statistical outliers. Hampel (median/MAD) and z-score over a centred 21-minute window, floored at each
    column's resolution; readings whose window is < 60% present are 'untested'. Not applied to rain (an isolated tip
    among zeros always "fails"; rain is checked at event level in Step 6) or wind (decided 2026-09-29: at 11, 21 and 61
    min alike it flags ~1-3% of minutes, 90-95% of 3D-PAWS speed flags are gusts the neighbours also saw; wind QC is the
    step test, stuck vane, calm check and documented events). stat_outliers() keeps a circular option for direction.
    Outcome: flagged (STAT_REMOVE = False); the neighbour check (Step 6) confirms or clears. Each reading is logged once,
    as 'hampel' if the Hampel test flags it, else 'z_score'.
    =============================================================================================================================
    """
    print(f"Step 5: Statistical outliers ({STAT_WINDOW}-min Hampel/z-score, >= {STAT_MIN_SHARE:.0%} data share; "
          f"{'remove' if STAT_REMOVE else 'flag only'}).")
    tsms_df_FILTERED.reset_index(drop=True, inplace=True)
    paws_df_FILTERED.reset_index(drop=True, inplace=True)

    for df_, cols, flags, label in [
            (tsms_df_FILTERED, ['temperature', 'humidity', 'actual_pressure', 'sea_level_pressure'], tsms_flags, 'TSMS'),
            (paws_df_FILTERED, ['bmp2_temp', 'htu_temp', 'sth_temp', 'mcp9808', 'bme2_hum', 'htu_hum', 'sth_hum',
                                'bmp2_pres', 'bmp2_slp'], paws_flags, '3D-PAWS')]:
        assert (df_['date'].diff().dropna() == pd.Timedelta('1min')).all(), "Step 5 needs the regular 1-min grid"
        counts = []
        speed = df_['wind_speed' if label == '3D-PAWS' else 'avg_wind_speed']
        for col in cols:
            circular = COLUMN_KIND.get(col) == "wd"
            series = df_[col].where(speed > 0) if circular else df_[col]    # direction means nothing in calm
            z, hm, unt = stat_outliers(series, RESOLUTION_FLOOR[col], circular=circular)
            hm = pd.Series(hm, index=df_.index); zo = pd.Series(z & ~hm.to_numpy(), index=df_.index)
            unt = pd.Series(unt, index=df_.index)
            for mask, reason in [(hm, flag_reasons[2]), (zo, flag_reasons[3]), (unt, flag_reasons[4])]:
                flags.append(flag_log(df_, mask, col, reason))
            if STAT_REMOVE:
                log = pd.concat([removal_log(df_, hm, col, outlier_reasons[6]), removal_log(df_, zo, col, outlier_reasons[5])])
                if label == 'TSMS': tsms_outliers = pd.concat([tsms_outliers, log], ignore_index=True)
                else:               paws_outliers = pd.concat([paws_outliers, log], ignore_index=True)
                df_.loc[hm | zo, col] = np.nan
            if df_[col].notna().any():
                counts.append(f"{col} {int(hm.sum()) + int(zo.sum()):,} (untested {int(unt.sum()):,})")
        print(f"\t{label}: " + ", ".join(counts))

    site = "Ankara" if i in [0,1,2] else "Konya" if i in [3,4,5] else "Adana"
    sd = site_data.setdefault(site, {'stations': {}})
    if 'ref' not in sd:     # the reference is cleaned identically on every pass; keep the first
        sd['ref'] = {'df': tsms_df_FILTERED, 'outliers': [tsms_outliers], 'flags': tsms_flags}
    sd['stations'][station] = {'df': paws_df_FILTERED, 'outliers': [paws_outliers], 'flags': paws_flags}
    print("\n----------------------")


"""
=============================================================================================================================
Step 6: Spatial consistency, per site (all four instruments at once). See NEIGHBOUR_GROUPS, CALM_*, RAIN_* at the top.
=============================================================================================================================
"""
for site, sd in site_data.items():
    print(f"\nStep 6: Spatial consistency, {site}.")
    insts = {'REF': sd['ref'], **sd['stations']}
    start = min(v['df']['date'].min() for v in insts.values()); end = max(v['df']['date'].max() for v in insts.values())
    grid = pd.date_range(start, end, freq='1min')
    aligned = {k: v['df'].set_index('date').reindex(grid) for k, v in insts.items()}

    # --- 6a: flagged readings need a co-located instrument showing the same event ---------------------------------------
    for group, (paws_cols_g, ref_col, circular) in NEIGHBOUR_GROUPS.items():
        members = [('REF', ref_col)] + [(st, c) for st in sd['stations'] for c in paws_cols_g]
        members = [(k, c) for k, c in members if c in aligned[k] and aligned[k][c].notna().any()]
        if circular:     # direction only while that instrument's cups are turning
            anom = {(k, c): local_anomaly(aligned[k][c].where(aligned[k]['wind_speed' if k != 'REF' else 'avg_wind_speed'] > 0), True)
                    for k, c in members}
        else:
            anom = {(k, c): local_anomaly(aligned[k][c]) for k, c in members}
        roll3 = dict(window=2 * NEIGHBOUR_LAG + 1, center=True, min_periods=1)
        amax = {m: a.rolling(**roll3).max() for m, a in anom.items()}
        amin = {m: a.rolling(**roll3).min() for m, a in anom.items()}

        for k, c in members:
            inst = insts[k]
            fl = pd.concat(inst['flags'], ignore_index=True)
            fl = fl[(fl['column_name'] == c) & fl['flag_type'].isin([flag_reasons[1], flag_reasons[2], flag_reasons[3]])]
            dates = pd.DatetimeIndex(fl['date'].drop_duplicates())
            dates = dates[aligned[k].loc[dates, c].notna().to_numpy()] if len(dates) else dates
            if not len(dates): continue
            d = anom[(k, c)].reindex(dates)
            corroborated = pd.Series(False, index=dates); available = pd.Series(False, index=dates)
            for m in members:
                if m == (k, c): continue
                hi, lo = amax[m].reindex(dates), amin[m].reindex(dates)
                floor = RESOLUTION_FLOOR[m[1]]
                corroborated |= ((d > 0) & (hi >= np.maximum(NEIGHBOUR_SHARE * d, floor))) | \
                                ((d < 0) & (lo <= np.minimum(NEIGHBOUR_SHARE * d, -floor)))
                available |= hi.notna()
            undetermined = d.isna()                       # no local median for the reading itself: left as flagged
            inst.setdefault('corroborated', {})[c] = dates[corroborated.to_numpy()]
            if group in NEIGHBOUR_FLAG_ONLY:
                print(f"\t{k} {c}: {len(dates):,} flagged -> {int(corroborated.sum()):,} corroborated, "
                      f"{int((~corroborated & ~undetermined).sum()):,} not (all kept as flags: wind)")
                continue
            remove = ~corroborated & ~undetermined
            df_ = inst['df']; pos = df_['date'].isin(dates[remove.to_numpy()])
            no_nb = df_['date'].isin(dates[(remove & ~available).to_numpy()])
            inst['outliers'].append(removal_log(df_, pos & ~no_nb, c, outlier_reasons[16]))
            inst['outliers'].append(removal_log(df_, no_nb, c, outlier_reasons[17]))
            df_.loc[pos, c] = np.nan
            print(f"\t{k} {c}: {len(dates):,} flagged -> {int(corroborated.sum()):,} corroborated (kept), "
                  f"{int((remove & available).sum()):,} contradicted, {int((remove & ~available).sum()):,} no neighbour "
                  f"(removed), {int(undetermined.sum()):,} undetermined")

    # --- 6b: calm runs while the other 3D-PAWS anemometers show wind --------------------------------------------------
    speeds = {k: aligned[k]['wind_speed' if k != 'REF' else 'avg_wind_speed'] for k in insts}
    for k in insts:
        s_ = speeds[k]
        zero = (s_ == 0).to_numpy()
        edges = np.flatnonzero(np.diff(np.r_[0, zero.astype(int), 0]))
        nbrs = [o for o in sd['stations'] if o != k]
        bad = np.zeros(len(grid), bool)
        for a0, a1 in zip(edges[::2], edges[1::2]):          # each run of zeros: positions a0 .. a1-1
            if a1 - a0 < CALM_RUN_MINUTES: continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)     # a neighbour with no data in the run
                windy = sum(np.nanmedian(speeds[o].to_numpy()[a0:a1]) >= CALM_NEIGHBOUR_SPEED for o in nbrs)
            if windy >= 2: bad[a0:a1] = True
        bad = pd.Series(bad, index=grid)
        if bad.any():
            df_ = insts[k]['df']; col = 'wind_speed' if k != 'REF' else 'avg_wind_speed'
            mask = df_['date'].isin(grid[bad.to_numpy()])
            reason = outlier_reasons[18] if k != 'REF' else outlier_reasons[19]
            insts[k]['outliers'].append(removal_log(df_, mask, col, reason))
            df_.loc[mask, col] = np.nan
            print(f"\t{k} wind speed: {int(mask.sum()):,} calm minutes removed ({reason})")

    # --- 6c: rain, daily totals (flag only) --------------------------------------------------------------------------
    rain = {k: aligned[k]['tipping' if k != 'REF' else 'total_rainfall'] for k in insts}
    daily = pd.DataFrame({k: r.resample('D').sum(min_count=int(DAILY_COMPLETENESS * 1440)) for k, r in rain.items()})
    for k in insts:
        others = daily.drop(columns=k)
        n_other = others.notna().sum(axis=1)
        dead = (daily[k] < RAIN_DRY_MM) & ((others >= RAIN_EVENT_MM).sum(axis=1) >= 2)
        spurious = (daily[k] >= RAIN_EVENT_MM) & (n_other >= 2) & (others.fillna(0) < RAIN_DRY_MM).all(axis=1)
        df_ = insts[k]['df']; col = 'tipping' if k != 'REF' else 'total_rainfall'
        day = df_['date'].dt.floor('D')
        for days, reason in [(dead, flag_reasons[5]), (spurious, flag_reasons[6])]:
            mask = day.isin(days.index[days.to_numpy()])
            insts[k]['flags'].append(flag_log(df_, mask, col, reason))
        print(f"\t{k} rain: {int(dead.sum())} dead-gauge days, {int(spurious.sum())} uncorroborated days (flagged; "
              f"{daily.loc[spurious, k].sum():.1f} mm)")

    """
    ==========================================================================================================================
    Step 7: Daily completeness (after all other QC), then output.
    ==========================================================================================================================
    """
    print(f"Step 7: Removing days with < {DAILY_COMPLETENESS:.0%} valid minutes (per variable).")
    for k, inst in insts.items():
        cols = list(variable_mapper.keys()) if k == 'REF' else [v for vs in variable_mapper.values() for v in vs]
        log = completeness_step(inst['df'], cols)
        if log is not None: inst['outliers'].append(log)

    print("Step 8: Output with flag columns (<column>_flag; empty = good).")
    ref = sd['ref']
    add_flag_columns(ref['df'], ref['flags'], ref.get('corroborated', {}), tsms_cols, station=f"REF-{site}")
    for st, inst in sd['stations'].items():
        add_flag_columns(inst['df'], inst['flags'], inst.get('corroborated', {}),
                         [c for c in paws_cols if c != 'bme2_hum'], station=st)
    for k, inst in insts.items():
        cols = [c for c in inst['df'].columns if c.endswith('_flag')]
        n_flag = {c[:-5]: int((inst['df'][c] != '').sum()) for c in cols}
        print(f"\t{k}: flagged readings " + ", ".join(f"{c} {n:,}" for c, n in n_flag.items() if n))
    pd.concat(ref['outliers'], ignore_index=True).to_csv(data_destination + f"TSMS_Reference_{site}_outliers.csv", index=False)
    pd.concat(ref['flags'], ignore_index=True).to_csv(data_destination + f"TSMS_Reference_{site}_flags.csv", index=False)
    ref['df'].to_csv(data_destination + f"TSMS_Reference_{site}_final.csv", index=False)   # keeps year_month etc., as before
    for st, inst in sd['stations'].items():
        pd.concat(inst['outliers'], ignore_index=True).to_csv(data_destination + f"3DPAWS_{st}_{site}_outliers.csv", index=False)
        pd.concat(inst['flags'], ignore_index=True).to_csv(data_destination + f"3DPAWS_{st}_{site}_flags.csv", index=False)
        inst['df'].drop(columns=['bme2_hum', 'year_month', 'year_month_day', 'year_month_day_hour'], errors='ignore').to_csv(
            data_destination + f"3DPAWS_{st}_{site}_final.csv", index=False)


pd.DataFrame(layout_warnings_all, columns=['file', 'column', 'month', 'median', 'expected']).drop_duplicates().to_csv(
    data_destination + "structure_layout_warnings.csv", index=False)
print(f"\nStep 0 layout guard: {len(layout_warnings_all)} warning(s) -> {data_destination}structure_layout_warnings.csv")
pd.DataFrame(event_flags_all, columns=['station', 'start', 'end', 'variables', 'event', 'catalog_id', 'readings', 'notes']).drop_duplicates().to_csv(
    data_destination + "station_event_flags.csv", index=False)
print(f"Step 1 flagged periods: {len(event_flags_all)} -> {data_destination}station_event_flags.csv")
