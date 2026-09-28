"""
Data filter. Creates final csv's as well as outlier csv's. Contains plot gen logic.

Requires station_TSMS00 -> 08 folder struct, with the complete records for TSMS and 3D-PAWS within each folder
within the data_origin directory. Alongside the station_TSMS00 -> 08 folders, have a folder for each site.
Note:   The subfolders for station_TSMS00 -> 08 are generated automatically.
        The subfolders for sites Ankara, Konya, and Adana are NOT generated automatically.

The data_destination pathway doesn't require this, just list the full pathname where you want things stored.

Pre-pass: 3D-PAWS humidity from every station, for the Phase 5 site cross-check
Phase 1: Nulls (-999.99)
Phase 2: Timestamp resets (out of order timestamps)
Phase 3: Thresholds (unrealistic values)
Phase 4: Manual removal of identified special cases, incl. documented sensor failures (sensor_failures)
Phase 5: HTU21D bit-switching filter (step test + co-located 3D-PAWS sensors; no reference data)
Phase 6: Statistical outlier removal (rolling z-score and Hampel filter, floored at sensor resolution)
Phase 7: Daily completeness (a variable's day is removed if < 80% of its minutes are valid)

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


data_origin = r"data/reformatted/"
data_destination = r"data/cleaned/"

outlier_reasons = [
    "null", "timestamp_reset", "threshold", "manual_removal", "htu_trend_switch", "z-score_contextual",
    "hampel_contextual", "hum_step_site_check", "hum_step_unverified", "temp_step_station_check",
    "temp_step_unverified", "sensor_failure", "daily_completeness"
]

# Documented sensor failures, removed in full (see docs/sensor-failures.md for evidence).
# (column, start, end, catalog id) -- end=None means through the end of the record.
sensor_failures = {
    # SF-01 (TSMS03 sth_hum) and SF-02 (TSMS04 htu_hum) were removed on 2026-09-28: they were not sensor failures but
    # mislabeled CHORDS columns (SF-10), fixed in data/reformatted by scripts/reformatting/splice_chords_dec2024.py.
}

# Phase 7: a day's readings of a variable are kept only if at least this share of its 1,440 minutes are valid
# (same criterion as the TSMS report, section 3.6). The analysis additionally requires 80% of minutes to be PAIRED.
DAILY_COMPLETENESS = 0.8

# Thresholds for the HTU21D "bit-switching" filter (Phase 5)
TEMP_THRESHOLD = 3.5            # °C, jump between consecutive minutes that makes an htu_temp reading suspect
HUM_THRESHOLD = 3.5             # %RH, jump between consecutive minutes that makes an htu_hum/sth_hum reading suspect
TEMP_STATION_THRESHOLD = 2.0    # °C, max distance of a suspect htu_temp from the station's other temperature sensors
HUM_SITE_THRESHOLD = 5.0        # %RH, max distance of a suspect humidity reading from the closest 3D-PAWS station at the site

# Minimum MAD (Hampel) and minimum rolling std (z-score) for Phase 6: the coarsest resolution each column
# is recorded at. Without a floor, a flat or near-flat window gives MAD = 0 / a tiny std, and a reading that
# differs from its neighbours by a single resolution step is flagged as an outlier.
# 3D-PAWS: 0.01 (SD-card era) or 0.1 (CHORDS era); MCP9808 0.0625 or 0.1. See docs/potential-fixes.md (noise floor).
RESOLUTION_FLOOR = {
    "temperature": 0.1, "humidity": 1.0, "actual_pressure": 0.1, "sea_level_pressure": 0.1,     # TSMS reference
    "bmp2_temp": 0.1, "htu_temp": 0.1, "sth_temp": 0.1, "mcp9808": 0.1,                          # 3D-PAWS
    "bme2_hum": 0.1, "htu_hum": 0.1, "sth_hum": 0.1, "bmp2_pres": 0.1, "bmp2_slp": 0.1
}

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


def failure_mask(dates:pd.Series, start, end):
    """True for dates inside a documented sensor-failure period (end=None: through the end of the record)."""
    mask = dates >= pd.Timestamp(start)
    if end is not None: mask &= dates <= pd.Timestamp(end)
    return mask


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

    failures = sensor_failures.get(station_dir[8:14], [])
    sensors = []
    for col in ['htu_hum', 'sth_hum']:
        h = pd.to_numeric(hum[col], errors='coerce')
        h = h.where((h >= 0) & (h <= 100))  # also removes -999.99 nulls
        for fail_col, start, end, _ in failures:  # a failed sensor can't vouch for its neighbours
            if fail_col == col: h = h.where(~failure_mask(h.index.to_series(), start, end))
        sensors.append(h.where(~step_suspect(h, HUM_THRESHOLD)))

    site_humidity[station_dir[8:14]] = sensors[0].combine_first(sensors[1])


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
    
    paws_df.reset_index(inplace=True)
    tsms_df.reset_index(inplace=True)

    paws_df_FILTERED = paws_df.copy()
    tsms_df_FILTERED = tsms_df.copy()

    paws_df.set_index('date', inplace=True)
    tsms_df.set_index('date', inplace=True)

    print()
    print("Starting outlier removal for ", station_directories[i][8:14])
    

    """
    =============================================================================================================================
    Phase 1: Filter out nulls (-999.99)
    =============================================================================================================================
    """
    print("Phase 1: Filtering out nulls (-999.99).")

    for variable in variable_mapper:                        # Filtering TSMS ----------------------------------------------------
        mask_999 = tsms_df_FILTERED[variable] == -999.99    # Replace -999.99 with np.nan
        tsms_df_FILTERED.loc[mask_999, variable] = np.nan
        
        mask_null = tsms_df_FILTERED[variable].isnull()     # Identify nulls
        
        if mask_null.any():                                 # Add nulls to outliers_df
            outliers_to_add = pd.DataFrame({
                'date': tsms_df_FILTERED['date'][mask_null],
                'column_name': variable,
                'original_value': -999.99,
                'outlier_type': outlier_reasons[0]
            })
            tsms_outliers = pd.concat([tsms_outliers, outliers_to_add], ignore_index=True)
        

        outliers_to_add = None
        

        for var in variable_mapper[variable]:               # Filtering PAWS ----------------------------------------------------
            mask_999 = paws_df_FILTERED[var] == -999.99   
            paws_df_FILTERED.loc[mask_999, var] = np.nan

            mask_null = paws_df_FILTERED[var].isnull()    

            if mask_null.any():                  
                outliers_to_add = pd.DataFrame({
                    'date': paws_df_FILTERED['date'][mask_null],
                    'column_name': var,
                    'original_value': -999.99,
                    'outlier_type': outlier_reasons[0]
                })
                paws_outliers = pd.concat([paws_outliers, outliers_to_add], ignore_index=True)
    

    """
    =============================================================================================================================
    Phase 2: Filter out time resets
    =============================================================================================================================
    """
    print(f"Phase 2: Filtering out time resets.")

    tsms_df_FILTERED = tsms_df_FILTERED.sort_values(by='date')  # Filtering TSMS ------------------------------------------------
    tsms_df_FILTERED['time_diff'] = tsms_df_FILTERED['date'].diff()
    
    out_of_order_tsms = tsms_df_FILTERED[tsms_df_FILTERED['time_diff'] <= pd.Timedelta(0)]  # Identify out-of-order timestamps

    tsms_outliers = pd.concat([tsms_outliers, pd.DataFrame({    # Add out-of-order timestamps to outlier dataframe
        'date': out_of_order_tsms['date'],
        'column_name': 'date',
        'original_value': np.nan,
        'outlier_type': outlier_reasons[1]
    })], ignore_index=True)

    df_sequential = tsms_df_FILTERED[tsms_df_FILTERED['time_diff'] > pd.Timedelta(0)]       # Filter out-of-order timestamps
    tsms_df_FILTERED = df_sequential.drop(columns=['time_diff'])

    df_sequential = None  

    paws_df_FILTERED = paws_df_FILTERED.sort_values(by='date')  # Filtering PAWS ------------------------------------------------
    paws_df_FILTERED['time_diff'] = paws_df_FILTERED['date'].diff()
    
    out_of_order_paws = paws_df_FILTERED[paws_df_FILTERED['time_diff'] <= pd.Timedelta(0)]  

    paws_outliers = pd.concat([paws_outliers, pd.DataFrame({    
        'date': out_of_order_paws['date'],
        'column_name': 'date',
        'original_value': np.nan,
        'outlier_type': outlier_reasons[1]
    })], ignore_index=True)

    df_sequential = paws_df_FILTERED[paws_df_FILTERED['time_diff'] > pd.Timedelta(0)]       
    paws_df_FILTERED = df_sequential.drop(columns=['time_diff'])


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

        Below station_rules, there are 2 other removals of erroneous rainfall data. The precipitation 
        data removed was determined to be the result of a faulty connection (TSMS08) and test data 
        generated during the fabrication process (TSMS04).

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

    # Erroneously high values -- most likely test tips during fabrication process
    if station_directories[i][8:14] == "TSMS04":
        existing_nulls = paws_df_FILTERED['tipping'].isnull() 

        exclude_rainfall_start = pd.to_datetime(paws_df_FILTERED['date'].iloc[0])
        exclude_rainfall_end = pd.to_datetime("2022-08-31 23:59:59")

        to_remove = paws_df_FILTERED.loc[
            (paws_df_FILTERED['date'] >= exclude_rainfall_start) & (paws_df_FILTERED['date'] <= exclude_rainfall_end), 'tipping'
        ].copy()

        paws_df_FILTERED.loc[
            (paws_df_FILTERED['date'] >= exclude_rainfall_start) & (paws_df_FILTERED['date'] <= exclude_rainfall_end), 'tipping'
        ] = np.nan

        new_nulls = paws_df_FILTERED['tipping'].isnull() & ~existing_nulls

        outliers_to_add = pd.DataFrame({                                
            'date': paws_df_FILTERED.loc[new_nulls, 'date'],
            'column_name': 'tipping',
            'original_value': to_remove,
            'outlier_type': outlier_reasons[3]
        })
        paws_outliers = pd.concat([paws_outliers, outliers_to_add], ignore_index=True)

    # Erroneously high values -- possibly faulty connector, or manual manipulation of the gauge by the public
    if station_directories[i][8:14] == "TSMS08":
        paws_df_FILTERED['tipping'] = pd.to_numeric(paws_df_FILTERED['tipping'], errors='coerce')
        existing_nulls = paws_df_FILTERED['tipping'].isnull() 
        original = paws_df_FILTERED['tipping'].copy()

        dates_to_remove = [
            ("2023-04-08","2023-04-14 23:59:00"),        
            ("2023-05-15 00:00:00","2023-05-17 23:59:59"), 
            ("2024-02-08 00:00:00","2024-02-11 23:59:59"), 
            ("2024-02-15 00:00:00","2024-02-20 23:59:59"), 
            ("2024-03-07 00:00:00","2024-03-07 23:59:59"),
            ("2024-03-09 00:00:00","2024-03-10 23:59:59"), 
            ("2024-03-21 00:00:00","2024-03-21 23:59:59"),
        ]

        to_remove_list = []
        for start_date, end_date in dates_to_remove:
            exclude_rainfall_start = pd.to_datetime(start_date)
            exclude_rainfall_end = pd.to_datetime(end_date)

            mask = (paws_df_FILTERED['date'] >= exclude_rainfall_start) & (paws_df_FILTERED['date'] <= exclude_rainfall_end)
            to_remove = paws_df_FILTERED.loc[mask, 'tipping'].copy()
            to_remove_list.append(to_remove)

            paws_df_FILTERED.loc[
                (paws_df_FILTERED['date'] >= exclude_rainfall_start) & (paws_df_FILTERED['date'] <= exclude_rainfall_end), 'tipping'
            ] = np.nan

        new_nulls = paws_df_FILTERED['tipping'].isnull() & ~existing_nulls

        all_removed = pd.concat(to_remove_list)
        all_removed = all_removed[new_nulls]

        outliers_to_add = pd.DataFrame({                                
            'date': paws_df_FILTERED.loc[new_nulls, 'date'],
            'column_name': 'tipping',
            'original_value': original.loc[new_nulls],
            'outlier_type': outlier_reasons[3]
        })
        paws_outliers = pd.concat([paws_outliers, outliers_to_add], ignore_index=True)

    # Documented sensor failures -- whole periods removed (see sensor_failures and docs/sensor-failures.md)
    for col, start, end, catalog_id in sensor_failures.get(station, []):
        mask = failure_mask(paws_df_FILTERED['date'], start, end)
        new_nulls = mask & paws_df_FILTERED[col].notna()
        print(f"\tRemoving {catalog_id}: {station} {col} from {start} to {end or 'end of record'} ({new_nulls.sum()} readings)")

        outliers_to_add = pd.DataFrame({
            'date': paws_df_FILTERED.loc[new_nulls, 'date'],
            'column_name': col,
            'original_value': paws_df_FILTERED.loc[new_nulls, col],
            'outlier_type': outlier_reasons[11]
        })
        paws_outliers = pd.concat([paws_outliers, outliers_to_add], ignore_index=True)
        paws_df_FILTERED.loc[mask, col] = np.nan


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
    Phase 6: Filter out contextual outliers using statistical methods.
    =============================================================================================================================
    """
    print(f"Phase 6: Filtering out contextual outliers using rolling Z-score and Hampel filter.")

    tsms_df_FILTERED.reset_index(drop=True, inplace=True)         
    paws_df_FILTERED.reset_index(drop=True, inplace=True)


    for variable in variable_mapper:                                # Filtering TSMS --------------------------------------------
        if variable in ["avg_wind_speed", "avg_wind_dir", "total_rainfall"]: continue

        tsms_df_FILTERED[variable] = pd.to_numeric(tsms_df_FILTERED[variable], errors='coerce')
        existing_nulls = tsms_df_FILTERED[variable].isna()

        original = tsms_df_FILTERED[variable].copy()
        stats_base = original.copy()

        window = 20  
        threshold = 3

        rolling_mean = stats_base.rolling(window=window, center=True, min_periods=window//2).mean() 
        rolling_std = stats_base.rolling(window=window, center=True, min_periods=window//2).std()
        rolling_med = stats_base.rolling(window=window, center=True, min_periods=window//2).median()

        rolling_std = rolling_std.clip(lower=RESOLUTION_FLOOR[variable]) # near-flat windows: a single resolution step is not a 3-sigma event

        z_score = (original - rolling_mean) / rolling_std


        mad = (original - rolling_med).abs().rolling(window=window, center=True, min_periods=window//2).median()
        mad = mad.clip(lower=RESOLUTION_FLOOR[variable])  # flat windows: don't flag single resolution steps
        hampel_threshold = threshold * 1.4826 * mad # 1.4826 rescales median absolute deviation to std (under gaussian assumption)

        mask_z = z_score.abs() > threshold
        mask_h = (original - rolling_med).abs() > hampel_threshold
        new_null_z = mask_z & ~existing_nulls
        new_null_h = mask_h & ~existing_nulls
        
        outliers_to_add = pd.DataFrame({
            'date': tsms_df_FILTERED.loc[new_null_z, 'date'],
            'column_name': variable,
            'original_value': original.loc[new_null_z],
            'outlier_type': outlier_reasons[5]
        })
        tsms_outliers = pd.concat([tsms_outliers, outliers_to_add], ignore_index=True)
        outliers_to_add = pd.DataFrame({
            'date': tsms_df_FILTERED.loc[new_null_h, 'date'],
            'column_name': variable,
            'original_value': original.loc[new_null_h],
            'outlier_type': outlier_reasons[6]
        })
        tsms_outliers = pd.concat([tsms_outliers, outliers_to_add], ignore_index=True)

        tsms_df_FILTERED.loc[new_null_z, variable] = np.nan
        tsms_df_FILTERED.loc[new_null_h, variable] = np.nan

        outliers_to_add = None

        for var in variable_mapper[variable]:               # Filtering PAWS ----------------------------------------------------
            paws_df_FILTERED[var] = pd.to_numeric(paws_df_FILTERED[var], errors='coerce')
            existing_nulls = paws_df_FILTERED[var].isnull()

            original = paws_df_FILTERED[var].copy()
            
            stats_base = original.copy()

            rolling_mean = stats_base.rolling(window=window, center=True, min_periods=window//2).mean()
            rolling_std = stats_base.rolling(window=window, center=True, min_periods=window//2).std()
            rolling_med = stats_base.rolling(window=window, center=True, min_periods=window//2).median()

            rolling_std = rolling_std.clip(lower=RESOLUTION_FLOOR[var])

            z_score = (original - rolling_mean) / rolling_std
            mad = (original - rolling_med).abs().rolling(window=window, center=True, min_periods=window//2).median()
            mad = mad.clip(lower=RESOLUTION_FLOOR[var])

            hampel_threshold = 3 * 1.4826 * mad

            mask_z = z_score.abs() > threshold
            mask_h = (original - rolling_med).abs() > hampel_threshold
            new_null_z = mask_z & ~existing_nulls 
            new_null_h = mask_h & ~existing_nulls 

            outliers_to_add = pd.DataFrame({
                'date': paws_df_FILTERED.loc[new_null_z, 'date'],
                'column_name': var,
                'original_value': original.loc[new_null_z],
                'outlier_type': outlier_reasons[5]
            })
            paws_outliers = pd.concat([paws_outliers, outliers_to_add], ignore_index=True)
            outliers_to_add = pd.DataFrame({
                'date': paws_df_FILTERED.loc[new_null_h, 'date'],
                'column_name': var,
                'original_value': original.loc[new_null_h],
                'outlier_type': outlier_reasons[6]
            })
            paws_outliers = pd.concat([paws_outliers, outliers_to_add], ignore_index=True)

            paws_df_FILTERED.loc[new_null_z, var] = np.nan
            paws_df_FILTERED.loc[new_null_h, var] = np.nan

    """
    =============================================================================================================================
    Phase 7: Daily completeness. After all other QC, a day's readings of a variable are kept only if at least
    DAILY_COMPLETENESS of the day's 1,440 minutes have a valid value; otherwise the whole day is removed for that
    variable (and logged). Applied per instrument and per variable, to TSMS and 3D-PAWS alike.
    =============================================================================================================================
    """
    print(f"Phase 7: Removing days with < {DAILY_COMPLETENESS:.0%} valid minutes (per variable).")

    for df_name, frame, columns in [
        ("tsms", tsms_df_FILTERED, list(variable_mapper.keys())),
        ("paws", paws_df_FILTERED, [v for vs in variable_mapper.values() for v in vs])
    ]:
        day = pd.to_datetime(frame['date']).dt.floor('D')
        for col in columns:
            if col not in frame.columns: continue
            frame[col] = pd.to_numeric(frame[col], errors='coerce')
            valid_per_day = frame[col].notna().groupby(day).transform('sum')
            incomplete = (valid_per_day < DAILY_COMPLETENESS * 1440) & frame[col].notna()
            if not incomplete.any(): continue

            outliers_to_add = pd.DataFrame({
                'date': frame.loc[incomplete, 'date'],
                'column_name': col,
                'original_value': frame.loc[incomplete, col],
                'outlier_type': outlier_reasons[12]
            })
            if df_name == "tsms": tsms_outliers = pd.concat([tsms_outliers, outliers_to_add], ignore_index=True)
            else:                 paws_outliers = pd.concat([paws_outliers, outliers_to_add], ignore_index=True)
            frame.loc[incomplete, col] = np.nan


    """
    =========================================================================================================
    CREATE FINAL CSV'S
    =========================================================================================================
    """
    paws_df_FILTERED.drop(columns=['bme2_hum','year_month', 'year_month_day', 'year_month_day_hour'], inplace=True)

    if i in [0,1,2]: 
        tsms_outliers.to_csv(data_destination+f"TSMS_Reference_Ankara_outliers.csv", index=False)
        paws_outliers.to_csv(data_destination+f"3DPAWS_{station_directories[i][8:14]}_Ankara_outliers.csv", index=False)
    elif i in [3,4,5]: 
        tsms_outliers.to_csv(data_destination+f"TSMS_Reference_Konya_outliers.csv", index=False)
        paws_outliers.to_csv(data_destination+f"3DPAWS_{station_directories[i][8:14]}_Konya_outliers.csv", index=False)
    elif i in [6,7,8]: 
        tsms_outliers.to_csv(data_destination+f"TSMS_Reference_Adana_outliers.csv", index=False)
        paws_outliers.to_csv(data_destination+f"3DPAWS_{station_directories[i][8:14]}_Adana_outliers.csv", index=False)

    if i in [0,1,2]: 
        tsms_df_FILTERED.to_csv(data_destination+f"TSMS_Reference_Ankara_final.csv", index=False)
        paws_df_FILTERED.to_csv(data_destination+f"3DPAWS_{station_directories[i][8:14]}_Ankara_final.csv", index=False)
    elif i in [3,4,5]: 
        tsms_df_FILTERED.to_csv(data_destination+f"TSMS_Reference_Konya_final.csv", index=False)
        paws_df_FILTERED.to_csv(data_destination+f"3DPAWS_{station_directories[i][8:14]}_Konya_final.csv", index=False)
    elif i in [6,7,8]: 
        tsms_df_FILTERED.to_csv(data_destination+f"TSMS_Reference_Adana_final.csv", index=False)
        paws_df_FILTERED.to_csv(data_destination+f"3DPAWS_{station_directories[i][8:14]}_Adana_final.csv", index=False)

    print("\n----------------------")
