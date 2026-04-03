"""
This script generates a CSV which matches the format of the input file for final_paws_reformatter.py

Input files for final_paws_reformatter.py can be located at:
/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/CSV_Format/3DPAWS/2022-Jan2024/complete_record/
"""

import pandas as pd
import numpy as np
from pathlib import Path

TSMS00_filepath = "/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/CSV_Format/3DPAWS/complete_dataperiod/station_TSMS00/complete/TSMS00_CompleteRecord_FINAL.csv"

space_sep_folderpath = Path("/Users/rzieber/Documents/3D-PAWS/Turkiye/raw/3DPAWS/2022_Jan-2024/station_TSMS00/space-sep")
space_sep_files = sorted([f for f in space_sep_folderpath.iterdir() if f.is_file() and f.name != '.DS_Store'])

dfs = []

for i in range(len(space_sep_files)):
    filepath = str(space_sep_files[i])

    columns = ['mon', 'day', 'year', 'hour', 'min', 'bmp2_temp', 'bmp2_pres', 'bmp2_slp', 'bmp2_alt', 'bme2_temp', 'bme2_pres', 'bme2_slp', 'bme2_alt',
              'bme2_hum', 'htu_temp', 'htu_hum', 'mcp9808', 'tipping', 'vis_light', 'ir_light', 'uv_light', 'wind_dir', 'wind_speed']
        
    df = pd.read_csv(filepath, delim_whitespace=True, header=None, names=columns)

    df.drop(columns=['bme2_temp', 'bme2_pres', 'bme2_slp', 'bme2_alt'], inplace=True)

    df['int'] = 900
    df['sth_temp'] = np.nan
    df['sth_hum'] = np.nan

    df = df[['year', 'mon', 'day', 'hour', 'min', 'int', 
             'bmp2_temp', 'bmp2_pres', 'bmp2_slp', 'bmp2_alt', 'bme2_hum', 
             'htu_temp', 'htu_hum', 'sth_temp', 'sth_hum', 'mcp9808', 
             'tipping', 'vis_light', 'ir_light', 'uv_light', 'wind_dir', 'wind_speed']]

    dfs.append(df)

combined_df = pd.concat(dfs)

combined_df.set_index('year', inplace=True)

combined_df.to_csv("/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/CSV_Format/3DPAWS/2022-Jan2024/TSMS00_SpaceSep/TSMS00_Aug16-Sept8_[FINAL].csv")
