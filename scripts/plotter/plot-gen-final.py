"""
USAGE----------------------------------------
    python scripts/plotter/plot-gen-final.py --list
        Print every plot name with a one-line description.

    python scripts/plotter/plot-gen-final.py [PLOT ...] [--stations TSMS00 TSMS06 ...] [--sites Adana ...] [--out DIR]
        Run the named plots. With no names, runs DEFAULT_PLOTS (the plots that were active before the refactor:
        just "windrose"). Per-station plots run for --stations (default: all nine); site-wide plots run for
        --sites (default: Ankara, Konya, Adana). --out overrides data_destination (default: plots/).

    From Python:  run(["windrose", "boxplots"], stations=["TSMS00"], sites=["Adana"], out=None)

Each plot section of the original single-loop script is now its own function (docstring = the original
section header). The original, pre-refactor script is kept outside the repo for reference.
"""
import argparse
import sys
import traceback
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive: figures are only ever saved
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr
from sklearn.metrics import mean_squared_error
from windrose import WindroseAxes

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from dev import functions as func

# pandas >= 3 (copy-on-write) removed SettingWithCopyWarning; keep the original filters working on both.
class _NoSuchWarning(Warning): pass
SettingWithCopyWarning = getattr(pd.errors, "SettingWithCopyWarning", _NoSuchWarning)



data_origin = Path("data/cleaned")
data_destination = Path("plots")

station_variables = [
    "temperature", "humidity", "actual_pressure", "sea_level_pressure", "wind", "total_rainfall"
]
variable_mapper = { # TSMS : 3DPAWS
    "temperature":       ["bmp2_temp", "htu_temp", "sth_temp", "mcp9808"],
    "humidity":          ["bme2_hum", "htu_hum", "sth_hum"],
    "actual_pressure":   ["bmp2_pres"],
    "sea_level_pressure":["bmp2_slp"],
    "avg_wind_dir":      ["wind_dir"],
    "avg_wind_speed":    ["wind_speed"],
    "total_rainfall":    ["tipping"]
}

instrument_to_site = {
    '3DPAWS_TSMS00_Ankara': 'Ankara',
    '3DPAWS_TSMS01_Ankara': 'Ankara',
    '3DPAWS_TSMS02_Ankara': 'Ankara',
    '3DPAWS_TSMS03_Konya':  'Konya',
    '3DPAWS_TSMS04_Konya':  'Konya',
    '3DPAWS_TSMS05_Konya':  'Konya',
    '3DPAWS_TSMS06_Adana':  'Adana',
    '3DPAWS_TSMS07_Adana':  'Adana',
    '3DPAWS_TSMS08_Adana':  'Adana',
}
site_to_reference = {
    'Ankara': 'TSMS_Reference_Ankara_final.csv',
    'Konya':  'TSMS_Reference_Konya_final.csv',
    'Adana':  'TSMS_Reference_Adana_final.csv',
}

magnetic_declinations = [
    6.11,   # Ankara
    5.73,   # Konya
    5.69    # Adana
]

# Wind regimes (same definition as scripts/error/error-analysis.py): classified from the TSMS reference only.
NONVARIABLE_THRESHOLD = 3.0     # m/s (~6 kt), reference's unadjusted 10-m speed
h1 = 10.0   # TSMS anemometer height (m)
h2 = 2.0    # 3D-PAWS anemometer height (m)
hellman_exponents = {
    "Ankara": 0.30,  # Urban
    "Konya":  0.35,  # Urban + many obstacles
    "Adana":  0.25   # Suburban + grass
}

wind_direction_bias = [ # calculated from error-analysis.py
    -148.5, # Ankara
    -136.5, # Konya
    -21.2   # Adana
] # NOTE: no longer needed, 3D-PAWS & TSMS aligned | dated 12-7-2025

station_order = [
    '3DPAWS_TSMS00_Ankara', '3DPAWS_TSMS01_Ankara', '3DPAWS_TSMS02_Ankara',
    '3DPAWS_TSMS03_Konya',  '3DPAWS_TSMS04_Konya',  '3DPAWS_TSMS05_Konya',
    '3DPAWS_TSMS06_Adana',  '3DPAWS_TSMS07_Adana',  '3DPAWS_TSMS08_Adana'
]

# Site-wide sections (originally repeated inside each section)
sites = {
    0:"Ankara", 1:"Konya", 2:"Adana"
}
station_map = {
    0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
}
ALL_SITES = list(sites.values())
sht_upgrade = [ # the day the upgrade from HTU to SHT was performed
    "2024-01-17", "2024-01-12", "2024-01-15"
] # same day that radiation shield sensor array updated

DEFAULT_PLOTS = ["windrose"]   # what was uncommented before the refactor


# =============================================================================================================================
# Helpers: paths, data loading (cached), column checks, saving
# =============================================================================================================================
def _root(p):
    """Relative config paths are relative to the repo root (the original assumed cwd == repo root)."""
    p = Path(p)
    return p if p.is_absolute() else project_root / p


_cache = {}


def _read(name):
    """Read one cleaned CSV once; add the year_month / year_month_day / year_month_day_hour period columns.
    String *_flag columns are not loaded (no plot uses them)."""
    if name not in _cache:
        path = _root(data_origin) / f"{name}_final.csv"
        print("Reading", name)
        df = pd.read_csv(path, parse_dates=['date'], usecols=lambda c: not c.endswith('_flag'))
        df['year_month'] =            df['date'].dt.to_period('M')
        df['year_month_day'] =        df['date'].dt.to_period('D')
        df['year_month_day_hour'] =   df['date'].dt.to_period('h')
        _cache[name] = df
    return _cache[name]


def load_station(paws_name):
    """(paws_df, tsms_df) for one 3D-PAWS instrument and its site reference. Both are cached; don't mutate them."""
    site = instrument_to_site[paws_name]
    return _read(paws_name), _read(f"TSMS_Reference_{site}")


def load_site(site):
    """([3 x (paws_name, paws_df)], tsms_df) for a site, in station_order."""
    names = [s for s in station_order if instrument_to_site[s] == site]
    return [(n, _read(n)) for n in names], _read(f"TSMS_Reference_{site}")


def _evict(names):
    for n in names:
        _cache.pop(n, None)


def _has(df, col, context):
    """True if df has col; otherwise print a note (sensor no longer in the cleaned CSVs) and return False."""
    if col in df.columns:
        return True
    print(f"\tNOTE: {context}: column '{col}' not in data -- skipped")
    return False


def _save(path, fig=None, **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    (fig if fig is not None else plt).savefig(path, **kwargs)


def _dest():
    return _root(data_destination)


def _site_index(site):
    return {v: k for k, v in sites.items()}[site]


def _site_frames(site, cols, context):
    """Copies of the three instruments (only date/period columns + `cols` that exist) and the reference.
    Mirrors paws_dfs[station_map[i][k]].copy(deep=True) / tsms_dfs[i*3].copy(deep=True) of the original."""
    members, tsms_df = load_site(site)
    period = ['date', 'year_month', 'year_month_day']
    insts = []
    for name, df in members:
        use = [c for c in cols if c in df.columns]
        insts.append(df[period + use].copy())
    return insts, tsms_df.copy(), [n for n, _ in members]


def _merge_site(inst_1, inst_2, inst_3, tsms_ref):
    merged_df = pd.merge(inst_1, inst_2, on='date', suffixes=('_1', '_2'))
    merged_df = pd.merge(merged_df, inst_3, on='date', suffixes=('', '_3'))
    merged_df = pd.merge(merged_df, tsms_ref, on='date', suffixes=('', '_tsms'))
    return merged_df


def _sensors_in_all(insts, sensors, context):
    ok = []
    for s in sensors:
        if all(s in df.columns for df in insts):
            ok.append(s)
        else:
            print(f"\tNOTE: {context}: sensor '{s}' missing in at least one instrument -- skipped")
    return ok


# =============================================================================================================================
# PER-STATION SECTIONS  (paws_name, paws_df, tsms_df)
# =============================================================================================================================
def timeseries_monthly(paws_name, paws_df, tsms_df, include_sea_level_pressure=False):
    """
    =============================================================================================================================
    Create a time series plot of the 3D PAWS station data versus the TSMS reference station. MONTHLY RECORDS
    =============================================================================================================================
    include_sea_level_pressure: the sea-level-pressure block was double-commented in the original (off by default).
    """
    print(f"{paws_name}: " \
            "Time-series plots for temperature, humidity, actual pressure and sea level pressure -- monthly records")

    paws_df_FILTERED = paws_df.set_index('date')
    tsms_df_FILTERED = tsms_df.set_index('date')

    tsms_df_FILTERED = tsms_df_FILTERED[paws_df_FILTERED.index[0]:paws_df_FILTERED.index[-1]]
    out = _dest() / "time-series" / f"{paws_name}"

    # Temperature ---------------------------------------------------------------------------------------------------------------
    print("Temperature per sensor")
    for t in variable_mapper['temperature']:
        if not _has(paws_df_FILTERED, t, f"{paws_name} time series"): continue
        for year_month, paws_group in paws_df_FILTERED.groupby('year_month'):
            tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

            plt.figure(figsize=(20,12))

            plt.plot(paws_group.index, paws_group[f'{t}'], marker='.', markersize=1, label=f"3D PAWS {t}")
            plt.plot(tsms_group.index, tsms_group['temperature'], marker='.', markersize=1, label='TSMS')

            plt.title(f'{paws_name} Temperature for {year_month}: 3D PAWS {t} versus TSMS')
            plt.xlabel('Date')
            plt.ylabel('Temperature (˚C)')
            plt.xticks(rotation=45)

            plt.legend()

            plt.grid(True)
            plt.tight_layout()
            _save(out / "temperature" / f"{paws_name}_{t}_{year_month}.png")

            plt.clf()
            plt.close()

    # Humidity ------------------------------------------------------------------------------------------------------------------
    print("Humidity per sensor")
    for h in variable_mapper['humidity']:
        if h == "bme2_hum": continue
        if not _has(paws_df_FILTERED, h, f"{paws_name} time series"): continue
        for year_month, paws_group in paws_df_FILTERED.groupby('year_month'):
            tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

            plt.figure(figsize=(20,12))

            plt.plot(paws_group.index, paws_group[f'{h}'], marker='.', markersize=1, label=f"3D PAWS {h}")
            plt.plot(tsms_group.index, tsms_group['humidity'], marker='.', markersize=1, label='TSMS')

            plt.title(f'{paws_name} Humidity for {year_month}: 3D PAWS {h} versus TSMS')
            plt.xlabel('Date')
            plt.ylabel('Humidity (%)')
            plt.xticks(rotation=45)

            plt.legend()

            plt.grid(True)
            plt.tight_layout()
            _save(out / "humidity" / f"{paws_name}_{h}_{year_month}.png")

            plt.clf()
            plt.close()

    # Pressure ------------------------------------------------------------------------------------------------------------------
    print("Pressure per sensor")
    for year_month, paws_group in paws_df_FILTERED.groupby("year_month"):
        tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

        plt.figure(figsize=(20,12))

        plt.plot(paws_group.index, paws_group['bmp2_pres'], marker='.', markersize=1, label="3D PAWS bmp2_pres")
        plt.plot(tsms_group.index, tsms_group['actual_pressure'], marker='.', markersize=1, label='TSMS')

        plt.title(f'{paws_name} Pressure for {year_month}: 3D PAWS bmp2_pres versus TSMS')
        plt.xlabel('Date')
        plt.ylabel('Pressure (mbar)')
        plt.xticks(rotation=45)

        plt.legend()

        plt.grid(True)
        plt.tight_layout()
        _save(out / "actual_pressure" / f"{paws_name}_bmp2-pres_{year_month}.png")

        plt.clf()
        plt.close()

    # Sea Level Pressure --------------------------------------------------------------------------------------------------------
    if include_sea_level_pressure:
        print("Sea Level Pressure per sensor")
        for year_month, paws_group in paws_df_FILTERED.groupby("year_month"):
            tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

            plt.figure(figsize=(20,12))

            plt.plot(paws_group.index, paws_group['bmp2_slp'], marker='.', markersize=1, label="3D PAWS bmp2_slp")
            plt.plot(tsms_group.index, tsms_group['sea_level_pressure'], marker='.', markersize=1, label='TSMS')

            plt.title(f'{paws_name} Sea Level Pressure for {year_month}: 3D PAWS bmp2_slp versus TSMS')
            plt.xlabel('Date')
            plt.ylabel('Pressure (mbar)')
            plt.xticks(rotation=45)

            plt.legend()

            plt.grid(True)
            plt.tight_layout()
            _save(out / "sea_level_pressure" / f"{paws_name}_bmp2-slp_{year_month}.png")

            plt.clf()
            plt.close()


def timeseries_temp_sensors(paws_name, paws_df, tsms_df):
    """
    =============================================================================================================================
    Create time series plots of the 3 temperature sensors compared to TSMS. MONTHLY RECORDS
    =============================================================================================================================
    """
    print(f"{paws_name} Temperature Comparison")
    sensors = [s for s in ["bmp2_temp", "htu_temp", "mcp9808"] if _has(paws_df, s, f"{paws_name} temp comparison")]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=SettingWithCopyWarning)

        # original relied on the previous section having set 'date' as the index of both frames
        paws_df_FILTERED = paws_df.set_index('date')
        tsms_df_FILTERED = tsms_df.set_index('date')
        tsms_df_FILTERED_2 = tsms_df_FILTERED[paws_df_FILTERED.index[0]:paws_df_FILTERED.index[-1]]

        tsms_df_FILTERED_2 = tsms_df_FILTERED_2.reset_index()
        paws_df_FILTERED = paws_df_FILTERED.reset_index()

        tsms_df_FILTERED_2['date'] = pd.to_datetime(tsms_df_FILTERED_2['date'])
        paws_df_FILTERED['date'] = pd.to_datetime(paws_df_FILTERED['date'])

        for year_month, paws_group in paws_df_FILTERED.groupby('year_month'):
            tsms_group = tsms_df_FILTERED_2[tsms_df_FILTERED_2['year_month'] == year_month]

            plt.figure(figsize=(20,12))

            for s in sensors:
                plt.plot(paws_group['date'], paws_group[s], marker='.', markersize=1, label=f"3D PAWS {s}")
            plt.plot(tsms_group['date'], tsms_group['temperature'], marker='.', markersize=1, label='TSMS')

            plt.title(f'{paws_name} Temperature Comparison for {year_month}: 3D PAWS versus TSMS')
            plt.xlabel('Date')
            plt.ylabel('Temperature (˚C)')
            plt.xticks(rotation=45)

            plt.legend()

            plt.grid(True)
            plt.tight_layout()
            _save(_dest() / "time-series" / f"{paws_name}" / "temperature" / f"{paws_name}_temp_comparison_{year_month}.png")

            plt.clf()
            plt.close()


def rain_monthly_bars(paws_name, paws_df, tsms_df):
    """
    =============================================================================================================================
    Create bar charts for monthly 3D PAWS rainfall accumulation compared to TSMS rainfall accumulation. COMPLETE RECORDS
    =============================================================================================================================
    """
    print(f"{paws_name}: " \
            "Bar charts for rainfall accumulation -- complete records")

    paws_cols = ['date', 'tipping', 'year_month']
    tsms_cols = ['date', 'total_rainfall', 'year_month']
    paws_df_FILTERED_2 = paws_df.loc[paws_df['tipping'] >= 0, paws_cols].copy().reset_index(drop=True)
    tsms_df_FILTERED_2 = tsms_df.loc[(tsms_df['total_rainfall']) >= 0, tsms_cols].copy().reset_index(drop=True)

    tsms_df_REDUCED = tsms_df_FILTERED_2[ # need to filter TSMS s.t. data timeframe equals PAWS
        (tsms_df_FILTERED_2['date'] >= paws_df_FILTERED_2['date'].iloc[0]) & \
        (tsms_df_FILTERED_2['date'] <= paws_df_FILTERED_2['date'].iloc[-1])
    ]

    paws_totals = {}
    tsms_totals = {}

    for year_month, paws_grouped in paws_df_FILTERED_2.groupby("year_month"):
        tsms_grouped = tsms_df_REDUCED[tsms_df_REDUCED['year_month'] == year_month]

        merged_df = pd.merge(paws_grouped, tsms_grouped, on='date', how='inner')  # to eliminate bias

        merged_df['cumulative_rainfall_3DPAWS'] = merged_df['tipping'].cumsum()
        merged_df['cumulative_rainfall_TSMS'] = merged_df['total_rainfall'].cumsum()

        paws_total_rainfall = merged_df['cumulative_rainfall_3DPAWS'].iloc[-1] - merged_df['cumulative_rainfall_3DPAWS'].iloc[0]
        tsms_total_rainfall = merged_df['cumulative_rainfall_TSMS'].iloc[-1] - merged_df['cumulative_rainfall_TSMS'].iloc[0]

        paws_totals[year_month] = paws_total_rainfall
        tsms_totals[year_month] = tsms_total_rainfall

    months = list(paws_totals.keys())
    paws_values = list(paws_totals.values())
    tsms_values = list(tsms_totals.values())

    index = range(len(months))

    plt.figure(figsize=(18, 12))

    bars1 = plt.bar(index, paws_values, width=0.35, color='blue', label='3DPAWS Rainfall')
    bars2 = plt.bar([i + 0.35 for i in index], tsms_values, width=0.35, color='orange', label='TSMS Rainfall')

    # Add labels, title, and legend
    plt.xlabel('Month')
    plt.ylabel('Cumulative Rainfall (mm)')
    plt.title(f'{paws_name} Monthly Rainfall Comparison: 3DPAWS vs TSMS')
    plt.xticks([i + 0.35 / 2 for i in index], [str(month) for month in months], rotation=45)
    plt.legend()

    # Add numerical values above bars
    for bar in bars1:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 2), ha='center', va='bottom', fontsize=12)

    for bar in bars2:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 2), ha='center', va='bottom', fontsize=12)

    plt.tight_layout()

    _save(_dest() / "bar-charts" / f"{paws_name}" / f"{paws_name}_monthly_rainfall.png")

    plt.clf()
    plt.close()


