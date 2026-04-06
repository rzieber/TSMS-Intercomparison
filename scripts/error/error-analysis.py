import numpy as np
import pandas as pd
from pathlib import Path
from functools import reduce
from scipy.stats import pearsonr
from sklearn.metrics import mean_absolute_error, root_mean_squared_error


output = Path("data/error-analysis")
data = Path("data/cleaned")

TIMESCALE = None    # 'H' --> hourly, 'D' --> daily, None --> point-for-point

variable_mapper = { # TSMS : 3DPAWS
    "temperature":          ["bmp2_temp", "htu_temp", "sth_temp", "mcp9808"],
    "humidity":             ["bme2_hum", "htu_hum", "sth_hum"],
    "actual_pressure":      ["bmp2_pres"],
    "avg_wind_dir":         ["wind_dir"],
    "avg_wind_speed_2m":    ["wind_speed"], 
    "total_rainfall":       ["tipping"]
}
wmo_thresholds = [  # indexed by variable_mapper keys
    0.2,            # temperature (deg C)
    3,              # humidity (%)
    0.15,           # atmospheric pressure (hPa)
    5,              # wind direction (deg)
    0.5,            # wind speed (m/s)
    5               # precip (%)
] 
magnetic_declinations = { # https://www.ngdc.noaa.gov/geomag/calculators/magcalc.shtml
    "Ankara":   6.11,          
    "Konya":    5.73,            
    "Adana":    5.69            
}
sht_upgrade = { 
    "Ankara":   pd.to_datetime("2024-01-17 00:00:00"), 
    "Konya":    pd.to_datetime("2024-01-12 00:00:00"),  
    "Adana":    pd.to_datetime("2024-01-15 00:00:00")   
}
hellman_exponents = {
    "Ankara": 0.30,  # Urban
    "Konya":  0.35,  # Urban + many obstacles  
    "Adana":  0.25   # Suburban + grass
}
h_tsms = 10.0 
h_paws = 2.0   


"""
=============================================================================================================================
Create the 3D PAWS and TSMS dataframes.
=============================================================================================================================    
"""
paws_dfs = {
    "Ankara":[],
    "Konya" :[],
    "Adana" :[]
}
tsms_dfs = {}

for csv in data.rglob("*final*.csv"):
    name = str(csv.stem)
    df = pd.read_csv(csv)

    key = "_".join(name.split("_")[2:3])

    if name.startswith("3DPAWS"):
        station_name = "_".join(name.split("_")[1:2])
        print("Reading", station_name)
        paws_dfs[key].append((df, station_name))
    elif name.startswith("TSMS"):
        print("Reading", key, "reference")

        # Hellman correction
        df['avg_wind_speed_2m'] = df['avg_wind_speed'] * \
            ((h_paws / h_tsms) ** hellman_exponents[key])
        tsms_dfs[key] = df

        tsms_dfs[key] = df

print()


"""
=============================================================================================================================
Calculate wind direction bias for 3D-PAWS relative to TSMS measurements. Bias introduced at installation.
Account for 10-m / 2-m discreplancy with Hellman function.
NOTE: As of 12-6-2025 we believe wind vanes calibrated to true north at installation and therefore no longer
require magnetic declination or bias correction
=============================================================================================================================    
"""
# def _vectorial_wind_average(wind_speed: np.ndarray, wind_dir: np.ndarray) -> tuple[float, float]:
#     """
#     Proper vectorial averaging of wind speed and direction (WMO standard).
#     Returns (mean_speed, mean_direction)
#     """
#     # Convert direction to meteorological convention (direction FROM)
#     theta = np.radians(wind_dir + 180)  # +180° for meteorological convention
    
#     # Vector components (speed-weighted)
#     u = wind_speed * np.cos(theta)
#     v = wind_speed * np.sin(theta)
    
#     # Average components
#     u_avg = np.mean(u)
#     v_avg = np.mean(v)
    
