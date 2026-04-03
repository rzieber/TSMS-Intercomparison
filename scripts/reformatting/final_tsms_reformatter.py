"""
=================================================================================================
Uses the reformatted TSMS data from 2022 -> Jan. 2024 and combines the remaining data
from Jan. 2024 - Nov. 2024. 

To be used in conjunction with the filegen script:
    Step 1. Run final_tsms_reformatter.py
    Step 2. Run final_tsms_filegen.py
Where the data DESTINATION in step 1 is the data ORIGIN in step 2.

2022 - 2024 data origin: TSMS database in Turkiye

NOTE: Requires the stations be ordered identically in data struct's for 1st & 2nd data periods.
      See line 137 to adjust manual reordering.
=================================================================================================
"""
import sys
import os
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta

sys.path.append(str(Path(__file__).resolve().parents[2]))
from dev import functions as func


data_destination = "/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/CSV_Format/TSMS/Aug2022-Nov2024"

data_origin_partI = "/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/CSV_Format/TSMS/2022-Jan2024/complete_record/"
data_origin_partII = "/Users/rzieber/Documents/3D-PAWS/Turkiye/raw/TSMS/2024-12-09-5 2024.txt"

all_files_partI = sorted([file for file in Path(data_origin_partI).rglob('*') if file.is_file() and file.name != ".DS_Store"])

station_mapper = {
    17351:'Adana', 17130:'Ankara', 17245:'Konya'
}

print("Building initial dataframes.")

tsms_dfs_partI = [] 
for file in all_files_partI:
    tsms_dfs_partI.append(
        pd.read_csv(file, low_memory=False)
    )

tsms_dfs_partII = None
tsms_df = pd.read_csv(
    data_origin_partII, delimiter=';', low_memory=False, header=0
    )
columns = [
    'Station Number','Year','Month','Day','Hour','Minute',
    'Temperature','Humidity','Actual Pressure','Sea Level Pressure',
    'Sunshine Duration','Mean Global Solar Radiation','Direct Solar Radiation Intensity',
    'Diffuse Solar Radiation Intensity','UVA Radiation Intensity','UVB Radiation Intensity',
    'Mean Wind Speed at 10m','Maximum Wind Speed at 10m','NRT Corrected Rainfall',
    'PWS Current Rainfall','Mean Wind Direction','Mean Wind Speed','Maximum Wind Direction',
    'Maximum Wind Speed','Maximum Wind Time','Total Rainfall'
    ]
tsms_df.columns = columns
station_ids = tsms_df['Station Number'].unique()
tsms_dfs_partII = [tsms_df[tsms_df['Station Number'] == station_id] for station_id in station_ids if station_id != 18250]

print("Building reformatted dataframes for 2022 -> Jan 2024.")