def rain_daily_bars(paws_name, paws_df, tsms_df):
    """
    =============================================================================================================================
    Create bar charts for daily 3D PAWS rainfall accumulation (per instrument) compared to TSMS rainfall accumulation. MONTHLY RECORDS
    =============================================================================================================================
    """
    print(f"{paws_name}: " \
                        "Bar charts for rainfall accumulation -- monthly records [INSTRUMENT VS REFERENCE COMPARISON]")

    paws_df_FILTERED = paws_df[['date', 'tipping', 'year_month', 'year_month_day']]
    tsms_df_FILTERED = tsms_df[['date', 'total_rainfall', 'year_month', 'year_month_day']]

    for year_month, paws_grouped in paws_df_FILTERED.groupby("year_month"):
        tsms_grouped = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

        merged_df = pd.merge(paws_grouped, tsms_grouped, on='date', how='inner')  # to eliminate bias

        # Calculate daily rainfall totals instead of cumulative
        merged_df['daily_rainfall_3DPAWS'] = merged_df['tipping']
        merged_df['daily_rainfall_TSMS'] = merged_df['total_rainfall']

        # Sum daily rainfall by date
        daily_totals = merged_df.groupby('year_month_day_x')[['daily_rainfall_3DPAWS', 'daily_rainfall_TSMS']].sum().reset_index()

        days = daily_totals['year_month_day_x'].dt.day
        paws_values = daily_totals['daily_rainfall_3DPAWS']
        tsms_values = daily_totals['daily_rainfall_TSMS']

        index = range(len(days))

        plt.figure(figsize=(20, 12))

        bars1 = plt.bar(index, paws_values, width=0.35, color='blue', label='3DPAWS Daily Rainfall')
        bars2 = plt.bar([i + 0.35 for i in index], tsms_values, width=0.35, color='orange', label='TSMS Daily Rainfall')

        # Add labels, title, and legend
        plt.xlabel(f'Day in {year_month}')
        plt.ylabel('Daily Rainfall (mm)')
        plt.title(f'{paws_name} Daily Rainfall Comparison: 3DPAWS vs TSMS for {year_month}')
        plt.xticks([i + 0.35 / 2 for i in index], days, rotation=45)
        plt.ylim(0, 50)
        plt.legend()

        # Add numerical values above bars
        for bar in bars1:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 1), ha='center', va='bottom', fontsize=12)

        for bar in bars2:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 1), ha='center', va='bottom', fontsize=12)

        # Display the plot
        plt.tight_layout()

        # Save the plot
        _save(_dest() / "bar-charts" / f"{paws_name}" / f"{paws_name}_{year_month}_daily_rainfall.png")

        plt.clf()
        plt.close()


WINDROSE_SPEED_BINS = [0, 2.0, 4.0, 6.0, 8.0, 10.0]
WINDROSE_LABELS = ['0-2.0 m/s', '2.0-4.0 m/s', '4.0-6.0 m/s', '6.0-8.0 m/s', '8.0-10.0 m/s']
_WR_HOURLY = {}     # paws_name -> (paws_hourly, tsms_hourly, regime_hours, regime_titles)
_WR_SCALE = {}      # site -> (rmax, ticks), shared by every rose at the site


def _windrose_hourly(paws_name, paws_df, tsms_df):
    """Hourly 10-min vector averages for one station and its reference, and the hours in each regime (cached)."""
    if paws_name in _WR_HOURLY:
        return _WR_HOURLY[paws_name]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        site = instrument_to_site[paws_name]
        top_of_hour = [51, 52, 53, 54, 55, 56, 57, 58, 59, 0]

        # 3D PAWS -----------------------------------------------------------------------------------------------------------------
        paws_wind = paws_df[['date', 'wind_speed', 'wind_dir']].copy()
        paws_wind['date'] = pd.to_datetime(paws_wind['date'])
        paws_wind['wind_speed'] = pd.to_numeric(paws_wind['wind_speed'], errors='coerce')
        paws_wind = paws_wind.dropna(subset=['wind_speed', 'wind_dir']).set_index('date')
        paws_wind = paws_wind[paws_wind.index.minute.isin(top_of_hour)]
        paws_hourly = paws_wind.groupby(paws_wind.index.floor('h') + pd.Timedelta('1h')).apply(func.paws_hourly_vectorial)

        # TSMS: Hellmann-adjusted 2-m speed for the rose, unadjusted 10-m speed for the regime ---------------------------------
        tsms_wind = tsms_df[['date', 'avg_wind_speed', 'avg_wind_dir']].copy()
        tsms_wind['date'] = pd.to_datetime(tsms_wind['date'])
        tsms_wind = tsms_wind.dropna().set_index('date')
        tsms_wind['avg_wind_speed_2m'] = tsms_wind['avg_wind_speed'] * ((h2 / h1) ** hellman_exponents[site])
        tsms_wind = tsms_wind[tsms_wind.index.minute.isin(top_of_hour)]
        tsms_groups = tsms_wind.groupby(tsms_wind.index.floor('h') + pd.Timedelta('1h'))
        tsms_hourly = tsms_groups.apply(func.tsms_hourly_vectorial)
        tsms_hourly['ref_speed_10m'] = tsms_groups['avg_wind_speed'].mean()

    common = paws_hourly.index.intersection(tsms_hourly.index)
    ref_speed = tsms_hourly.loc[common, 'ref_speed_10m']
    regime_hours = {
        'all':          common,
        'variable':     common[ref_speed < NONVARIABLE_THRESHOLD],
        'nonvariable':  common[ref_speed >= NONVARIABLE_THRESHOLD],
    }
    regime_titles = {
        'all':          "all winds",
        'variable':     f"variable winds (ref. < {NONVARIABLE_THRESHOLD} m/s at 10 m)",
        'nonvariable':  f"non-variable winds (ref. ≥ {NONVARIABLE_THRESHOLD} m/s at 10 m)",
    }
    _WR_HOURLY[paws_name] = (paws_hourly, tsms_hourly, regime_hours, regime_titles)
    return _WR_HOURLY[paws_name]


def _rose_table(hourly):
    """The windrose library's own normed frequency table (% per speed bin x direction sector) for the non-calm hours."""
    windy = hourly[hourly['ws_avg'] > 0]
    if windy.empty:
        return None
    ax = WindroseAxes.from_ax()
    ax.bar(windy['wd_avg'], windy['ws_avg'], normed=True, opening=0.8, edgecolor='white', bins=WINDROSE_SPEED_BINS)
    table = ax._info['table']
    plt.close(ax.figure)
    return table


def _nice_scale(peak):
    """Radial maximum and ring positions: the smallest 'nice' step giving at most 6 rings that covers peak (%)."""
    for step in (1, 2, 2.5, 5, 10, 20, 25, 50):
        n = int(np.ceil(peak / step))
        if n <= 6:
            rmax = max(n, 1) * step
            return rmax, np.arange(step, rmax + step / 2, step)
    return 100.0, np.arange(20, 101, 20)


def _windrose_site_scale(site):
    """One radial scale per site: covers the largest sector of every rose at the site (all three 3D-PAWS stations and
    the reference, all / variable / non-variable winds), so every ring means the same percentage on every rose there."""
    if site not in _WR_SCALE:
        peak = 0.0
        for name in [n for n in station_order if instrument_to_site[n] == site]:
            p_df, t_df = load_station(name)
            paws_hourly, tsms_hourly, regime_hours, _ = _windrose_hourly(name, p_df, t_df)
            for hours in regime_hours.values():
                for hourly in (paws_hourly.loc[hours], tsms_hourly.loc[hours]):
                    table = _rose_table(hourly)
                    if table is not None:
                        peak = max(peak, table.sum(axis=0).max())
        _WR_SCALE[site] = _nice_scale(peak)
        print(f"	{site}: shared wind-rose scale 0–{_WR_SCALE[site][0]:g}% (largest sector {peak:.1f}%)")
    return _WR_SCALE[site]


def windrose(paws_name, paws_df, tsms_df):
    """
    =============================================================================================================================
    Create wind rose plots of the 3D PAWS station data as well as the TSMS reference station. COMPLETE RECORDS
    Hourly values are 10-min vector averages over (:50, :00]. Every hour is classified from the TSMS reference ONLY:
        non-variable = reference 10-min mean of the unadjusted 10-m speed >= NONVARIABLE_THRESHOLD (3.0 m/s, ~6 kt)
        variable     = below that
    Both roses of a regime use the same hours (hours where both instruments report), so they're directly comparable.
    Zero-speed minutes are kept: they add a zero vector, so the stale 3D-PAWS vane direction carries no weight.
    Hours whose vector-mean speed is 0 are calm -- they have no direction, so they're counted in the legend, not drawn.
    Radial rings are the same for every rose at a site (3D-PAWS and reference, all / variable / non-variable winds);
    the legend gives N, the number of hourly values drawn.
    =============================================================================================================================
    """
    print(f"{paws_name}: Wind roses (all / variable / non-variable winds, classified by the reference).")
    site = instrument_to_site[paws_name]
    paws_hourly, tsms_hourly, regime_hours, regime_titles = _windrose_hourly(paws_name, paws_df, tsms_df)
    rmax, ticks = _windrose_site_scale(site)

    out_dir = _dest() / "wind-roses" / paws_name
    out_dir.mkdir(parents=True, exist_ok=True)

    for regime, hours in regime_hours.items():
        roses = [
            (paws_hourly.loc[hours], f"{paws_name}",            out_dir / f"{paws_name}_{regime}_winds_[10-MIN-AVG].png"),
            (tsms_hourly.loc[hours], f"TSMS Reference {site}",  out_dir / f"TSMS-Reference_{site}_{regime}_winds_[10-MIN-AVG].png"),
        ]
        if any((r[0]['ws_avg'] > 0).sum() == 0 for r in roses):
            print(f"\t{regime}: no non-calm hours for one of the instruments -- skipped")
            continue

        for hourly, name, path in roses:
            calm = hourly['ws_avg'] <= 0
            windy = hourly[~calm]
            ax = WindroseAxes.from_ax()
            ax.bar(windy['wd_avg'], windy['ws_avg'], normed=True, opening=0.8, edgecolor='white', bins=WINDROSE_SPEED_BINS)
            ax.set_legend(title=f"{name} (m/s)\n{regime_titles[regime]}\nN = {len(windy):,} hourly values\n"
                                f"(calm: {calm.sum():,} h, {100 * calm.mean():.1f}%, not drawn)",
                          labels=WINDROSE_LABELS, loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8, title_fontsize=8)
            ax.set_rmax(rmax)
            ax.set_yticks(ticks)
            ax.set_yticklabels([f"{t:g}%" for t in ticks])
            ax.grid(True, linewidth=0.5)
            ax.figure.savefig(path, bbox_inches="tight")
            plt.close(ax.figure)

        print(f"\t{regime}: {len(hours)} hours")


def windrose_monthly(paws_name, paws_df, tsms_df, regime="nonvariable", apply_declination=False,
                     replicate_tsms_study_window=False):
    """
    =============================================================================================================================
    Create wind rose plots of the 3D PAWS station data as well as the TSMS reference station. MONTHLY RECORDS
    NOTE: Still need to add 10-minute averaging to capture steady state wind speed and direction
    =============================================================================================================================
    regime="nonvariable" (the original's active choice): 3D-PAWS and TSMS minutes with their OWN speed >= 3.0 m/s,
        bins 2-10 m/s, radial axis 0-100 %.
    regime="variable" (the original's commented alternative): 3D-PAWS wind_speed > 0; TSMS with the (speed==0 & dir==0)
        rows removed (the original's line that the non-variable filter overwrote); bins 0-10 m/s, radial axis 0-60 %.
    apply_declination: the original's commented-out wind_dir_true = wind_dir + declination + bias (computed but the
        rose still plots wind_dir, exactly as in the original).
    replicate_tsms_study_window: the original's commented 2022-09-09 00:00 .. 2023-02-24 12:42 window.
    """
    print(f"{paws_name}: Wind roses for 3D PAWS and TSMS -- monthly records")
    variable = regime == "variable"
    site = instrument_to_site[paws_name]

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=SettingWithCopyWarning)
        warnings.filterwarnings("ignore", category=RuntimeWarning)

        # 3D PAWS -------------------------------------------------------------------------------------------------------------------
        print("3D PAWS")
        paws_df_FILTERED = paws_df[['date', 'wind_speed', 'wind_dir', 'year_month']].copy()
        paws_df_FILTERED['date'] = pd.to_datetime(paws_df_FILTERED['date'])

        paws_df_FILTERED['wind_speed'] = pd.to_numeric(paws_df_FILTERED['wind_speed'], errors='coerce')
        if variable:
            paws_df_FILTERED_2 = paws_df_FILTERED[(paws_df_FILTERED["wind_speed"] > 0)]      # for variable winds
        else:
            paws_df_FILTERED_2 = paws_df_FILTERED[paws_df_FILTERED['wind_speed'] >= 3.0]    # for NON-variable winds

        if apply_declination:
            if paws_name.endswith("Ankara"):
                paws_df_FILTERED_2['wind_dir_true'] = (paws_df_FILTERED_2['wind_dir'] + magnetic_declinations[0] + wind_direction_bias[0]) % 360
            elif paws_name.endswith("Konya"):
                paws_df_FILTERED_2['wind_dir_true'] = (paws_df_FILTERED_2['wind_dir'] + magnetic_declinations[1] + wind_direction_bias[1]) % 360
            else:
                paws_df_FILTERED_2['wind_dir_true'] = (paws_df_FILTERED_2['wind_dir'] + magnetic_declinations[2] + wind_direction_bias[2]) % 360

        paws_df_FILTERED_2 = paws_df_FILTERED_2.set_index('date')

        if replicate_tsms_study_window:
            first_timestamp = pd.Timestamp("2022-09-09 00:00") # for replicating the TSMS intercomparison study
            last_timestamp = pd.Timestamp("2023-02-24 12:42")
        else:
            first_timestamp = paws_df_FILTERED_2.index[0]
            last_timestamp = paws_df_FILTERED_2.index[-1]

        if variable:
            wind_speed_bins = [0, 2.0, 4.0, 6.0, 8.0, 10.0]
            labels = ['0-2.0 m/s', '2.0-4.0 m/s', '4.0-6.0 m/s', '6.0-8.0 m/s', '8.0-10.0 m/s']       # for variable winds
            rmax, yticks, yticklabels = 60, [12, 24, 36, 48, 60], ['12%', '24%', '36%', '48%', '60%']
        else:
            wind_speed_bins = [2.0, 4.0, 6.0, 8.0, 10.0]
            labels = [f"{wind_speed_bins[i]}–{wind_speed_bins[i+1]} m/s" for i in range(len(wind_speed_bins)-1)]  # for NON-variable winds
            rmax, yticks, yticklabels = 100, [20, 40, 60, 80, 100], ['20%', '40%', '60%', '80%', '100%']

        paws_df_FILTERED_2.loc[:, 'wind_speed_category'] = pd.cut(paws_df_FILTERED_2['wind_speed'], bins=wind_speed_bins, labels=labels, right=False)

        for year_month, paws_group in paws_df_FILTERED_2.groupby("year_month"):
            plt.figure(figsize=(20, 12))

            ax = WindroseAxes.from_ax()
            ax.bar(paws_group['wind_dir'], paws_group['wind_speed'], normed=True, opening=0.8, edgecolor='white', bins=wind_speed_bins)
            ax.set_legend(title=f"{paws_name} for {year_month} (m/s)", labels=labels)

            ax.set_rmax(rmax)
            ax.set_yticks(yticks)
            ax.set_yticklabels(yticklabels)

            ax.grid(True, linewidth=0.5)  # Thinner grid lines can improve readability

            if variable:
                _save(_dest() / "wind-roses" / f"{paws_name}" / f"{paws_name}_{year_month}_variable_winds.png")
            else:
                _save(_dest() / "wind-roses" / f"{paws_name}" / f"{paws_name}_{year_month}_nonvariable_winds.png")
            plt.clf()
            plt.close('all')   # original plt.close() left the empty 20x12 figure open


        # TSMS ----------------------------------------------------------------------------------------------------------------------
        print("TSMS") # TSMS dataset was already cleaned
        tsms_df_FILTERED = tsms_df[['date', 'avg_wind_speed', 'avg_wind_dir', 'year_month']].copy()
        tsms_df_FILTERED['date'] = pd.to_datetime(tsms_df_FILTERED['date'])

        tsms_df_FILTERED_2 = tsms_df_FILTERED[~((tsms_df_FILTERED['avg_wind_speed'] == 0.0) & (tsms_df_FILTERED['avg_wind_dir'] == 0.0))]
        if not variable:
            tsms_df_FILTERED_2 = tsms_df_FILTERED[tsms_df_FILTERED['avg_wind_speed'] >= 3.0]  # for NON-variable winds

        # Apply Hellman correction to 2m
        # NOTE: this section uses its own neutral-stability exponent, not the per-site hellman_exponents above.
        hellman_exp = 0.14  # Neutral stability, short grass[web:362]

        tsms_df_FILTERED_2['avg_wind_speed_2m'] = tsms_df_FILTERED_2['avg_wind_speed'] * \
            ((h2 / h1) ** hellman_exp)

        tsms_df_FILTERED_2 = tsms_df_FILTERED_2.set_index('date')

        tsms_subset = tsms_df_FILTERED_2.loc[first_timestamp:last_timestamp]

        tsms_subset.loc[:, 'wind_speed_category'] = pd.cut(tsms_subset['avg_wind_speed_2m'], bins=wind_speed_bins, labels=labels, right=False)

        for year_month, tsms_group in tsms_subset.groupby("year_month"):
            plt.figure(figsize=(20, 12))

            ax = WindroseAxes.from_ax()
            ax.bar(tsms_group['avg_wind_dir'], tsms_group['avg_wind_speed_2m'], normed=True, opening=0.8, edgecolor='white', bins=wind_speed_bins)

            ax.set_legend(title=f"TSMS Reference at {site} for {year_month} (m/s)", labels=labels)

            ax.set_rmax(rmax)
            ax.set_yticks(yticks)
            ax.set_yticklabels(yticklabels)

            ax.grid(True, linewidth=0.5)  # Thinner grid lines can improve readability

            if variable:
                _save(_dest() / "wind-roses" / site /  f"TSMS-Reference_{year_month}_variable_winds.png")
            else:
                _save(_dest() / "wind-roses" / site /  f"TSMS-Reference_{site}_{year_month}_nonvariable_winds.png")

            plt.clf()
            plt.close('all')


def _scatter_stats_box(x, y):
    # Calculate correlation coefficient
    corr_coef, _ = pearsonr(x, y)
    plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')
    return corr_coef