#     # Convert back
#     ws_avg = np.sqrt(u_avg**2 + v_avg**2)
#     theta_avg = np.degrees(np.arctan2(v_avg, u_avg))
#     wd_avg = (theta_avg - 180 + 360) % 360  # Back to meteorological convention
    
#     return ws_avg, wd_avg

# # FIXED wind bias calculation - Proper paired arrays
# wind_dir_bias = {}
# wind_speed_bias = {}

# for key in paws_dfs:
#     tsms_df = tsms_dfs[key].copy()
    
#     # Hellman correction FIRST
#     tsms_df['avg_wind_speed_2m'] = tsms_df['avg_wind_speed'] * \
#         ((h_paws / h_tsms) ** hellman_exponents[key])
#     tsms_dfs[key] = tsms_df
    
#     # VECTORIAL AVERAGING - TSMS (use corrected speed)
#     tsms_valid = tsms_df[['avg_wind_speed_2m', 'avg_wind_dir']].dropna()
#     if len(tsms_valid) == 0:
#         print(f"WARNING: No valid TSMS wind data for {key}")
#         continue
        
#     tsms_speed = tsms_valid['avg_wind_speed_2m'].to_numpy()
#     tsms_dir = tsms_valid['avg_wind_dir'].to_numpy()
#     tsms_ws_avg, tsms_wd_avg = vectorial_wind_average(tsms_speed, tsms_dir)
    
#     # VECTORIAL AVERAGING - PAWS (all stations, mag corrected)
#     paws_all_speed = []
#     paws_all_dir = []
    
#     for paws_df, _ in paws_dfs[key]:
#         # PAIR speed + direction from SAME rows (FIXED)
#         paws_valid = paws_df[['wind_speed', 'wind_dir']].dropna()
#         if len(paws_valid) > 0:
#             paws_speed = paws_valid['wind_speed'].to_numpy()
#             paws_dir = paws_valid['wind_dir'].to_numpy()
#             paws_dir_mag = (paws_dir + magnetic_declinations[key]) % 360
#             # Append ONLY paired valid data
#             paws_all_speed.extend(paws_speed)
#             paws_all_dir.extend(paws_dir_mag)
    
#     if len(paws_all_speed) == 0:
#         print(f"WARNING: No valid PAWS wind data for {key}")
#         continue
        
#     paws_speed_array = np.array(paws_all_speed)
#     paws_dir_array = np.array(paws_all_dir)
#     paws_ws_avg, paws_wd_avg = vectorial_wind_average(paws_speed_array, paws_dir_array)
    
#     # Calculate bias
#     dir_bias = (tsms_wd_avg - paws_wd_avg + 180) % 360 - 180
#     speed_bias = tsms_ws_avg - paws_ws_avg
    
#     wind_dir_bias[key] = dir_bias
#     wind_speed_bias[key] = speed_bias
    
#     print(f"{key}: TSMS({tsms_ws_avg:.1f}m/s, {tsms_wd_avg:.0f}°)")
#     print(f"      PAWS({paws_ws_avg:.1f}m/s, {paws_wd_avg:.0f}°)  [{len(paws_speed_array)} points]")
#     print(f"      Bias: {dir_bias:+.1f}°, {speed_bias:+.1f}m/s\n")


"""
=============================================================================================================================
Aggregate the dataframes according to the specified frequency.
=============================================================================================================================    
"""
def _agg_timescale(df:pd.DataFrame, freq):
    """Helper function that resamples the dataframes based on desired timeframe (hourly, daily, none)."""
    if freq is None: return df

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')

    agg_map = {
        'temperature':          'mean',
        'bmp2_temp':            'mean',
        'htu_temp':             'mean',
        'sth_temp':             'mean',
        'mcp9808':              'mean',
        'humidity':             'mean',
        'bme2_hum':             'mean',
        'htu_hum':              'mean',
        'sth_hum':              'mean',
        'actual_pressure':      'mean',
        'bmp2_pres':            'mean',
        'avg_wind_dir':         'mean',  
        'wind_dir':             'mean',    
        'avg_wind_speed_2m':    'mean',
        'wind_speed':           'mean',
        'total_rainfall':       'sum',
        'tipping':              'sum'
    }

    agg_map_use = {c: agg_map[c] for c in df.columns if c in agg_map}
    df_agg = df.resample(freq).agg(agg_map_use).dropna(how='all')
    df_agg = df_agg.reset_index().rename(columns={'date':'date'})

    return df_agg