tsms_dfs_reformatted_partI = []
for i in range(len(tsms_dfs_partI)):
    df = tsms_dfs_partI[i]
    print(f"\tReformatting {station_mapper[df['Station Number'].iloc[0]]}")

    df.columns = df.columns.str.strip()

    with warnings.catch_warnings(): # supress warnings from printing to the console
        warnings.simplefilter("ignore", pd.errors.SettingWithCopyWarning)
        
        try:
            df['date'] = pd.to_datetime(df[['Year', 'Month', 'Day', 'Hour', 'Minute']], errors='coerce')
        except Exception as e:
            print(f"Error converting date for {station_mapper[df['Station Number'].iloc[0]]}: {e}")
    
    df.drop(
        ['Year', 'Month', 'Day', 'Hour', 'Minute',
         'Sunshine Duration', 'Mean Global Solar Radiation', 'Direct Solar Radiation Intensity',
         'Diffuse Solar Radiation Intensity', 'UVA Radiation Intensity', 'UVB Radiation Intensity',
         'Maximum Wind Speed at 10m', 'NRT Corrected Rainfall', 'PWS Current Rainfall', 'Mean Wind Speed at 10m',
         'Maximum Wind Direction', 'Maximum Wind Speed', 'Maximum Wind Time', 'Unnamed: 0'], 
        axis=1, 
        inplace=True
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", pd.errors.SettingWithCopyWarning)

        df['year_month'] = df['date'].dt.to_period('M')
        df['year_month_day'] = df['date'].dt.to_period('D')
        df['year_month_day_hour'] = df['date'].dt.to_period('H')
    
    tsms_dfs_reformatted_partI.append(df.drop_duplicates(subset='date', keep='first'))

print("Building reformatted dataframes for Jan 2024 -> Nov 2024.")

tsms_dfs_reformatted_partII = []
for i in range(len(tsms_dfs_partII)):
    df = tsms_dfs_partII[i]
    print(f"\tReformatting {station_mapper[df['Station Number'].iloc[0]]}")

    df.columns = df.columns.str.strip()

    with warnings.catch_warnings(): # supress warnings from printing to the console
        warnings.simplefilter("ignore", pd.errors.SettingWithCopyWarning)
        
        try:
            df['date'] = pd.to_datetime(df[['Year', 'Month', 'Day', 'Hour', 'Minute']], errors='coerce')
        except Exception as e:
            print(f"Error converting date for {station_mapper[df['Station Number'].iloc[0]]}: {e}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", pd.errors.SettingWithCopyWarning)

        df.drop(
            ['Year', 'Month', 'Day', 'Hour', 'Minute',
            'Sunshine Duration', 'Mean Global Solar Radiation', 'Direct Solar Radiation Intensity',
            'Diffuse Solar Radiation Intensity', 'UVA Radiation Intensity', 'UVB Radiation Intensity',
            'Maximum Wind Speed at 10m', 'NRT Corrected Rainfall', 'PWS Current Rainfall', 'Mean Wind Speed at 10m',
            'Maximum Wind Direction', 'Maximum Wind Speed', 'Maximum Wind Time'], 
            axis=1, 
            inplace=True
        )

        df['year_month'] = df['date'].dt.to_period('M')
        df['year_month_day'] = df['date'].dt.to_period('D')
        df['year_month_day_hour'] = df['date'].dt.to_period('H')
    
    tsms_dfs_reformatted_partII.append(df.drop_duplicates(subset='date', keep='first'))

# manually rearranging the order of jan 2024 - nov 2024 to match that of 1st data period
ankara = tsms_dfs_reformatted_partII[0]
konya = tsms_dfs_reformatted_partII[1]
adana = tsms_dfs_reformatted_partII[2]
tsms_dfs_reformatted_partII = [adana, ankara, konya]
# order of 1st data period determined by the order of the data files stored on local machine

print("Filling in datagaps.")

dfs_gaps_filled_partI = []
dfs_gaps_filled_partII = []

for i in range(len(tsms_dfs_reformatted_partI)):
    df_1 = tsms_dfs_reformatted_partI[i]
    df_2 = tsms_dfs_reformatted_partII[i]

    print(f"\tFilling {station_mapper[df_1['Station Number'].iloc[0]]}")

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)

        gaps_filled_df_ptI = func.fill_empty_rows(df_1, timedelta(minutes=1))
        gaps_filled_df_ptII = func.fill_empty_rows(df_2, timedelta(minutes=1))

    dfs_gaps_filled_partI.append(gaps_filled_df_ptI)
    dfs_gaps_filled_partII.append(gaps_filled_df_ptII)

print("Merging 1st and 2nd data periods.")

complete_records = []
for i in range(len(dfs_gaps_filled_partI)):
    df_1 = dfs_gaps_filled_partI[i]
    df_2 = dfs_gaps_filled_partII[i]

    print(f"\tMerging {station_mapper[df_1['Station Number'].iloc[0]]}")

    complete_record = pd.concat([df_1, df_2], axis=0, join='outer')

    complete_records.append(complete_record)

print("Creating final CSV's")

for df in complete_records:
    print(f"\tConverting {station_mapper[df['Station Number'].iloc[0]]}")

    file_path = os.path.join(
        data_destination, 
        f"{station_mapper[df['Station Number'].iloc[0]]}", 
        f"{station_mapper[df['Station Number'].iloc[0]]}_CompleteRecord.csv"
    )
    
    df.drop(columns=['Station Number'], axis=1, inplace=True)
    
    df.to_csv(file_path)