def scatter_vs_ref(paws_name, paws_df, tsms_df):
    """
    =============================================================================================================================
    Create scatter plots for each 3D PAWS sensor compared to the TSMS reference data. COMPLETE RECORDS
    =============================================================================================================================
    """
    print(f"{paws_name}: " \
                        "Scatter plots for temperature, humidity, actual pressure, sea level pressure, and rain\n" \
                        "3D PAWS vs TSMS")

    for variable in station_variables:
        print(f"{variable} -- 3D PAWS vs TSMS")

        if variable == 'wind': variable = 'avg_wind_speed'

        for v in variable_mapper[f'{variable}']:
            if v in ['bme2_hum', 'wind_dir', 'bmp2_slp']:
                continue
            if not _has(paws_df, v, f"{paws_name} scatter"): continue

            if v == 'tipping':
                merged_df = pd.merge(
                    paws_df[['date', f"{v}"]],
                    tsms_df[['date', f"{variable}"]],
                    on='date',
                    how='inner'
                )

                hourly_totals = (
                    merged_df
                    .set_index('date')
                    .resample('h')     # group into 1-hour bins
                    [[v, variable]]    # PAWS vs TSMS cols
                    .sum()             # sum rainfall within each hour
                    .reset_index()
                )

                x = hourly_totals[v]
                y = hourly_totals[variable]

                mask = x.notna() & y.notna()
                x, y = x[mask], y[mask]

                plt.figure(figsize=(6, 6))

                plt.scatter(x, y, alpha=0.5, s=10)

                # Calculate and plot trend line
                m, b = np.polyfit(x, y, 1)

                x_line = np.linspace(x.min(), x.max(), 100)
                y_line = (m * x_line) + b

                plt.plot(x_line, y_line, color='red', linewidth=2, label='Trend line')

                corr_coef = _scatter_stats_box(x, y)

                # Calculate RMSE
                rmse = np.sqrt(mean_squared_error(y, x))
                textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
                bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
                plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
                        verticalalignment='top', bbox=bbox_props)

                plt.title(f'{paws_name} 3D PAWS Rainfall versus TSMS')
                plt.xlabel(f'3D PAWS Rainfall')
                plt.ylabel(f"TSMS {variable}")

                plt.legend()
                plt.grid(True)
                plt.tight_layout()

                _save(_dest() / "statistical" / "scatter-plots" / f"{paws_name}" / "total_rainfall" / f"{paws_name}_rainfall_scatter-plot.png")

                plt.clf()
                plt.close()

                continue


            merged_df = pd.merge(
                paws_df[['date', f"{v}"]],
                tsms_df[['date', f"{variable}"]],
                on='date',
                how='inner'
            )

            x = merged_df[f'{v}'].to_numpy()
            y = merged_df[f'{variable}'].to_numpy()

            if len(x) == 0 or len(y) == 0:
                print(f"Skipping {paws_name} {v} vs {variable}: no overlapping data")
                continue

            mask = np.isfinite(x) & np.isfinite(y)
            x, y = x[mask], y[mask]

            if len(x) == 0 or len(y) == 0:
                print(f"Skipping {paws_name} {v} vs {variable}: no finite data after filtering")
                continue

            plt.figure(figsize=(6, 6))

            plt.scatter(x, y, s=10)

            # Calculate and plot trend line
            m, b = np.polyfit(x, y, 1)
            x_line = np.linspace(x.min(), x.max(), 100)
            y_line = (m * x_line) + b

            plt.plot(x_line, y_line, color='red', linewidth=2, label='Trend line')

            corr_coef = _scatter_stats_box(x, y)

            # Calculate RMSE
            rmse = np.sqrt(mean_squared_error(y, x))
            textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
            bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
            plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
                    verticalalignment='top', bbox=bbox_props)

            plt.title(f'{paws_name} 3D PAWS {v} versus TSMS')
            plt.xlabel(f'3D PAWS {v}')
            plt.ylabel(f"TSMS {variable}")

            plt.legend()
            plt.grid(True)
            plt.tight_layout()

            folder = "wind" if variable == "avg_wind_speed" else variable

            # NOTE (as in the original): the file name has no sensor in it, so for temperature/humidity each sensor
            # overwrites the previous one and only the last sensor's plot survives.
            _save(_dest() / "statistical" / "scatter-plots" / f"{paws_name}" / f"{folder}" / f"{paws_name}_{folder}_scatter-plot.png")

            plt.clf()
            plt.close()