paws_dfs_agg = {k: [(_agg_timescale(df_raw, TIMESCALE), name) for df_raw, name in v] 
                for k, v in paws_dfs.items()}
tsms_dfs_agg = {k: _agg_timescale(df_raw, TIMESCALE) for k, df_raw in tsms_dfs.items()}

print(f"Aggregated to {TIMESCALE}")

"""
=============================================================================================================================
Accuracy (systematic errors) -------------------------          
    Bias, Mean Absolute Error, Root Mean Squared Error
=============================================================================================================================    
"""
accuracy = []  # [TSMS00[TSMS00, var, bias, mae, rmse], TSMS01[TSMS01, var, bias, mae, rmse], ...]
accuracy.append(['Station', 'Variable', 'Bias', 'Mean Absolute Error', 'Root Mean Squared Error'])

print("Accuracy statistics.")
for key in paws_dfs_agg:
    tsms_df = tsms_dfs_agg[key]

    for df in paws_dfs_agg[key]:
        print(df[1])
        paws_df = df[0]

        for variable in variable_mapper.keys():
            print(f'\t\t{variable}')

            for var in variable_mapper[variable]:
                merged = None
                if var in ['bme2_hum', 'bmp2_slp']: continue
                elif var == 'wind_dir': # filter out records where wind speed is zero
                    tsms_wind = tsms_df[tsms_df['avg_wind_speed_2m'] > 0][['date', variable]]
                    paws_wind = paws_df[paws_df['wind_speed'] > 0][['date', var]]
                    
                    merged = pd.merge(
                        tsms_wind.rename(columns={variable: 'tsms'}),
                        paws_wind.rename(columns={var: 'paws'}),
                        on='date', how='inner'
                    )
                else:
                    merged = pd.merge(
                        tsms_df[['date', variable]].rename(columns={variable:'tsms'}), 
                        paws_df[['date', var]].rename(columns={var:'paws'}), 
                        on='date', 
                        how='inner'
                    )

                merged = merged.dropna(subset=['tsms', 'paws'])

                tsms = merged['tsms'].to_numpy()
                paws = merged['paws'].to_numpy()

                if len(paws) == 0: 
                    accuracy.append([df[1], f'{var}', np.nan, np.nan, np.nan])
                    continue     

                s = []
                s.append(df[1])
                s.append(f'{var}')

                if var in ['wind_dir']: # handle circular discrepancy at 360 -> 0
                    # paws_corrected = (paws + magnetic_declinations[key] + wind_dir_bias[key]) % 360
                    # raw_diff = tsms - paws_corrected
                    raw_diff = tsms - paws
                    abs_err = np.minimum(np.abs(raw_diff), 360 - np.abs(raw_diff))
                    signed_diff = (raw_diff + 180) % 360 - 180
                    s.append(round(signed_diff.mean(), 1))              # bias
                    s.append(round(abs_err.mean(), 1))                  # mae
                    s.append(round(np.sqrt((abs_err**2).mean()), 1))    # rmse
                elif var in ['tipping']: # exclude dry periods
                    nonzero_mask = ~((tsms == 0) & (paws == 0))
                    tsms_nonzero = tsms[nonzero_mask]
                    paws_nonzero = paws[nonzero_mask]
                    s.append(round((tsms_nonzero - paws_nonzero).mean(), 1))   
                    s.append(round(mean_absolute_error(tsms_nonzero, paws_nonzero), 1))         
                    s.append(round(root_mean_squared_error(tsms_nonzero, paws_nonzero),1))      
                else:
                    s.append(round((tsms - paws).mean(), 1))                   
                    s.append(round(mean_absolute_error(tsms, paws), 1))        
                    s.append(round(root_mean_squared_error(tsms, paws),1))     

                accuracy.append(s)

