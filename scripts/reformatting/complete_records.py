"""
Reads in pre-formatted daily files.
Writes to a TSV or CSV formatted aggregate file with all measurements per station.
"""

import os
import warnings
import pandas as pd
import numpy as np
from pathlib import Path

data_origin = "/Users/rzieber/Documents/3D-PAWS/Turkiye/raw/3DPAWS/2022_Jan-2024/"
data_destination = "/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/CSV_Format/3DPAWS/2022-Jan2024/TSMS00_SpaceSep/"

station_directories = [ # do not use for station TSMS06-08 from Adana
    "station_TSMS00/"#, "station_TSMS01/", "station_TSMS02/"      # Ankara
    #"station_TSMS03/", "station_TSMS04/", "station_TSMS05/"      # Konya
]
station_files = [] # list of lists of filenames under each station directory [[TSMS06 files], [TSMS07 files], [TSMS08 files]]
for station in station_directories: # sorted by filename
    station_files.append(sorted([f for f in os.listdir(data_origin + station) if os.path.isfile(os.path.join(data_origin + station, f))]))

# TSV Formatter --------------------------
# for i in range(len(station_files)): 
#     print(f"Reading station {station_directories[i][:len(station_directories[i])-1]}")

#     filename = station_directories[i][8:14]+'_Complete_Record.dat'
#     with open(data_destination+station_directories[i]+filename, 'w', newline='') as outfile:
#         outfile.write("year  mon  day  hour  min  int  bmp2_temp  bmp2_pres  bmp2_slp  bmp2_alt  bme2_hum  htu_temp  htu_hum  sth_temp  sth_hum  mcp9808  tipping  vis_light  ir_light  uv_light  wind_dir  wind_speed\n")

#         for file in station_files[i]: # go through each daily file at each station
#             with open(data_origin+station_directories[i]+file, 'r', encoding='utf-8', errors='replace') as infile:
#                 next(infile) # skip the header row
#                 for row in infile:
#                     outfile.write(row)

# CSV Formatter --------------------------
for i in range(len(station_files)):
    print(f"Reading station {station_directories[i][8:14]}")

    filename = station_directories[i][8:14]+'_Complete_Record.csv'
    filepath = Path(data_origin+station_directories[i])
    files = sorted([f for f in filepath.iterdir() if f.is_file() and f.name != '.DS_Store'])

    lines = None
    standardized_lines = []

    for file in files:
        print(f"\tReading file {file.name}")

        with open(file, 'r', encoding='utf-8', errors='replace') as f:
            next(f) # skip header
            lines = f.readlines()

        for i in range(len(lines)):
            line = lines[i]

            next_line = line.split(' ')
            standardized_line = [x.strip() for x in next_line if x != '']

            # also side note for future Rebecca -- a .dat created from .rtf will need to be manually named as .dat via the terminal,
            #   and you'll need to manually delete via nano the boiler plate that gets added to rtf's that you can't see in TextEdit 
            #   ( ༎ຶ ۝ ༎ຶ )
            if standardized_line[-1][-1] == '\\': # when a .dat file is created from .rtf, there's \'s at the end of each line
                standardized_line[-1] = standardized_line[-1][:len(standardized_line[-1])-1]

            standardized_lines.append(standardized_line)

    columns=[
            'year', 'mon', 'day', 'hour',  'min',  
            'bmp2_temp',  'bmp2_pres', 'bmp2_slp', 'bmp2_alt', 
            'bme_temp', 'bme_pres', 'bme_slp', 'bme_alt', 'bme2_hum', 
            'htu_temp', 'htu_hum', 'mcp9808', 
            'tipping', 'vis_light', 'ir_light', 'uv_light', 'wind_dir', 'wind_speed'
        ]
    df = pd.DataFrame(standardized_lines, columns=columns)
    
    df['int'] = 900
    df['sth_temp'] = np.nan
    df['sth_hum'] = np.nan

    df.drop(columns=['bme_temp', 'bme_pres', 'bme_slp', 'bme_alt'], inplace=True)

    columns_2 = [
        'year', 'mon', 'day', 'hour', 'min', 'int',
        'bmp2_temp', 'bmp2_pres', 'bmp2_slp', 'bmp2_alt',
        'bme2_hum', 'htu_temp', 'htu_hum', 'sth_temp', 'sth_hum', 'mcp9808',
        'tipping', 'vis_light', 'ir_light', 'uv_light', 'wind_dir', 'wind_speed'
    ]

    df = df[columns_2]

    df.set_index('year', inplace=True)

    df.to_csv(data_destination+filename[:len(filename)-4]+'_[FINAL].csv')

    # creating monthly and daily files for TSMS00 here because I need to move on with my life and I am literally so done reformatting data.
    # like, so done. so unbelievably done. i can taste freedom. i can see the light at the end of the tunnel. but i am here, still.
    # i grow weak. 
    df = pd.DataFrame(standardized_lines, columns=columns)
    df.rename(columns={"mon":"month", "min":"minute"}, inplace=True)

    with warnings.catch_warnings(): # supress warning from printing to the console
        warnings.simplefilter("ignore", pd.errors.SettingWithCopyWarning)
        
        try:
            df['date'] = pd.to_datetime(df[['year', 'month', 'day', 'hour', 'minute']], errors='coerce')
        except Exception as e:
            print(f"Error converting date for TSMS0{i}: {e}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", pd.errors.SettingWithCopyWarning)

        df['year_month'] = df['date'].dt.to_period('M')
        df['year_month_day'] = df['date'].dt.to_period('D')

    
    for year_month, grouped_df in df.groupby('year_month'):
        print(f"\tCreating CSV for {year_month}")

        df_monthly = grouped_df.drop(columns=['date', 'year_month', 'year_month_day'])
        df_monthly.set_index('year', inplace=True)
        
        df_monthly.to_csv(f"/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/CSV_Format/3DPAWS/2022-Jan2024/TSMS00_SpaceSep/monthly/TSMS00_{year_month}.csv")
    
    for year_month_day, grouped_df in df.groupby('year_month_day'):
        print(f"\tCreating CSV for {year_month_day}")

        df_daily = grouped_df.drop(columns=['date', 'year_month', 'year_month_day'])
        df_daily.set_index('year', inplace=True)

        df_daily.to_csv(f"/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/CSV_Format/3DPAWS/2022-Jan2024/TSMS00_SpaceSep/daily/TSMS00_{year_month_day}.csv")
