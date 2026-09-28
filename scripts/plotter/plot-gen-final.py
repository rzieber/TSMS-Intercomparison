"""
USAGE----------------------------------------
    1. Update data_origin and data_destination with correct paths.
    2. Uncomment the portion you wish to make plots for.
"""
import pandas as pd
import numpy as np
import sys
import matplotlib.pyplot as plt
from datetime import timedelta, datetime
from functools import reduce
from scipy.stats import pearsonr, linregress
from sklearn.metrics import mean_squared_error
import seaborn as sns
from windrose import WindroseAxes
import matplotlib.cm as cm
from pathlib import Path
import warnings

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from dev import functions as func



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
paws_dfs = []
tsms_dfs = []
for paws_name in station_order:
    paws_path = data_origin / f"{paws_name}_final.csv"
    site = instrument_to_site[paws_name]
    ref_name = f"TSMS_Reference_{site}"
    ref_path = data_origin / f"{ref_name}_final.csv"

    print("Reading", paws_name, "and", ref_name)

    paws_df_FILTERED = pd.read_csv(paws_path, parse_dates=['date'])
    tsms_df_FILTERED = pd.read_csv(ref_path, parse_dates=['date'])

    paws_df_FILTERED['year_month'] =            paws_df_FILTERED['date'].dt.to_period('M')
    paws_df_FILTERED['year_month_day'] =        paws_df_FILTERED['date'].dt.to_period('D')
    paws_df_FILTERED['year_month_day_hour'] =   paws_df_FILTERED['date'].dt.to_period('h')
    
    tsms_df_FILTERED['year_month'] =            tsms_df_FILTERED['date'].dt.to_period('M')
    tsms_df_FILTERED['year_month_day'] =        tsms_df_FILTERED['date'].dt.to_period('D')
    tsms_df_FILTERED['year_month_day_hour'] =   tsms_df_FILTERED['date'].dt.to_period('h')
    

    """
    =============================================================================================================================
    Create a time series plot of the 3D PAWS station data versus the TSMS reference station. MONTHLY RECORDS
    =============================================================================================================================
    """
    # print(f"{paws_name}: " \
    #         "Time-series plots for temperature, humidity, actual pressure and sea level pressure -- monthly records")
    
    # paws_df_FILTERED.set_index('date', inplace=True)
    # tsms_df_FILTERED.set_index('date', inplace=True)
    
    # tsms_df_FILTERED = tsms_df_FILTERED[paws_df_FILTERED.index[0]:paws_df_FILTERED.index[-1]]

    # # Temperature ---------------------------------------------------------------------------------------------------------------
    # print("Temperature per sensor")
    # for t in variable_mapper['temperature']:
    #     for year_month, paws_group in paws_df_FILTERED.groupby('year_month'):
    #         tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #         plt.figure(figsize=(20,12))

    #         plt.plot(paws_group.index, paws_group[f'{t}'], marker='.', markersize=1, label=f"3D PAWS {t}")
    #         plt.plot(tsms_group.index, tsms_group['temperature'], marker='.', markersize=1, label='TSMS')
        
    #         plt.title(f'{paws_name} Temperature for {year_month}: 3D PAWS {t} versus TSMS')
    #         plt.xlabel('Date')
    #         plt.ylabel('Temperature (˚C)')
    #         plt.xticks(rotation=45)

    #         plt.legend()

    #         plt.grid(True)
    #         plt.tight_layout()
    #         plt.savefig(data_destination / "time-series" / f"{paws_name}" / "temperature" / f"{paws_name}_{t}_{year_month}.png")
            
    #         plt.clf()
    #         plt.close()


    # # Humidity ------------------------------------------------------------------------------------------------------------------
    # print("Humidity per sensor")
    # for h in variable_mapper['humidity']:
    #     if h == "bme2_hum": continue
    #     for year_month, paws_group in paws_df_FILTERED.groupby('year_month'):
    #         tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #         plt.figure(figsize=(20,12))

    #         plt.plot(paws_group.index, paws_group[f'{h}'], marker='.', markersize=1, label=f"3D PAWS {h}")
    #         plt.plot(tsms_group.index, tsms_group['humidity'], marker='.', markersize=1, label='TSMS')
        
    #         plt.title(f'{paws_name} Humidity for {year_month}: 3D PAWS {h} versus TSMS')
    #         plt.xlabel('Date')
    #         plt.ylabel('Humidity (%)')
    #         plt.xticks(rotation=45)

    #         plt.legend()

    #         plt.grid(True)
    #         plt.tight_layout()
    #         plt.savefig(data_destination / "time-series" / f"{paws_name}" / "humidity" / f"{paws_name}_{h}_{year_month}.png")
            
    #         plt.clf()
    #         plt.close()


    # # Pressure ------------------------------------------------------------------------------------------------------------------
    # print("Pressure per sensor")
    # for year_month, paws_group in paws_df_FILTERED.groupby("year_month"):
    #     tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #     plt.figure(figsize=(20,12))

    #     plt.plot(paws_group.index, paws_group['bmp2_pres'], marker='.', markersize=1, label="3D PAWS bmp2_pres")
    #     plt.plot(tsms_group.index, tsms_group['actual_pressure'], marker='.', markersize=1, label='TSMS')

    #     plt.title(f'{paws_name} Pressure for {year_month}: 3D PAWS bmp2_pres versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Pressure (mbar)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination / "time-series" / f"{paws_name}" / "actual_pressure" / f"{paws_name}_bmp2-pres_{year_month}.png")
        
    #     plt.clf()
    #     plt.close()

    
    # # # Sea Level Pressure --------------------------------------------------------------------------------------------------------
    # # print("Sea Level Pressure per sensor")
    # # for year_month, paws_group in paws_df_FILTERED.groupby("year_month"):
    # #     tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    # #     plt.figure(figsize=(20,12))

    # #     plt.plot(paws_group.index, paws_group['bmp2_slp'], marker='.', markersize=1, label="3D PAWS bmp2_slp")
    # #     plt.plot(tsms_group.index, tsms_group['sea_level_pressure'], marker='.', markersize=1, label='TSMS')

    # #     plt.title(f'{paws_name} Sea Level Pressure for {year_month}: 3D PAWS bmp2_slp versus TSMS')
    # #     plt.xlabel('Date')
    # #     plt.ylabel('Pressure (mbar)')
    # #     plt.xticks(rotation=45)

    # #     plt.legend()

    # #     plt.grid(True)
    # #     plt.tight_layout()
    # #     plt.savefig(data_destination / "time-series" / f"{paws_name}" / "sea_level_pressure" / f"{paws_name}_bmp2-slp_{year_month}.png")
        
    # #     plt.clf()
    # #     plt.close()


    """
    =============================================================================================================================
    Create time series plots of the 3 temperature sensors compared to TSMS. MONTHLY RECORDS
    =============================================================================================================================
    """
    # print(f"{paws_name} Temperature Comparison")

    # with warnings.catch_warnings():
    #     warnings.simplefilter("ignore", category=pd.errors.SettingWithCopyWarning)

    #     tsms_df_FILTERED_2 = tsms_df_FILTERED[paws_df_FILTERED.index[0]:paws_df_FILTERED.index[-1]]

    #     tsms_df_FILTERED_2.reset_index(inplace=True)
    #     paws_df_FILTERED.reset_index(inplace=True)

    #     tsms_df_FILTERED_2['date'] = pd.to_datetime(tsms_df_FILTERED_2['date'])
    #     paws_df_FILTERED['date'] = pd.to_datetime(paws_df_FILTERED['date'])

    #     for year_month, paws_group in paws_df_FILTERED.groupby('year_month'):
    #         tsms_group = tsms_df_FILTERED_2[tsms_df_FILTERED_2['year_month'] == year_month]

    #         plt.figure(figsize=(20,12))

    #         plt.plot(paws_group['date'], paws_group["bmp2_temp"], marker='.', markersize=1, label=f"3D PAWS bmp2_temp")
    #         plt.plot(paws_group['date'], paws_group["htu_temp"], marker='.', markersize=1, label=f"3D PAWS htu_temp")
    #         plt.plot(paws_group['date'], paws_group["mcp9808"], marker='.', markersize=1, label=f"3D PAWS mcp9808")
    #         plt.plot(tsms_group['date'], tsms_group['temperature'], marker='.', markersize=1, label='TSMS')

    #         plt.title(f'{paws_name} Temperature Comparison for {year_month}: 3D PAWS versus TSMS')
    #         plt.xlabel('Date')
    #         plt.ylabel('Temperature (˚C)')
    #         plt.xticks(rotation=45)

    #         plt.legend()

    #         plt.grid(True)
    #         plt.tight_layout()
    #         plt.savefig(data_destination / "time-series" / f"{paws_name}" / "temperature" / f"{paws_name}_temp_comparison_{year_month}.png")

    #         plt.clf()
    #         plt.close()


    """
    =============================================================================================================================
    Create bar charts for monthly 3D PAWS rainfall accumulation compared to TSMS rainfall accumulation. COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{paws_name}: " \
    #         "Bar charts for rainfall accumulation -- complete records")
    
    # paws_df_FILTERED_2 = paws_df_FILTERED[paws_df_FILTERED['tipping'] >= 0].copy().reset_index()
    # tsms_df_FILTERED_2 = tsms_df_FILTERED[(tsms_df_FILTERED['total_rainfall']) >= 0].copy().reset_index()

    # tsms_df_REDUCED = tsms_df_FILTERED_2[ # need to filter TSMS s.t. data timeframe equals PAWS
    #     (tsms_df_FILTERED_2['date'] >= paws_df_FILTERED_2['date'].iloc[0]) & \
    #     (tsms_df_FILTERED_2['date'] <= paws_df_FILTERED_2['date'].iloc[-1])
    # ]

    # paws_totals = {}
    # tsms_totals = {}

    # for year_month, paws_grouped in paws_df_FILTERED_2.groupby("year_month"):
    #     tsms_grouped = tsms_df_REDUCED[tsms_df_REDUCED['year_month'] == year_month]

    #     merged_df = pd.merge(paws_grouped, tsms_grouped, on='date', how='inner')  # to eliminate bias

    #     merged_df['cumulative_rainfall_3DPAWS'] = merged_df['tipping'].cumsum()
    #     merged_df['cumulative_rainfall_TSMS'] = merged_df['total_rainfall'].cumsum()

    #     paws_total_rainfall = merged_df['cumulative_rainfall_3DPAWS'].iloc[-1] - merged_df['cumulative_rainfall_3DPAWS'].iloc[0]
    #     tsms_total_rainfall = merged_df['cumulative_rainfall_TSMS'].iloc[-1] - merged_df['cumulative_rainfall_TSMS'].iloc[0]

    #     paws_totals[year_month] = paws_total_rainfall
    #     tsms_totals[year_month] = tsms_total_rainfall
    
    # months = list(paws_totals.keys())
    # paws_values = list(paws_totals.values())
    # tsms_values = list(tsms_totals.values())

    # index = range(len(months))

    # plt.figure(figsize=(18, 12))

    # bars1 = plt.bar(index, paws_values, width=0.35, color='blue', label='3DPAWS Rainfall')
    # bars2 = plt.bar([i + 0.35 for i in index], tsms_values, width=0.35, color='orange', label='TSMS Rainfall')

    # # Add labels, title, and legend
    # plt.xlabel('Month')
    # plt.ylabel('Cumulative Rainfall (mm)')
    # plt.title(f'{paws_name} Monthly Rainfall Comparison: 3DPAWS vs TSMS')
    # plt.xticks([i + 0.35 / 2 for i in index], [str(month) for month in months], rotation=45)
    # plt.legend()

    # # Add numerical values above bars
    # for bar in bars1:
    #     yval = bar.get_height()
    #     plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 2), ha='center', va='bottom', fontsize=12)

    # for bar in bars2:
    #     yval = bar.get_height()
    #     plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 2), ha='center', va='bottom', fontsize=12)

    # plt.tight_layout()

    # plt.savefig(data_destination / "bar-charts" / f"{paws_name}" / f"{paws_name}_monthly_rainfall.png") 
    
    # plt.clf()
    # plt.close()   

    """
    =============================================================================================================================
    Create bar charts for daily 3D PAWS rainfall accumulation (per instrument) compared to TSMS rainfall accumulation. MONTHLY RECORDS
    =============================================================================================================================
    """
    # print(f"{paws_name}: " \
    #                     "Bar charts for rainfall accumulation -- monthly records [INSTRUMENT VS REFERENCE COMPARISON]")
        
    # for year_month, paws_grouped in paws_df_FILTERED.groupby("year_month"):
    #     tsms_grouped = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #     merged_df = pd.merge(paws_grouped, tsms_grouped, on='date', how='inner')  # to eliminate bias

    #     # Calculate daily rainfall totals instead of cumulative
    #     merged_df['daily_rainfall_3DPAWS'] = merged_df['tipping']
    #     merged_df['daily_rainfall_TSMS'] = merged_df['total_rainfall']

    #     # Sum daily rainfall by date
    #     daily_totals = merged_df.groupby('year_month_day_x')[['daily_rainfall_3DPAWS', 'daily_rainfall_TSMS']].sum().reset_index()

    #     days = daily_totals['year_month_day_x'].dt.day
    #     paws_values = daily_totals['daily_rainfall_3DPAWS']
    #     tsms_values = daily_totals['daily_rainfall_TSMS']

    #     index = range(len(days))

    #     plt.figure(figsize=(20, 12))

    #     bars1 = plt.bar(index, paws_values, width=0.35, color='blue', label='3DPAWS Daily Rainfall')
    #     bars2 = plt.bar([i + 0.35 for i in index], tsms_values, width=0.35, color='orange', label='TSMS Daily Rainfall')

    #     # Add labels, title, and legend
    #     plt.xlabel(f'Day in {year_month}')
    #     plt.ylabel('Daily Rainfall (mm)')
    #     plt.title(f'{paws_name} Daily Rainfall Comparison: 3DPAWS vs TSMS for {year_month}')
    #     plt.xticks([i + 0.35 / 2 for i in index], days, rotation=45)
    #     plt.ylim(0, 50)
    #     plt.legend()

    #     # Add numerical values above bars
    #     for bar in bars1:
    #         yval = bar.get_height()
    #         plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 1), ha='center', va='bottom', fontsize=12)

    #     for bar in bars2:
    #         yval = bar.get_height()
    #         plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 1), ha='center', va='bottom', fontsize=12)

    #     # Display the plot
    #     plt.tight_layout()

    #     # Save the plot   
    #     plt.savefig(data_destination / "bar-charts" / f"{paws_name}" / f"{paws_name}_{year_month}_daily_rainfall.png")    
        
    #     plt.clf()
    #     plt.close()


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
        paws_wind = paws_df_FILTERED[['date', 'wind_speed', 'wind_dir']].copy()
        paws_wind['date'] = pd.to_datetime(paws_wind['date'])
        paws_wind['wind_speed'] = pd.to_numeric(paws_wind['wind_speed'], errors='coerce')
        paws_wind = paws_wind.dropna(subset=['wind_speed', 'wind_dir']).set_index('date')
        paws_wind = paws_wind[paws_wind.index.minute.isin(top_of_hour)]
        paws_hourly = paws_wind.groupby(paws_wind.index.floor('h') + pd.Timedelta('1h')).apply(func.paws_hourly_vectorial)

        # TSMS: Hellmann-adjusted 2-m speed for the rose, unadjusted 10-m speed for the regime ---------------------------------
        tsms_wind = tsms_df_FILTERED[['date', 'avg_wind_speed', 'avg_wind_dir']].copy()
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

        out_dir = data_destination / "wind-roses" / paws_name
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



    """
    =============================================================================================================================
    Create wind rose plots of the 3D PAWS station data as well as the TSMS reference station. MONTHLY RECORDS
    NOTE: Still need to add 10-minute averaging to capture steady state wind speed and direction
    =============================================================================================================================
    """
    # print(f"{paws_name}: Wind roses for 3D PAWS and TSMS -- monthly records")

    # with warnings.catch_warnings():
    #     warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
    #     warnings.filterwarnings("ignore", category=RuntimeWarning)

    #     # 3D PAWS -------------------------------------------------------------------------------------------------------------------
    #     print("3D PAWS")
    #     paws_df_FILTERED.reset_index(inplace=True)
    #     paws_df_FILTERED['date'] = pd.to_datetime(paws_df_FILTERED['date'])

    #     paws_df_FILTERED['wind_speed'] = pd.to_numeric(paws_df_FILTERED['wind_speed'], errors='coerce')
    #     #paws_df_FILTERED = paws_df[(paws_df["wind_speed"] > 0)]                   # for variable winds
    #     paws_df_FILTERED_2 = paws_df_FILTERED[paws_df_FILTERED['wind_speed'] >= 3.0]  # for NON-variable winds

    #     # if paws_name.endswith("Ankara"):
    #     #     paws_df_FILTERED_2['wind_dir_true'] = (paws_df_FILTERED_2['wind_dir'] + magnetic_declinations[0] + wind_direction_bias[0]) % 360
    #     # elif paws_name.endswith("Konya"):
    #     #     paws_df_FILTERED_2['wind_dir_true'] = (paws_df_FILTERED_2['wind_dir'] + magnetic_declinations[1] + wind_direction_bias[1]) % 360
    #     # else:
    #     #     paws_df_FILTERED_2['wind_dir_true'] = (paws_df_FILTERED_2['wind_dir'] + magnetic_declinations[2] + wind_direction_bias[2]) % 360

    #     paws_df_FILTERED_2.set_index('date', inplace=True)

    #     first_timestamp = paws_df_FILTERED_2.index[0]
    #     last_timestamp = paws_df_FILTERED_2.index[-1]
    #     # first_timestamp = pd.Timestamp("2022-09-09 00:00") # for replicating the TSMS intercomparison study
    #     # last_timestamp = pd.Timestamp("2023-02-24 12:42")

    #     # wind_speed_bins = [0, 2.0, 4.0, 6.0, 8.0, 10.0]
    #     # labels = ['0-2.0 m/s', '2.0-4.0 m/s', '4.0-6.0 m/s', '6.0-8.0 m/s', '8.0-10.0 m/s']       # for variable winds
    #     wind_speed_bins = [2.0, 4.0, 6.0, 8.0, 10.0]        
    #     labels = [f"{wind_speed_bins[i]}–{wind_speed_bins[i+1]} m/s" for i in range(len(wind_speed_bins)-1)]                    # for NON-variable winds

    #     paws_df_FILTERED_2.loc[:, 'wind_speed_category'] = pd.cut(paws_df_FILTERED_2['wind_speed'], bins=wind_speed_bins, labels=labels, right=False)

    #     for year_month, paws_group in paws_df_FILTERED_2.groupby("year_month"): 
    #         plt.figure(figsize=(20, 12))

    #         ax = WindroseAxes.from_ax()
    #         ax.bar(paws_group['wind_dir'], paws_group['wind_speed'], normed=True, opening=0.8, edgecolor='white', bins=wind_speed_bins)
    #         ax.set_legend(title=f"{paws_name} for {year_month} (m/s)", labels=labels)
            
    #         # ax.set_rmax(60)
    #         # ax.set_yticks([12, 24, 36, 48, 60])
    #         # ax.set_yticklabels(['12%', '24%', '36%', '48%', '60%']) # for variable winds
    #         ax.set_rmax(100)
    #         ax.set_yticks([20, 40, 60, 80, 100])
    #         ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%']) # for NON-variable winds
                
    #         ax.grid(True, linewidth=0.5)  # Thinner grid lines can improve readability

    #         plt.savefig(data_destination / "wind-roses" / f"{paws_name}" / f"{paws_name}_{year_month}_nonvariable_winds.png")
    #         # plt.savefig(data_destination / "wind-roses" / f"{paws_name}" / f"{paws_name}_{year_month}_variable_winds.png")
    #         plt.clf()
    #         plt.close()


    #     # TSMS ----------------------------------------------------------------------------------------------------------------------
    #     print("TSMS") # TSMS dataset was already cleaned
    #     tsms_df_FILTERED.reset_index(inplace=True)
    #     tsms_df_FILTERED['date'] = pd.to_datetime(tsms_df_FILTERED['date'])

    #     tsms_df_FILTERED_2 = tsms_df_FILTERED[~((tsms_df_FILTERED['avg_wind_speed'] == 0.0) & (tsms_df_FILTERED['avg_wind_dir'] == 0.0))]
    #     tsms_df_FILTERED_2 = tsms_df_FILTERED[tsms_df_FILTERED['avg_wind_speed'] >= 3.0]  # for NON-variable winds

    #     # Apply Hellman correction to 2m
    #     h1 = 10.0 
    #     h2 = 2.0 
    #     hellman_exp = 0.14  # Neutral stability, short grass[web:362]

    #     tsms_df_FILTERED_2['avg_wind_speed_2m'] = tsms_df_FILTERED_2['avg_wind_speed'] * \
    #         ((h2 / h1) ** hellman_exp)

    #     tsms_df_FILTERED_2.set_index('date', inplace=True)

    #     tsms_subset = tsms_df_FILTERED_2.loc[first_timestamp:last_timestamp]

    #     tsms_subset.loc[:, 'wind_speed_category'] = pd.cut(tsms_subset['avg_wind_speed_2m'], bins=wind_speed_bins, labels=labels, right=False)

    #     for year_month, tsms_group in tsms_subset.groupby("year_month"):
    #         plt.figure(figsize=(20, 12))

    #         ax = WindroseAxes.from_ax()
    #         ax.bar(tsms_group['avg_wind_dir'], tsms_group['avg_wind_speed_2m'], normed=True, opening=0.8, edgecolor='white', bins=wind_speed_bins)

    #         if paws_name.endswith("Ankara"):
    #             ax.set_legend(title=f"TSMS Reference at Ankara for {year_month} (m/s)", labels=labels)
    #         elif paws_name.endswith("Konya"):
    #             ax.set_legend(title=f"TSMS Reference at Konya for {year_month} (m/s)", labels=labels)
    #         else: 
    #             ax.set_legend(title=f"TSMS Reference at Adana for {year_month} (m/s)", labels=labels)
            
    #         # ax.set_rmax(60)
    #         # ax.set_yticks([12, 24, 36, 48, 60])
    #         # ax.set_yticklabels(['12%', '24%', '36%', '48%', '60%']) # for variable winds
    #         ax.set_rmax(100)
    #         ax.set_yticks([20, 40, 60, 80, 100])
    #         ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%']) # for NON-variable winds
                
    #         ax.grid(True, linewidth=0.5)  # Thinner grid lines can improve readability

    #         if paws_name.endswith("Ankara"):
    #             plt.savefig(data_destination / "wind-roses" / "Ankara" /  f"TSMS-Reference_Ankara_{year_month}_nonvariable_winds.png")
    #             # plt.savefig(data_destination / "wind-roses" / "Ankara" /  f"TSMS-Reference_{year_month}_variable_winds.png")
    #         elif paws_name.endswith("Konya"):
    #             plt.savefig(data_destination / "wind-roses" / "Konya" /  f"TSMS-Reference_Konya_{year_month}_nonvariable_winds.png")
    #             # plt.savefig(data_destination / "wind-roses" / "Konya" /  f"TSMS-Reference_{year_month}_variable_winds.png")
    #         else:
    #             plt.savefig(data_destination / "wind-roses" / "Adana" /  f"TSMS-Reference_Adana_{year_month}_nonvariable_winds.png")
    #             # plt.savefig(data_destination / "wind-roses" / "Adana" /  f"TSMS-Reference_{year_month}_variable_winds.png")
            
    #         plt.clf()
    #         plt.close()


    """
    =============================================================================================================================
    Create scatter plots for each 3D PAWS sensor compared to the TSMS reference data. COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{paws_name}: " \
    #                     "Scatter plots for temperature, humidity, actual pressure, sea level pressure, and rain\n" \
    #                     "3D PAWS vs TSMS")

    # for variable in station_variables: 
    #     print(f"{variable} -- 3D PAWS vs TSMS")

    #     if variable == 'wind': variable = 'avg_wind_speed'

    #     for v in variable_mapper[f'{variable}']:
    #         if v in ['bme2_hum', 'wind_dir', 'bmp2_slp']:
    #             continue

    #         if v == 'tipping': 
    #             merged_df = pd.merge(
    #                 paws_df_FILTERED[['date', f"{v}"]],
    #                 tsms_df_FILTERED[['date', f"{variable}"]],
    #                 on='date',
    #                 how='inner'
    #             )

    #             hourly_totals = (
    #                 merged_df
    #                 .set_index('date') 
    #                 .resample('h')     # group into 1-hour bins
    #                 [[v, variable]]    # PAWS vs TSMS cols
    #                 .sum()             # sum rainfall within each hour
    #                 .reset_index()
    #             )

    #             x = hourly_totals[v]
    #             y = hourly_totals[variable]

    #             mask = x.notna() & y.notna()
    #             x, y = x[mask], y[mask]

    #             plt.figure(figsize=(6, 6))

    #             plt.scatter(x, y, alpha=0.5, s=10)

    #             # Calculate and plot trend line
    #             m, b = np.polyfit(x, y, 1)

    #             x_line = np.linspace(x.min(), x.max(), 100)
    #             y_line = (m * x_line) + b

    #             plt.plot(x_line, y_line, color='red', linewidth=2, label='Trend line')

    #             # Calculate correlation coefficient
    #             corr_coef, _ = pearsonr(x, y)
    #             plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #             # Calculate RMSE
    #             rmse = np.sqrt(mean_squared_error(y, x))
    #             textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #             bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #             plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                     verticalalignment='top', bbox=bbox_props)

    #             plt.title(f'{paws_name} 3D PAWS Rainfall versus TSMS')
    #             plt.xlabel(f'3D PAWS Rainfall')
    #             plt.ylabel(f"TSMS {variable}")

    #             plt.legend()
    #             plt.grid(True)
    #             plt.tight_layout()

    #             plt.savefig(data_destination / "statistical" / "scatter-plots" / f"{paws_name}" / "total_rainfall" / f"{paws_name}_rainfall_scatter-plot.png")
    
    #             plt.clf()
    #             plt.close()

    #             continue


    #         merged_df = pd.merge(
    #             paws_df_FILTERED[['date', f"{v}"]],
    #             tsms_df_FILTERED[['date', f"{variable}"]],
    #             on='date',
    #             how='inner'
    #         )

    #         x = merged_df[f'{v}'].to_numpy()
    #         y = merged_df[f'{variable}'].to_numpy()

    #         if len(x) == 0 or len(y) == 0: 
    #             print(f"Skipping {paws_name} {v} vs {variable}: no overlapping data")
    #             continue

    #         mask = np.isfinite(x) & np.isfinite(y)
    #         x, y = x[mask], y[mask]

    #         if len(x) == 0 or len(y) == 0: 
    #             print(f"Skipping {paws_name} {v} vs {variable}: no finite data after filtering")
    #             continue

    #         plt.figure(figsize=(6, 6))

    #         plt.scatter(x, y, s=10)

    #         # Calculate and plot trend line
    #         m, b = np.polyfit(x, y, 1)
    #         x_line = np.linspace(x.min(), x.max(), 100)
    #         y_line = (m * x_line) + b

    #         plt.plot(x_line, y_line, color='red', linewidth=2, label='Trend line')

    #         # Calculate correlation coefficient
    #         corr_coef, _ = pearsonr(x, y)
    #         plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #         # Calculate RMSE
    #         rmse = np.sqrt(mean_squared_error(y, x))
    #         textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #         bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #         plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                 verticalalignment='top', bbox=bbox_props)

    #         plt.title(f'{paws_name} 3D PAWS {v} versus TSMS')
    #         plt.xlabel(f'3D PAWS {v}')
    #         plt.ylabel(f"TSMS {variable}")

    #         plt.legend()
    #         plt.grid(True)
    #         plt.tight_layout()

    #         if variable == "avg_wind_speed": variable = "wind"

    #         plt.savefig(data_destination / "statistical" / "scatter-plots" / f"{paws_name}" / f"{variable}" / f"{paws_name}_{variable}_scatter-plot.png")

    #         plt.clf()
    #         plt.close()


    """
    =============================================================================================================================
    Create scatter plots for each 3D PAWS sensor compared to other 3D PAWS sensors (temp only). COMPLETE RECORDS
    ----> currently broke, skipping due to time constraints
    =============================================================================================================================
    """
    # print(f"{paws_name}: " \
    #                     "Scatter plots for temperature -- complete records\n3D PAWS vs 3DPAWS")

    # merged_bmp_vs_htu = pd.merge(
    #     paws_df_FILTERED[['date', "bmp2_temp"]],
    #     paws_df_FILTERED[['date', 'htu_temp']],
    #     on='date',
    #     how='inner'
    # )
    # merged_bmp_vs_mcp = pd.merge(
    #     paws_df_FILTERED[['date', "bmp2_temp"]],
    #     paws_df_FILTERED[['date', 'mcp9808']],
    #     on='date',
    #     how='inner'
    # )
    # merged_htu_vs_mcp = pd.merge(
    #     paws_df_FILTERED[['date', "htu_temp"]],
    #     paws_df_FILTERED[['date', 'mcp9808']],
    #     on='date',
    #     how='inner'
    # )

    # plt.figure(figsize=(20, 12))

    # plt.scatter(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"], alpha=0.5, s=10)

    # m, b = np.polyfit(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"], 1)
    # plt.plot(merged_bmp_vs_htu["htu_temp"], m*merged_bmp_vs_htu["htu_temp"] + b, color='red', linewidth=2, label='Trend line')

    # corr_coef, _ = pearsonr(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"])
    # plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    # rmse = np.sqrt(mean_squared_error(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"]))
    # textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    # bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    # plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #         verticalalignment='top', bbox=bbox_props)

    # plt.title(f'{paws_name} -- 3D PAWS bmp2_temp versus 3D PAWS htu_temp')
    # plt.xlabel('3D PAWS bmp2_temp')
    # plt.ylabel('3D PAWS htu_temp')    

    # plt.legend()
    # plt.grid(True)
    # plt.tight_layout()  

    # plt.savefig(data_destination+station_directories[i]+f"temperature\\{paws_name}_bmp_vs_htu_scatter.png")    

    # plt.clf()
    # plt.close()  



    # plt.figure(figsize=(20, 12))

    # plt.scatter(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"], alpha=0.5, s=10)

    # m, b = np.polyfit(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"], 1)
    # plt.plot(merged_bmp_vs_mcp["bmp2_temp"], m*merged_bmp_vs_mcp["bmp2_temp"] + b, color='red', linewidth=2, label='Trend line')

    # corr_coef, _ = pearsonr(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"])
    # plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    # rmse = np.sqrt(mean_squared_error(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"]))
    # textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    # bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    # plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #         verticalalignment='top', bbox=bbox_props)

    # plt.title(f'{paws_name} -- 3D PAWS bmp2_temp versus 3D PAWS mcp9808')
    # plt.xlabel('3D PAWS bmp2_temp')
    # plt.ylabel('3D PAWS mcp9808')    

    # plt.legend()
    # plt.grid(True)
    # plt.tight_layout()  

    # plt.savefig(data_destination+station_directories[i]+f"temperature\\{paws_name}_bmp_vs_mcp9808_scatter.png")    

    # plt.clf()
    # plt.close()  



    # plt.figure(figsize=(20, 12))

    # plt.scatter(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"], alpha=0.5, s=10)

    # m, b = np.polyfit(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"], 1)
    # plt.plot(merged_htu_vs_mcp["mcp9808"], m*merged_htu_vs_mcp["mcp9808"] + b, color='red', linewidth=2, label='Trend line')

    # corr_coef, _ = pearsonr(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"])
    # plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    # rmse = np.sqrt(mean_squared_error(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"]))
    # textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    # bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    # plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #         verticalalignment='top', bbox=bbox_props)

    # plt.title(f'{paws_name} -- 3D PAWS mcp9808 versus 3D PAWS htu_temp')
    # plt.xlabel('3D PAWS mcp9808')
    # plt.ylabel('3D PAWS htu_temp')    

    # plt.legend()
    # plt.grid(True)
    # plt.tight_layout()  

    # plt.savefig(data_destination+station_directories[i]+f"temperature\\{paws_name}_mcp9808_vs_htu_scatter.png")    

    # plt.clf()
    # plt.close()  


    """
    =============================================================================================================================
    Creating box plots for temperature, relative humidity, pressure, wind speed, and rain. COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{paws_name} Box Plots")

    # paws_temp_cols = ['bmp2_temp', 'htu_temp', 'mcp9808']
    # paws_hum_cols = ['htu_hum']
    # paws_pres_cols = ['bmp2_pres']
    # paws_wind_cols = ['wind_speed']
    # paws_rain_cols = ['tipping']
    # tsms_temp_cols = ['temperature']
    # tsms_hum_cols = ['humidity']
    # tsms_pres_cols = ['actual_pressure']
    # tsms_wind_cols = ['avg_wind_speed']
    # tsms_rain_cols = ['total_rainfall']

    # with warnings.catch_warnings():
    #     warnings.simplefilter("ignore", category=FutureWarning)

    #     combined_df = paws_df_FILTERED.merge(
    #         tsms_df_FILTERED[tsms_temp_cols + tsms_hum_cols + tsms_pres_cols + tsms_wind_cols + tsms_rain_cols], 
    #         left_index=True, right_index=True
    #     )
    #     combined_temp_df = combined_df[paws_temp_cols + ['temperature']]
    #     combined_hum_df = combined_df[paws_hum_cols + ['humidity']]
    #     combined_pres_df = combined_df[paws_pres_cols + ['actual_pressure']]
    #     combined_wind_df = combined_df[paws_wind_cols + ['avg_wind_speed']]
    #     combined_rain_df = combined_df[paws_rain_cols + ['total_rainfall']]

    #     # temperature box plot
    #     plt.figure(figsize=(12, 12))
    #     sns.boxplot(data=combined_temp_df, palette=['blue', 'orange', 'green', 'red'])

    #     plt.title(f'{paws_name} Temperature Box Plot: 3D-PAWS & TSMS')
    #     plt.xlabel('Temperature Sensors')
    #     plt.ylabel('Temperature (°C)')
    #     plt.xticks([0, 1, 2, 3], ['BMP2 Temp', 'HTU Temp', 'MCP9808 Temp', 'TSMS Reference Temp'])
    #     plt.grid(True)

    #     plt.tight_layout()
    #     plt.savefig(data_destination / "statistical" / "box-plots" / f"{paws_name}" / "temperature" / f"{paws_name}_box-plot.png")
    #     plt.clf()
    #     plt.close()

    #     # humidity boxplot
    #     plt.figure(figsize=(12, 12))
    #     sns.boxplot(data=combined_hum_df, palette=['blue', 'red'])

    #     plt.title(f'{paws_name} Humidity Box Plot: 3D-PAWS & TSMS')
    #     plt.xlabel('Humidity Sensors')
    #     plt.ylabel('Humidity (%)')
    #     plt.xticks([0, 1], ['HTU Hum', 'TSMS Reference Hum'])
    #     plt.grid(True)

    #     plt.tight_layout()
    #     plt.savefig(data_destination / "statistical" / "box-plots" / f"{paws_name}" / "humidity" / f"{paws_name}_box-plot.png")
    #     plt.clf()
    #     plt.close()

    #     # pressure box plots
    #     plt.figure(figsize=(12, 12))
    #     sns.boxplot(data=combined_pres_df, palette=['blue', 'red'])

    #     plt.title(f'{paws_name} Pressure Box Plot: 3D-PAWS & TSMS')
    #     plt.xlabel('Pressure Sensors')
    #     plt.ylabel('Station Pressure (hPa)')
    #     plt.xticks([0, 1], ['BMP2 Pressure', 'TSMS Reference Pressure'])
    #     plt.grid(True)

    #     plt.tight_layout()
    #     plt.savefig(data_destination / "statistical" / "box-plots" / f"{paws_name}" / "actual_pressure" / f"{paws_name}_box-plot.png")
    #     plt.clf()
    #     plt.close()

    #     # # wind speed box plots -- not relevant
    #     # plt.figure(figsize=(12, 12))
    #     # sns.boxplot(data=combined_pres_df, palette=['blue', 'red'])

    #     # plt.title(f'{paws_name} Wind Speed Box Plot: 3D-PAWS & TSMS')
    #     # plt.xlabel('Anemometers')
    #     # plt.ylabel('Wind Speed (m/s)')
    #     # plt.xticks([0, 1], ['3D-PAWS Anemometer', 'TSMS Reference Anemometer'])
    #     # plt.grid(True)

    #     # plt.tight_layout()
    #     # plt.savefig(data_destination / "statistical" / "box-plots" / f"{paws_name}" / "wind" / f"{paws_name}_box-plot.png")
    #     # plt.clf()
    #     # plt.close()

    #     # # precipitation box plots -- not relevant
    #     # plt.figure(figsize=(12, 12))
    #     # sns.boxplot(data=combined_pres_df, palette=['blue', 'red'])

    #     # plt.title(f'{paws_name} Precipitation Box Plot: 3D-PAWS & TSMS')
    #     # plt.xlabel('Precipitation Sensors')
    #     # plt.ylabel('Total Rainfall (mm)')
    #     # plt.xticks([0, 1], ['3D-PAWS Tipping Bucket', 'TSMS Reference Gauge'])
    #     # plt.grid(True)

    #     # plt.tight_layout()
    #     # plt.savefig(data_destination / "statistical" / "box-plots" / f"{paws_name}" / "rainfall" / f"{paws_name}_box-plot.png")
    #     # plt.clf()
    #     # plt.close()


    """
    =============================================================================================================================
    Violin plots for temperature, humidity, and pressure. COMPLETE RECORDS
    * this style of plot is uninformative for wind speed and precip
    =============================================================================================================================
    """
    # print(f"{paws_name} Violin Plots")

    # y_axis_labels = {
    #     'temperature': 'Temperature (˚C)',
    #     'humidity': 'Relative Humidity (%)',
    #     'actual_pressure': 'Pressure (hPa)'
    # }

    # # Drop 'level_0' if it exists to prevent duplicates
    # if 'level_0' in paws_df_FILTERED.columns:
    #     paws_df_FILTERED = paws_df_FILTERED.drop(columns=['level_0'])
    # if 'level_0' in tsms_df_FILTERED.columns:
    #     tsms_df_FILTERED = tsms_df_FILTERED.drop(columns=['level_0'])

    # # Reset once outside loop
    # paws_for_plots = paws_df_FILTERED.reset_index().copy()
    # tsms_for_plots = tsms_df_FILTERED.reset_index().copy()

    # for var in station_variables:
    #     if var in ['sea_level_pressure', 'wind', 'total_rainfall']:
    #         continue

    #     for v in variable_mapper[var]:
    #         if v in ['bme2_hum']:
    #             continue

    #         x_axis_labels = {
    #             v: f'3D-PAWS ({v})',
    #             var: 'TSMS Reference Sensor'
    #         }
    #         custom_palette = {
    #             x_axis_labels[v]: "#1f77b4",        # Blue
    #             "TSMS Reference Sensor": "#d62728"  # Red
    #         }

    #         merged_df = pd.merge(
    #             paws_for_plots[['date', v]], 
    #             tsms_for_plots[['date', var]], 
    #             on='date', 
    #             suffixes=['_paws', '_tsms']
    #         )

    #         long_df = pd.melt(  # Seaborn expects data in long format
    #             merged_df,
    #             id_vars='date',
    #             value_vars=[v, var],
    #             var_name='Source',
    #             value_name='Value'
    #         )
    #         long_df['Source'] = long_df['Source'].map(x_axis_labels)

    #         plt.figure(figsize=(12, 12))
    #         sns.violinplot(x='Source', y='Value', data=long_df, palette=custom_palette, inner='box')
    #         plt.title(f"{paws_name} Violin Plot of {var[0].upper() + var[1:]}: 3D PAWS ({v}) vs TSMS Reference Sensor")
    #         plt.ylabel(y_axis_labels[var])
    #         plt.tight_layout()
    #         plt.savefig(
    #             data_destination / "statistical" / "violin-plots" / f"{paws_name}" / f"{var}" / f"{paws_name}_{v}_violin-plot.png"
    #         )
    #         plt.clf()
    #         plt.close()

    # # print(f"{paws_name} Violin Plots")

    # # y_axis_labels = {
    # #     'temperature': 'Temperature (˚C)',
    # #     'humidity': 'Relative Humidity (%)',
    # #     'actual_pressure': 'Pressure (hPa)'
    # # }

    # # # Reset ONCE before the loops
    # # paws_for_plots = paws_df_FILTERED.reset_index().copy()
    # # tsms_for_plots = tsms_df_FILTERED.reset_index().copy()

    # # for var in station_variables:
    # #     if var in ['sea_level_pressure', 'wind', 'total_rainfall']: continue

    # #     for v in variable_mapper[var]:
    # #         if v in ['bme2_hum']: continue

    # #         x_axis_labels = {
    # #             v: f'3D-PAWS ({v})',
    # #             var: 'TSMS Reference Sensor'
    # #         }
    # #         custom_palette = {
    # #             x_axis_labels[v]: "#1f77b4",        # Blue
    # #             "TSMS Reference Sensor": "#d62728"  # Red
    # #         }
        

    # #         # # Then in your loops:
    # #         # for var in station_variables:
    # #         #     if var in ['sealevel_pressure', 'wind', 'total_rainfall']: continue
    # #         #     for v in variable_mapper[var]:
    # #         #         if v in ['bme2_hum']: continue
    # #         #         merged_df = pd.merge(
    # #         #             paws_for_plots[['date', v]], 
    # #         #             tsms_for_plots[['date', var]], 
    # #         #             on='date', suffixes=('_paws', '_tsms')
    # #         #        )

    # #         merged_df = pd.merge(
    # #             paws_df_FILTERED.reset_index()[['date', v]], 
    # #             tsms_df_FILTERED.reset_index()[['date' ,var]],
    # #             on='date', 
    # #             suffixes=['_paws', '_tsms']
    # #         )
        
    # #         long_df = pd.melt(  # Seaborn wants data in long format
    # #             merged_df,
    # #             id_vars='date',
    # #             value_vars=[f'{v}', f'{var}'],
    # #             var_name='Source',
    # #             value_name='Value'
    # #         )
    # #         long_df['Source'] = long_df['Source'].map(x_axis_labels)

    # #         plt.figure(figsize=(12, 12))
    # #         sns.violinplot(x='Source', y='Value', data=long_df, palette=custom_palette, inner='box')
    # #         plt.title(f"{paws_name} Violin Plot of {var[0].upper()+var[1:]}: 3D PAWS ({v}) vs TSMS Reference Sensor")
    # #         plt.ylabel(y_axis_labels[var])
    # #         plt.tight_layout()
    # #         plt.savefig(data_destination / "statistical" / "violin-plots" / f"{paws_name}" / f"{var}" / f"{paws_name}_{v}_violin-plot.png")
    # #         plt.clf()
    # #         plt.close()


    """
    =============================================================================================================================
    Creating histograms for each variable. COMPLETE RECORDS
    =============================================================================================================================
    """
#     print(f"{paws_name} Histograms")

#     for variable in variable_mapper.keys():
#         if variable in ['sea_level_pressure', 'total_rainfall']: continue

#         for var in variable_mapper[variable]:
#             if var in ['bme2_hum']: continue

#             merged_df = pd.merge(
#                 paws_df_FILTERED.reset_index()[['date', var]], 
#                 tsms_df_FILTERED.reset_index()[['date' ,variable]],
#                 on='date', 
#                 suffixes=['_paws', '_tsms']
#             )

#             cleaned_df = merged_df.dropna(subset=[var, variable])

#             plt.figure(figsize=(12,12))
#             plt.hist(cleaned_df[var], bins=15, edgecolor='black')
#             plt.xlabel(variable[0].upper() + variable[1:])
#             plt.ylabel("Frequency")
#             plt.title(f"3D-PAWS {variable[0].upper()+variable[1:]} ({var})")
#             plt.tight_layout()
#             if variable in ['avg_wind_speed', 'avg_wind_dir']: 
#                 plt.savefig(data_destination / "statistical" / "histograms" / f"{paws_name}" / "wind" / f"{paws_name}_{variable}_histogram.png")
#             else:
#                 plt.savefig(data_destination / "statistical" / "histograms" / f"{paws_name}" / f"{variable}" / f"{paws_name}_{var}_histogram.png")
#             plt.clf()
#             plt.close()

#             plt.figure(figsize=(12,12))
#             plt.hist(cleaned_df[variable], bins=15, edgecolor='black', color='indianred')
#             plt.xlabel(variable[0].upper()+variable[1:])
#             plt.ylabel("Frequency")
#             plt.title(f"TSMS {variable[0].upper()+variable[1:]}")
#             plt.tight_layout()
#             if variable in ['avg_wind_speed', 'avg_wind_dir']:
#                 if paws_name in ['3DPAWS-TSMS00', '3DPAWS-TSMS01', '3DPAWS-TSMS02']:
#                     plt.savefig(data_destination / "statistical" / "histograms" / f"{paws_name}" / "wind" / f"TSMS-Ankara_{variable}_histogram.png")
#                 elif paws_name in ['3DPAWS-TSMS03', '3DPAWS-TSMS04', '3DPAWS-TSMS05']:
#                     plt.savefig(data_destination / "statistical" / "histograms" / f"{paws_name}" / "wind" / f"TSMS-Konya_{variable}_histogram.png")
#                 else:
#                     plt.savefig(data_destination / "statistical" / "histograms" / f"{paws_name}" / "wind" / f"TSMS-Adana_{variable}_histogram.png")
#             else:
#                 if paws_name in ['3DPAWS-TSMS00', '3DPAWS-TSMS01', '3DPAWS-TSMS02']:
#                     plt.savefig(data_destination / "statistical" / "histograms" / f"{paws_name}" / f"{variable}" /  f"TSMS-Ankara_histogram.png")
#                 elif paws_name in ['3DPAWS-TSMS03', '3DPAWS-TSMS04', '3DPAWS-TSMS05']:
#                     plt.savefig(data_destination / "statistical" / "histograms" / f"{paws_name}" / f"{variable}" /  f"TSMS-Konya_histogram.png")
#                 else:
#                     plt.savefig(data_destination / "statistical" / "histograms" / f"{paws_name}" / f"{variable}" /  f"TSMS-Adana_histogram.png")
#             plt.clf()
#             plt.close()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    paws_dfs.append(paws_df_FILTERED)
    tsms_dfs.append(tsms_df_FILTERED)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


"""
=============================================================================================================================
Site-wide comparison of each type of temperature sensor versus the reference. MONTHLY RECORDS
=============================================================================================================================
"""
# print("Temperature comparison (this will take some time)")
# sites = {
#     0:"Ankara", 1:"Konya", 2:"Adana"
# }
# station_map = {
#     0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
# }

# for i in range(3):
#     print(f"\t{sites[i]}: Temperature Comparison per sensor per site")

#     inst_1 = paws_dfs[station_map[i][0]].copy(deep=True)
#     inst_2 = paws_dfs[station_map[i][1]].copy(deep=True)
#     inst_3 = paws_dfs[station_map[i][2]].copy(deep=True)
#     tsms_ref = tsms_dfs[i*3].copy(deep=True)

#     inst_1.reset_index(inplace=True)
#     inst_2.reset_index(inplace=True)
#     inst_3.reset_index(inplace=True)
#     tsms_ref.reset_index(inplace=True)

#     for year_month in set(inst_1['year_month']) & \
#                         set(inst_2['year_month']) & \
#                             set(inst_3['year_month']) & \
#                                 set(tsms_ref['year_month']):
#         inst_1_grouped = inst_1[inst_1['year_month'] == year_month]
#         inst_2_grouped = inst_2[inst_2['year_month'] == year_month]
#         inst_3_grouped = inst_3[inst_3['year_month'] == year_month]
#         tsms_grouped = tsms_ref[tsms_ref['year_month'] == year_month]

#         merged_df = pd.merge(inst_1_grouped, inst_2_grouped, on='date', suffixes=('_1', '_2'))
#         merged_df = pd.merge(merged_df, inst_3_grouped, on='date', suffixes=('', '_3'))
#         merged_df = pd.merge(merged_df, tsms_grouped, on='date', suffixes=('', '_tsms'))

#         for sensor in variable_mapper['temperature']:
#             plt.figure(figsize=(20, 12))

#             plt.plot(merged_df['date'], merged_df[f'{sensor}_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} {sensor}")
#             plt.plot(merged_df['date'], merged_df[f'{sensor}_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} {sensor}")
#             plt.plot(merged_df['date'], merged_df[f'{sensor}'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} {sensor}")
#             plt.plot(merged_df['date'], merged_df[f'temperature'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

#             plt.title(f'{sites[i]} {year_month}: {sensor} Temperature Comparison')
#             plt.xlabel('Date')
#             plt.ylabel('Temperature (˚C)')
#             plt.xticks(rotation=45)

#             plt.legend()

#             plt.grid(True)
#             plt.tight_layout()

#             plt.savefig(data_destination / "time-series" / f"{sites[i]}" / "temperature" / "trends" / f"{sites[i]}_{sensor}_{year_month}_temp_comparison.png")

#             plt.clf()
#             plt.close()


"""
=============================================================================================================================
Site-wide comparison of each type of humidity sensor versus the reference. MONTHLY RECORDS
=============================================================================================================================
"""
# print("Humidity comparison (this will take some time)")
# sites = {
#     0:"Ankara", 1:"Konya", 2:"Adana"
# }
# station_map = {
#     0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
# }

# for i in range(3):
#     print(f"\t{sites[i]}: Humidity Comparison per sensor per site")

#     inst_1 = paws_dfs[station_map[i][0]].copy(deep=True)
#     inst_2 = paws_dfs[station_map[i][1]].copy(deep=True)
#     inst_3 = paws_dfs[station_map[i][2]].copy(deep=True)
#     tsms_ref = tsms_dfs[i*3].copy(deep=True)

#     inst_1.reset_index(inplace=True)
#     inst_2.reset_index(inplace=True)
#     inst_3.reset_index(inplace=True)
#     tsms_ref.reset_index(inplace=True)

#     for year_month in set(inst_1['year_month']) & \
#                         set(inst_2['year_month']) & \
#                             set(inst_3['year_month']) & \
#                                 set(tsms_ref['year_month']):
#         inst_1_grouped = inst_1[inst_1['year_month'] == year_month]
#         inst_2_grouped = inst_2[inst_2['year_month'] == year_month]
#         inst_3_grouped = inst_3[inst_3['year_month'] == year_month]
#         tsms_grouped = tsms_ref[tsms_ref['year_month'] == year_month]

#         merged_df = pd.merge(inst_1_grouped, inst_2_grouped, on='date', suffixes=('_1', '_2'))
#         merged_df = pd.merge(merged_df, inst_3_grouped, on='date', suffixes=('', '_3'))
#         merged_df = pd.merge(merged_df, tsms_grouped, on='date', suffixes=('', '_tsms'))

#         for sensor in variable_mapper['humidity']:
#             if sensor == 'bme2_hum': continue

#             plt.figure(figsize=(20, 12))

#             plt.plot(merged_df['date'], merged_df[f'{sensor}_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} {sensor}")
#             plt.plot(merged_df['date'], merged_df[f'{sensor}_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} {sensor}")
#             plt.plot(merged_df['date'], merged_df[f'{sensor}'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} {sensor}")
#             plt.plot(merged_df['date'], merged_df[f'humidity'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

#             plt.title(f'{sites[i]} {year_month}: {sensor} Relative Humidity Comparison')
#             plt.xlabel('Date')
#             plt.ylabel('Relative Humidity (%)')
#             plt.xticks(rotation=45)

#             plt.legend()

#             plt.grid(True)
#             plt.tight_layout()

#             plt.savefig(data_destination / "time-series" / f"{sites[i]}" / "humidity" / "trends" / f"{sites[i]}_{sensor}_{year_month}_humidity_comparison.png")

#             plt.clf()
#             plt.close()


"""
=============================================================================================================================
Site-wide comparison of each type of pressure sensor versus the reference. MONTHLY RECORDS
=============================================================================================================================
"""
# sites = {
#     0:"Ankara", 1:"Konya", 2:"Adana"
# }
# station_map = {
#     0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
# }

# for i in range(3):
#     print(f"\t{sites[i]}: Actual & sea level pressure per site.")

#     inst_1 = paws_dfs[station_map[i][0]].copy(deep=True)
#     inst_2 = paws_dfs[station_map[i][1]].copy(deep=True)
#     inst_3 = paws_dfs[station_map[i][2]].copy(deep=True)
#     tsms_ref = tsms_dfs[i*3].copy(deep=True)

#     inst_1.reset_index(inplace=True)
#     inst_2.reset_index(inplace=True)
#     inst_3.reset_index(inplace=True)
#     tsms_ref.reset_index(inplace=True)

#     for year_month in set(inst_1['year_month']) & \
#                         set(inst_2['year_month']) & \
#                             set(inst_3['year_month']) & \
#                                 set(tsms_ref['year_month']):
#         inst_1_grouped = inst_1[inst_1['year_month'] == year_month]
#         inst_2_grouped = inst_2[inst_2['year_month'] == year_month]
#         inst_3_grouped = inst_3[inst_3['year_month'] == year_month]
#         tsms_grouped = tsms_ref[tsms_ref['year_month'] == year_month]

#         merged_df = pd.merge(inst_1_grouped, inst_2_grouped, on='date', suffixes=('_1', '_2'))
#         merged_df = pd.merge(merged_df, inst_3_grouped, on='date', suffixes=('', '_3'))
#         merged_df = pd.merge(merged_df, tsms_grouped, on='date', suffixes=('', '_tsms'))

#         plt.figure(figsize=(20, 12))

#         plt.plot(merged_df['date'], merged_df['bmp2_pres_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} 3D PAWS")
#         plt.plot(merged_df['date'], merged_df['bmp2_pres_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} 3D PAWS")
#         plt.plot(merged_df['date'], merged_df['bmp2_pres'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} 3D PAWS")
#         plt.plot(merged_df['date'], merged_df['actual_pressure'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

#         plt.title(f'{sites[i]} {year_month} Station Pressure')
#         plt.xlabel('Date')
#         plt.ylabel('Pressure (hPa)')
#         plt.xticks(rotation=45)

#         plt.legend()

#         plt.grid(True)
#         plt.tight_layout()

#         plt.savefig(data_destination / "time-series" / f"{sites[i]}" / "actual_pressure" / "trends" / f"{sites[i]}_{year_month}_pressure_comparison.png")

#         plt.clf()
#         plt.close()

#         # # We don't care about sea level pressure
#         # print("\t\tSea Level Pressure")
#         # print(f"\t\t\t{sites[i]} at {year_month}")

#         # plt.figure(figsize=(20, 12))

#         # plt.plot(merged_df['date'], merged_df['bmp2_slp_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} 3D PAWS")
#         # plt.plot(merged_df['date'], merged_df['bmp2_slp_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} 3D PAWS")
#         # plt.plot(merged_df['date'], merged_df['bmp2_slp'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} 3D PAWS")
#         # plt.plot(merged_df['date'], merged_df['sea_level_pressure'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

#         # plt.title(f'{sites[i]} {year_month} Sea Level Pressure')
#         # plt.xlabel('Date')
#         # plt.ylabel('Sea Level Pressure (hPa)')
#         # plt.xticks(rotation=45)

#         # plt.legend()

#         # plt.grid(True)
#         # plt.tight_layout()

#         # #plt.savefig(data_destination+station_directories[i]+f"total_rainfall/raw/{paws_name}_rainfall_accumulation_TEST.png")
#         # #plt.savefig(data_destination+sites[i]+f"\\sea_level_pressure\\{sites[i]}_{year_month}_station_sea_level_pressure.png")
#         # plt.savefig(data_destination / "time-series" / f"{sites[i]}" / "sea_level_pressure" / f"{sites[i]}_{year_month}_pressure_comparison.png")

#         # plt.clf()
#         # plt.close()


"""
=============================================================================================================================
Rainfall accumulation time series of each individual 3D PAWS station data versus the TSMS reference station. COMPLETE RECORDS
=============================================================================================================================
"""
# sites = {
#     0:"Ankara", 1:"Konya", 2:"Adana"
# }
# station_map = {
#     0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
# }

# for i in range(3):
#     print(f"\t{sites[i]}: Rainfall accumulation per site")

#     inst_1 = paws_dfs[station_map[i][0]].copy(deep=True)
#     inst_2 = paws_dfs[station_map[i][1]].copy(deep=True)
#     inst_3 = paws_dfs[station_map[i][2]].copy(deep=True)
#     tsms_ref = tsms_dfs[i*3].copy(deep=True)

#     inst_1.reset_index(inplace=True)
#     inst_2.reset_index(inplace=True)
#     inst_3.reset_index(inplace=True)
#     tsms_ref.reset_index(inplace=True)

#     merged_df = pd.merge(inst_1, inst_2, on='date', suffixes=('_1', '_2'))
#     merged_df = pd.merge(merged_df, inst_3, on='date', suffixes=('', '_3'))
#     merged_df = pd.merge(merged_df, tsms_ref, on='date', suffixes=('', '_tsms'))

#     merged_df['cumulative_rainfall_3DPAWS_1'] = merged_df['tipping_1'].cumsum()
#     merged_df['cumulative_rainfall_3DPAWS_2'] = merged_df['tipping_2'].cumsum()
#     merged_df['cumulative_rainfall_3DPAWS_3'] = merged_df['tipping'].cumsum()
#     merged_df['cumulative_rainfall_TSMS'] = merged_df['total_rainfall'].cumsum()

#     plt.figure(figsize=(20, 12))

#     plt.plot(merged_df['date'], merged_df['cumulative_rainfall_3DPAWS_1'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} 3D PAWS")
#     plt.plot(merged_df['date'], merged_df['cumulative_rainfall_3DPAWS_2'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} 3D PAWS")
#     plt.plot(merged_df['date'], merged_df['cumulative_rainfall_3DPAWS_3'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} 3D PAWS")
#     plt.plot(merged_df['date'], merged_df['cumulative_rainfall_TSMS'], marker='.', markersize=1, label=f'{sites[i]} TSMS Reference')

#     plt.title(f'{sites[i]} Rainfall Accumulation')
#     plt.xlabel('Date')
#     plt.ylabel('Rainfall (mm)')
#     plt.xticks(rotation=45)

#     plt.legend()

#     plt.grid(True)
#     plt.tight_layout()

#     plt.savefig(data_destination / "time-series" / f"{sites[i]}" / "total_rainfall" / "trends" / f"{sites[i]}_rainfall_accumulation.png")

#     plt.clf()
#     plt.close()


"""
=============================================================================================================================
Create bar charts for daily 3D PAWS rainfall accumulation (per site) compared to TSMS rainfall accumulation. MONTHLY RECORDS
=============================================================================================================================
"""
# sites = {
#     0:"Ankara", 1:"Konya", 2:"Adana"
# }
# station_map = {
#     0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
# }

# for i in range(3):
#     print(f"{sites[i]}: Bar charts for rainfall accumulation -- daily totals [ALL INSTRUMENTS PER SITE]")

#     inst_1 = paws_dfs[station_map[i][0]].copy(deep=True)
#     inst_2 = paws_dfs[station_map[i][1]].copy(deep=True)
#     inst_3 = paws_dfs[station_map[i][2]].copy(deep=True)
#     tsms_ref = tsms_dfs[i*3].copy(deep=True)

#     inst_1.reset_index(inplace=True)
#     inst_2.reset_index(inplace=True)
#     inst_3.reset_index(inplace=True)
#     tsms_ref.reset_index(inplace=True)
        
#     for year_month in set(inst_1['year_month']) & \
#                         set(inst_2['year_month']) & \
#                             set(inst_3['year_month']) & \
#                                 set(tsms_ref['year_month']):
#         inst_1_grouped = inst_1[inst_1['year_month'] == year_month]
#         inst_2_grouped = inst_2[inst_2['year_month'] == year_month]
#         inst_3_grouped = inst_3[inst_3['year_month'] == year_month]
#         tsms_grouped = tsms_ref[tsms_ref['year_month'] == year_month]

#         merged_df = pd.merge(inst_1_grouped, inst_2_grouped, on='date', suffixes=('_1', '_2'))
#         merged_df = pd.merge(merged_df, inst_3_grouped, on='date', suffixes=('', '_3'))
#         merged_df = pd.merge(merged_df, tsms_grouped, on='date', suffixes=('', '_tsms'))

#         merged_df['daily_rainfall_1'] = merged_df['tipping_1']    # Calculate daily rainfall totals
#         merged_df['daily_rainfall_2'] = merged_df['tipping_2']
#         merged_df['daily_rainfall_3'] = merged_df['tipping']
#         merged_df['daily_rainfall_TSMS'] = merged_df['total_rainfall']
        
#         daily_totals = merged_df.groupby('year_month_day')[     # Sum daily rainfall by date
#             ['daily_rainfall_1', 'daily_rainfall_2', 'daily_rainfall_3', 'daily_rainfall_TSMS']
#         ].sum().reset_index()

#         days = daily_totals['year_month_day'].dt.day
#         values_1 = daily_totals['daily_rainfall_1']
#         values_2 = daily_totals['daily_rainfall_2']
#         values_3 = daily_totals['daily_rainfall_3']
#         values_tsms = daily_totals['daily_rainfall_TSMS']

#         index = range(len(days))

#         plt.figure(figsize=(20, 12), constrained_layout=True)

#         bar_width = 0.2
#         bars1 = plt.bar(index, values_1, width=bar_width, color='blue', label=f'3DPAWS TSMS0{station_map[i][0]}')
#         bars2 = plt.bar([i + bar_width for i in index], values_2, width=bar_width, color='orange', label=f'3DPAWS TSMS0{station_map[i][1]}')
#         bars3 = plt.bar([i + 2*bar_width for i in index], values_3, width=bar_width, color='green', label=f'3DPAWS TSMS0{station_map[i][2]}')
#         bars4 = plt.bar([i + 3*bar_width for i in index], values_tsms, width=bar_width, color='red', label='TSMS Reference')
        
#         plt.xlabel(f'Day in {year_month}', fontsize=8)          # Add labels, title, and legend
#         plt.ylabel('Daily Rainfall (mm)', fontsize=8)
#         plt.title(f'{sites[i]} Daily Rainfall Comparison: All Instruments for {year_month}', fontsize=8)
#         plt.xticks([i + 1.5*bar_width for i in index], days, rotation=45)
#         plt.ylim(0, 50)
#         plt.legend()

#         for bars in [bars1, bars2, bars3, bars4]:               # Add numerical values above bars
#             for bar in bars:
#                 yval = bar.get_height()
#                 plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 1), ha='center', va='bottom', fontsize=8)
   
#         plt.savefig(data_destination / "bar-charts" / f"{sites[i]}" / f"{sites[i]} _{year_month}_daily_rainfall_all_instruments.png")
        
#         plt.clf()
#         plt.close()

    
"""
=============================================================================================================================
Create bar charts for daily 3D PAWS rainfall accumulation (per site) compared to TSMS rainfall accumulation. COMPLETE RECORDS
=============================================================================================================================
"""
# sites = {
#     0:"Ankara", 1:"Konya", 2:"Adana"
# }
# station_map = {
#     0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
# }

# for i in range(3):
#     print(f"{sites[i]}: Bar charts for rainfall accumulation -- monthly totals [ALL INSTRUMENTS PER SITE]")

#     inst_1 = paws_dfs[station_map[i][0]].copy(deep=True)
#     inst_2 = paws_dfs[station_map[i][1]].copy(deep=True)
#     inst_3 = paws_dfs[station_map[i][2]].copy(deep=True)
#     tsms_ref = tsms_dfs[i*3].copy(deep=True)

#     inst_1.reset_index(inplace=True)
#     inst_2.reset_index(inplace=True)
#     inst_3.reset_index(inplace=True)
#     tsms_ref.reset_index(inplace=True)

#     merged_df = pd.merge(inst_1, inst_2, on='date', suffixes=('_1', '_2'))
#     merged_df = pd.merge(merged_df, inst_3, on='date', suffixes=('', '_3'))
#     merged_df = pd.merge(merged_df, tsms_ref, on='date', suffixes=('', '_tsms'))

#     merged_df['monthly_rainfall_1'] = merged_df['tipping_1']
#     merged_df['monthly_rainfall_2'] = merged_df['tipping_2']
#     merged_df['monthly_rainfall_3'] = merged_df['tipping']
#     merged_df['monthly_rainfall_TSMS'] = merged_df['total_rainfall']

#     monthly_totals = merged_df.groupby('year_month')[
#         ['monthly_rainfall_1', 'monthly_rainfall_2', 'monthly_rainfall_3', 'monthly_rainfall_TSMS']
#     ].sum().reset_index()

#     months = monthly_totals['year_month']
#     values_1 = monthly_totals['monthly_rainfall_1']
#     values_2 = monthly_totals['monthly_rainfall_2']
#     values_3 = monthly_totals['monthly_rainfall_3']
#     values_tsms = monthly_totals['monthly_rainfall_TSMS']

#     index = range(len(months))

#     plt.figure(figsize=(20, 12), constrained_layout=True)

#     bar_width = 0.2
#     bars1 = plt.bar(index, values_1, width=bar_width, color='blue', label=f'3DPAWS TSMS0{station_map[i][0]}')
#     bars2 = plt.bar([i + bar_width for i in index], values_2, width=bar_width, color='orange', label=f'3DPAWS TSMS0{station_map[i][1]}')
#     bars3 = plt.bar([i + 2*bar_width for i in index], values_3, width=bar_width, color='green', label=f'3DPAWS TSMS0{station_map[i][2]}')
#     bars4 = plt.bar([i + 3*bar_width for i in index], values_tsms, width=bar_width, color='red', label='TSMS Reference')

#     plt.xlabel('Month', fontsize=8)
#     plt.ylabel('Monthly Rainfall (mm)', fontsize=8)
#     plt.title(f'{sites[i]} Monthly Rainfall Comparison: All Instruments', fontsize=10)
#     plt.xticks([i + 1.5*bar_width for i in index], months, rotation=45, ha='right')
#     plt.legend(fontsize='small')

#     for bars in [bars1, bars2, bars3, bars4]:
#         for bar in bars:
#             yval = bar.get_height()
#             plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 1), ha='center', va='bottom', fontsize=6)

#     plt.savefig(data_destination / "bar-charts" / f"{sites[i]}" / f"{sites[i]}_monthly_rainfall_all_instruments.png")
    
#     plt.clf()
#     plt.close()


"""
=============================================================================================================================
Create time series DIFFERENCE plots for pressure compared to TSMS at each site. COMPLETE RECORDS
Complete record with daily average difference
=============================================================================================================================
"""
# print("Pressure difference")

# sites = {
#     0:"Ankara", 1:"Konya", 2:"Adana"
# }
# station_map = {
#     0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
# }
# sht_upgrade = [ # the day the upgrade from HTU to SHT was performed
#     "2024-01-17", "2024-01-12", "2024-01-15"
# ] # same day that radiation shield sensor array updated

# for i in range(3):
#     print(f"\t{sites[i]}: Pressure Difference per Sensor")

#     inst_1 = paws_dfs[station_map[i][0]].copy(deep=True)
#     inst_2 = paws_dfs[station_map[i][1]].copy(deep=True)
#     inst_3 = paws_dfs[station_map[i][2]].copy(deep=True)
#     tsms_ref = tsms_dfs[i*3].copy(deep=True)

#     inst_1.reset_index(inplace=True)
#     inst_2.reset_index(inplace=True)
#     inst_3.reset_index(inplace=True)
#     tsms_ref.reset_index(inplace=True)

#     # Step 1: Calculate the daily mean difference for each temperature sensor from the reference.
#     daily_mean_diffs = []
#     for year_month_day in set(inst_1['year_month_day']) & \
#                         set(inst_2['year_month_day']) & \
#                             set(inst_3['year_month_day']) & \
#                                 set(tsms_ref['year_month_day']):    # not ordered when working w/ sets

#         inst_1_grouped = inst_1[inst_1['year_month_day'] == year_month_day]
#         inst_2_grouped = inst_2[inst_2['year_month_day'] == year_month_day]
#         inst_3_grouped = inst_3[inst_3['year_month_day'] == year_month_day]
#         tsms_grouped = tsms_ref[tsms_ref['year_month_day'] == year_month_day]

#         merged_df = pd.merge(inst_1_grouped, inst_2_grouped, on='date', suffixes=('_1', '_2'))
#         merged_df = pd.merge(merged_df, inst_3_grouped, on='date', suffixes=('', '_3'))
#         merged_df = pd.merge(merged_df, tsms_grouped, on='date', suffixes=('', '_tsms'))

#         for sensor in variable_mapper['actual_pressure']:
#             merged_df[f"{sensor}_1_diff"] = merged_df[f'{sensor}_1'] - merged_df['actual_pressure'] # 3D-PAWS instrument 1
#             merged_df[f"{sensor}_2_diff"] = merged_df[f'{sensor}_2'] - merged_df['actual_pressure'] # 3D-PAWS instrument 2
#             merged_df[f"{sensor}_diff"] = merged_df[f'{sensor}'] - merged_df['actual_pressure']     # 3D-PAWS instrument 3

#             daily_mean_diffs.append({
#                 'date':year_month_day,
#                 'sensor':sensor,
#                 f'TSMS{station_map[i][0]}_diff':merged_df[f"{sensor}_1_diff"].mean(),
#                 f'TSMS{station_map[i][1]}_diff':merged_df[f"{sensor}_2_diff"].mean(),
#                 f'TSMS{station_map[i][2]}_diff':merged_df[f"{sensor}_diff"].mean()
#             })

#     # Step 2: Plot average daily diff's for each sensor.
#     df = pd.DataFrame(daily_mean_diffs)
#     df['date'] = pd.to_datetime(df['date'].astype(str))

#     for sensor in variable_mapper['actual_pressure']:
#         this_sensor = df[df['sensor'] == sensor].sort_values('date')

#         plt.figure(figsize=(20, 12))

#         plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][0]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} {sensor}")
#         plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][1]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} {sensor}")
#         plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][2]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} {sensor}")

#         plt.title(f'{sites[i]}: {sensor} Pressure Difference from Reference')
#         plt.xlabel('Date')
#         plt.ylabel('Pressure Difference [Actual] (hPa)')
#         plt.ylim(-5, 5)
#         plt.axvline(pd.to_datetime(sht_upgrade[i]), color='red', linestyle='--', linewidth=2)
#         plt.xticks(rotation=45)

#         plt.legend()

#         plt.grid(True)
#         plt.tight_layout()

#         plt.savefig(data_destination / "time-series" / f"{sites[i]}" / "actual_pressure" / "differences" / f"{sites[i]}_actual_pressure_difference.png")

#         plt.clf()
#         plt.close()


"""
=============================================================================================================================
Create time series DIFFERENCE plots for each temperature sensor compared to TSMS at each site. COMPLETE RECORDS
Daily average difference
=============================================================================================================================
"""
# print("Temperature difference")

# sites = {
#     0:"Ankara", 1:"Konya", 2:"Adana"
# }
# station_map = {
#     0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
# }
# sht_upgrade = [ # the day the upgrade from HTU to SHT was performed
#     "2024-01-17", "2024-01-12", "2024-01-15"
# ] # same day that radiation shield sensor array updated

# for i in range(3):
#     print(f"\t{sites[i]}: Temperature Difference per Sensor")

#     inst_1 = paws_dfs[station_map[i][0]].copy(deep=True)
#     inst_2 = paws_dfs[station_map[i][1]].copy(deep=True)
#     inst_3 = paws_dfs[station_map[i][2]].copy(deep=True)
#     tsms_ref = tsms_dfs[i*3].copy(deep=True)

#     inst_1.reset_index(inplace=True)
#     inst_2.reset_index(inplace=True)
#     inst_3.reset_index(inplace=True)
#     tsms_ref.reset_index(inplace=True)

#     # Step 1: Calculate the daily mean difference for each temperature sensor from the reference.
#     daily_mean_diffs = []
#     for year_month_day in set(inst_1['year_month_day']) & \
#                         set(inst_2['year_month_day']) & \
#                             set(inst_3['year_month_day']) & \
#                                 set(tsms_ref['year_month_day']):    # not ordered when working w/ sets

#         inst_1_grouped = inst_1[inst_1['year_month_day'] == year_month_day]
#         inst_2_grouped = inst_2[inst_2['year_month_day'] == year_month_day]
#         inst_3_grouped = inst_3[inst_3['year_month_day'] == year_month_day]
#         tsms_grouped = tsms_ref[tsms_ref['year_month_day'] == year_month_day]

#         merged_df = pd.merge(inst_1_grouped, inst_2_grouped, on='date', suffixes=('_1', '_2'))
#         merged_df = pd.merge(merged_df, inst_3_grouped, on='date', suffixes=('', '_3'))
#         merged_df = pd.merge(merged_df, tsms_grouped, on='date', suffixes=('', '_tsms'))

#         for sensor in variable_mapper['temperature']:
#             merged_df[f"{sensor}_1_diff"] = merged_df[f'{sensor}_1'] - merged_df['temperature'] # 3D-PAWS instrument 1
#             merged_df[f"{sensor}_2_diff"] = merged_df[f'{sensor}_2'] - merged_df['temperature'] # 3D-PAWS instrument 2
#             merged_df[f"{sensor}_diff"] = merged_df[f'{sensor}'] - merged_df['temperature']     # 3D-PAWS instrument 3

#             daily_mean_diffs.append({
#                 'date':year_month_day,
#                 'sensor':sensor,
#                 f'TSMS{station_map[i][0]}_diff':merged_df[f"{sensor}_1_diff"].mean(),
#                 f'TSMS{station_map[i][1]}_diff':merged_df[f"{sensor}_2_diff"].mean(),
#                 f'TSMS{station_map[i][2]}_diff':merged_df[f"{sensor}_diff"].mean()
#             })

#     # Step 2: Plot average daily diff's for each sensor.
#     df = pd.DataFrame(daily_mean_diffs)
#     df['date'] = pd.to_datetime(df['date'].astype(str))

#     for sensor in variable_mapper['temperature']:
#         this_sensor = df[df['sensor'] == sensor].sort_values('date')

#         plt.figure(figsize=(20, 12))

#         plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][0]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} {sensor}")
#         plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][1]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} {sensor}")
#         plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][2]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} {sensor}")

#         plt.title(f'{sites[i]}: {sensor} Temperature Difference from Reference')
#         plt.xlabel('Date')
#         plt.ylabel('Temperature Difference (˚C)')
#         plt.ylim(-5, 5)
#         plt.axvline(pd.to_datetime(sht_upgrade[i]), color='red', linestyle='--', linewidth=2)
#         plt.xticks(rotation=45)

#         plt.legend()

#         plt.grid(True)
#         plt.tight_layout()

#         plt.savefig(data_destination / "time-series" / f"{sites[i]}" / "temperature" / "differences" / f"{sites[i]}_{sensor}_temperature_difference.png")

#         plt.clf()
#         plt.close()
            

"""
=============================================================================================================================
Create time series DIFFERENCE plots for each humidity sensor compared to TSMS at each site. MONTHLY RECORDS
Daily average difference
=============================================================================================================================
"""
# print("Humidity difference")

# sites = {
#     0:"Ankara", 1:"Konya", 2:"Adana"
# }
# station_map = {
#     0:[0,1,2], 1:[3,4,5], 2:[6,7,8]
# }
# sht_upgrade = [ # the day the upgrade from HTU to SHT was performed
#     "2024-01-17", "2024-01-12", "2024-01-15"
# ] # same day that radiation shield sensor array updated

# for i in range(3):
#     print(f"\t{sites[i]}: Humidity Difference per Sensor")

#     inst_1 = paws_dfs[station_map[i][0]].copy(deep=True)
#     inst_2 = paws_dfs[station_map[i][1]].copy(deep=True)
#     inst_3 = paws_dfs[station_map[i][2]].copy(deep=True)
#     tsms_ref = tsms_dfs[i*3].copy(deep=True)

#     inst_1.reset_index(inplace=True)
#     inst_2.reset_index(inplace=True)
#     inst_3.reset_index(inplace=True)
#     tsms_ref.reset_index(inplace=True)

#     # Step 1: Calculate the daily mean difference for each temperature sensor from the reference.
#     daily_mean_diffs = []
#     for year_month_day in set(inst_1['year_month_day']) & \
#                         set(inst_2['year_month_day']) & \
#                             set(inst_3['year_month_day']) & \
#                                 set(tsms_ref['year_month_day']):    # not ordered when working w/ sets

#         inst_1_grouped = inst_1[inst_1['year_month_day'] == year_month_day]
#         inst_2_grouped = inst_2[inst_2['year_month_day'] == year_month_day]
#         inst_3_grouped = inst_3[inst_3['year_month_day'] == year_month_day]
#         tsms_grouped = tsms_ref[tsms_ref['year_month_day'] == year_month_day]

#         merged_df = pd.merge(inst_1_grouped, inst_2_grouped, on='date', suffixes=('_1', '_2'))
#         merged_df = pd.merge(merged_df, inst_3_grouped, on='date', suffixes=('', '_3'))
#         merged_df = pd.merge(merged_df, tsms_grouped, on='date', suffixes=('', '_tsms'))

#         for sensor in variable_mapper['humidity']:
#             if sensor == "bme2_hum": continue
#             merged_df[f"{sensor}_1_diff"] = merged_df[f'{sensor}_1'] - merged_df['humidity'] # 3D-PAWS instrument 1
#             merged_df[f"{sensor}_2_diff"] = merged_df[f'{sensor}_2'] - merged_df['humidity'] # 3D-PAWS instrument 2
#             merged_df[f"{sensor}_diff"] = merged_df[f'{sensor}'] - merged_df['humidity']     # 3D-PAWS instrument 3

#             daily_mean_diffs.append({
#                 'date':year_month_day,
#                 'sensor':sensor,
#                 f'TSMS{station_map[i][0]}_diff':merged_df[f"{sensor}_1_diff"].mean(),
#                 f'TSMS{station_map[i][1]}_diff':merged_df[f"{sensor}_2_diff"].mean(),
#                 f'TSMS{station_map[i][2]}_diff':merged_df[f"{sensor}_diff"].mean()
#             })

#     # Step 2: Plot average daily diff's for each sensor.
#     df = pd.DataFrame(daily_mean_diffs)
#     df['date'] = pd.to_datetime(df['date'].astype(str))

#     for sensor in variable_mapper['humidity']:
#         if sensor == 'bme2_hum': continue

#         this_sensor = df[df['sensor'] == sensor].sort_values('date')

#         plt.figure(figsize=(20, 12))

#         plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][0]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][0]} {sensor}")
#         plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][1]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][1]} {sensor}")
#         plt.plot(this_sensor['date'], this_sensor[f'TSMS{station_map[i][2]}_diff'], marker='.', markersize=1, label=f"TSMS0{station_map[i][2]} {sensor}")

#         plt.title(f'{sites[i]}: {sensor} Humidity Difference from Reference')
#         plt.xlabel('Date')
#         plt.ylabel('Humidity Difference (%)')
#         plt.ylim(-50, 50)
#         plt.axvline(pd.to_datetime(sht_upgrade[i]), color='red', linestyle='--', linewidth=2)
#         plt.xticks(rotation=45)

#         plt.legend()

#         plt.grid(True)
#         plt.tight_layout()

#         plt.savefig(data_destination / "time-series" / f"{sites[i]}" / "humidity" / "differences" / f"{sites[i]}_{sensor}_humidity_difference.png")

#         plt.clf()
#         plt.close()