df_accuracy = pd.DataFrame(accuracy[1:], columns=accuracy[0])
# df_accuracy.to_csv(output / "accuracy.csv", index=False)

print()

"""
=============================================================================================================================
Precision (random errors) ----------------------
    Standard Deviations, Correlation Coefficients
=============================================================================================================================    
"""
precision = [] # [TSMS00[TSMS00, var, std_paws, std_tsms, r], TSMS01[TSMS01, var, std, r], ...]
precision.append(['Station', 'Variable', '3D-PAWS Standard Deviation', 'TSMS Standard Deviation', 'Pearson Correlation Coefficient'])

print("Precision statistics.")
for key in paws_dfs_agg:
    tsms_df = tsms_dfs_agg[key]

    for paws_df, stn_name in paws_dfs_agg[key]:
        print(stn_name)

        for variable in variable_mapper.keys():
            print(f'\t\t{variable}')

            for var in variable_mapper[variable]:
                merged = None
                if var in ['bme2_hum', 'bmp2_slp']: continue
                elif var == 'wind_dir': # filter out records where wind speed is zero
                    tsms_wind = tsms_df[tsms_df['avg_wind_speed_2m'] > 0][['date', variable]]
                    paws_wind = paws_df[paws_df['wind_speed'] > 0][['date', var]]
                    
                    merged = pd.merge(
                        tsms_wind.rename(columns={variable: 'tsms'}),
                        paws_wind.rename(columns={var: 'paws'}),
                        on='date', how='inner'
                    )
                else:
                    merged = pd.merge(
                        tsms_df[['date', variable]].rename(columns={variable:'tsms'}), 
                        paws_df[['date', var]].rename(columns={var:'paws'}), 
                        on='date', 
                        how='inner'
                    )

                merged = merged.dropna(subset=['tsms', 'paws'])

                tsms = merged['tsms'].to_numpy()
                paws = merged['paws'].to_numpy()

                if len(paws) == 0: 
                    precision.append([stn_name, var, np.nan, np.nan, np.nan])
                    continue    

                if var in ['tipping']:
                    nonzero_mask = ~((tsms == 0) & (paws == 0))
                    tsms_nonzero = tsms[nonzero_mask]
                    paws_nonzero = paws[nonzero_mask]
                    corr_coef, _ = pearsonr(tsms_nonzero, paws_nonzero)
                    paws_std = np.std(paws_nonzero, ddof=1)
                    tsms_std = np.std(tsms_nonzero, ddof=1)
                elif var in ['wind_dir']:
                    # paws_corrected = (paws + magnetic_declinations[key] + wind_dir_bias[key]) % 360
                    # corr_coef, _ = pearsonr(tsms, paws_corrected)
                    corr_coef, _ = pearsonr(tsms, paws)
                    # paws_std = np.std(paws_corrected, ddof=1)
                    paws_std = np.std(paws, ddof=1)
                    tsms_std = np.std(tsms, ddof=1)
                else:
                    corr_coef, _ = pearsonr(tsms, paws)
                    paws_std = np.std(paws, ddof=1)
                    tsms_std = np.std(tsms, ddof=1)

                precision.append([stn_name, var, round(paws_std, 1), round(tsms_std, 1), round(corr_coef, 1)])

df_precision = pd.DataFrame(precision[1:], columns=precision[0])
# df_precision.to_csv(output / "precision.csv", index=False)

print()

"""
=============================================================================================================================
Reliability
=============================================================================================================================    
"""
reliable = []  # [TSMS00[TSMS00, var, reliability, inaccuracy], TSMS01[TSMS01, var, reliability, inaccuracy], ...]
reliable.append(['Station', 'Variable', 'Reliability', 'Inaccuracy'])

