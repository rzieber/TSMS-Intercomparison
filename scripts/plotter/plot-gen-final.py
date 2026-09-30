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
    =============================================================================================================================
    """
    print(f"{paws_name}: Wind roses (all / variable / non-variable winds, classified by the reference).")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)

        site = instrument_to_site[paws_name]
        top_of_hour = [51, 52, 53, 54, 55, 56, 57, 58, 59, 0]
        wind_speed_bins = [0, 2.0, 4.0, 6.0, 8.0, 10.0]
        labels = ['0-2.0 m/s', '2.0-4.0 m/s', '4.0-6.0 m/s', '6.0-8.0 m/s', '8.0-10.0 m/s']

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

            axes = []
            for hourly, name, path in roses:
                calm = hourly['ws_avg'] <= 0
                windy = hourly[~calm]
                ax = WindroseAxes.from_ax()
                ax.bar(windy['wd_avg'], windy['ws_avg'], normed=True, opening=0.8, edgecolor='white', bins=wind_speed_bins)
                ax.set_legend(title=f"{name} (m/s)\n{regime_titles[regime]}\n{len(hourly)} h, calm {100 * calm.mean():.1f}%", labels=labels,
                              loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8, title_fontsize=8)
                axes.append((ax, path))

            # same radial scale for the 3D-PAWS and TSMS roses of a regime
            rmax = 5 * np.ceil(max(ax._info['table'].sum(axis=0).max() for ax, _ in axes) / 5)
            ticks = np.linspace(rmax / 5, rmax, 5)
            for ax, path in axes:
                ax.set_rmax(rmax)
                ax.set_yticks(ticks)
                ax.set_yticklabels([f"{t:.0f}%" for t in ticks])
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
    global data_destination
    plots = list(plots) if plots else list(DEFAULT_PLOTS)
    unknown = [p for p in plots if p not in PLOTS]
    if unknown:
        raise SystemExit(f"Unknown plot(s): {', '.join(unknown)}. Use --list.")
    if out is not None:
        data_destination = Path(out).resolve()

    station_list = [_resolve_station(s) for s in stations] if stations else list(station_order)
    site_list = [_resolve_site(s) for s in sites] if sites else list(ALL_SITES)
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