def scatter_temp_sensors(paws_name, paws_df, tsms_df):
    """
    =============================================================================================================================
    Create scatter plots for each 3D PAWS sensor compared to other 3D PAWS sensors (temp only). COMPLETE RECORDS
    ----> currently broke, skipping due to time constraints
    =============================================================================================================================
    Refactor fixes (minimal, so it runs): the original saved to `data_destination+station_directories[i]+"temperature\\..."`
    (Path + str, undefined station_directories) -> now statistical/scatter-plots/<station>/temperature/; NaN rows are
    dropped per pair (np.polyfit fails on NaN). The first trend line is still drawn against htu_temp, as in the original.
    """
    print(f"{paws_name}: " \
                        "Scatter plots for temperature -- complete records\n3D PAWS vs 3DPAWS")
    for s in ["bmp2_temp", "htu_temp", "mcp9808"]:
        if not _has(paws_df, s, f"{paws_name} temp-sensor scatter"): return

    out = _dest() / "statistical" / "scatter-plots" / f"{paws_name}" / "temperature"

    merged_bmp_vs_htu = pd.merge(
        paws_df[['date', "bmp2_temp"]],
        paws_df[['date', 'htu_temp']],
        on='date',
        how='inner'
    ).dropna()
    merged_bmp_vs_mcp = pd.merge(
        paws_df[['date', "bmp2_temp"]],
        paws_df[['date', 'mcp9808']],
        on='date',
        how='inner'
    ).dropna()
    merged_htu_vs_mcp = pd.merge(
        paws_df[['date', "htu_temp"]],
        paws_df[['date', 'mcp9808']],
        on='date',
        how='inner'
    ).dropna()

    bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)

    # bmp2 vs htu -----------------------------------------------------------------------------------------------------------
    plt.figure(figsize=(20, 12))

    plt.scatter(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"], alpha=0.5, s=10)

    m, b = np.polyfit(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"], 1)
    plt.plot(merged_bmp_vs_htu["htu_temp"], m*merged_bmp_vs_htu["htu_temp"] + b, color='red', linewidth=2, label='Trend line')

    corr_coef, _ = pearsonr(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"])
    plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    rmse = np.sqrt(mean_squared_error(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"]))
    textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
            verticalalignment='top', bbox=bbox_props)

    plt.title(f'{paws_name} -- 3D PAWS bmp2_temp versus 3D PAWS htu_temp')
    plt.xlabel('3D PAWS bmp2_temp')
    plt.ylabel('3D PAWS htu_temp')

    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    _save(out / f"{paws_name}_bmp_vs_htu_scatter.png")

    plt.clf()
    plt.close()

    # bmp2 vs mcp9808 -------------------------------------------------------------------------------------------------------
    plt.figure(figsize=(20, 12))

    plt.scatter(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"], alpha=0.5, s=10)

    m, b = np.polyfit(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"], 1)
    plt.plot(merged_bmp_vs_mcp["bmp2_temp"], m*merged_bmp_vs_mcp["bmp2_temp"] + b, color='red', linewidth=2, label='Trend line')

    corr_coef, _ = pearsonr(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"])
    plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    rmse = np.sqrt(mean_squared_error(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"]))
    textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
            verticalalignment='top', bbox=bbox_props)

    plt.title(f'{paws_name} -- 3D PAWS bmp2_temp versus 3D PAWS mcp9808')
    plt.xlabel('3D PAWS bmp2_temp')
    plt.ylabel('3D PAWS mcp9808')

    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    _save(out / f"{paws_name}_bmp_vs_mcp9808_scatter.png")

    plt.clf()
    plt.close()

    # htu vs mcp9808 --------------------------------------------------------------------------------------------------------
    plt.figure(figsize=(20, 12))

    plt.scatter(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"], alpha=0.5, s=10)

    m, b = np.polyfit(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"], 1)
    plt.plot(merged_htu_vs_mcp["mcp9808"], m*merged_htu_vs_mcp["mcp9808"] + b, color='red', linewidth=2, label='Trend line')

    corr_coef, _ = pearsonr(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"])
    plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    rmse = np.sqrt(mean_squared_error(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"]))
    textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
            verticalalignment='top', bbox=bbox_props)

    plt.title(f'{paws_name} -- 3D PAWS mcp9808 versus 3D PAWS htu_temp')
    plt.xlabel('3D PAWS mcp9808')
    plt.ylabel('3D PAWS htu_temp')

    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    _save(out / f"{paws_name}_mcp9808_vs_htu_scatter.png")

    plt.clf()
    plt.close()


def boxplots(paws_name, paws_df, tsms_df):
    """
    =============================================================================================================================
    Creating box plots for temperature, relative humidity, pressure, wind speed, and rain. COMPLETE RECORDS
    =============================================================================================================================
    Wind-speed and precipitation box plots were commented out in the original as "not relevant" (and both re-used
    combined_pres_df by mistake); they are not produced.
    Frames are joined on the date index (in the original run order the time-series section had already set 'date'
    as the index; with a plain RangeIndex the index join would pair unrelated rows).
    """
    print(f"{paws_name} Box Plots")

    paws_temp_cols = ['bmp2_temp', 'htu_temp', 'mcp9808']
    paws_hum_cols = ['htu_hum']
    paws_pres_cols = ['bmp2_pres']
    paws_wind_cols = ['wind_speed']
    paws_rain_cols = ['tipping']
    tsms_temp_cols = ['temperature']
    tsms_hum_cols = ['humidity']
    tsms_pres_cols = ['actual_pressure']
    tsms_wind_cols = ['avg_wind_speed']
    tsms_rain_cols = ['total_rainfall']

    tick_names = {
        'bmp2_temp': 'BMP2 Temp', 'htu_temp': 'HTU Temp', 'mcp9808': 'MCP9808 Temp', 'temperature': 'TSMS Reference Temp',
        'htu_hum': 'HTU Hum', 'humidity': 'TSMS Reference Hum',
        'bmp2_pres': 'BMP2 Pressure', 'actual_pressure': 'TSMS Reference Pressure',
    }

    def present(cols):
        return [c for c in cols if _has(paws_df, c, f"{paws_name} box plots")]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)

        paws_cols = present(paws_temp_cols + paws_hum_cols + paws_pres_cols + paws_wind_cols + paws_rain_cols)
        combined_df = paws_df.set_index('date')[paws_cols].merge(
            tsms_df.set_index('date')[tsms_temp_cols + tsms_hum_cols + tsms_pres_cols + tsms_wind_cols + tsms_rain_cols],
            left_index=True, right_index=True
        )
        combined_temp_df = combined_df[[c for c in paws_temp_cols if c in paws_cols] + ['temperature']]
        combined_hum_df = combined_df[[c for c in paws_hum_cols if c in paws_cols] + ['humidity']]
        combined_pres_df = combined_df[[c for c in paws_pres_cols if c in paws_cols] + ['actual_pressure']]

        out = _dest() / "statistical" / "box-plots" / f"{paws_name}"

        # temperature box plot
        plt.figure(figsize=(12, 12))
        sns.boxplot(data=combined_temp_df, palette=['blue', 'orange', 'green', 'red'][:len(combined_temp_df.columns) - 1] + ['red'])

        plt.title(f'{paws_name} Temperature Box Plot: 3D-PAWS & TSMS')
        plt.xlabel('Temperature Sensors')
        plt.ylabel('Temperature (°C)')
        plt.xticks(range(len(combined_temp_df.columns)), [tick_names[c] for c in combined_temp_df.columns])
        plt.grid(True)

        plt.tight_layout()
        _save(out / "temperature" / f"{paws_name}_box-plot.png")
        plt.clf()
        plt.close()

        # humidity boxplot
        plt.figure(figsize=(12, 12))
        sns.boxplot(data=combined_hum_df, palette=['blue', 'red'])

        plt.title(f'{paws_name} Humidity Box Plot: 3D-PAWS & TSMS')
        plt.xlabel('Humidity Sensors')
        plt.ylabel('Humidity (%)')
        plt.xticks(range(len(combined_hum_df.columns)), [tick_names[c] for c in combined_hum_df.columns])
        plt.grid(True)

        plt.tight_layout()
        _save(out / "humidity" / f"{paws_name}_box-plot.png")
        plt.clf()
        plt.close()

        # pressure box plots
        plt.figure(figsize=(12, 12))
        sns.boxplot(data=combined_pres_df, palette=['blue', 'red'])

        plt.title(f'{paws_name} Pressure Box Plot: 3D-PAWS & TSMS')
        plt.xlabel('Pressure Sensors')
        plt.ylabel('Station Pressure (hPa)')
        plt.xticks(range(len(combined_pres_df.columns)), [tick_names[c] for c in combined_pres_df.columns])
        plt.grid(True)

        plt.tight_layout()
        _save(out / "actual_pressure" / f"{paws_name}_box-plot.png")
        plt.clf()
        plt.close()


def violins(paws_name, paws_df, tsms_df):
    """
    =============================================================================================================================
    Violin plots for temperature, humidity, and pressure. COMPLETE RECORDS
    * this style of plot is uninformative for wind speed and precip
    =============================================================================================================================
    (The original also carried an older, fully commented duplicate of this section; it produced the same plots.)
    """
    print(f"{paws_name} Violin Plots")

    y_axis_labels = {
        'temperature': 'Temperature (˚C)',
        'humidity': 'Relative Humidity (%)',
        'actual_pressure': 'Pressure (hPa)'
    }

    paws_for_plots = paws_df
    tsms_for_plots = tsms_df

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)   # seaborn: palette without hue

        for var in station_variables:
            if var in ['sea_level_pressure', 'wind', 'total_rainfall']:
                continue

            for v in variable_mapper[var]:
                if v in ['bme2_hum']:
                    continue
                if not _has(paws_df, v, f"{paws_name} violins"): continue

                x_axis_labels = {
                    v: f'3D-PAWS ({v})',
                    var: 'TSMS Reference Sensor'
                }
                custom_palette = {
                    x_axis_labels[v]: "#1f77b4",        # Blue
                    "TSMS Reference Sensor": "#d62728"  # Red
                }

                merged_df = pd.merge(
                    paws_for_plots[['date', v]],
                    tsms_for_plots[['date', var]],
                    on='date',
                    suffixes=['_paws', '_tsms']
                )

                long_df = pd.melt(  # Seaborn expects data in long format
                    merged_df,
                    id_vars='date',
                    value_vars=[v, var],
                    var_name='Source',
                    value_name='Value'
                )
                long_df['Source'] = long_df['Source'].map(x_axis_labels)

                plt.figure(figsize=(12, 12))
                sns.violinplot(x='Source', y='Value', data=long_df, palette=custom_palette, inner='box')
                plt.title(f"{paws_name} Violin Plot of {var[0].upper() + var[1:]}: 3D PAWS ({v}) vs TSMS Reference Sensor")
                plt.ylabel(y_axis_labels[var])
                plt.tight_layout()
                _save(
                    _dest() / "statistical" / "violin-plots" / f"{paws_name}" / f"{var}" / f"{paws_name}_{v}_violin-plot.png"
                )
                plt.clf()
                plt.close()


def histograms(paws_name, paws_df, tsms_df):
    """
    =============================================================================================================================
    Creating histograms for each variable. COMPLETE RECORDS
    =============================================================================================================================
    NOTE (kept from the original): the reference file name is chosen by comparing paws_name to '3DPAWS-TSMS00' etc.
    (hyphens), which never matches names like '3DPAWS_TSMS00_Ankara', so every reference histogram is named TSMS-Adana_*.
    """
    print(f"{paws_name} Histograms")
    out = _dest() / "statistical" / "histograms" / f"{paws_name}"

    for variable in variable_mapper.keys():
        if variable in ['sea_level_pressure', 'total_rainfall']: continue

        for var in variable_mapper[variable]:
            if var in ['bme2_hum']: continue
            if not _has(paws_df, var, f"{paws_name} histograms"): continue

            merged_df = pd.merge(
                paws_df[['date', var]],
                tsms_df[['date' ,variable]],
                on='date',
                suffixes=['_paws', '_tsms']
            )

            cleaned_df = merged_df.dropna(subset=[var, variable])

            plt.figure(figsize=(12,12))
            plt.hist(cleaned_df[var], bins=15, edgecolor='black')
            plt.xlabel(variable[0].upper() + variable[1:])
            plt.ylabel("Frequency")
            plt.title(f"3D-PAWS {variable[0].upper()+variable[1:]} ({var})")
            plt.tight_layout()
            if variable in ['avg_wind_speed', 'avg_wind_dir']:
                _save(out / "wind" / f"{paws_name}_{variable}_histogram.png")
            else:
                _save(out / f"{variable}" / f"{paws_name}_{var}_histogram.png")
            plt.clf()
            plt.close()

            plt.figure(figsize=(12,12))
            plt.hist(cleaned_df[variable], bins=15, edgecolor='black', color='indianred')
            plt.xlabel(variable[0].upper()+variable[1:])
            plt.ylabel("Frequency")
            plt.title(f"TSMS {variable[0].upper()+variable[1:]}")
            plt.tight_layout()
            if variable in ['avg_wind_speed', 'avg_wind_dir']:
                if paws_name in ['3DPAWS-TSMS00', '3DPAWS-TSMS01', '3DPAWS-TSMS02']:
                    _save(out / "wind" / f"TSMS-Ankara_{variable}_histogram.png")
                elif paws_name in ['3DPAWS-TSMS03', '3DPAWS-TSMS04', '3DPAWS-TSMS05']:
                    _save(out / "wind" / f"TSMS-Konya_{variable}_histogram.png")
                else:
                    _save(out / "wind" / f"TSMS-Adana_{variable}_histogram.png")
            else:
                if paws_name in ['3DPAWS-TSMS00', '3DPAWS-TSMS01', '3DPAWS-TSMS02']:
                    _save(out / f"{variable}" /  f"TSMS-Ankara_histogram.png")
                elif paws_name in ['3DPAWS-TSMS03', '3DPAWS-TSMS04', '3DPAWS-TSMS05']:
                    _save(out / f"{variable}" /  f"TSMS-Konya_histogram.png")
                else:
                    _save(out / f"{variable}" /  f"TSMS-Adana_histogram.png")
            plt.clf()
            plt.close()


# =============================================================================================================================
# SITE-WIDE SECTIONS  (site)
# =============================================================================================================================
def _site_monthly_lines(site, sensors, ref_col, context, draw):
    """Shared month loop of the three site-wide MONTHLY time-series sections."""
    i = _site_index(site)
    (inst_1, inst_2, inst_3), tsms_ref, _ = _site_frames(site, sensors, context)
    tsms_ref = tsms_ref[['date', 'year_month', 'year_month_day', ref_col]]
    sensors = _sensors_in_all([inst_1, inst_2, inst_3], sensors, context)

    for year_month in set(inst_1['year_month']) & \
                        set(inst_2['year_month']) & \
                            set(inst_3['year_month']) & \
                                set(tsms_ref['year_month']):
        inst_1_grouped = inst_1[inst_1['year_month'] == year_month]
        inst_2_grouped = inst_2[inst_2['year_month'] == year_month]
        inst_3_grouped = inst_3[inst_3['year_month'] == year_month]
        tsms_grouped = tsms_ref[tsms_ref['year_month'] == year_month]

        merged_df = _merge_site(inst_1_grouped, inst_2_grouped, inst_3_grouped, tsms_grouped)
        draw(i, year_month, merged_df, sensors)


def site_temp_monthly(site):
    """
    =============================================================================================================================
    Site-wide comparison of each type of temperature sensor versus the reference. MONTHLY RECORDS
    =============================================================================================================================
    """
    print(f"\t{site}: Temperature Comparison per sensor per site")

    def draw(i, year_month, merged_df, sensors):
        for sensor in sensors:
            plt.figure(figsize=(20, 12))

            plt.plot(merged_df['date'], merged_df[f'{sensor}_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} {sensor}")
            plt.plot(merged_df['date'], merged_df[f'{sensor}_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} {sensor}")
            plt.plot(merged_df['date'], merged_df[f'{sensor}'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} {sensor}")
            plt.plot(merged_df['date'], merged_df[f'temperature'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

            plt.title(f'{sites[i]} {year_month}: {sensor} Temperature Comparison')
            plt.xlabel('Date')
            plt.ylabel('Temperature (˚C)')
            plt.xticks(rotation=45)

            plt.legend()

            plt.grid(True)
            plt.tight_layout()

            _save(_dest() / "time-series" / f"{sites[i]}" / "temperature" / "trends" / f"{sites[i]}_{sensor}_{year_month}_temp_comparison.png")

            plt.clf()
            plt.close()

    _site_monthly_lines(site, variable_mapper['temperature'], 'temperature', f"{site} temperature comparison", draw)


def site_hum_monthly(site):
    """
    =============================================================================================================================
    Site-wide comparison of each type of humidity sensor versus the reference. MONTHLY RECORDS
    =============================================================================================================================
    """
    print(f"\t{site}: Humidity Comparison per sensor per site")

    def draw(i, year_month, merged_df, sensors):
        for sensor in sensors:
            if sensor == 'bme2_hum': continue

            plt.figure(figsize=(20, 12))

            plt.plot(merged_df['date'], merged_df[f'{sensor}_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} {sensor}")
            plt.plot(merged_df['date'], merged_df[f'{sensor}_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} {sensor}")
            plt.plot(merged_df['date'], merged_df[f'{sensor}'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} {sensor}")
            plt.plot(merged_df['date'], merged_df[f'humidity'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

            plt.title(f'{sites[i]} {year_month}: {sensor} Relative Humidity Comparison')
            plt.xlabel('Date')
            plt.ylabel('Relative Humidity (%)')
            plt.xticks(rotation=45)

            plt.legend()

            plt.grid(True)
            plt.tight_layout()

            _save(_dest() / "time-series" / f"{sites[i]}" / "humidity" / "trends" / f"{sites[i]}_{sensor}_{year_month}_humidity_comparison.png")

            plt.clf()
            plt.close()

    _site_monthly_lines(site, [s for s in variable_mapper['humidity'] if s != 'bme2_hum'], 'humidity',
                        f"{site} humidity comparison", draw)


def site_pres_monthly(site, include_sea_level_pressure=False):
    """
    =============================================================================================================================
    Site-wide comparison of each type of pressure sensor versus the reference. MONTHLY RECORDS
    =============================================================================================================================
    include_sea_level_pressure: the original's commented block ("We don't care about sea level pressure"); off by default.
    """
    print(f"\t{site}: Actual & sea level pressure per site.")

    def draw(i, year_month, merged_df, sensors):
        plt.figure(figsize=(20, 12))

        plt.plot(merged_df['date'], merged_df['bmp2_pres_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} 3D PAWS")
        plt.plot(merged_df['date'], merged_df['bmp2_pres_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} 3D PAWS")
        plt.plot(merged_df['date'], merged_df['bmp2_pres'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} 3D PAWS")
        plt.plot(merged_df['date'], merged_df['actual_pressure'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

        plt.title(f'{sites[i]} {year_month} Station Pressure')
        plt.xlabel('Date')
        plt.ylabel('Pressure (hPa)')
        plt.xticks(rotation=45)

        plt.legend()

        plt.grid(True)
        plt.tight_layout()

        _save(_dest() / "time-series" / f"{sites[i]}" / "actual_pressure" / "trends" / f"{sites[i]}_{year_month}_pressure_comparison.png")

        plt.clf()
        plt.close()

        if include_sea_level_pressure:
            print("\t\tSea Level Pressure")
            print(f"\t\t\t{sites[i]} at {year_month}")

            plt.figure(figsize=(20, 12))

            plt.plot(merged_df['date'], merged_df['bmp2_slp_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} 3D PAWS")
            plt.plot(merged_df['date'], merged_df['bmp2_slp_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} 3D PAWS")
            plt.plot(merged_df['date'], merged_df['bmp2_slp'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} 3D PAWS")
            plt.plot(merged_df['date'], merged_df['sea_level_pressure'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

            plt.title(f'{sites[i]} {year_month} Sea Level Pressure')
            plt.xlabel('Date')
            plt.ylabel('Sea Level Pressure (hPa)')
            plt.xticks(rotation=45)

            plt.legend()

            plt.grid(True)
            plt.tight_layout()

            _save(_dest() / "time-series" / f"{sites[i]}" / "sea_level_pressure" / f"{sites[i]}_{year_month}_pressure_comparison.png")

            plt.clf()
            plt.close()

    if include_sea_level_pressure:
        # needs both reference columns
        i = _site_index(site)
        (inst_1, inst_2, inst_3), tsms_ref, _ = _site_frames(site, ['bmp2_pres', 'bmp2_slp'], f"{site} pressure")
        tsms_ref = tsms_ref[['date', 'year_month', 'year_month_day', 'actual_pressure', 'sea_level_pressure']]
        for year_month in set(inst_1['year_month']) & set(inst_2['year_month']) & set(inst_3['year_month']) & set(tsms_ref['year_month']):
            merged_df = _merge_site(inst_1[inst_1['year_month'] == year_month], inst_2[inst_2['year_month'] == year_month],
                                    inst_3[inst_3['year_month'] == year_month], tsms_ref[tsms_ref['year_month'] == year_month])
            draw(i, year_month, merged_df, None)
    else:
        _site_monthly_lines(site, ['bmp2_pres'], 'actual_pressure', f"{site} pressure", draw)


def rain_accum_timeseries(site):
    """
    =============================================================================================================================
    Rainfall accumulation time series of each individual 3D PAWS station data versus the TSMS reference station. COMPLETE RECORDS
    =============================================================================================================================
    """
    print(f"\t{site}: Rainfall accumulation per site")
    i = _site_index(site)
    (inst_1, inst_2, inst_3), tsms_ref, _ = _site_frames(site, ['tipping'], f"{site} rainfall accumulation")
    tsms_ref = tsms_ref[['date', 'year_month', 'year_month_day', 'total_rainfall']]

    merged_df = _merge_site(inst_1, inst_2, inst_3, tsms_ref)

    merged_df['cumulative_rainfall_3DPAWS_1'] = merged_df['tipping_1'].cumsum()
    merged_df['cumulative_rainfall_3DPAWS_2'] = merged_df['tipping_2'].cumsum()
    merged_df['cumulative_rainfall_3DPAWS_3'] = merged_df['tipping'].cumsum()
    merged_df['cumulative_rainfall_TSMS'] = merged_df['total_rainfall'].cumsum()

    plt.figure(figsize=(20, 12))

    plt.plot(merged_df['date'], merged_df['cumulative_rainfall_3DPAWS_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} 3D PAWS")
    plt.plot(merged_df['date'], merged_df['cumulative_rainfall_3DPAWS_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} 3D PAWS")
    plt.plot(merged_df['date'], merged_df['cumulative_rainfall_3DPAWS_3'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} 3D PAWS")
    plt.plot(merged_df['date'], merged_df['cumulative_rainfall_TSMS'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

    plt.title(f'{sites[i]} Rainfall Accumulation')
    plt.xlabel('Date')
    plt.ylabel('Rainfall (mm)')
    plt.xticks(rotation=45)

    plt.legend()

    plt.grid(True)
    plt.tight_layout()

    _save(_dest() / "time-series" / f"{sites[i]}" / "total_rainfall" / "trends" / f"{sites[i]}_rainfall_accumulation.png")

    plt.clf()
    plt.close()


def site_rain_daily_bars(site):
    """
    =============================================================================================================================
    Create bar charts for daily 3D PAWS rainfall accumulation (per site) compared to TSMS rainfall accumulation. MONTHLY RECORDS
    =============================================================================================================================
    """
    print(f"{site}: Bar charts for rainfall accumulation -- daily totals [ALL INSTRUMENTS PER SITE]")
    i = _site_index(site)
    (inst_1, inst_2, inst_3), tsms_ref, _ = _site_frames(site, ['tipping'], f"{site} daily rainfall bars")
    tsms_ref = tsms_ref[['date', 'year_month', 'year_month_day', 'total_rainfall']]

    for year_month in set(inst_1['year_month']) & \
                        set(inst_2['year_month']) & \
                            set(inst_3['year_month']) & \
                                set(tsms_ref['year_month']):
        inst_1_grouped = inst_1[inst_1['year_month'] == year_month]
        inst_2_grouped = inst_2[inst_2['year_month'] == year_month]
        inst_3_grouped = inst_3[inst_3['year_month'] == year_month]
        tsms_grouped = tsms_ref[tsms_ref['year_month'] == year_month]

        merged_df = _merge_site(inst_1_grouped, inst_2_grouped, inst_3_grouped, tsms_grouped)

        merged_df['daily_rainfall_1'] = merged_df['tipping_1']    # Calculate daily rainfall totals
        merged_df['daily_rainfall_2'] = merged_df['tipping_2']
        merged_df['daily_rainfall_3'] = merged_df['tipping']
        merged_df['daily_rainfall_TSMS'] = merged_df['total_rainfall']

        daily_totals = merged_df.groupby('year_month_day')[     # Sum daily rainfall by date
            ['daily_rainfall_1', 'daily_rainfall_2', 'daily_rainfall_3', 'daily_rainfall_TSMS']
        ].sum().reset_index()

        days = daily_totals['year_month_day'].dt.day
        values_1 = daily_totals['daily_rainfall_1']
        values_2 = daily_totals['daily_rainfall_2']
        values_3 = daily_totals['daily_rainfall_3']
        values_tsms = daily_totals['daily_rainfall_TSMS']

        index = range(len(days))

        plt.figure(figsize=(20, 12), constrained_layout=True)

        bar_width = 0.2
        bars1 = plt.bar(index, values_1, width=bar_width, color='blue', label=f'3DPAWS TSMS0{station_map[i][0]}')
        bars2 = plt.bar([k + bar_width for k in index], values_2, width=bar_width, color='orange', label=f'3DPAWS TSMS0{station_map[i][1]}')
        bars3 = plt.bar([k + 2*bar_width for k in index], values_3, width=bar_width, color='green', label=f'3DPAWS TSMS0{station_map[i][2]}')
        bars4 = plt.bar([k + 3*bar_width for k in index], values_tsms, width=bar_width, color='red', label='TSMS Reference')

        plt.xlabel(f'Day in {year_month}', fontsize=8)          # Add labels, title, and legend
        plt.ylabel('Daily Rainfall (mm)', fontsize=8)
        plt.title(f'{sites[i]} Daily Rainfall Comparison: All Instruments for {year_month}', fontsize=8)
        plt.xticks([k + 1.5*bar_width for k in index], days, rotation=45)
        plt.ylim(0, 50)
        plt.legend()

        for bars in [bars1, bars2, bars3, bars4]:               # Add numerical values above bars
            for bar in bars:
                yval = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 1), ha='center', va='bottom', fontsize=8)

        _save(_dest() / "bar-charts" / f"{sites[i]}" / f"{sites[i]} _{year_month}_daily_rainfall_all_instruments.png")

        plt.clf()
        plt.close()


def site_rain_monthly_bars(site):
    """
    =============================================================================================================================
    Create bar charts for daily 3D PAWS rainfall accumulation (per site) compared to TSMS rainfall accumulation. COMPLETE RECORDS
    =============================================================================================================================
    (Despite the header, the bars are monthly totals over the complete record.)
    """
    print(f"{site}: Bar charts for rainfall accumulation -- monthly totals [ALL INSTRUMENTS PER SITE]")
    i = _site_index(site)
    (inst_1, inst_2, inst_3), tsms_ref, _ = _site_frames(site, ['tipping'], f"{site} monthly rainfall bars")
    tsms_ref = tsms_ref[['date', 'year_month', 'year_month_day', 'total_rainfall']]

    merged_df = _merge_site(inst_1, inst_2, inst_3, tsms_ref)

    merged_df['monthly_rainfall_1'] = merged_df['tipping_1']
    merged_df['monthly_rainfall_2'] = merged_df['tipping_2']
    merged_df['monthly_rainfall_3'] = merged_df['tipping']
    merged_df['monthly_rainfall_TSMS'] = merged_df['total_rainfall']

    monthly_totals = merged_df.groupby('year_month')[
        ['monthly_rainfall_1', 'monthly_rainfall_2', 'monthly_rainfall_3', 'monthly_rainfall_TSMS']
    ].sum().reset_index()

    months = monthly_totals['year_month']
    values_1 = monthly_totals['monthly_rainfall_1']
    values_2 = monthly_totals['monthly_rainfall_2']
    values_3 = monthly_totals['monthly_rainfall_3']
    values_tsms = monthly_totals['monthly_rainfall_TSMS']

    index = range(len(months))

    plt.figure(figsize=(20, 12), constrained_layout=True)

    bar_width = 0.2
    bars1 = plt.bar(index, values_1, width=bar_width, color='blue', label=f'3DPAWS TSMS0{station_map[i][0]}')
    bars2 = plt.bar([k + bar_width for k in index], values_2, width=bar_width, color='orange', label=f'3DPAWS TSMS0{station_map[i][1]}')
    bars3 = plt.bar([k + 2*bar_width for k in index], values_3, width=bar_width, color='green', label=f'3DPAWS TSMS0{station_map[i][2]}')
    bars4 = plt.bar([k + 3*bar_width for k in index], values_tsms, width=bar_width, color='red', label='TSMS Reference')

    plt.xlabel('Month', fontsize=8)
    plt.ylabel('Monthly Rainfall (mm)', fontsize=8)
    plt.title(f'{sites[i]} Monthly Rainfall Comparison: All Instruments', fontsize=10)
    plt.xticks([k + 1.5*bar_width for k in index], months, rotation=45, ha='right')
    plt.legend(fontsize='small')

    for bars in [bars1, bars2, bars3, bars4]:
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 1), ha='center', va='bottom', fontsize=6)

    _save(_dest() / "bar-charts" / f"{sites[i]}" / f"{sites[i]}_monthly_rainfall_all_instruments.png")

    plt.clf()
    plt.close()


def _site_daily_mean_diffs(site, sensors, ref_col, context):
    """Step 1 of the three DIFFERENCE sections: daily mean (instrument - reference) per sensor per instrument.

    Same result as the original per-day loop (filter each frame to the day, merge on date, take the mean), computed
    with one merge + groupby: rows that share a timestamp share a day, so grouping the full merge by day gives the
    same per-day rows. Days in the four-way day intersection with no common timestamp give NaN, as before."""
    i = _site_index(site)
    (inst_1, inst_2, inst_3), tsms_ref, _ = _site_frames(site, sensors, context)
    tsms_ref = tsms_ref[['date', 'year_month', 'year_month_day', ref_col]]
    sensors = _sensors_in_all([inst_1, inst_2, inst_3], sensors, context)

    days = set(inst_1['year_month_day']) & \
                set(inst_2['year_month_day']) & \
                    set(inst_3['year_month_day']) & \
                        set(tsms_ref['year_month_day'])
    days = pd.PeriodIndex(sorted(days), freq='D')

    merged_df = _merge_site(inst_1, inst_2, inst_3, tsms_ref)

    frames = []
    for sensor in sensors:
        merged_df[f"{sensor}_1_diff"] = merged_df[f'{sensor}_1'] - merged_df[ref_col] # 3D-PAWS instrument 1
        merged_df[f"{sensor}_2_diff"] = merged_df[f'{sensor}_2'] - merged_df[ref_col] # 3D-PAWS instrument 2
        merged_df[f"{sensor}_diff"] = merged_df[f'{sensor}'] - merged_df[ref_col]     # 3D-PAWS instrument 3

        daily = merged_df.groupby('year_month_day')[[f"{sensor}_1_diff", f"{sensor}_2_diff", f"{sensor}_diff"]].mean().reindex(days)
        daily.columns = [f'TSMS{station_map[i][0]}_diff', f'TSMS{station_map[i][1]}_diff', f'TSMS{station_map[i][2]}_diff']
        daily.insert(0, 'sensor', sensor)
        daily.insert(0, 'date', days.to_timestamp())
        frames.append(daily.reset_index(drop=True))

    # Step 2 input: average daily diff's for each sensor.
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=['date', 'sensor'])
    return i, df, sensors


def _plot_diff(i, this_sensor, sensor, title, ylabel, ylim, path):
    plt.figure(figsize=(20, 12))

    plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][0]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} {sensor}")
    plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][1]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} {sensor}")
    plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][2]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} {sensor}")

    plt.title(title)
    plt.xlabel('Date')
    plt.ylabel(ylabel)
    plt.ylim(*ylim)
    plt.axvline(pd.to_datetime(sht_upgrade[i]), color='red', linestyle='--', linewidth=2)
    plt.xticks(rotation=45)

    plt.legend()

    plt.grid(True)
    plt.tight_layout()

    _save(path)

    plt.clf()
    plt.close()


def diff_pressure(site):
    """
    =============================================================================================================================
    Create time series DIFFERENCE plots for pressure compared to TSMS at each site. COMPLETE RECORDS
    Complete record with daily average difference
    =============================================================================================================================
    """
    print(f"\t{site}: Pressure Difference per Sensor")
    i, df, sensors = _site_daily_mean_diffs(site, variable_mapper['actual_pressure'], 'actual_pressure', f"{site} pressure difference")

    for sensor in sensors:
        this_sensor = df[df['sensor'] == sensor].sort_values('date')
        _plot_diff(i, this_sensor, sensor,
                   f'{sites[i]}: {sensor} Pressure Difference from Reference', 'Pressure Difference [Actual] (hPa)', (-5, 5),
                   _dest() / "time-series" / f"{sites[i]}" / "actual_pressure" / "differences" / f"{sites[i]}_actual_pressure_difference.png")


def diff_temperature(site):
    """
    =============================================================================================================================
    Create time series DIFFERENCE plots for each temperature sensor compared to TSMS at each site. COMPLETE RECORDS
    Daily average difference
    =============================================================================================================================
    """
    print(f"\t{site}: Temperature Difference per Sensor")
    i, df, sensors = _site_daily_mean_diffs(site, variable_mapper['temperature'], 'temperature', f"{site} temperature difference")

    for sensor in sensors:
        this_sensor = df[df['sensor'] == sensor].sort_values('date')
        _plot_diff(i, this_sensor, sensor,
                   f'{sites[i]}: {sensor} Temperature Difference from Reference', 'Temperature Difference (˚C)', (-5, 5),
                   _dest() / "time-series" / f"{sites[i]}" / "temperature" / "differences" / f"{sites[i]}_{sensor}_temperature_difference.png")


def diff_humidity(site):
    """
    =============================================================================================================================
    Create time series DIFFERENCE plots for each humidity sensor compared to TSMS at each site. MONTHLY RECORDS
    Daily average difference
    =============================================================================================================================
    (Despite "MONTHLY RECORDS" in the header, this is one complete-record plot per sensor.)
    """
    print(f"\t{site}: Humidity Difference per Sensor")
    i, df, sensors = _site_daily_mean_diffs(site, [s for s in variable_mapper['humidity'] if s != "bme2_hum"], 'humidity',
                                            f"{site} humidity difference")

    for sensor in sensors:
        if sensor == 'bme2_hum': continue

        this_sensor = df[df['sensor'] == sensor].sort_values('date')
        _plot_diff(i, this_sensor, sensor,
                   f'{sites[i]}: {sensor} Humidity Difference from Reference', 'Humidity Difference (%)', (-50, 50),
                   _dest() / "time-series" / f"{sites[i]}" / "humidity" / "differences" / f"{sites[i]}_{sensor}_humidity_difference.png")


# =============================================================================================================================
# REPORT-PARITY FIGURES: our data drawn the way the TSMS draft report draws its Figs 6.1-10.3
#   -> plots/report-comparison/<Fig-...>.png   (report figure left | ours right, when the report image is available)
#   -> plots/report-comparison/ours/<Fig-...>.png   (ours alone)
# Report images were extracted from docs/TSMS_3D-PAWS_DATA_ANALYSIS_REPORT (2).pdf with pypdf (page.images) into
# plots/report-comparison/report-figures/. Methods follow the report: period 1 Nov 2022 - 31 Oct 2025 (UTC), paired
# = both values present in the same minute, daily values only from days with >= 80% (1,152) valid minutes, monthly
# means = mean of eligible daily means, TSMS wind reduced 10 m -> 2 m with the Hellmann exponents (report §3.8).
# Sensors: temperature mcp9808; RH sth_hum where present, else htu_hum; pressure bmp2_pres; wind wind_speed/wind_dir;
# rain tipping. Network figures (all three sites in one figure) are drawn when the run reaches its last site.
# =============================================================================================================================
from matplotlib import cbook

RC_START, RC_END = pd.Timestamp("2022-11-01 00:00"), pd.Timestamp("2025-10-31 23:59")
RC_REF_COLOR = "#222222"
RC_COLORS = ["#0072B2", "#E69F00", "#009E73"]     # first / second / third 3D-PAWS station of a site
RC_MARKERS = ["o", "s", "^"]
RC_REF_ID = {"Ankara": "17130", "Konya": "17245", "Adana": "17351"}
RC_MIN_DAY = 1152                                 # 80% of 1,440 minutes
RC_LOCAL_H = 3                                    # Türkiye local time = UTC+3 (report's diurnal x-axes)
RC_SEASON = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
             6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"}
RC_SEASONS = ["Winter", "Spring", "Summer", "Autumn"]
RC_ROSE_EDGES = [1, 2, 3, 5, 7, 10, 15, 20]       # report's speed classes (m/s)
RC_ROSE_LABELS = ["0-1", "1-2", "2-3", "3-5", "5-7", "7-10", "10-15", "15-20", ">20"]
RC_HUM_NOTE = "3D-PAWS RH: sth_hum where present, else htu_hum"
RC_TEMP_NOTE = "3D-PAWS temperature: MCP9808 (mcp9808)"
RC_RAIN_CAVEAT = ("CAVEAT: our Ankara TSMS reference rain file is x10 too high from 6 Mar 2023 (SF-09, docs/sensor-failures.md); "
                  "the report used correct data. Ankara rain is plotted as is (uncorrected) and is NOT comparable with the report.")
RC_WIND_NOTE = (f"TSMS 10-m wind speed reduced to 2 m: U2 = U10 (2/10)^a, a = 0.30 Ankara, 0.35 Konya, 0.25 Adana "
                "(report §3.8); 3D-PAWS not adjusted")

RC_FIGS = {   # id: (pdf page, file slug, site or None = whole network, report image files, stack 'h'/'v')
    "6.1":  (20, "monthly-mean-temperature", "Ankara", ["report_p20_Im4.png"], "h"),
    "6.2":  (21, "monthly-mean-temperature", "Adana",  ["report_p21_Im5.png"], "h"),
    "6.3":  (22, "monthly-mean-temperature", "Konya",  ["report_p22_Im6.png"], "h"),
    "6.4":  (23, "temperature-scatter", None, ["report_p23_Im7.png", "report_p23_Im8.png", "report_p23_Im9.png"], "h"),
    "6.5":  (24, "temperature-difference-distribution", "Ankara", ["report_p24_Im10.png"], "h"),
    "6.6":  (25, "temperature-difference-distribution", "Konya",  ["report_p25_Im11.png"], "h"),
    "6.7":  (26, "temperature-difference-distribution", "Adana",  ["report_p26_Im12.png"], "h"),
    "6.8":  (27, "temperature-taylor-diagrams", None, ["report_p27_Im13.png"], "h"),
    "6.9":  (28, "diurnal-temperature", None, ["report_p28_Im14.png", "report_p28_Im15.png", "report_p28_Im16.png"], "v"),
    "6.10": (29, "temperature-difference-boxplots", None, ["report_p29_Im17.png"], "h"),
    "7.1":  (32, "monthly-mean-humidity", "Ankara", ["report_p32_Im18.png"], "h"),
    "7.2":  (33, "monthly-mean-humidity", "Konya",  ["report_p33_Im19.png"], "h"),
    "7.3":  (34, "monthly-mean-humidity", "Adana",  ["report_p34_Im20.png"], "h"),
    "7.4":  (35, "humidity-scatter", None, ["report_p35_Im21.png", "report_p35_Im22.png", "report_p35_Im23.png"], "h"),
    "7.5":  (36, "diurnal-median-humidity", None, ["report_p36_Im24.png"], "h"),
    "8.1":  (39, "daily-pressure-regression", None, ["report_p39_Im25.png", "report_p39_Im26.png", "report_p39_Im27.png"], "h"),
    "8.2":  (40, "pressure-difference-boxplots", None, ["report_p40_Im28.png"], "h"),
    "8.3":  (41, "diurnal-pressure-bias", None, ["report_p41_Im29.png"], "h"),
    "8.4":  (42, "pressure-bias-vs-temperature", None, ["report_p42_Im30.png"], "h"),
    "8.5":  (43, "pressure-bland-altman", None, ["report_p43_Im31.png"], "h"),
    "8.6":  (44, "seasonal-pressure-bias", None, ["report_p44_Im32.png"], "h"),
    "8.7":  (45, "pressure-abs-error-cdf", None, ["report_p45_Im33.png"], "h"),
    "9.1":  (48, "wind-roses", "Ankara", ["report_p48_Im34.png"], "h"),
    "9.2":  (49, "wind-roses", "Konya",  ["report_p49_Im35.png"], "h"),
    "9.3":  (50, "wind-roses", "Adana",  ["report_p50_Im36.png"], "h"),
    "9.4":  (51, "seasonal-wind-speed", None, ["report_p51_Im37.png"], "h"),
    "9.5":  (52, "diurnal-wind-speed", None, ["report_p52_Im38.png"], "h"),
    "9.6":  (53, "seasonal-wind-speed-bias", None, ["report_p53_Im39.png"], "h"),
    "9.7":  (54, "wind-speed-scatter", None, ["report_p54_Im40.png"], "h"),
    "10.1": (61, "monthly-precipitation-totals", None, ["report_p61_Im41.png"], "h"),
    "10.2": (62, "monthly-precipitation-scatter", None, ["report_p62_Im42.png"], "h"),
    "10.3": (63, "precipitation-pod-far-csi", None, ["report_p63_Im43.png"], "h"),
}

_RC_MIN = {}                  # site -> (station short names, {key: minute DataFrame}); one site held at a time
_RC_NET = {}                  # figure id -> {site: summary} for whole-network figures
_RUN_SITES = list(ALL_SITES)  # set by run(): the sites of the current run


def _rc_short(paws_name):
    return paws_name.split("_")[1]


def _rc_ref_label(site):
    return f"TSMS {RC_REF_ID[site]} (ref)"


def _rc_grab(df, cols, idx):
    d = df[['date'] + [c for c in cols if c in df.columns]]
    d = d[(d['date'] >= RC_START) & (d['date'] <= RC_END)]
    d = d.drop_duplicates('date', keep='first').set_index('date').reindex(idx)
    for c in cols:
        if c not in d.columns:
            d[c] = np.nan
    return d.astype('float32')


def _rc_minutes(site):
    """Minute grid (study period) for the site: frames['ref'] and frames['TSMS0n'] with T, RH, P, WS, WD, R
    (+ WS10 for the reference; WS = Hellmann-reduced 2-m speed)."""
    if site in _RC_MIN:
        return _RC_MIN[site]
    _RC_MIN.clear()
    members, ref = load_site(site)
    idx = pd.date_range(RC_START, RC_END, freq='min')
    r = _rc_grab(ref, ['temperature', 'humidity', 'actual_pressure', 'avg_wind_speed', 'avg_wind_dir', 'total_rainfall'], idx)
    frames = {'ref': pd.DataFrame({'T': r['temperature'], 'RH': r['humidity'], 'P': r['actual_pressure'],
                                   'WS10': r['avg_wind_speed'], 'WD': r['avg_wind_dir'], 'R': r['total_rainfall']}, index=idx)}
    frames['ref']['WS'] = frames['ref']['WS10'] * np.float32((h2 / h1) ** hellman_exponents[site])
    names = []
    for name, df in members:
        s = _rc_short(name)
        names.append(s)
        d = _rc_grab(df, ['mcp9808', 'sth_hum', 'htu_hum', 'bmp2_pres', 'wind_speed', 'wind_dir', 'tipping'], idx)
        frames[s] = pd.DataFrame({'T': d['mcp9808'], 'RH': d['sth_hum'].fillna(d['htu_hum']), 'P': d['bmp2_pres'],
                                  'WS': d['wind_speed'], 'WD': d['wind_dir'], 'R': d['tipping']}, index=idx)
    _RC_MIN[site] = (names, frames)
    return names, frames


def _rc_daily(s, how="mean"):
    """Daily mean (or sum) from days with >= 80% valid minutes."""
    g = s.resample('D')
    v = g.mean() if how == "mean" else g.sum()
    return v[g.count() >= RC_MIN_DAY]


def _rc_pair(ref, st):
    m = ref.notna() & st.notna()
    return ref[m], st[m]


def _rc_fit(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3:
        return dict(n=len(x), r=np.nan, r2=np.nan, slope=np.nan, icpt=np.nan, bias=np.nan)
    slope, icpt = np.polyfit(x, y, 1)
    r = np.corrcoef(x, y)[0, 1]
    return dict(n=len(x), r=r, r2=r * r, slope=slope, icpt=icpt, bias=float(np.mean(y - x)))


def _rc_bstats(d, label, fliers=True, cap=20000):
    st = cbook.boxplot_stats(np.asarray(d, float), whis=1.5)[0]
    st['label'] = label
    f = st['fliers']
    if not fliers:
        st['fliers'] = np.array([])
    elif len(f) > cap:   # draw a random subset of the fliers (plus the extremes); stats use every value
        keep = np.random.default_rng(0).choice(len(f), cap, replace=False)
        st['fliers'] = np.concatenate([f[keep], [f.min(), f.max()]])
    return st


def _rc_style(ax):
    ax.grid(True, color='#e3e3e3', lw=0.6)
    ax.set_axisbelow(True)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)


def _rc_note(fig, text, y=0.005):
    fig.text(0.5, y, text, ha='center', va='bottom', fontsize=9, color='#555555', wrap=True)


def _rc_dir():
    return _dest() / "report-comparison"


def _rc_compose(report_paths, how, ours_path, out_path, left_label):
    """Side-by-side PNG: report figure (left) | ours (right), same height, labels on top."""
    from PIL import Image
    ims = [Image.open(p).convert('RGB') for p in report_paths]
    if len(ims) > 1:
        if how == 'h':
            h = min(i.height for i in ims)
            ims = [i.resize((round(i.width * h / i.height), h), Image.LANCZOS) for i in ims]
            rep = Image.new('RGB', (sum(i.width for i in ims), h), 'white')
            x = 0
            for i in ims:
                rep.paste(i, (x, 0)); x += i.width
        else:
            w = min(i.width for i in ims)
            ims = [i.resize((w, round(i.height * w / i.width)), Image.LANCZOS) for i in ims]
            rep = Image.new('RGB', (w, sum(i.height for i in ims)), 'white')
            y = 0
            for i in ims:
                rep.paste(i, (0, y)); y += i.height
    else:
        rep = ims[0]
    our = Image.open(ours_path).convert('RGB')
    H = min(1600, max(our.height, 900))
    rep = rep.resize((round(rep.width * H / rep.height), H), Image.LANCZOS)
    our = our.resize((round(our.width * H / our.height), H), Image.LANCZOS)
    gap, band = 50, 80
    W, TH = rep.width + gap + our.width, H + band
    fig = plt.figure(figsize=(W / 100, TH / 100), dpi=100, facecolor='white')
    for x0, img, lab in [(0, rep, left_label), (rep.width + gap, our, "Ours")]:
        ax = fig.add_axes([x0 / W, 0, img.width / W, H / TH])
        ax.imshow(np.asarray(img), interpolation='none')
        ax.axis('off')
        fig.text((x0 + img.width / 2) / W, 1 - band / 2 / TH, lab, ha='center', va='center', fontsize=26, weight='bold',
                 color=RC_REF_COLOR)
    fig.add_artist(plt.Line2D([(rep.width + gap / 2) / W] * 2, [0.02, 0.98], color='#999999', lw=2))
    _save(out_path, fig, dpi=100)
    plt.close(fig)


def _rc_save(fig, fid, site=None):
    page, slug, fsite, imgs, how = RC_FIGS[fid]
    name = f"Fig-{fid}_p{page}_{slug}" + (f"_{site}" if site else "") + ".png"
    ours = _rc_dir() / "ours" / name
    _save(ours, fig, dpi=130, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    paths = [_root("plots/report-comparison/report-figures") / f for f in imgs]
    out = _rc_dir() / name
    if paths and all(p.exists() for p in paths):
        _rc_compose(paths, how, ours, out, f"TSMS report, Fig {fid}, p. {page}")
    else:
        print(f"\tNOTE: report image for Fig {fid} not found -- writing ours alone")
        import shutil
        shutil.copyfile(ours, out)
    print("\tsaved", out)


def _rc_site_only(site, fid):
    want = RC_FIGS[fid][2]
    if site != want:
        print(f"\tFig {fid} is the {want} figure -- nothing to do for {site}")
        return False
    return True


def _rc_network(fid, site, summarize, draw):
    """Summaries per site; draw once the run's last site is reached (loading any site the run skipped)."""
    store = _RC_NET.setdefault(fid, {})
    store[site] = summarize(site)
    run_sites = [s for s in ALL_SITES if s in _RUN_SITES]
    if run_sites and site != run_sites[-1]:
        return
    for s in ALL_SITES:
        if s not in store:
            store[s] = summarize(s)
            _RC_MIN.pop(s, None)
            _evict([n for n in station_order if instrument_to_site[n] == s] + [f"TSMS_Reference_{s}"])
    draw({s: store[s] for s in ALL_SITES})
    _RC_NET.pop(fid, None)


def _rc_series_list(site, names, with_ref=True):
    out = [('ref', _rc_ref_label(site), RC_REF_COLOR)] if with_ref else []
    return out + [(n, n, c) for n, c in zip(names, RC_COLORS)]


# ---- Monthly means (Figs 6.1-6.3, 7.1-7.3) ----------------------------------------------------------------------------------
def _rc_monthly(site, fid, var, what, unit, ylim, note):
    names, F = _rc_minutes(site)
    months = pd.date_range(RC_START, RC_END, freq='MS')
    fig, ax = plt.subplots(figsize=(15, 5.8))
    for key, lab, col in _rc_series_list(site, names):
        d = _rc_daily(F[key][var])
        m = d.resample('MS').mean().reindex(months)
        ax.plot(months, m.values, color=col, lw=2.2 if key == 'ref' else 1.6, marker='o', ms=3.5,
                label=f"{lab}  N = {len(d):,} eligible days", zorder=3 if key == 'ref' else 2)
    ax.set_xticks(months)
    ax.set_xticklabels([m.strftime('%Y-%m') for m in months], rotation=45, ha='right', fontsize=8)
    ax.set_xlim(months[0] - pd.Timedelta(days=12), months[-1] + pd.Timedelta(days=12))
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_ylabel(unit)
    _rc_style(ax)
    ax.set_title(f"Monthly mean {what} - {site} (mean of eligible daily means; day eligible if >= 80% of minutes valid)",
                 fontsize=12, weight='bold')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.2), ncol=4, fontsize=9, frameon=False)
    _rc_note(fig, note + ". Each series uses its own eligible days (not paired), as in the report.", y=-0.06)
    _rc_save(fig, fid, site)


# ---- Daily-mean scatter + regression (Figs 6.4, 7.4, 8.1) --------------------------------------------------------------------
def _rc_daily_pairs(site, var):
    names, F = _rc_minutes(site)
    r = _rc_daily(F['ref'][var])
    out = {}
    for n in names:
        j = pd.concat([r, _rc_daily(F[n][var])], axis=1, join='inner').dropna()
        out[n] = (j.iloc[:, 0].to_numpy(float), j.iloc[:, 1].to_numpy(float))
    return names, out


def _rc_draw_scatter(fid, data, what, unit, title, note, eq=False, pad=1.0):
    fig, axes = plt.subplots(1, 3, figsize=(19, 6.9))
    for ax, site in zip(axes, ALL_SITES):
        names, pairs = data[site]
        lo, hi = np.inf, -np.inf
        for n, c, mk in zip(names, RC_COLORS, RC_MARKERS):
            x, y = pairs[n]
            if len(x) < 3:
                continue
            st = _rc_fit(x, y)
            lo, hi = min(lo, x.min(), y.min()), max(hi, x.max(), y.max())
            ax.scatter(x, y, s=10, marker=mk, color=c, alpha=0.45, edgecolors='none', rasterized=True)
            xx = np.array([x.min(), x.max()])
            lab = f"{n}: R² = {st['r2']:.3f}, N = {st['n']:,} days"
            if eq:
                lab += f"\n      fit y = {st['slope']:.3f}x {st['icpt']:+.1f}"
            ax.plot(xx, st['slope'] * xx + st['icpt'], color=c, lw=1.8, label=lab)
        lo, hi = lo - pad, hi + pad
        ax.plot([lo, hi], [lo, hi], color=RC_REF_COLOR, ls='--', lw=1.2, label='1:1')
        ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect('equal')
        ax.set_title(f"{site} (TSMS {RC_REF_ID[site]})", fontsize=12, weight='bold')
        ax.set_xlabel(f"TSMS daily mean {what} ({unit})")
        ax.set_ylabel(f"3D-PAWS daily mean {what} ({unit})")
        _rc_style(ax)
        ax.legend(loc='upper left', fontsize=8.5, framealpha=0.9)
    fig.suptitle(title, fontsize=14, weight='bold')
    _rc_note(fig, note + ". Paired eligible days (both >= 80% valid minutes); R² from paired daily means.", y=-0.02)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    _rc_save(fig, fid)


# ---- Difference-distribution boxplots (Figs 6.10, 8.2) ------------------------------------------------------------------------
def _rc_diff_box_summary(site, var):
    names, F = _rc_minutes(site)
    out = []
    for n in names:
        r, s = _rc_pair(F['ref'][var], F[n][var])
        d = (s - r).to_numpy(float)
        out.append(_rc_bstats(d, f"{n}\nN = {len(d):,} min"))
    return out


def _rc_draw_diff_box(fid, data, what, unit, ylim, title, note):
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.4), sharey=True)
    for ax, site in zip(axes, ALL_SITES):
        stats = data[site]
        b = ax.bxp(stats, positions=[0, 1, 2], widths=0.6, patch_artist=True, showfliers=True,
                   flierprops=dict(marker='.', ms=2, alpha=0.3, mec='none', mfc='#555555'),
                   medianprops=dict(color='#111111', lw=1.5))
        for patch, c in zip(b['boxes'], RC_COLORS):
            patch.set_facecolor(c); patch.set_alpha(0.85)
        for fl in b['fliers']:
            fl.set_rasterized(True)
        ax.axhline(0, color=RC_REF_COLOR, ls='--', lw=1)
        ax.set_ylim(*ylim)
        ax.set_title(f"{site}\n(TSMS {RC_REF_ID[site]})", fontsize=12, weight='bold')
        _rc_style(ax)
        ax.tick_params(axis='x', labelsize=9)
    axes[0].set_ylabel(f"{what} difference, 3D-PAWS - TSMS ({unit})")
    fig.suptitle(title, fontsize=14, weight='bold')
    _rc_note(fig, note + ". Paired 1-min values. Box = IQR, line = median, whiskers = 1.5 IQR, dots = outliers "
             "(at most 20,000 drawn per station); y-axis clipped as in the report.", y=-0.01)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    _rc_save(fig, fid)


# ---- Figs 6.1-6.3 -------------------------------------------------------------------------------------------------------------
def _rc_temp_monthly(fid):
    def f(site):
        """Report Fig. {fid}: monthly mean air temperature, reference + 3 stations (MCP9808)."""
        if _rc_site_only(site, fid):
            _rc_monthly(site, fid, 'T', 'air temperature', '°C', (-10, 35), RC_TEMP_NOTE)
    return f


report_fig_6_1, report_fig_6_2, report_fig_6_3 = (_rc_temp_monthly(i) for i in ("6.1", "6.2", "6.3"))


def report_fig_6_4(site):
    """Report Fig. 6.4: temperature scatter vs reference, daily means, regression + 1:1, three sites."""
    _rc_network("6.4", site, lambda s: _rc_daily_pairs(s, 'T'),
                lambda d: _rc_draw_scatter("6.4", d, "temperature", "°C", "Air temperature: 3D-PAWS vs TSMS", RC_TEMP_NOTE))


def _rc_temp_hist(fid):
    def f(site):
        """Report Figs. 6.5-6.7: distribution of 1-min temperature differences at one site, with a stats table."""
        if not _rc_site_only(site, fid):
            return
        names, F = _rc_minutes(site)
        fig = plt.figure(figsize=(13, 8.6))
        ax = fig.add_axes([0.08, 0.34, 0.9, 0.56])
        tax = fig.add_axes([0.08, 0.03, 0.9, 0.2]); tax.axis('off')
        bins = np.arange(-5, 5.0001, 0.1)
        rows = []
        for n, c in zip(names, RC_COLORS):
            r, s = _rc_pair(F['ref']['T'], F[n]['T'])
            d = (s - r).to_numpy(float)
            ax.hist(d, bins=bins, density=True, histtype='stepfilled', alpha=0.15, color=c)
            ax.hist(d, bins=bins, density=True, histtype='step', lw=1.8, color=c, label=f"{n}  (N = {len(d):,} paired min)")
            q1, q3 = np.percentile(d, [25, 75])
            rows.append([n, f"{len(d):,}", f"{d.mean():.2f}", f"{np.median(d):.2f}", f"{d.std():.2f}", f"{q3 - q1:.2f}"])
        ax.axvline(0, color=RC_REF_COLOR, ls='--', lw=1.4, label='Perfect agreement')
        ax.set_xlabel("Temperature difference, 3D-PAWS - TSMS (°C)"); ax.set_ylabel("Density")
        ax.set_xlim(-5, 5)
        _rc_style(ax)
        ax.legend(loc='upper right', fontsize=9)
        ax.set_title(f"{site} temperature difference distribution (3D-PAWS MCP9808 - TSMS {RC_REF_ID[site]}), 1-min pairs",
                     fontsize=12, weight='bold')
        tab = tax.table(cellText=rows, colLabels=['Station', 'N (paired min)', 'Mean (°C)', 'Median (°C)', 'STD (°C)', 'IQR (°C)'],
                        loc='center', cellLoc='center')
        tab.auto_set_font_size(False); tab.set_fontsize(10); tab.scale(1, 1.6)
        _rc_note(fig, "Histogram bins 0.1 °C (report: histogram + density line; bin width not stated). Stats use every pair.", y=0.0)
        _rc_save(fig, fid, site)
    return f


report_fig_6_5, report_fig_6_6, report_fig_6_7 = (_rc_temp_hist(i) for i in ("6.5", "6.6", "6.7"))


def _rc_taylor_summary(site):
    names, F = _rc_minutes(site)
    out = []
    for n in names:
        r, s = _rc_pair(F['ref']['T'], F[n]['T'])
        a, b = r.to_numpy(float), s.to_numpy(float)
        sr, ss = a.std(), b.std()
        cor = np.corrcoef(a, b)[0, 1]
        crmsd = np.sqrt(np.mean(((b - b.mean()) - (a - a.mean())) ** 2))
        out.append(dict(name=n, n=len(a), sd_ref=sr, sd=ss, ratio=ss / sr, r=cor, crmsd=crmsd / sr))
    return out


def _rc_taylor_axes(ax, rmin, rmax, tmax_deg, cticks, levels):
    ax.set_thetamin(0); ax.set_thetamax(tmax_deg)
    ax.set_rlim(rmin, rmax)
    ax.set_thetagrids(np.degrees(np.arccos(cticks)), labels=[f"{c:g}" for c in cticks], fontsize=8)
    t = np.linspace(0, np.radians(tmax_deg), 300); rr = np.linspace(rmin, rmax, 300)
    T, R = np.meshgrid(t, rr)
    D = np.sqrt(R ** 2 + 1 - 2 * R * np.cos(T))
    cs = ax.contour(T, R, D, levels=levels, colors='#7a9a7a', linestyles='--', linewidths=0.7)
    ax.clabel(cs, fmt='%g', fontsize=7)
    ax.plot(t, np.ones_like(t), color=RC_REF_COLOR, lw=1.2)
    ax.plot([0], [1], marker='*', ms=15, color=RC_REF_COLOR, ls='none', label='TSMS reference')


def _rc_taylor_zoom(ax, stats):
    """Cartesian zoom of the Taylor plane around the reference point (x = SD ratio * r, y = SD ratio * sin(acos r))."""
    x0, x1, y1 = 0.94, 1.08, 0.11
    t = np.linspace(0, np.pi / 2, 400)
    for lev in (0.02, 0.05, 0.1):
        ax.plot(1 + lev * np.cos(t * 2), lev * np.sin(t * 2), color='#7a9a7a', ls='--', lw=0.7)
        ax.text(1 + lev * np.cos(1.9), lev * np.sin(1.9), f"{lev:g}", color='#7a9a7a', fontsize=7)
    for c in (0.99, 0.995, 0.998, 0.999):
        a = np.arccos(c)
        ax.plot([0, 2 * np.cos(a)], [0, 2 * np.sin(a)], color='#bbbbbb', lw=0.7)
        if x1 * np.tan(a) <= y1:
            ax.text(x1, x1 * np.tan(a), f" r={c:g}", fontsize=7, va='center', color='#555555', clip_on=False)
    ax.plot(np.cos(t), np.sin(t), color=RC_REF_COLOR, lw=1.2)
    ax.plot([1], [0], marker='*', ms=15, color=RC_REF_COLOR, ls='none')
    for st, c, mk in zip(stats, RC_COLORS, RC_MARKERS):
        a = np.arccos(min(st['r'], 1))
        ax.plot([st['ratio'] * np.cos(a)], [st['ratio'] * np.sin(a)], marker=mk, ms=10, color=c, mec='white', ls='none')
    ax.set_xlim(x0, x1); ax.set_ylim(0, y1); ax.set_aspect('equal')
    ax.set_xlabel("SD ratio x r"); ax.set_ylabel("SD ratio x sin(acos r)")
    _rc_style(ax)


def report_fig_6_8(site):
    """Report Fig. 6.8: temperature Taylor diagrams per site (normalised by the reference SD), plus a zoom."""
    def draw(data):
        fig = plt.figure(figsize=(19, 13))
        for i, s in enumerate(ALL_SITES):
            stats = data[s]
            ax = fig.add_axes([0.03 + i * 0.33, 0.47, 0.27, 0.43], projection='polar')
            _rc_taylor_axes(ax, 0, 1.5, 90, [0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 0.99, 1], [0.25, 0.5, 0.75, 1.0])
            for st, c, mk in zip(stats, RC_COLORS, RC_MARKERS):
                lab = f"{st['name']}: r = {st['r']:.4f}, SD ratio = {st['ratio']:.3f}, cRMSD = {st['crmsd']:.3f}, N = {st['n']:,}"
                ax.plot([np.arccos(min(st['r'], 1))], [st['ratio']], marker=mk, ms=10, color=c, mec='white', ls='none', label=lab)
            ax.set_title(f"{s} temperature Taylor diagram", fontsize=12, weight='bold', pad=16)
            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.07), fontsize=8.5, frameon=False)
            az = fig.add_axes([0.05 + i * 0.33, 0.07, 0.25, 0.22])
            _rc_taylor_zoom(az, stats)
            az.set_title(f"{s}: zoom around the reference point", fontsize=10)
        fig.suptitle("Taylor diagrams: air temperature, 3D-PAWS (MCP9808) vs TSMS, 1-min pairs\n"
                     "angle = correlation, radius = SD / SD(ref), dashed = centred RMSD / SD(ref)", fontsize=13, weight='bold')
        _rc_note(fig, "Normalised by each pair's reference SD (the report plots absolute SD in °C).", y=0.0)
        _rc_save(fig, "6.8")
    _rc_network("6.8", site, _rc_taylor_summary, draw)


def _rc_diurnal_summary(site, var, stat='mean', local=True, with_ref=True):
    names, F = _rc_minutes(site)
    out = []
    for key, lab, col in _rc_series_list(site, names, with_ref):
        s = F[key][var].dropna()
        hrs = (s.index + pd.Timedelta(hours=RC_LOCAL_H if local else 0)).hour
        g = s.groupby(hrs)
        out.append((lab, col, (g.mean() if stat == 'mean' else g.median()).reindex(range(24)), len(s)))
    return out


def report_fig_6_9(site):
    """Report Fig. 6.9: mean diurnal temperature cycle per site, local time (UTC+3) as in the report's axes."""
    def draw(data):
        fig, axes = plt.subplots(3, 1, figsize=(12, 15))
        for ax, s in zip(axes, ALL_SITES):
            for lab, col, v, n in data[s]:
                ax.plot(v.index, v.values, color=col, lw=2.2 if 'ref' in lab else 1.8, marker='o', ms=3,
                        label=f"{lab}  N = {n:,} min")
            ax.set_xticks(range(24)); ax.set_xlabel("Local hour (UTC+3)"); ax.set_ylabel("Temperature (°C)")
            ax.set_title(f"{s} diurnal temperature cycle", fontsize=12, weight='bold')
            _rc_style(ax); ax.legend(fontsize=9)
        fig.suptitle("Mean diurnal air temperature (3D-PAWS MCP9808 and TSMS)", fontsize=14, weight='bold')
        _rc_note(fig, "Hourly means of each series' own valid 1-min values (not paired). Local time as on the report's axis; "
                 "report §3.6 says diurnal analyses use UTC.", y=0.0)
        fig.tight_layout(rect=(0, 0.02, 1, 0.97))
        _rc_save(fig, "6.9")
    _rc_network("6.9", site, lambda s: _rc_diurnal_summary(s, 'T'), draw)


def report_fig_6_10(site):
    """Report Fig. 6.10: boxplots of 1-min temperature differences, all sites."""
    _rc_network("6.10", site, lambda s: _rc_diff_box_summary(s, 'T'),
                lambda d: _rc_draw_diff_box("6.10", d, "Temperature", "°C", (-6, 6),
                                            "Temperature difference distribution (3D-PAWS - TSMS)", RC_TEMP_NOTE))


# ---- Figs 7.x -----------------------------------------------------------------------------------------------------------------
def _rc_hum_monthly(fid):
    def f(site):
        """Report Figs. 7.1-7.3: monthly mean relative humidity, reference + 3 stations."""
        if _rc_site_only(site, fid):
            _rc_monthly(site, fid, 'RH', 'relative humidity', 'RH (%)', (0, 100), RC_HUM_NOTE)
    return f


report_fig_7_1, report_fig_7_2, report_fig_7_3 = (_rc_hum_monthly(i) for i in ("7.1", "7.2", "7.3"))


def report_fig_7_4(site):
    """Report Fig. 7.4: RH scatter vs reference, daily means, regression + 1:1, three sites."""
    _rc_network("7.4", site, lambda s: _rc_daily_pairs(s, 'RH'),
                lambda d: _rc_draw_scatter("7.4", d, "RH", "%", "Relative humidity: 3D-PAWS vs TSMS", RC_HUM_NOTE, pad=2))


def report_fig_7_5(site):
    """Report Fig. 7.5: median diurnal RH of the 3D-PAWS stations (no reference, as in the report), UTC hours."""
    def draw(data):
        fig, axes = plt.subplots(1, 3, figsize=(19, 6.2), sharey=True)
        for ax, s in zip(axes, ALL_SITES):
            for lab, col, v, n in data[s]:
                ax.plot(v.index, v.values, color=col, lw=1.8, marker='o', ms=3.5, label=f"{lab}  N = {n:,} min")
            ax.set_title(f"{s} median diurnal relative humidity", fontsize=12, weight='bold')
            ax.set_xticks(range(0, 24, 3)); ax.set_xlabel("Hour (UTC)")
            _rc_style(ax); ax.legend(fontsize=9)
        axes[0].set_ylabel("Median relative humidity (%)")
        fig.suptitle("Median diurnal relative humidity at the 3D-PAWS stations", fontsize=14, weight='bold')
        _rc_note(fig, RC_HUM_NOTE + ". Median of each station's own valid 1-min values per hour (not paired); "
                 "hour axis taken as UTC (report axis unlabelled; §3.6 says UTC). No reference line, as in the report.", y=-0.02)
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        _rc_save(fig, "7.5")
    _rc_network("7.5", site, lambda s: _rc_diurnal_summary(s, 'RH', stat='median', local=False, with_ref=False), draw)


# ---- Figs 8.x -----------------------------------------------------------------------------------------------------------------
RC_PRES_NOTE = "3D-PAWS pressure: bmp2_pres; TSMS: actual_pressure (station pressure)"


def report_fig_8_1(site):
    """Report Fig. 8.1: daily pressure regression vs reference, three sites."""
    _rc_network("8.1", site, lambda s: _rc_daily_pairs(s, 'P'),
                lambda d: _rc_draw_scatter("8.1", d, "pressure", "hPa", "Daily station pressure: 3D-PAWS vs TSMS",
                                           RC_PRES_NOTE, eq=True, pad=1))


def report_fig_8_2(site):
    """Report Fig. 8.2: boxplots of 1-min pressure differences, all sites."""
    _rc_network("8.2", site, lambda s: _rc_diff_box_summary(s, 'P'),
                lambda d: _rc_draw_diff_box("8.2", d, "Pressure", "hPa", (-5, 5),
                                            "Pressure bias distribution (3D-PAWS - TSMS)", RC_PRES_NOTE))


def _rc_pdiff(site):
    names, F = _rc_minutes(site)
    out = {}
    for n in names:
        r, s = _rc_pair(F['ref']['P'], F[n]['P'])
        out[n] = (s - r).astype(float)
    return names, F, out


def _rc_draw_lines3(fid, data, title, xlabel, ylabel, note, band=True, xticks=None):
    fig, axes = plt.subplots(1, 3, figsize=(19, 6.4), sharey=True)
    for ax, s in zip(axes, ALL_SITES):
        for lab, col, x, m, sd, n in data[s]:
            ax.plot(x, m, color=col, lw=2, marker='o', ms=3.5, label=f"{lab}  N = {n:,} paired min")
            if band:
                ax.fill_between(x, m - sd, m + sd, color=col, alpha=0.15, lw=0)
        ax.axhline(0, color=RC_REF_COLOR, ls='--', lw=1)
        ax.set_title(f"{s}\n(TSMS {RC_REF_ID[s]})", fontsize=12, weight='bold')
        ax.set_xlabel(xlabel)
        if xticks is not None:
            ax.set_xticks(xticks)
        _rc_style(ax); ax.legend(fontsize=8.5, loc='best')
    axes[0].set_ylabel(ylabel)
    fig.suptitle(title, fontsize=14, weight='bold')
    _rc_note(fig, note, y=-0.02)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    _rc_save(fig, fid)


def report_fig_8_3(site):
    """Report Fig. 8.3: hourly mean pressure bias +/- 1 SD, local time (UTC+3)."""
    def summ(s):
        names, F, D = _rc_pdiff(s)
        out = []
        for n, c in zip(names, RC_COLORS):
            d = D[n]
            g = d.groupby((d.index + pd.Timedelta(hours=RC_LOCAL_H)).hour)
            out.append((n, c, np.arange(24), g.mean().reindex(range(24)).values, g.std().reindex(range(24)).values, len(d)))
        return out
    _rc_network("8.3", site, summ, lambda d: _rc_draw_lines3(
        "8.3", d, "Diurnal pressure bias (hourly mean of 3D-PAWS - TSMS)", "Local time (UTC+3)", "Mean pressure bias (hPa)",
        RC_PRES_NOTE + ". Shaded = +/-1 SD within each hour. Local time as on the report's axis (report §3.6 says UTC).",
        xticks=range(0, 24, 2)))


def report_fig_8_4(site):
    """Report Fig. 8.4: mean pressure bias in 1 °C bins of TSMS air temperature."""
    def summ(s):
        names, F, D = _rc_pdiff(s)
        out = []
        for n, c in zip(names, RC_COLORS):
            d = D[n]
            t = F['ref']['T'].reindex(d.index)
            m = t.notna()
            d, t = d[m], t[m]
            g = d.groupby(np.floor(t.to_numpy(float)))
            agg = pd.DataFrame({'m': g.mean(), 'sd': g.std(), 'n': g.size()})
            agg = agg[agg['n'] >= 60]
            out.append((n, c, agg.index.to_numpy() + 0.5, agg['m'].values, agg['sd'].values, len(d)))
        return out
    _rc_network("8.4", site, summ, lambda d: _rc_draw_lines3(
        "8.4", d, "Pressure bias vs TSMS air temperature (1 °C bins)", "TSMS air temperature (°C)", "Mean pressure bias (hPa)",
        RC_PRES_NOTE + ". Point = mean bias in a 1 °C bin of the reference temperature (bins with >= 60 paired minutes); "
        "shaded = +/-1 SD."))


def report_fig_8_5(site):
    """Report Fig. 8.5: Bland-Altman plots of 1-min pressure, three sites."""
    def summ(s):
        names, F, D = _rc_pdiff(s)
        out, alld = [], []
        rng = np.random.default_rng(0)
        for n, c in zip(names, RC_COLORS):
            d = D[n]
            mean = ((F[n]['P'].reindex(d.index) + F['ref']['P'].reindex(d.index)) / 2).to_numpy(float)
            dv = d.to_numpy(float)
            k = rng.choice(len(dv), min(len(dv), 40000), replace=False)
            out.append((n, c, mean[k], dv[k], dv.mean(), dv.std(), len(dv)))
            alld.append(dv)
        a = np.concatenate(alld)
        return out, (a.mean(), a.std(), len(a))

    def draw(data):
        fig, axes = plt.subplots(1, 3, figsize=(19, 6.6))
        for ax, s in zip(axes, ALL_SITES):
            rows, (pm, psd, pn) = data[s]
            for n, c, x, y, m, sd, N in rows:
                ax.scatter(x, y, s=3, color=c, alpha=0.25, edgecolors='none', rasterized=True)
                ax.axhline(m, color=c, lw=1.8, label=f"{n}: bias {m:+.2f}, LoA {m - 1.96 * sd:+.2f} / {m + 1.96 * sd:+.2f} hPa, N = {N:,}")
                ax.axhline(m - 1.96 * sd, color=c, lw=1, ls='--'); ax.axhline(m + 1.96 * sd, color=c, lw=1, ls='--')
            ax.text(0.02, 0.98, f"All stations: mean bias = {pm:.2f} hPa\nUpper LoA = {pm + 1.96 * psd:.2f} hPa\n"
                    f"Lower LoA = {pm - 1.96 * psd:.2f} hPa\nN = {pn:,} paired min", transform=ax.transAxes, va='top',
                    fontsize=9, bbox=dict(boxstyle='round', fc='white', ec='#999999'))
            ax.set_title(f"{s}\n(TSMS {RC_REF_ID[s]})", fontsize=12, weight='bold')
            ax.set_xlabel("Mean pressure, (3D-PAWS + TSMS)/2 (hPa)")
            _rc_style(ax); ax.legend(fontsize=7.5, loc='lower right')
        axes[0].set_ylabel("Pressure bias, 3D-PAWS - TSMS (hPa)")
        fig.suptitle("Bland-Altman analysis of pressure", fontsize=14, weight='bold')
        _rc_note(fig, RC_PRES_NOTE + ". Solid = mean bias, dashed = 95% limits of agreement (mean +/- 1.96 SD), from all pairs; "
                 "40,000 random pairs per station drawn.", y=-0.02)
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        _rc_save(fig, "8.5")
    _rc_network("8.5", site, summ, draw)


def _rc_seasonal_box(fid, data, title, ylabel, note, fliers, zero=True):
    """data[site] = (series labels, colours, {season: [bstats per series]})."""
    fig, axes = plt.subplots(1, 3, figsize=(19, 6.6), sharey=True)
    ylims = []
    for ax, s in zip(axes, ALL_SITES):
        labels, colors, by_season = data[s]
        k = len(labels)
        w = 0.8 / k
        for i, season in enumerate(RC_SEASONS):
            stats = by_season[season]
            pos = [i - 0.4 + w * (j + 0.5) for j in range(k)]
            b = ax.bxp(stats, positions=pos, widths=w * 0.85, patch_artist=True, showfliers=fliers,
                       flierprops=dict(marker='.', ms=2, alpha=0.3, mec='none', mfc='#555555'),
                       medianprops=dict(color='#111111', lw=1.4))
            for patch, c in zip(b['boxes'], colors):
                patch.set_facecolor(c); patch.set_alpha(0.85)
            for fl in b['fliers']:
                fl.set_rasterized(True)
        ax.set_xticks(range(4)); ax.set_xticklabels(RC_SEASONS)
        allst = [st for se in RC_SEASONS for st in by_season[se] if np.isfinite(st['whislo'])]
        lo_all = min(st['whislo'] for st in allst); hi_all = max(st['whishi'] for st in allst)
        pad = 0.08 * (hi_all - lo_all)
        ylims.append((lo_all - pad, hi_all + pad))
        if zero:
            ax.axhline(0, color=RC_REF_COLOR, ls='--', lw=1)
        ax.set_title(f"{s}\n(TSMS {RC_REF_ID[s]})", fontsize=12, weight='bold')
        _rc_style(ax)
        n_tot = {lab: sum(by_season[se][j]['n'] for se in RC_SEASONS) for j, lab in enumerate(labels)}
        handles = [plt.Rectangle((0, 0), 1, 1, fc=c, alpha=0.85) for c in colors]
        ax.legend(handles, [f"{lab}  N = {n_tot[lab]:,}" for lab in labels], fontsize=8.5, loc='best')
    axes[0].set_ylabel(ylabel)
    axes[0].set_ylim(min(l for l, _ in ylims), max(h for _, h in ylims))   # whisker range; far outliers fall off-axis
    fig.suptitle(title, fontsize=14, weight='bold')
    _rc_note(fig, note, y=-0.02)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    _rc_save(fig, fid)


def _rc_bstats_n(d, label, fliers):
    st = _rc_bstats(d, label, fliers)
    st['n'] = len(d)
    return st


def report_fig_8_6(site):
    """Report Fig. 8.6: seasonal boxplots of 1-min pressure bias (DJF/MAM/JJA/SON)."""
    def summ(s):
        names, F, D = _rc_pdiff(s)
        by = {}
        for se in RC_SEASONS:
            by[se] = []
            for n in names:
                d = D[n]
                v = d[d.index.month.map(RC_SEASON) == se].to_numpy(float)
                by[se].append(_rc_bstats_n(v, '', True))
        return names, RC_COLORS, by
    def draw(data):
        _rc_seasonal_box("8.6", data, "Seasonal distribution of pressure bias (3D-PAWS - TSMS)", "Pressure bias (hPa)",
                         RC_PRES_NOTE + ". Paired 1-min values; N = paired minutes. Winter = DJF ... Autumn = SON. Whiskers 1.5 IQR, "
                         "dots = outliers (<= 20,000 drawn). y-axis spans all whiskers (the report clips at +/-2 hPa, hiding most Konya boxes); "
                         "outliers beyond it are off-axis.", True)
    _rc_network("8.6", site, summ, draw)


def report_fig_8_7(site):
    """Report Fig. 8.7: CDF of absolute 1-min pressure error, with threshold table."""
    grid = np.linspace(0, 2, 801)
    thr = [0.1, 0.3, 0.5, 1.0]

    def summ(s):
        names, F, D = _rc_pdiff(s)
        out = []
        for n, c in zip(names, RC_COLORS):
            a = np.sort(np.abs(D[n].to_numpy(float)))
            cdf = np.searchsorted(a, grid, side='right') / len(a) * 100
            pct = [np.searchsorted(a, t + 1e-9, side='right') / len(a) * 100 for t in thr]
            out.append((n, c, cdf, pct, len(a)))
        return out

    def draw(data):
        fig = plt.figure(figsize=(19, 9.2))
        for i, s in enumerate(ALL_SITES):
            ax = fig.add_axes([0.05 + i * 0.32, 0.36, 0.27, 0.53])
            tax = fig.add_axes([0.05 + i * 0.32, 0.06, 0.27, 0.2]); tax.axis('off')
            rows = []
            for n, c, cdf, pct, N in data[s]:
                ax.plot(grid, cdf, color=c, lw=2, label=f"{n}  N = {N:,} paired min")
                rows.append([n] + [f"{p:.1f}%" for p in pct])
            for t in thr:
                ax.axvline(t, color='#999999', ls='--', lw=0.8)
            ax.set_xlim(0, 2); ax.set_ylim(0, 100)
            ax.set_xlabel("Absolute pressure error |3D-PAWS - TSMS| (hPa)")
            if i == 0:
                ax.set_ylabel("Cumulative probability (%)")
            ax.set_title(f"{s}\n(TSMS {RC_REF_ID[s]})", fontsize=12, weight='bold')
            _rc_style(ax); ax.legend(fontsize=8.5, loc='lower right')
            tab = tax.table(cellText=rows, colLabels=['Station'] + [f"<= {t} hPa" for t in thr], loc='center', cellLoc='center')
            tab.auto_set_font_size(False); tab.set_fontsize(9.5); tab.scale(1, 1.6)
        fig.suptitle("Cumulative distribution of absolute pressure error", fontsize=14, weight='bold', y=0.98)
        _rc_note(fig, RC_PRES_NOTE + ". Empirical CDF of every paired 1-min value (report: PCHIP-interpolated curves; "
                 "thresholds from the original observations, as here).", y=0.0)
        _rc_save(fig, "8.7")
    _rc_network("8.7", site, summ, draw)


# ---- Figs 9.x -----------------------------------------------------------------------------------------------------------------
def _rc_rose_table(ws, wd):
    m = ws.notna() & wd.notna()
    ws, wd = ws[m].to_numpy(float), wd[m].to_numpy(float) % 360
    sec = (((wd + 11.25) % 360) // 22.5).astype(int) % 16
    cls = np.digitize(ws, RC_ROSE_EDGES)
    tab = np.zeros((16, len(RC_ROSE_LABELS)))
    np.add.at(tab, (sec, cls), 1)
    return tab / max(len(ws), 1) * 100, len(ws)


def _rc_windrose(fid):
    def f(site):
        """Report Figs. 9.1-9.3: wind roses of the reference (2-m adjusted speed) and the three stations, 1-min values."""
        if not _rc_site_only(site, fid):
            return
        names, F = _rc_minutes(site)
        panels = [(f"TSMS {RC_REF_ID[site]} (ref, speed reduced to 2 m)", 'ref')] + [(n, n) for n in names]
        tabs = [(t, *_rc_rose_table(F[k]['WS'], F[k]['WD'])) for t, k in panels]
        rmax = max(tab.sum(axis=1).max() for _, tab, _ in tabs) * 1.05
        cmap = plt.get_cmap('YlGnBu')
        cols = [cmap(v) for v in np.linspace(0.2, 1.0, len(RC_ROSE_LABELS))]
        theta = np.radians(np.arange(16) * 22.5)
        fig = plt.figure(figsize=(12, 13.5))
        for i, (title, tab, n) in enumerate(tabs):
            ax = fig.add_subplot(2, 2, i + 1, projection='polar')
            ax.set_theta_zero_location('N'); ax.set_theta_direction(-1)
            bottom = np.zeros(16)
            for k in range(len(RC_ROSE_LABELS)):
                ax.bar(theta, tab[:, k], width=np.radians(22.5) * 0.92, bottom=bottom, color=cols[k], edgecolor='white', lw=0.4)
                bottom += tab[:, k]
            ax.set_ylim(0, rmax)
            ax.set_xticks(theta)
            ax.set_xticklabels(['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'],
                               fontsize=8)
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}%"))
            ax.tick_params(axis='y', labelsize=7)
            ax.set_title(f"{title}\nN = {n:,} min", fontsize=11, weight='bold', pad=14)
        handles = [plt.Rectangle((0, 0), 1, 1, fc=c) for c in cols]
        fig.legend(handles, [f"{l} m/s" for l in RC_ROSE_LABELS], loc='lower center', ncol=9, fontsize=9, frameon=False,
                   bbox_to_anchor=(0.5, 0.025))
        fig.suptitle(f"Wind rose comparison - {site}", fontsize=15, weight='bold')
        _rc_note(fig, RC_WIND_NOTE + ".\nFrequency (%) of each series' own valid 1-min speed+direction values; 16 sectors; "
                 "one radial scale for all four roses (the report scales each rose separately).", y=0.0)
        fig.subplots_adjust(left=0.05, right=0.95, top=0.9, bottom=0.1, hspace=0.38, wspace=0.3)
        _rc_save(fig, fid, site)
    return f


report_fig_9_1, report_fig_9_2, report_fig_9_3 = (_rc_windrose(i) for i in ("9.1", "9.2", "9.3"))


def report_fig_9_4(site):
    """Report Fig. 9.4: seasonal boxplots of wind speed (reference at 2 m + 3 stations), no outliers."""
    def summ(s):
        names, F = _rc_minutes(s)
        ser = _rc_series_list(s, names)
        by = {}
        for se in RC_SEASONS:
            by[se] = []
            for key, lab, col in ser:
                v = F[key]['WS'].dropna()
                by[se].append(_rc_bstats_n(v[v.index.month.map(RC_SEASON) == se].to_numpy(float), '', False))
        return [lab for _, lab, _ in ser], [col for _, _, col in ser], by
    _rc_network("9.4", site, summ, lambda d: _rc_seasonal_box(
        "9.4", d, "Seasonal distribution of wind speed", "Wind speed at 2 m (m/s)",
        RC_WIND_NOTE + ". Each series' own valid 1-min values (N = minutes); outliers omitted, as in the report.", False, zero=False))


def report_fig_9_5(site):
    """Report Fig. 9.5: mean diurnal wind speed (reference at 2 m + 3 stations), local time (UTC+3)."""
    def draw(data):
        fig, axes = plt.subplots(1, 3, figsize=(19, 6.4), sharey=True)
        for ax, s in zip(axes, ALL_SITES):
            for lab, col, v, n in data[s]:
                ax.plot(v.index, v.values, color=col, lw=2.2 if 'ref' in lab else 1.8, marker='o', ms=3.5, label=f"{lab}  N = {n:,} min")
            ax.set_title(s, fontsize=12, weight='bold')
            ax.set_xticks(range(0, 24, 3)); ax.set_xlabel("Local time (UTC+3)")
            ax.set_ylim(bottom=0)
            _rc_style(ax); ax.legend(fontsize=8.5)
        axes[0].set_ylabel("Mean wind speed at 2 m (m/s)")
        fig.suptitle("Diurnal cycle of wind speed", fontsize=14, weight='bold')
        _rc_note(fig, RC_WIND_NOTE + ". Hourly means of each series' own valid 1-min values (not paired). Local time as on "
                 "the report's axis (report §3.6 says UTC).", y=-0.02)
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        _rc_save(fig, "9.5")
    _rc_network("9.5", site, lambda s: _rc_diurnal_summary(s, 'WS'), draw)


def report_fig_9_6(site):
    """Report Fig. 9.6: seasonal boxplots of paired 1-min wind speed bias, no outliers."""
    def summ(s):
        names, F = _rc_minutes(s)
        by = {se: [] for se in RC_SEASONS}
        for n in names:
            r, st = _rc_pair(F['ref']['WS'], F[n]['WS'])
            d = st - r
            season = d.index.month.map(RC_SEASON)
            for se in RC_SEASONS:
                by[se].append(_rc_bstats_n(d[season == se].to_numpy(float), '', False))
        return names, RC_COLORS, by
    _rc_network("9.6", site, summ, lambda d: _rc_seasonal_box(
        "9.6", d, "Seasonal distribution of wind speed bias (3D-PAWS - TSMS at 2 m)", "Wind speed bias (m/s)",
        RC_WIND_NOTE + ". Paired 1-min values (N = paired minutes); outliers omitted, as in the report.", False))


def report_fig_9_7(site):
    """Report Fig. 9.7: 1-min wind speed scatter vs the 2-m-adjusted reference, regression + 1:1."""
    def summ(s):
        names, F = _rc_minutes(s)
        rng = np.random.default_rng(0)
        out = []
        for n, c in zip(names, RC_COLORS):
            r, st = _rc_pair(F['ref']['WS'], F[n]['WS'])
            x, y = r.to_numpy(float), st.to_numpy(float)
            k = rng.choice(len(x), min(len(x), 30000), replace=False)
            out.append((n, c, x[k], y[k], _rc_fit(x, y)))
        return out

    def draw(data):
        fig, axes = plt.subplots(1, 3, figsize=(19, 6.8), sharey=True)
        for ax, s in zip(axes, ALL_SITES):
            for n, c, x, y, st in data[s]:
                ax.scatter(x, y, s=4, color=c, alpha=0.2, edgecolors='none', rasterized=True)
                xx = np.array([0, 5])
                ax.plot(xx, st['slope'] * xx + st['icpt'], color=c, lw=2,
                        label=f"{n}: R² = {st['r2']:.3f}, bias {st['bias']:+.2f} m/s, N = {st['n']:,}")
            ax.plot([0, 5], [0, 5], color=RC_REF_COLOR, ls='--', lw=1.2, label='1:1')
            ax.set_xlim(0, 5); ax.set_ylim(0, 5); ax.set_aspect('equal')
            ax.set_title(s, fontsize=12, weight='bold'); ax.set_xlabel("TSMS wind speed at 2 m (m/s)")
            _rc_style(ax); ax.legend(fontsize=8, loc='upper left')
        axes[0].set_ylabel("3D-PAWS wind speed at 2 m (m/s)")
        fig.suptitle("Comparison of wind speed measurements", fontsize=14, weight='bold')
        _rc_note(fig, RC_WIND_NOTE + ". Paired 1-min values; fit and R² from all pairs (N), 30,000 random pairs per station drawn.",
                 y=-0.02)
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        _rc_save(fig, "9.7")
    _rc_network("9.7", site, summ, draw)


# ---- Figs 10.x ----------------------------------------------------------------------------------------------------------------
def report_fig_10_1(site):
    """Report Fig. 10.1: monthly precipitation totals (sum of eligible daily totals), reference + 3 stations."""
    months = pd.date_range(RC_START, RC_END, freq='MS')

    def summ(s):
        names, F = _rc_minutes(s)
        out = []
        for key, lab, col in _rc_series_list(s, names):
            d = _rc_daily(F[key]['R'], 'sum')
            out.append((lab, col, d.resample('MS').sum(min_count=1).reindex(months), len(d)))
        return out

    def draw(data):
        fig, axes = plt.subplots(3, 1, figsize=(18, 13.5))
        x = np.arange(len(months))
        for ax, s in zip(axes, ALL_SITES):
            allv = np.concatenate([m.dropna().values for _, _, m, _ in data[s]])
            nz = allv[allv > 0]
            top = min(allv.max(), 3 * np.percentile(nz, 95)) * 1.1 if len(nz) else 1
            for j, (lab, col, m, n) in enumerate(data[s]):
                v = m.fillna(0).values
                ax.bar(x - 0.3 + 0.2 * j, v, width=0.2, color=col, label=f"{lab}  N = {n:,} eligible days")
                for xi in np.where(v > top)[0]:   # bars cut by the axis: print their value
                    ax.text(x[xi] - 0.3 + 0.2 * j, top * 0.97, f"{lab.split()[0] if lab.startswith('TSMS0') else 'ref'}\n{v[xi]:,.0f} mm",
                            ha='center', va='top', fontsize=7.5, color=RC_REF_COLOR,
                            bbox=dict(boxstyle='round,pad=0.2', fc='white', ec=col, lw=0.8))
            ax.set_ylim(0, top)
            ax.set_xticks(x[::3]); ax.set_xticklabels([m.strftime('%b\n%Y') for m in months[::3]], fontsize=9)
            ax.set_xlim(-0.6, len(months) - 0.4)
            ax.set_ylabel("Monthly precipitation (mm)")
            ax.set_title(s + ("  (reference x10 from Mar 2023 - see caveat)" if s == "Ankara" else ""), loc='left',
                         fontsize=12, weight='bold')
            _rc_style(ax); ax.legend(fontsize=8.5, ncol=4, loc='upper right')
        fig.suptitle("Monthly precipitation totals at TSMS reference and 3D-PAWS stations", fontsize=14, weight='bold')
        _rc_note(fig, "Sum of daily totals from eligible days (>= 80% valid minutes), each series separately; months without an "
                 "eligible day shown as 0. Bars taller than the axis are cut and labelled with their value.\n" + RC_RAIN_CAVEAT, y=0.0)
        fig.tight_layout(rect=(0, 0.045, 1, 0.97))
        _rc_save(fig, "10.1")
    _rc_network("10.1", site, summ, draw)


def _rc_rain_paired_days(site):
    names, F = _rc_minutes(site)
    r = _rc_daily(F['ref']['R'], 'sum')
    out = {}
    for n in names:
        j = pd.concat([r, _rc_daily(F[n]['R'], 'sum')], axis=1, join='inner').dropna()
        j.columns = ['ref', 'st']
        out[n] = j
    return names, out


def report_fig_10_2(site):
    """Report Fig. 10.2: monthly precipitation totals, 3D-PAWS vs reference, regression, R² and bias."""
    def summ(s):
        names, P = _rc_rain_paired_days(s)
        out = []
        for n, c in zip(names, RC_COLORS):
            m = P[n].resample('MS').sum()
            m = m[P[n]['ref'].resample('MS').count() > 0]
            out.append((n, c, m['ref'].to_numpy(float), m['st'].to_numpy(float)))
        return out

    def draw(data):
        fig, axes = plt.subplots(1, 3, figsize=(19, 6.9))
        for ax, s in zip(axes, ALL_SITES):
            hi = 1
            for n, c, x, y in data[s]:
                st = _rc_fit(x, y)
                hi = max(hi, x.max() if len(x) else 0, y.max() if len(y) else 0)
                ax.scatter(x, y, s=30, color=c, alpha=0.75, edgecolors='white', lw=0.5)
                xx = np.array([0, hi * 1.1])
                ax.plot(xx, st['slope'] * xx + st['icpt'], color=c, lw=1.5,
                        label=f"{n}: R² = {st['r2']:.2f}, bias = {st['bias']:+.1f} mm, N = {st['n']} months")
            allv = np.concatenate([np.concatenate([x, y]) for _, _, x, y in data[s]])
            nz = allv[allv > 0]
            hi = min(hi, 3 * np.percentile(nz, 95)) * 1.05 if len(nz) else hi * 1.05
            off = [(n, xv, yv) for n, _, x, y in data[s] for xv, yv in zip(x, y) if xv > hi or yv > hi]
            if off:
                ax.text(0.98, 0.02, "Off-axis: " + "; ".join(f"{n} ({xv:,.0f}, {yv:,.0f} mm)" for n, xv, yv in off),
                        transform=ax.transAxes, ha='right', va='bottom', fontsize=8, color=RC_REF_COLOR,
                        bbox=dict(boxstyle='round', fc='white', ec='#999999'))
            ax.plot([0, hi], [0, hi], color=RC_REF_COLOR, ls='--', lw=1.2, label='1:1')
            ax.set_xlim(0, hi); ax.set_ylim(0, hi); ax.set_aspect('equal')
            ax.set_title(s + (" (reference x10 - not comparable)" if s == "Ankara" else ""), fontsize=12, weight='bold')
            ax.set_xlabel("TSMS reference (mm/month)"); ax.set_ylabel("3D-PAWS (mm/month)")
            _rc_style(ax); ax.legend(fontsize=8, loc='upper left')
        fig.suptitle("Monthly precipitation: TSMS reference vs 3D-PAWS", fontsize=14, weight='bold')
        _rc_note(fig, "Monthly sums over days eligible (>= 80% valid minutes) at both the station and the reference; bias = mean "
                 "monthly (3D-PAWS - TSMS).\n" + RC_RAIN_CAVEAT, y=-0.04)
        fig.tight_layout(rect=(0, 0.05, 1, 0.94))
        _rc_save(fig, "10.2")
    _rc_network("10.2", site, summ, draw)


def report_fig_10_3(site):
    """Report Fig. 10.3: daily precipitation event detection (POD, FAR, CSI), wet day >= 0.2 mm, paired eligible days."""
    def summ(s):
        names, P = _rc_rain_paired_days(s)
        out = []
        for n, c in zip(names, RC_COLORS):
            rw, sw = P[n]['ref'] >= 0.2, P[n]['st'] >= 0.2
            H, M, FA, CN = int((rw & sw).sum()), int((rw & ~sw).sum()), int((~rw & sw).sum()), int((~rw & ~sw).sum())
            pod = H / (H + M) if H + M else np.nan
            far = FA / (H + FA) if H + FA else np.nan
            csi = H / (H + M + FA) if H + M + FA else np.nan
            out.append((n, c, [pod, far, csi], (H, M, FA, CN), len(P[n])))
        return out

    def draw(data):
        fig, axes = plt.subplots(3, 1, figsize=(14, 12.5))
        metrics = ["POD (higher better)", "FAR (lower better)", "CSI (higher better)"]
        for ax, s in zip(axes, ALL_SITES):
            for j, (n, c, vals, (H, M, FA, CN), N) in enumerate(data[s]):
                x = np.arange(3) - 0.27 + 0.27 * j
                bars = ax.bar(x, vals, width=0.25, color=c,
                              label=f"{n}: N = {N:,} paired days (H {H}, M {M}, FA {FA}, CN {CN})")
                for b, v in zip(bars, vals):
                    ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}", ha='center', va='bottom', fontsize=8.5,
                            color=RC_REF_COLOR)
            ax.set_xticks(range(3)); ax.set_xticklabels(metrics)
            ax.set_ylim(0, 1.12); ax.set_ylabel("Score")
            ax.set_title(f"{s} (TSMS {RC_REF_ID[s]})" + ("  - reference rain x10 from Mar 2023, see caveat" if s == "Ankara" else ""),
                         loc='left', fontsize=12, weight='bold')
            _rc_style(ax); ax.legend(fontsize=8.5, loc='upper right', bbox_to_anchor=(1.0, 1.0))
        fig.suptitle("Daily precipitation event detection performance", fontsize=14, weight='bold')
        _rc_note(fig, "Wet day = daily total >= 0.2 mm; days with >= 80% valid minutes at both station and reference. "
                 "POD = H/(H+M), FAR = FA/(H+FA), CSI = H/(H+M+FA).\n" + RC_RAIN_CAVEAT, y=0.0)
        fig.tight_layout(rect=(0, 0.05, 1, 0.97))
        _rc_save(fig, "10.3")
    _rc_network("10.3", site, summ, draw)


RC_PLOTS = {f"report-fig-{fid}": (globals()[f"report_fig_{fid.replace('.', '_')}"], "site-wide",
                                  f"TSMS report Fig {fid} (p. {v[0]}) redrawn with our data"
                                  + (f" [{v[2]} only]" if v[2] else " [all sites; drawn after the last site]")
                                  + f" -> report-comparison/")
            for fid, v in RC_FIGS.items()}


# =============================================================================================================================
# Registry + CLI
# =============================================================================================================================
STATION, SITE = "per-station", "site-wide"

PLOTS = {   # name: (function, scope, one-line description)
    "timeseries-monthly":     (timeseries_monthly,      STATION, "monthly time series per sensor (temp, hum, pressure) vs reference -> time-series/<station>/"),
    "timeseries-temp-sensors":(timeseries_temp_sensors, STATION, "monthly time series of bmp2/htu/mcp9808 temperature together with reference -> time-series/<station>/temperature/"),
    "rain-monthly-bars":      (rain_monthly_bars,       STATION, "bar chart of monthly rain totals, instrument vs reference, complete record -> bar-charts/<station>/"),
    "rain-daily-bars":        (rain_daily_bars,         STATION, "one bar chart per month of daily rain totals, instrument vs reference -> bar-charts/<station>/"),
    "windrose":               (windrose,                STATION, "complete-record 10-min-avg wind roses, all/variable/non-variable (regime from reference) -> wind-roses/<station>/"),
    "windrose-monthly":       (windrose_monthly,        STATION, "monthly non-variable (>=3 m/s) wind roses, instrument and reference -> wind-roses/<station>/ and wind-roses/<site>/"),
    "scatter-vs-ref":         (scatter_vs_ref,          STATION, "scatter + trend/r/RMSE per sensor vs reference (rain as hourly sums) -> statistical/scatter-plots/<station>/"),
    "scatter-temp-sensors":   (scatter_temp_sensors,    STATION, "scatter between the 3D-PAWS temperature sensors (bmp2/htu/mcp9808) -> statistical/scatter-plots/<station>/temperature/"),
    "boxplots":               (boxplots,                STATION, "box plots of temperature, humidity, pressure sensors vs reference -> statistical/box-plots/<station>/"),
    "violins":                (violins,                 STATION, "violin plot per temp/hum/pressure sensor vs reference -> statistical/violin-plots/<station>/"),
    "histograms":             (histograms,              STATION, "histograms per sensor and for the reference -> statistical/histograms/<station>/"),
    "site-temp-monthly":      (site_temp_monthly,       SITE,    "per site, per temperature sensor type: 3 instruments + reference, monthly -> time-series/<site>/temperature/trends/"),
    "site-hum-monthly":       (site_hum_monthly,        SITE,    "per site, per humidity sensor type: 3 instruments + reference, monthly -> time-series/<site>/humidity/trends/"),
    "site-pres-monthly":      (site_pres_monthly,       SITE,    "per site station pressure: 3 instruments + reference, monthly -> time-series/<site>/actual_pressure/trends/"),
    "rain-accum-timeseries":  (rain_accum_timeseries,   SITE,    "per site cumulative rainfall, 3 instruments + reference, complete record -> time-series/<site>/total_rainfall/trends/"),
    "site-rain-daily-bars":   (site_rain_daily_bars,    SITE,    "per site, one bar chart per month of daily rain totals, all instruments -> bar-charts/<site>/"),
    "site-rain-monthly-bars": (site_rain_monthly_bars,  SITE,    "per site bar chart of monthly rain totals, all instruments, complete record -> bar-charts/<site>/"),
    "diff-pressure":          (diff_pressure,           SITE,    "per site daily-mean pressure difference from reference, SHT-upgrade line -> time-series/<site>/actual_pressure/differences/"),
    "diff-temperature":       (diff_temperature,        SITE,    "per site daily-mean difference per temperature sensor, SHT-upgrade line -> time-series/<site>/temperature/differences/"),
    "diff-humidity":          (diff_humidity,           SITE,    "per site daily-mean difference per humidity sensor, SHT-upgrade line -> time-series/<site>/humidity/differences/"),
}
PLOTS.update(RC_PLOTS)   # report-fig-6.1 ... report-fig-10.3 (TSMS draft report parity figures)


def _resolve_station(s):
    if s in station_order:
        return s
    hits = [n for n in station_order if s.upper() in n.upper()]
    if len(hits) != 1:
        raise SystemExit(f"Unknown or ambiguous station '{s}' (choose from {', '.join(station_order)})")
    return hits[0]


def _resolve_site(s):
    for name in ALL_SITES:
        if s.lower() == name.lower():
            return name
    raise SystemExit(f"Unknown site '{s}' (choose from {', '.join(ALL_SITES)})")


def run(plots=None, stations=None, sites=None, out=None):
    """Run the named plots. stations: names or short ids (TSMS00); sites: Ankara/Konya/Adana; out: output root.
    Returns a list of (plot, target, error-or-None)."""
    global data_destination, _RUN_SITES
    plots = list(plots) if plots else list(DEFAULT_PLOTS)
    unknown = [p for p in plots if p not in PLOTS]
    if unknown:
        raise SystemExit(f"Unknown plot(s): {', '.join(unknown)}. Use --list.")
    if out is not None:
        data_destination = Path(out).resolve()

    station_list = [_resolve_station(s) for s in stations] if stations else list(station_order)
    site_list = [_resolve_site(s) for s in sites] if sites else list(ALL_SITES)
    _RUN_SITES = list(site_list)   # whole-network report figures draw after the last of these
    per_station = [p for p in plots if PLOTS[p][1] == STATION]
    site_wide = [p for p in plots if PLOTS[p][1] == SITE]

    results = []

    def call(name, target, *args):
        try:
            PLOTS[name][0](*args)
            results.append((name, target, None))
        except Exception as e:                      # keep going; report at the end
            traceback.print_exc()
            results.append((name, target, f"{type(e).__name__}: {e}"))
        finally:
            plt.close('all')

    # Work site by site so at most one site's data is held in memory.
    for site in ALL_SITES:
        todo_stations = [s for s in station_list if instrument_to_site[s] == site] if per_station else []
        todo_site = site in site_list and bool(site_wide)
        if not todo_stations and not todo_site:
            continue
        for paws_name in todo_stations:
            paws_df, tsms_df = load_station(paws_name)
            for name in per_station:
                call(name, paws_name, paws_name, paws_df, tsms_df)
        if todo_site:
            for name in site_wide:
                call(name, site, site)
        _evict([s for s in station_order if instrument_to_site[s] == site] + [f"TSMS_Reference_{site}"])
        for n in [s for s in station_order if instrument_to_site[s] == site]:
            _WR_HOURLY.pop(n, None)

    failed = [r for r in results if r[2]]
    print(f"\nDone: {len(results) - len(failed)} ok, {len(failed)} failed")
    for name, target, err in failed:
        print(f"\tFAILED {name} [{target}]: {err}")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Final plots for the TSMS intercomparison.")
    parser.add_argument("plots", nargs="*", help=f"plot names (default: {' '.join(DEFAULT_PLOTS)}); see --list")
    parser.add_argument("--list", action="store_true", help="list plot names and exit")
    parser.add_argument("--stations", nargs="+", help="per-station plots: stations (e.g. TSMS00 TSMS06); default all nine")
    parser.add_argument("--sites", nargs="+", help="site-wide plots: sites (Ankara Konya Adana); default all three")
    parser.add_argument("--out", help="output root directory (overrides data_destination = plots/)")
    args = parser.parse_args(argv)

    if args.list:
        width = max(len(n) for n in PLOTS)
        for name, (_, scope, desc) in PLOTS.items():
            mark = "*" if name in DEFAULT_PLOTS else " "
            print(f"{mark} {name:<{width}}  [{scope:<11}]  {desc}")
        print("\n* = default when no plot names are given")
        return 0

    results = run(args.plots, stations=args.stations, sites=args.sites, out=args.out)
    return 1 if any(r[2] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