print("Reliability statistics.")
for key in paws_dfs_agg:
    tsms_df = tsms_dfs_agg[key]

    for df in paws_dfs_agg[key]:
        print(df[1])
        paws_df = df[0]

        for variable, threshold in zip(variable_mapper.keys(), wmo_thresholds):
            print(f'\t\t{variable}\t\tWMO threshold --> {threshold}')

            for var in variable_mapper[variable]:
                merged = None
                if var in ['bme2_hum', 'bmp2_slp']: continue
                elif var in ['wind_speed', 'wind_dir']: # filter out records where wind speed is zero
                    tsms_wind = tsms_df[tsms_df['avg_wind_speed_2m'] > 0][['date', variable]]
                    paws_wind = paws_df[paws_df['wind_speed'] > 0][['date', var]]
                    
                    merged = pd.merge(
                        tsms_wind.rename(columns={variable: 'tsms'}),
                        paws_wind.rename(columns={var: 'paws'}),
                        on='date', how='inner'
                    )
                else:
                    merged = pd.merge(
                        tsms_df[['date', variable]].rename(columns={variable:'tsms'}), 
                        paws_df[['date', var]].rename(columns={var:'paws'}), 
                        on='date', 
                        how='inner'
                    )

                merged = merged.dropna(subset=['tsms', 'paws'])

                tsms = merged['tsms'].to_numpy()
                paws = merged['paws'].to_numpy()

                if len(paws) == 0: 
                    reliable.append([f'{df[1]}', f'{var}', np.nan, np.nan])
                    continue 

                tsms_use, paws_use = None, None
                if var in ['tipping']:  # exclude dry periods
                    nonzero_mask = ~((tsms == 0) & (paws == 0))
                    tsms_nonzero = tsms[nonzero_mask]
                    paws_nonzero = paws[nonzero_mask]
                    tsms_use, paws_use = tsms_nonzero, paws_nonzero
                # elif var in ['wind_dir']:  # circular correction
                #     paws_corrected = (paws + magnetic_declinations[key] + wind_dir_bias[key]) % 360
                #     tsms_use, paws_use = tsms, paws_corrected
                else:
                    tsms_use, paws_use = tsms, paws

                mae = np.mean(np.abs(tsms_use - paws_use))
                ref_std = np.std(tsms_use, ddof=1)
                reliability_pct = max(0, (1 - (mae / (ref_std + 1e-9))) * 100)  # Avoid div by zero
                inaccuracy_pct = 100 - reliability_pct

                reliable.append([f'{df[1]}', f'{var}', round(reliability_pct, 1), round(inaccuracy_pct, 1)])

df_reliable = pd.DataFrame(reliable[1:], columns=reliable[0]) 
# df_reliable.to_csv(output / "reliability.csv", index=False)

print()

"""
=============================================================================================================================
Create comprehensive csv
=============================================================================================================================    
"""
print("Creating CSV.")
key_cols = ['Station', 'Variable']

# For each DataFrame, select only key columns + non-key columns (excluding duplicates)
def select_merge_cols(df):
    return df[key_cols + [col for col in df.columns if col not in key_cols]]

dfs = [df_accuracy, df_precision, df_reliable]
dfs_selected = [select_merge_cols(df) for df in dfs]

df_merged = reduce(
    lambda left, right: pd.merge(left, right, on=key_cols, how='outer'),
    dfs_selected
)

df_merged = df_merged.sort_values(
    by="Station",
    key=lambda s: s.str.extract(r"(\d+)", expand=False).astype(int)
)


if TIMESCALE == 'D':    df_merged.to_csv(output / 'daily-statistical-analysis_[NO-WIND-CORRECTION].csv', index=False)
elif TIMESCALE == 'H':  df_merged.to_csv(output / 'hourly-statistical-analysis_[NO-WIND-CORRECTION].csv', index=False)
else:                   df_merged.to_csv(output / 'point-for-point-statistical-analysis_[NO-WIND-CORRECTION].csv', index=False)
