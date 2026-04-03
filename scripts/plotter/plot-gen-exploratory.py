"""
Initital Evaluation Plot Generator

PREREQUESITE:
The TSV's fed into the 'data_origin' variable have been standardized such that the datapoints are separated by an equal number
of tabs. In other words, 'data_origin' accepts a standard TSV. We formatted the data with variable number of tabs to create
human-readable columns when viewed in a text editor, so our data needed to be standardized before pandas could accept it.

INDENTED USAGE:
Uncomment each section that you want to generate plots for. Leave all other sections commented as the 'data_destination' 
variables need to be changed up top (until I find the spoons to rewire everything so this isn't necessary, but that'd
also make the code take ages to run so maybe it's for the best, idk). Sections are divided by the plot type (time-series,
wind rose, scatter plots) and the level of resolution(complete records, monthly records).
"""
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
from windrose import WindroseAxes
import matplotlib.cm as cm
import numpy as np
from scipy.stats import pearsonr
from sklearn.metrics import mean_squared_error
import seaborn as sns

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

data_origin = ...
data_destination = ...


station_variables = [ 
    "temp", "humidity", "actual_pressure", "sea_level_pressure", "wind", "total_rainfall"
]
variable_mapper = { # TSMS : 3DPAWS
    "temp":["bmp2_temp", "htu_temp", "mcp9808"],
    "humidity":["bme2_hum", "htu_hum"],
    "actual_pressure":"bmp2_pres",
    "sea_level_pressure":"bmp2_slp",
    "avg_wind_dir":"wind_dir", # both using 1-minute average
    "avg_wind_speed":"wind_speed", # both using 1-minute average
    "total_rainfall":"tipping"
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
    
# set up folder struct for each station where data is outputted
for i in range(len(station_directories)):
    try:
        os.makedirs(data_destination+station_directories[i], exist_ok=True)
        for file in station_files[i]:
            try:
                for var in station_variables:
                    os.makedirs(data_destination+station_directories[i]+var+'/', exist_ok=True)
                    os.makedirs(data_destination+station_directories[i]+var+'/raw/', exist_ok=True)
                    os.makedirs(data_destination+station_directories[i]+var+'/filtered_nulls/', exist_ok=True)
            except Exception as e:
                print("Error creating the directory: ", var)
    except Exception as e:
        print("Could not create ", station_directories[i][:len(station_directories[i])-1])
    
# -------------------------------------------------------------------------------------------------------------------------------
paws_dfs = []
tsms_dfs = []

for i in range(len(station_directories)):
    """
    =============================================================================================================================
    Create the 3D PAWS and TSMS dataframes.
    =============================================================================================================================
    """
    paws_df = None 
    tsms_df = None
    for file in station_files[i]:
        if file.startswith("TSMS"): # the 3D PAWS dataset starts with 'TSMS' and the TSMS dataset starts with 'paws'  :')
            paws_df = pd.read_csv( 
                            data_origin+station_directories[i]+file,
                            header=0,
                            low_memory=False
                        )
            paws_df.columns = paws_df.columns.str.strip()
            paws_df.rename(columns={'mon':'month', 'min':'minute'}, inplace=True)
            paws_df['date'] = pd.to_datetime(paws_df[['year', 'month', 'day', 'hour', 'minute']])
            
            paws_df.drop( # no reference data for these col's OR no data exists in these columns (e.g. sth) OR scalar (e.g. alt)
                        ['int', 'sth_temp', 'sth_hum', 'bmp2_alt', 'vis_light', 'ir_light', 'uv_light',
                            'year', 'month', 'day', 'hour', 'minute'], 
                        axis=1, 
                        inplace=True
                    )
            
            paws_df = paws_df[['date', 'bmp2_temp', 'htu_temp', 'mcp9808', 'bme2_hum', 'htu_hum', 'bmp2_pres',
                                'bmp2_slp', 'wind_dir', 'wind_speed', "tipping"]]
            
            paws_df['year_month'] = paws_df['date'].dt.to_period('M')
            paws_df['year_month_day'] = paws_df['date'].dt.to_period('D')
            paws_df['year_month_day_hour'] = paws_df['date'].dt.to_period('H')
            
            paws_df.set_index('date', inplace=True)

            paws_dfs.append(paws_df)

        else:
            tsms_df = pd.read_csv(
                            data_origin+station_directories[i]+file,
                            header=0,
                            low_memory=False
                        )
            tsms_df.columns = tsms_df.columns.str.strip()
            tsms_df.rename(columns={'mon':'month', 'min':'minute'}, inplace=True)
            tsms_df['date'] = pd.to_datetime(tsms_df[['year', 'month', 'day', 'hour', 'minute']])
            
            tsms_df.drop(['year', 'month', 'day', 'hour', 'minute'], axis=1, inplace=True)

            tsms_df = tsms_df[['date', 'temp', 'humidity', 'actual_pressure', 'sea_level_pressure', 
                                'avg_wind_dir', 'avg_wind_speed', 'total_rainfall']]
            
            tsms_df['year_month'] = tsms_df['date'].dt.to_period('M')
            tsms_df['year_month_day'] = tsms_df['date'].dt.to_period('D')
            tsms_df['year_month_day_hour'] = tsms_df['date'].dt.to_period('H')

            tsms_df.set_index('date', inplace=True) 

            tsms_dfs.append(tsms_df) 


    """
    =============================================================================================================================
    Create a time series plot of the 3D PAWS station data versus the TSMS reference station. COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]}: " \
    #                     "Time-series plots for temperature, humidity, actual & sea level pressure, and cumulative rainfall -- complete records")
    
    # tsms_FILTERED = tsms_df[paws_df.index[0]:paws_df.index[-1]]

    # Temperature ---------------------------------------------------------------------------------------------------------------
    # print("Temperature -- raw")
    # for t in variable_mapper['temp']:
    #     plt.figure(figsize=(20, 12))

    #     plt.plot(paws_df.index, paws_df[f'{t}'], marker='.', markersize=1, label=f"3D PAWS {t}")
    #     plt.plot(tsms_FILTERED.index, tsms_FILTERED['temp'], marker='.', markersize=1, alpha=0.25, label='TSMS')
    
    #     plt.title(f'{station_directories[i][8:14]} Temperature: 3D PAWS {t} versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Temperature (˚C)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"temp/raw/{station_directories[i][8:14]}_{t}.png")

    #     plt.clf()
    #     plt.close()

    # print("Temperature -- nulls filtered")
    # for t in variable_mapper['temp']:
    #     paws_df_FILTERED = paws_df[paws_df[f"{t}"] > -999.99]

    #     plt.figure(figsize=(20, 12))

    #     plt.plot(paws_df_FILTERED.index, paws_df_FILTERED[f'{t}'], marker='.', markersize=1, label=f"3D PAWS {t}")
    #     plt.plot(tsms_FILTERED.index, tsms_FILTERED['temp'], alpha=0.5, marker='.', markersize=1, label='TSMS')
    
    #     plt.title(f'{station_directories[i][8:14]} Temperature: 3D PAWS {t} versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Temperature (˚C)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_{t}_FILTERED.png")
        
    #     plt.clf()
    #     plt.close()

    # # Humidity ------------------------------------------------------------------------------------------------------------------
    # print("Humidity -- raw")
    # for h in variable_mapper['humidity']:
    #     plt.figure(figsize=(20, 12))

    #     plt.plot(paws_df.index, paws_df[f'{h}'], marker='.', markersize=1, label=f"3D PAWS {h}")
    #     plt.plot(tsms_FILTERED.index, tsms_FILTERED['humidity'], marker='.', markersize=1, label='TSMS')
    
    #     plt.title(f'{station_directories[i][8:14]} Humidity: 3D PAWS {h} versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Humidity (%)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"humidity/raw/{station_directories[i][8:14]}_{h}.png")
        
    #     plt.clf()
    #     plt.close()

    # print("Humidity -- nulls filtered")
    # for h in variable_mapper['humidity']:
    #     paws_df_FILTERED = paws_df[paws_df[f"{h}"] > -999.99]

    #     plt.figure(figsize=(20, 12))

    #     plt.plot(paws_df_FILTERED.index, paws_df_FILTERED[f'{h}'], marker='.', markersize=1, label=f"3D PAWS {h}")
    #     plt.plot(tsms_FILTERED.index, tsms_FILTERED['temp'], marker='.', markersize=1, label='TSMS')
    
    #     plt.title(f'{station_directories[i][8:14]} Humidity: 3D PAWS {h} versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Humidity (%)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"humidity/filtered_nulls/{station_directories[i][8:14]}_{h}_FILTERED.png")
        
    #     plt.clf()
    #     plt.close()

    
    # # Pressure ------------------------------------------------------------------------------------------------------------------
    # print("Actual pressure -- raw")
    # plt.figure(figsize=(20, 12))

    # plt.plot(paws_df.index, paws_df['bmp2_pres'], marker='.', markersize=1, label="3D PAWS bmp2_pres")
    # plt.plot(tsms_FILTERED.index, tsms_FILTERED['actual_pressure'], marker='.', markersize=1, label='TSMS')

    # plt.title(f'{station_directories[i][8:14]} Pressure: 3D PAWS bmp2_pres versus TSMS')
    # plt.xlabel('Date')
    # plt.ylabel('Pressure (mbar)')
    # plt.xticks(rotation=45)

    # plt.legend()

    # plt.grid(True)
    # plt.tight_layout()
    # plt.savefig(data_destination+station_directories[i]+f"actual_pressure/raw/{station_directories[i][8:14]}_bmp2_pressure.png")
    
    # plt.clf()
    # plt.close()


    # print("Actual pressure -- nulls filtered")
    # paws_df_FILTERED = paws_df[paws_df["bmp2_pres"] > -999.99] 
    # tsms_df_FILTERED = tsms_FILTERED[(tsms_FILTERED['actual_pressure']) > 0]

    # plt.figure(figsize=(20, 12))

    # plt.plot(paws_df_FILTERED.index, paws_df_FILTERED['bmp2_pres'], marker='.', markersize=1, label="3D PAWS bmp2_pres")
    # plt.plot(tsms_df_FILTERED.index, tsms_df_FILTERED['actual_pressure'], marker='.', markersize=1, label='TSMS')

    # plt.title(f'{station_directories[i][8:14]} Pressure: 3D PAWS bmp2_pres versus TSMS')
    # plt.xlabel('Date')
    # plt.ylabel('Pressure (mbar)')
    # plt.xticks(rotation=45)

    # plt.legend()

    # plt.grid(True)
    # plt.tight_layout()
    # plt.savefig(data_destination+station_directories[i]+f"actual_pressure/filtered_nulls/{station_directories[i][8:14]}_bmp2_pressure_FILTERED.png")
    
    # plt.clf()
    # plt.close()


    # # Sea Level Pressure --------------------------------------------------------------------------------------------------------
    # print("Sea level pressure -- raw")
    # plt.figure(figsize=(20, 12)) 

    # plt.plot(paws_df.index, paws_df['bmp2_slp'], marker='.', markersize=1, label="3D PAWS bmp2_slp")
    # plt.plot(tsms_FILTERED.index, tsms_FILTERED['sea_level_pressure'], marker='.', markersize=1, label='TSMS')

    # plt.title(f'{station_directories[i][8:14]} Sea Level Pressure: 3D PAWS bmp2_slp versus TSMS')
    # plt.xlabel('Date')
    # plt.ylabel('Pressure (mbar)')
    # plt.xticks(rotation=45)

    # plt.legend()

    # plt.grid(True)
    # plt.tight_layout()
    # plt.savefig(data_destination+station_directories[i]+f"sea_level_pressure/raw/{station_directories[i][8:14]}_bmp2_slp.png")
    
    # plt.clf()
    # plt.close()


    # print("Sea level pressure -- nulls filtered")
    # paws_df_FILTERED = paws_df[paws_df["bmp2_slp"] > -999.99] 
    # tsms_df_FILTERED = tsms_FILTERED[(tsms_FILTERED['sea_level_pressure']) > 0]

    # plt.figure(figsize=(20, 12))

    # plt.plot(paws_df_FILTERED.index, paws_df_FILTERED['bmp2_slp'], marker='.', markersize=1, label="3D PAWS bmp2_slp")
    # plt.plot(tsms_df_FILTERED.index, tsms_df_FILTERED['sea_level_pressure'], marker='.', markersize=1, label='TSMS')

    # plt.title(f'{station_directories[i][8:14]} Sea Level Pressure: 3D PAWS bmp2_slp versus TSMS')
    # plt.xlabel('Date')
    # plt.ylabel('Pressure (mbar)')
    # plt.xticks(rotation=45)

    # plt.legend()

    # plt.grid(True)
    # plt.tight_layout()
    # plt.savefig(data_destination+station_directories[i]+f"sea_level_pressure/filtered_nulls/{station_directories[i][8:14]}_bmp2_slp_FILTERED.png")
    
    # plt.clf()
    # plt.close()


    # # Rainfall Accumulation --------------------------------------------------------------------------------------------------------
    # print("Rainfall accumulation -- nulls filtered")
    # for paws_station in station_directories: 
    #     paws_df_FILTERED = paws_df[paws_df['tipping'] >= 0].copy().reset_index()
    #     tsms_df_FILTERED = tsms_df[(tsms_df['total_rainfall']) >= 0].copy().reset_index()

    #     if station_directories[i] == "station_TSMS08/":
    #         exclude_garbage_start = pd.to_datetime("2023-04-08")
    #         exclude_garbage_end = pd.to_datetime("2023-04-15")
    #         paws_df_FILTERED = paws_df_FILTERED[
    #             ~((paws_df_FILTERED['date'] >= exclude_garbage_start) & (paws_df_FILTERED['date'] <= exclude_garbage_end))
    #         ]
    #     elif station_directories[i] == "station_TSMS04/":
    #         exclude_garbage = pd.to_datetime("2022-09-01")
    #         tsms_df_FILTERED = tsms_df_FILTERED[
    #             (tsms_df_FILTERED['date'] >= exclude_garbage) & \
    #             (tsms_df_FILTERED['date'] <= paws_df_FILTERED['date'].iloc[-1])
    #         ]
    #         paws_df_FILTERED = paws_df_FILTERED[
    #             (paws_df_FILTERED['date'] >= exclude_garbage) & \
    #             (paws_df_FILTERED['date'] <= paws_df_FILTERED['date'].iloc[-1])
    #         ]

    #     merged_df = pd.merge(paws_df_FILTERED, tsms_df_FILTERED, on='date', how='inner')  # to eliminate bias

    #     merged_df['cumulative_rainfall_3DPAWS'] = merged_df['tipping'].cumsum()
    #     merged_df['cumulative_rainfall_TSMS'] = merged_df['total_rainfall'].cumsum()

    #     plt.figure(figsize=(20, 12))

    #     plt.plot(merged_df['date'], merged_df['cumulative_rainfall_3DPAWS'], marker='.', markersize=1, label="3D PAWS")
    #     plt.plot(merged_df['date'], merged_df['cumulative_rainfall_TSMS'], marker='.', markersize=1, label='TSMS')

    #     plt.title(f'{station_directories[i][8:14]} Rainfall Accumulation: 3D PAWS versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Rainfall (mm)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"total_rainfall/filtered_nulls/{station_directories[i][8:14]}_rainfall_accumulation_FILTERED.png")
        
    #     plt.clf()
    #     plt.close()


    """
    =============================================================================================================================
    Create time series plots of the 3 temperature sensors compared to TSMS. COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][:len(station_directories[i])-1]} Temperature Comparison")

    # tsms_FILTERED = tsms_df[paws_df.index[0]:paws_df.index[-1]]

    # paws_df_FILTERED = paws_df[
    #     (paws_df["bmp2_temp"] > -50) | (paws_df["htu_temp"] > -50) | (paws_df["mcp9808"] > -50)
    #     ]

    # plt.figure(figsize=(20, 12))

    # plt.plot(paws_df_FILTERED.index, paws_df_FILTERED["bmp2_temp"], marker='.', markersize=1, label=f"3D PAWS bmp2_temp")
    # plt.plot(paws_df_FILTERED.index, paws_df_FILTERED["htu_temp"], marker='.', markersize=1, label=f"3D PAWS htu_temp")
    # plt.plot(paws_df_FILTERED.index, paws_df_FILTERED["mcp9808"], marker='.', markersize=1, label=f"3D PAWS mcp9808")
    # plt.plot(tsms_FILTERED.index, tsms_FILTERED['temp'], alpha=0.5, marker='.', markersize=1, label='TSMS')

    # plt.title(f'{station_directories[i][8:14]} Temperature Comparison: 3D PAWS versus TSMS')
    # #plt.title(f'{station_directories[i][8:14]} Temperature Comparison: 3D PAWS')
    # plt.xlabel('Date')
    # plt.ylabel('Temperature (˚C)')
    # plt.xticks(rotation=45)

    # plt.legend()

    # plt.grid(True)
    # plt.tight_layout()
    # plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_temp_comparison_FILTERED.png")
    
    # plt.clf()
    # plt.close()


    """
    =============================================================================================================================
    Create time series plots of the 3 temperature sensors compared to TSMS. MONTHLY RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][:len(station_directories[i])-1]} Temperature Comparison -- nulls filtered")

    # tsms_df_FILTERED = tsms_df[paws_df.index[0]:paws_df.index[-1]]
    
    # paws_df_FILTERED = paws_df.replace(-999.99, np.nan)
    # tsms_df_FILTERED = tsms_df_FILTERED.replace(-999.99, np.nan, inplace=True)

    # paws_df_FILTERED = paws_df[
    #     (paws_df[f"bmp2_temp"] != -999.99) & (paws_df['htu_temp'] != -999.99) & (paws_df['mcp9808'] != -999.99)
    # ]
    # paws_df_FILTERED = paws_df_FILTERED[paws_df_FILTERED['htu_temp'] > -50.0]
    # paws_df_FILTERED = paws_df_FILTERED[paws_df_FILTERED['mcp9808'] > -50.0]    

    # paws_df_FILTERED.to_csv(f'/Users/rzieber/Downloads/{station_directories[i][8:14]}_paws_df_filtered.csv')

    # tsms_df_FILTERED = tsms_df_FILTERED[
    #     (tsms_df_FILTERED['temp'] > -50.0)
    # ]

    # for year_month, paws_group in paws_df_FILTERED.groupby('year_month'):
    #     tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]
    #     #tsms_group = tsms_df_FILTERED.groupby('year_month')

    #     plt.figure(figsize=(20, 12))

    #     plt.plot(paws_group.index, paws_group["bmp2_temp"], marker='.', markersize=1, label=f"3D PAWS bmp2_temp")
    #     plt.plot(paws_group.index, paws_group["htu_temp"], marker='.', markersize=1, label=f"3D PAWS htu_temp")
    #     plt.plot(paws_group.index, paws_group["mcp9808"], marker='.', markersize=1, label=f"3D PAWS mcp9808")
    #     plt.plot(tsms_group.index, tsms_group['temp'], marker='.', markersize=1, label='TSMS')
    
    #     plt.title(f'{station_directories[i][8:14]} Temperature Comparison for {year_month}: 3D PAWS versus TSMS')
    #     #plt.title(f'{station_directories[i][8:14]} Temperature Comparison for {year_month}: 3D PAWS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Temperature (˚C)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_temp_comparison_{year_month}_FILTERED.png")
        
    #     plt.clf()
    #     plt.close()


    # """
    # =============================================================================================================================
    # Create wind rose plots of the 3D PAWS station data as well as the TSMS reference station. COMPLETE RECORDS
    # =============================================================================================================================
    # """
    # # 3D PAWS  ------------------------------------------------------------------------------------------------------------------
    # print("3D PAWS -- nulls filtered")
    # paws_df.reset_index(inplace=True)
    # paws_df['date'] = pd.to_datetime(paws_df['date'])

    # # Convert the 'wind_speed' column to numeric, forcing errors to NaN
    # paws_df['wind_speed'] = pd.to_numeric(paws_df['wind_speed'], errors='coerce')

    # # Filter out rows where 'wind_speed' is NaN
    # paws_df_FILTERED = paws_df[
    #     ((paws_df["wind_speed"].notna()) & (paws_df["wind_speed"] >= 0))
    #     ]
    # paws_df_FILTERED = paws_df_FILTERED[paws_df_FILTERED["wind_speed"] >= 3.0] # filter out variable winds 6 knots
    # paws_df_FILTERED.set_index('date', inplace=True)

    # # wind_speed_bins = [0, 2.0, 4.0, 6.0, 8.0, 10.0]       # for variable winds
    # # labels = ['0-2.0 m/s', '2.0-4.0 m/s', '4.0-6.0 m/s', '6.0-8.0 m/s', '8.0-10.0 m/s']
    # wind_speed_bins = [2.0, 4.0, 6.0, 8.0, 10.0]         # for non-variable winds
    # labels = ['2.0-4.0 m/s', '4.0-6.0 m/s', '6.0-8.0 m/s', '8.0-10.0 m/s']

    # first_timestamp = paws_df_FILTERED.index[0]
    # last_timestamp = paws_df_FILTERED.index[-1]
    # # first_timestamp = pd.Timestamp("2022-09-09 00:00") # for reproducing TSMS study period
    # # last_timestamp = pd.Timestamp("2023-02-24 12:42")

    # paws_df_FILTERED.loc[:, 'wind_speed_category'] = pd.cut(paws_df_FILTERED['wind_speed'], bins=wind_speed_bins, labels=labels, right=False)

    # ax = WindroseAxes.from_ax()
    # ax.bar(paws_df_FILTERED['wind_dir'], paws_df_FILTERED['wind_speed'], normed=True, opening=0.8, edgecolor='white', bins=wind_speed_bins)
    # ax.set_legend(title=f"{station_directories[i][8:len(station_directories[i])-1]} Wind Rose")

    # # ax.set_rmax(35)
    # # ax.set_yticks([7, 14, 21, 28, 35])
    # # ax.set_yticklabels(['7%', '14%', '21%', '28%', '35%']) # for complete records
    # ax.set_rmax(80)
    # ax.set_yticks([16, 32, 48, 64, 80])
    # ax.set_yticklabels(['16%', '32%', '48%', '64%', '80%']) # for complete records w/ non-variable winds
        
    # ax.grid(True, linewidth=0.5)  # Thinner grid lines can improve readability

    # plt.savefig(data_destination+station_directories[i]+f"wind/filtered_nulls/{station_directories[i][8:14]}_3DPAWS_windrose_FILTERED.png")
    # plt.clf()
    # plt.close()

    
    # # TSMS ----------------------------------------------------------------------------------------------------------------------
    # print("TSMS -- raw")
    # tsms_df.reset_index(inplace=True)
    # tsms_df['date'] = pd.to_datetime(tsms_df['date'])

    # tsms_df_FILTERED = tsms_df[
    #     ~((tsms_df['avg_wind_speed'] == 0.0) & (tsms_df['avg_wind_dir'] == 0.0)) # filter out 0.0 pair wind speed & dir
    #     ] 
    # tsms_df_FILTERED = tsms_df_FILTERED[tsms_df_FILTERED['avg_wind_speed'] >= 3.0] # filter out variable winds
    # tsms_df_FILTERED.set_index('date', inplace=True)

    # tsms_subset = tsms_df_FILTERED.loc[first_timestamp:last_timestamp]

    # tsms_subset.loc[:, 'wind_speed_category'] = pd.cut(tsms_subset['avg_wind_speed'], bins=wind_speed_bins, labels=labels, right=False)

    # ax = WindroseAxes.from_ax() # TSMS data was already cleaned
    # ax.bar(tsms_subset['avg_wind_dir'], tsms_subset['avg_wind_speed'], normed=True, opening=0.8, edgecolor='white', bins=wind_speed_bins)
    # ax.set_legend(title=f"TSMS Wind Rose")
    
    # # ax.set_rmax(35)
    # # ax.set_yticks([7, 14, 21, 28, 35])
    # # ax.set_yticklabels(['7%', '14%', '21%', '28%', '35%']) # for complete records
    # ax.set_rmax(80)
    # ax.set_yticks([16, 32, 48, 64, 80])
    # ax.set_yticklabels(['16%', '32%', '48%', '64%', '80%']) # for non-variable winds

    # ax.grid(True, linewidth=0.5)  # Thinner grid lines can improve readability

    # plt.savefig(data_destination+station_directories[i]+f"wind/raw/{station_directories[i][8:14]}_windrose.png")
    # plt.clf()
    # plt.close()


    """
    =============================================================================================================================
    Create a time series plot of the 3D PAWS station data versus the TSMS reference station. MONTHLY RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]}: " \
    #                    "Time-series plots for temperature, humidity, actual pressure and sea level pressure -- monthly records")
    
    # tsms_df_FILTERED = tsms_df[paws_df.index[0]:paws_df.index[-1]]

    # # Temperature ---------------------------------------------------------------------------------------------------------------
    # print("Temperature -- raw")
    # for t in variable_mapper['temp']:
    #     for year_month, paws_group in paws_df.groupby('year_month'):
    #         tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #         plt.figure(figsize=(20, 12))

    #         plt.plot(paws_group.index, paws_group[f'{t}'], marker='.', markersize=1, label=f"3D PAWS {t}")
    #         plt.plot(tsms_group.index, tsms_group['temp'], marker='.', markersize=1, label='TSMS')
        
    #         plt.title(f'{station_directories[i][8:14]} Temperature for {year_month}: 3D PAWS {t} versus TSMS')
    #         plt.xlabel('Date')
    #         plt.ylabel('Temperature (˚C)')
    #         plt.xticks(rotation=45)

    #         plt.legend()

    #         plt.grid(True)
    #         plt.tight_layout()
    #         plt.savefig(data_destination+station_directories[i]+f"temp/raw/{station_directories[i][8:14]}_{t}_{year_month}.png")
            
    #         plt.clf()
    #         plt.close()

    # print("Temperature -- nulls filtered")
    # for t in variable_mapper['temp']:
    #     paws_df_FILTERED = paws_df[(paws_df[f"{t}"] > -999.99)]

    #     for year_month, paws_group in paws_df_FILTERED.groupby('year_month'):
    #         tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #         plt.figure(figsize=(20, 12))

    #         plt.plot(paws_group.index, paws_group[f'{t}'], marker='.', markersize=1, label=f"3D PAWS {t}")
    #         plt.plot(tsms_group.index, tsms_group['temp'], marker='.', markersize=1, label='TSMS')
        
    #         plt.title(f'{station_directories[i][8:14]} Temperature for {year_month}: 3D PAWS {t} versus TSMS')
    #         plt.xlabel('Date')
    #         plt.ylabel('Temperature (˚C)')
    #         plt.xticks(rotation=45)

    #         plt.legend()

    #         plt.grid(True)
    #         plt.tight_layout()
    #         plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_{t}_{year_month}_FILTERED.png")
            
    #         plt.clf()
    #         plt.close()


    # # Humidity ------------------------------------------------------------------------------------------------------------------
    # print("Humidity -- raw")
    # for h in variable_mapper['humidity']:
    #     for year_month, paws_group in paws_df.groupby('year_month'):
    #         tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #         plt.figure(figsize=(20, 12))

    #         plt.plot(paws_group.index, paws_group[f'{h}'], marker='.', markersize=1, label=f"3D PAWS {h}")
    #         plt.plot(tsms_group.index, tsms_group['humidity'], marker='.', markersize=1, label='TSMS')
        
    #         plt.title(f'{station_directories[i][8:14]} Humidity for {year_month}: 3D PAWS {h} versus TSMS')
    #         plt.xlabel('Date')
    #         plt.ylabel('Humidity (%)')
    #         plt.xticks(rotation=45)

    #         plt.legend()

    #         plt.grid(True)
    #         plt.tight_layout()
    #         plt.savefig(data_destination+station_directories[i]+f"humidity/raw/{station_directories[i][8:14]}_{h}_{year_month}.png")
            
    #         plt.clf()
    #         plt.close()

    # print("Humidity -- nulls filtered")
    # for h in variable_mapper['humidity']:
    #     paws_df_FILTERED = paws_df[(paws_df[f"{h}"] > -999.99)]

    #     for year_month, paws_group in paws_df_FILTERED.groupby('year_month'):
    #         tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #         plt.figure(figsize=(20, 12))

    #         plt.plot(paws_group.index, paws_group[f'{h}'], marker='.', markersize=1, label=f"3D PAWS {h}")
    #         plt.plot(tsms_group.index, tsms_group['humidity'], marker='.', markersize=1, label='TSMS')
        
    #         plt.title(f'{station_directories[i][8:14]} Humidity for {year_month}: 3D PAWS {h} versus TSMS')
    #         plt.xlabel('Date')
    #         plt.ylabel('Humidity (%)')
    #         plt.xticks(rotation=45)

    #         plt.legend()

    #         plt.grid(True)
    #         plt.tight_layout()
    #         plt.savefig(data_destination+station_directories[i]+f"humidity/filtered_nulls/{station_directories[i][8:14]}_{h}_{year_month}_FILTERED.png")
            
    #         plt.clf()
    #         plt.close()


    # # Pressure ------------------------------------------------------------------------------------------------------------------
    # print("Pressure -- raw")
    # for year_month, paws_group in paws_df.groupby("year_month"):
    #     tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #     plt.figure(figsize=(20, 12))

    #     plt.plot(paws_group.index, paws_group['bmp2_pres'], marker='.', markersize=1, label="3D PAWS bmp2_pres")
    #     plt.plot(tsms_group.index, tsms_group['actual_pressure'], marker='.', markersize=1, label='TSMS')

    #     plt.title(f'{station_directories[i][8:14]} Pressure for {year_month}: 3D PAWS bmp2_pres versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Pressure (mbar)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"actual_pressure/raw/{station_directories[i][8:14]}_bmp2_pres_{year_month}.png")
        
    #     plt.clf()
    #     plt.close()

    # print("Pressure -- nulls filtered")
    # paws_df_FILTERED = paws_df[(paws_df['bmp2_pres'] > -999.99)]
    # tsms_df_FILTERED = tsms_df_FILTERED[(tsms_df_FILTERED['actual_pressure']) > 0]
    # tsms_df_FILTERED.to_csv("/Users/rzieber/Downloads/tsms_df_pressure_FILTERED.csv")
    # for year_month, paws_group in paws_df_FILTERED.groupby("year_month"):
    #     tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #     plt.figure(figsize=(20, 12))

    #     plt.plot(paws_group.index, paws_group['bmp2_pres'], marker='.', markersize=1, label="3D PAWS bmp2_pres")
    #     plt.plot(tsms_group.index, tsms_group['actual_pressure'], marker='.', markersize=1, label='TSMS')

    #     plt.title(f'{station_directories[i][8:14]} Pressure for {year_month}: 3D PAWS bmp2_pres versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Pressure (mbar)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"actual_pressure/filtered_nulls/{station_directories[i][8:14]}_bmp2_pres_{year_month}_FILTERED.png")
        
    #     plt.clf()
    #     plt.close()

    
    # # Sea Level Pressure --------------------------------------------------------------------------------------------------------
    # print("Sea level pressure -- raw")
    # for year_month, paws_group in paws_df.groupby("year_month"):
    #     tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #     plt.figure(figsize=(20, 12))

    #     plt.plot(paws_group.index, paws_group['bmp2_slp'], marker='.', markersize=1, label="3D PAWS bmp2_slp")
    #     plt.plot(tsms_group.index, tsms_group['sea_level_pressure'], marker='.', markersize=1, label='TSMS')

    #     plt.title(f'{station_directories[i][8:14]} Sea Level Pressure for {year_month}: 3D PAWS bmp2_slp versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Pressure (mbar)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"sea_level_pressure/raw/{station_directories[i][8:14]}_bmp2_slp_{year_month}.png")
        
    #     plt.clf()
    #     plt.close()


    # print("Sea level pressure -- nulls filtered")
    # paws_df_FILTERED = paws_df[(paws_df['bmp2_slp'] > -999.99)]
    # tsms_df_FILTERED = tsms_df_FILTERED[(tsms_df_FILTERED['sea_level_pressure']) > 0]
    # for year_month, paws_group in paws_df_FILTERED.groupby("year_month"):
    #     tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #     plt.figure(figsize=(20, 12))

    #     plt.plot(paws_group.index, paws_group['bmp2_slp'], marker='.', markersize=1, label="3D PAWS bmp2_slp")
    #     plt.plot(tsms_group.index, tsms_group['sea_level_pressure'], marker='.', markersize=1, label='TSMS')

    #     plt.title(f'{station_directories[i][8:14]} Sea Level Pressure for {year_month}: 3D PAWS bmp2_slp versus TSMS')
    #     plt.xlabel('Date')
    #     plt.ylabel('Pressure (mbar)')
    #     plt.xticks(rotation=45)

    #     plt.legend()

    #     plt.grid(True)
    #     plt.tight_layout()
    #     plt.savefig(data_destination+station_directories[i]+f"sea_level_pressure/filtered_nulls/{station_directories[i][8:14]}_bmp2_slp_{year_month}_FILTERED.png")
        
    #     plt.clf()
    #     plt.close()


    """
    =============================================================================================================================
    Create wind rose plots of the 3D PAWS station data as well as the TSMS reference station. MONTHLY RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]}: Wind roses for 3D PAWS and TSMS -- monthly records")

    # # 3D PAWS -------------------------------------------------------------------------------------------------------------------
    # print("3D PAWS -- nulls filtered")
    # paws_df.reset_index(inplace=True)
    # paws_df['date'] = pd.to_datetime(paws_df['date'])

    # # Convert the 'wind_speed' column to numeric and filter out NaN's (and variable winds)
    # paws_df['wind_speed'] = pd.to_numeric(paws_df['wind_speed'], errors='coerce')
    # paws_df_FILTERED = paws_df[(paws_df["wind_speed"] >= 0)]
    # #paws_df_FILTERED = paws_df_FILTERED[paws_df_FILTERED['wind_speed'] >= 3.0]
    # paws_df_FILTERED.set_index('date', inplace=True)

    # first_timestamp = paws_df_FILTERED.index[0]
    # last_timestamp = paws_df_FILTERED.index[-1]
    # # first_timestamp = pd.Timestamp("2022-09-09 00:00") # for replicating the TSMS intercomparison study
    # # last_timestamp = pd.Timestamp("2023-02-24 12:42")

    # paws_wind_speed_bins = [0, 2.0, 4.0, 6.0, 8.0, 10.0]
    # paws_labels = ['0-2.0 m/s', '2.0-4.0 m/s', '4.0-6.0 m/s', '6.0-8.0 m/s', '8.0-10.0 m/s']

    # paws_df_FILTERED.loc[:, 'wind_speed_category'] = pd.cut(paws_df_FILTERED['wind_speed'], bins=paws_wind_speed_bins, labels=paws_labels, right=False)

    # for year_month, paws_group in paws_df_FILTERED.groupby("year_month"): # monthly 3D PAWS wind filtered for nulls
    #     plt.figure(figsize=(20, 12))

    #     ax = WindroseAxes.from_ax()
    #     ax.bar(paws_group['wind_dir'], paws_group['wind_speed'], normed=True, opening=0.8, edgecolor='white', bins=paws_wind_speed_bins)
    #     ax.set_legend(title=f"{station_directories[i][8:len(station_directories[i])-1]} 3D PAWS Wind Rose for {year_month}")
        
    #     ax.set_rmax(60)
    #     ax.set_yticks([12, 24, 36, 48, 60])
    #     ax.set_yticklabels(['12%', '24%', '36%', '48%', '60%']) # for monthly records
    #     # ax.set_rmax(100)
    #     # ax.set_yticks([20, 40, 60, 80, 100])
    #     # ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%']) # for monthly records w/ 6 knot winds filtered
            
    #     ax.grid(True, linewidth=0.5)  # Thinner grid lines can improve readability

    #     plt.savefig(data_destination+station_directories[i]+f"wind/filtered_nulls/{station_directories[i][8:14]}_3DPAWS_windrose_{year_month}_FILTERED.png")
    #     plt.clf()
    #     plt.close()


    # # TSMS ----------------------------------------------------------------------------------------------------------------------
    # print("TSMS -- raw") # TSMS dataset was already cleaned
    # tsms_df.reset_index(inplace=True)
    # tsms_df['date'] = pd.to_datetime(tsms_df['date'])

    # # Filter out rows where wind speed and wind direction are both 0.0 (and variable winds)
    # tsms_df_FILTERED = tsms_df[~((tsms_df['avg_wind_speed'] == 0.0) & (tsms_df['avg_wind_dir'] == 0.0))]
    # #tsms_df_FILTERED = tsms_df_FILTERED[tsms_df_FILTERED['avg_wind_speed'] >= 3.0]
    # tsms_df_FILTERED.set_index('date', inplace=True)

    # tsms_wind_speed_bins = [0, 2.0, 4.0, 6.0, 8.0, 10.0]
    # tsms_labels = ['0-2.0 m/s', '2.0-4.0 m/s', '4.0-6.0 m/s', '6.0-8.0 m/s', '8.0-10.0 m/s']

    # tsms_subset = tsms_df_FILTERED.loc[first_timestamp:last_timestamp]

    # tsms_subset.loc[:, 'wind_speed_category'] = pd.cut(tsms_subset['avg_wind_speed'], bins=tsms_wind_speed_bins, labels=tsms_labels, right=False)

    # for year_month, tsms_group in tsms_subset.groupby("year_month"):
    #     plt.figure(figsize=(20, 12))

    #     ax = WindroseAxes.from_ax()
    #     ax.bar(tsms_group['avg_wind_dir'], tsms_group['avg_wind_speed'], normed=True, opening=0.8, edgecolor='white', bins=tsms_wind_speed_bins)
    #     ax.set_legend(title=f"TSMS Wind Rose for {year_month}")
        
    #     ax.set_rmax(60)
    #     ax.set_yticks([12, 24, 36, 48, 60])
    #     ax.set_yticklabels(['12%', '24%', '36%', '48%', '60%']) # for monthly records
    #     # ax.set_rmax(100)
    #     # ax.set_yticks([20, 40, 60, 80, 100])
    #     # ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%']) # for monthly records w/ 6 knot winds filtered
            
    #     ax.grid(True, linewidth=0.5)  # Thinner grid lines can improve readability

    #     plt.savefig(data_destination+station_directories[i]+f"wind/raw/{station_directories[i][8:14]}_TSMS_windrose_{year_month}.png")
    #     plt.clf()
    #     plt.close()


    """
    =============================================================================================================================
    Create scatter plots for each 3D PAWS sensor compared to the TSMS reference data. COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]}: " \
    #                    "Scatter plots for temperature, humidity, actual pressure, sea level pressure, and wind -- complete records\n" \
    #                    "3D PAWS vs TSMS")

    # for variable in station_variables: 
    #     print(f"{variable} -- 3D PAWS vs TSMS")

    #     if variable == 'wind': # scatters of wind are pretty much useless (but they're still on the shared drive if u really wanna know)
    #         continue

    #     if variable == 'temp' or variable == 'humidity': # contain multiple types of sensors
    #         for v in variable_mapper[f'{variable}']:
    #             paws_df_FILTERED = paws_df[(paws_df[f"{v}"] > -999.99)].copy()
    #             tsms_df_FILTERED = tsms_df[(tsms_df[variable] > -999.99)].copy()

    #             # Reset index to use 'date' as a column for merging
    #             paws_df_FILTERED = paws_df_FILTERED.reset_index()
    #             tsms_df_FILTERED = tsms_df_FILTERED.reset_index()
                
    #             merged_df = pd.merge(
    #                 paws_df_FILTERED[['date', f"{v}"]],
    #                 tsms_df_FILTERED[['date', f"{variable}"]],
    #                 on='date',
    #                 how='inner'
    #             )

    #             plt.figure(figsize=(20, 12))

    #             plt.scatter(merged_df[f"{v}"], merged_df[variable], alpha=0.5, s=10)

    #             if not merged_df.empty: # no data for the bme2 humidity sensor
    #                 # Calculate and plot trend line
    #                 m, b = np.polyfit(merged_df[f"{v}"], merged_df[variable], 1)
    #                 plt.plot(merged_df[f"{v}"], m*merged_df[f"{v}"] + b, color='red', linewidth=2, label='Trend line')

    #                 # Calculate correlation coefficient
    #                 corr_coef, _ = pearsonr(merged_df[f"{v}"], merged_df[variable])
    #                 plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #                 # Calculate RMSE
    #                 rmse = np.sqrt(mean_squared_error(merged_df[variable], merged_df[f"{v}"]))
    #                 textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #                 bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #                 plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                         verticalalignment='top', bbox=bbox_props)

    #                 plt.title(f'{station_directories[i][8:14]} 3D PAWS {v} versus TSMS')
    #                 plt.xlabel(f'3D PAWS {v}')
    #                 plt.ylabel(f"TSMS {variable}")

    #                 plt.legend()
    #                 plt.grid(True)
    #                 plt.tight_layout()

    #                 plt.savefig(data_destination+station_directories[i]+f"{variable}/filtered_nulls/{v}_FILTERED.png")
    #             else:
    #                 print("No data for the bme humidity sensor. CSV created in Downloads folder")
    #                 merged_df.to_csv(f"/Users/rzieber/Downloads/empty_df_{station_directories[i][:len(station_directories[i])-1]}_{variable}_{v}")

    #     else: # actual_pressure, sea_level_pressure, rainfall
    #         paws_df_FILTERED = paws_df[(paws_df[variable_mapper[variable]] >= 0)].copy()
    #         tsms_df_FILTERED = tsms_df[(tsms_df[variable] >= 0)].copy() 

    #         # Reset index to use 'date' as a column for merging
    #         paws_df_FILTERED = paws_df_FILTERED.reset_index()
    #         tsms_df_FILTERED = tsms_df_FILTERED.reset_index()

    #         merged_df = pd.merge( 
    #             paws_df_FILTERED,
    #             tsms_df_FILTERED,
    #             on='date',
    #             how='inner'
    #         )

    #         if variable == 'actual_pressure' or variable == 'sea_level_pressure':
    #             plt.figure(figsize=(20, 12))

    #             plt.scatter(merged_df[f"{variable_mapper[variable]}"], merged_df[variable], alpha=0.5, s=10)

    #             # Calculate and plot trend line
    #             m, b = np.polyfit(merged_df[f"{variable_mapper[variable]}"], merged_df[variable], 1)
    #             plt.plot(merged_df[f"{variable_mapper[variable]}"], m*merged_df[f"{variable_mapper[variable]}"] + b, color='red', linewidth=2, label='Trend line')

    #             # Calculate correlation coefficient
    #             corr_coef, _ = pearsonr(merged_df[f"{variable_mapper[variable]}"], merged_df[variable])
    #             plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #             # Calculate RMSE
    #             rmse = np.sqrt(mean_squared_error(merged_df[variable], merged_df[f"{variable_mapper[variable]}"]))
    #             textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #             bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #             plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                     verticalalignment='top', bbox=bbox_props)

    #             plt.title(f'{station_directories[i][8:14]} 3D PAWS {variable_mapper[variable]} versus TSMS')
    #             plt.xlabel(f'3D PAWS {variable_mapper[variable]}')
    #             plt.ylabel(f"TSMS {variable}")

    #             plt.legend()
    #             plt.grid(True)
    #             plt.tight_layout()

    #             plt.savefig(data_destination+station_directories[i]+f"{variable}/filtered_nulls/{variable_mapper[variable]}_FILTERED.png")
    #         else: # if variable == 'total_rainfall'
    #             # need to create hourly aggregated values instead of 1-min ob comparison, which is literally a useless comparison
    #             hourly_totals = merged_df.groupby('year_month_day_hour_x')[[f"{variable_mapper[variable]}", f"{variable}"]].sum().reset_index()

    #             hours = hourly_totals['year_month_day_hour_x'].dt.day
    #             paws_values = hourly_totals[f"{variable_mapper[variable]}"]
    #             tsms_values = hourly_totals[f"{variable}"]

    #             index = range(len(hours))

    #             plt.figure(figsize=(20, 12))

    #             plt.scatter(merged_df[f"{variable_mapper[variable]}"], merged_df[variable], alpha=0.5, s=10)

    #             # Calculate and plot trend line
    #             m, b = np.polyfit(merged_df[f"{variable_mapper[variable]}"], merged_df[variable], 1)
    #             plt.plot(merged_df[f"{variable_mapper[variable]}"], m*merged_df[f"{variable_mapper[variable]}"] + b, color='red', linewidth=2, label='Trend line')

    #             # Calculate correlation coefficient
    #             corr_coef, _ = pearsonr(merged_df[f"{variable_mapper[variable]}"], merged_df[variable])
    #             plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #             # Calculate RMSE
    #             rmse = np.sqrt(mean_squared_error(merged_df[variable], merged_df[f"{variable_mapper[variable]}"]))
    #             textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #             bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #             plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                     verticalalignment='top', bbox=bbox_props)

    #             plt.title(f'{station_directories[i][8:14]} 3D PAWS {variable_mapper[variable]} versus TSMS')
    #             plt.xlabel(f'3D PAWS {variable_mapper[variable]}')
    #             plt.ylabel(f"TSMS {variable}")

    #             plt.legend()
    #             plt.grid(True)
    #             plt.tight_layout()

    #             plt.savefig(data_destination+station_directories[i]+f"{variable}/filtered_nulls/{variable_mapper[variable]}_FILTERED.png")
    
    # plt.clf()
    # plt.close()


    """
    =============================================================================================================================
    Create scatter plots for each 3D PAWS sensor compared to other 3D PAWS sensors (temp and hum only). COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]}: " \
    #                    "Scatter plots for temperature and humidity -- complete records\n3D PAWS vs 3DPAWS")
    
    # paws_df_bmp_FILTERED = paws_df[(paws_df["bmp2_temp"] > -999.99)].copy().reset_index()
    # paws_df_htu_FILTERED = paws_df[(paws_df["htu_temp"] > -999.99)].copy().reset_index()
    # paws_df_mcp_FILTERED = paws_df[(paws_df["mcp9808"] > -999.99)].copy().reset_index()

    # merged_bmp_vs_htu = pd.merge(
    #     paws_df_bmp_FILTERED[['date', "bmp2_temp"]],
    #     paws_df_htu_FILTERED[['date', 'htu_temp']],
    #     on='date',
    #     how='inner'
    # )
    # merged_bmp_vs_mcp = pd.merge(
    #     paws_df_bmp_FILTERED[['date', "bmp2_temp"]],
    #     paws_df_mcp_FILTERED[['date', 'mcp9808']],
    #     on='date',
    #     how='inner'
    # )
    # merged_htu_vs_mcp = pd.merge(
    #     paws_df_htu_FILTERED[['date', "htu_temp"]],
    #     paws_df_mcp_FILTERED[['date', 'mcp9808']],
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

    # plt.title(f'{station_directories[i][8:14]} -- 3D PAWS bmp2_temp versus 3D PAWS htu_temp')
    # plt.xlabel('3D PAWS bmp2_temp')
    # plt.ylabel('3D PAWS htu_temp')    

    # plt.legend()
    # plt.grid(True)
    # plt.tight_layout()  

    # plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_bmp_vs_htu_FILTERED.png")    

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

    # plt.title(f'{station_directories[i][8:14]} -- 3D PAWS bmp2_temp versus 3D PAWS mcp9808')
    # plt.xlabel('3D PAWS bmp2_temp')
    # plt.ylabel('3D PAWS mcp9808')    

    # plt.legend()
    # plt.grid(True)
    # plt.tight_layout()  

    # plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_bmp_vs_mcp9808_FILTERED.png")    

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

    # plt.title(f'{station_directories[i][8:14]} -- 3D PAWS mcp9808 versus 3D PAWS htu_temp')
    # plt.xlabel('3D PAWS mcp9808')
    # plt.ylabel('3D PAWS htu_temp')    

    # plt.legend()
    # plt.grid(True)
    # plt.tight_layout()  

    # plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_mcp9808_vs_htu_FILTERED.png")    

    # plt.clf()
    # plt.close()  
   
    # # ---------------------------------------------------------------------------------------------------------------

    # paws_df_htu_FILTERED = paws_df[(paws_df["htu_hum"] > -999.99)].copy().reset_index()
    # paws_df_bme_FILTERED = paws_df[(paws_df["bme2_hum"] > -999.99)].copy().reset_index()

    # merged_htu_vs_bme = pd.merge(
    #     paws_df_htu_FILTERED[['date', "htu_hum"]],
    #     paws_df_bme_FILTERED[['date', 'bme2_hum']],
    #     on='date',
    #     how='inner'
    # )

    # if not merged_htu_vs_bme.empty:
    #     plt.figure(figsize=(20, 12))

    #     plt.scatter(merged_htu_vs_bme["htu_hum"], merged_htu_vs_bme["bme2_hum"], alpha=0.5, s=10)

    #     m, b = np.polyfit(merged_htu_vs_bme["htu_hum"], merged_htu_vs_bme["bme2_hum"], 1)
    #     plt.plot(merged_htu_vs_bme["bme2_hum"], m*merged_htu_vs_bme["bme2_hum"] + b, color='red', linewidth=2, label='Trend line')

    #     corr_coef, _ = pearsonr(merged_htu_vs_bme["htu_hum"], merged_htu_vs_bme["bme2_hum"])
    #     plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #     rmse = np.sqrt(mean_squared_error(merged_htu_vs_bme["htu_hum"], merged_htu_vs_bme["bme2_hum"]))
    #     textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #     bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #     plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #             verticalalignment='top', bbox=bbox_props)

    #     plt.title(f'{station_directories[i][8:14]} -- 3D PAWS htu_hum versus 3D PAWS bme2_hum')
    #     plt.xlabel('3D PAWS htu_hum')
    #     plt.ylabel('3D PAWS bme2_hum')    

    #     plt.legend()
    #     plt.grid(True)
    #     plt.tight_layout()  

    #     plt.savefig(data_destination+station_directories[i]+f"humidity/filtered_nulls/{station_directories[i][8:14]}_htu_vs_bme_FILTERED.png")    

    #     plt.clf()
    #     plt.close()  
    
    # else:
    #     print("No data for bme\n")



    """
    =============================================================================================================================
    Create scatter plots for each 3D PAWS sensor compared to the TSMS reference data. MONTHLY RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]}: " \
    #                    "Scatter plots for temperature, humidity, actual pressure, sea level pressure, and wind -- complete records\n" \
    #                     "3D PAWS vs TSMS, MONTHLY RECORDS")

    # for variable in station_variables: 
    #     print(f"{variable} -- 3D PAWS vs TSMS")

    #     if variable == 'total_rainfall':
    #         continue

    #     if variable == 'temp' or variable == 'humidity': # contain multiple types of sensors
    #         for v in variable_mapper[f'{variable}']:
    #             paws_df_FILTERED = paws_df[(paws_df[f"{v}"] > -999.99)].copy()
    #             tsms_df_FILTERED = tsms_df[(tsms_df[variable] > -999.99)].copy()
    #             for year_month, paws_group in paws_df_FILTERED.groupby("year_month"):
    #                 tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #                 # Reset index to use 'date' as a column for merging
    #                 paws_group = paws_group.reset_index()
    #                 tsms_group = tsms_group.reset_index()
                    
    #                 merged_df = pd.merge(
    #                     paws_group[['date', f"{v}"]],
    #                     tsms_group[['date', f"{variable}"]],
    #                     on='date',
    #                     how='inner'
    #                 )

    #                 plt.figure(figsize=(20, 12))

    #                 plt.scatter(merged_df[f"{v}"], merged_df[variable], alpha=0.5, s=10)

    #                 if not merged_df.empty: # no data for the bme2 humidity sensor
    #                     # Calculate and plot trend line
    #                     m, b = np.polyfit(merged_df[f"{v}"], merged_df[variable], 1)
    #                     plt.plot(merged_df[f"{v}"], m*merged_df[f"{v}"] + b, color='red', linewidth=2, label='Trend line')

    #                     # Calculate correlation coefficient
    #                     corr_coef, _ = pearsonr(merged_df[f"{v}"], merged_df[variable])
    #                     plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #                     # Calculate RMSE
    #                     rmse = np.sqrt(mean_squared_error(merged_df[variable], merged_df[f"{v}"]))
    #                     textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #                     bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #                     plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                             verticalalignment='top', bbox=bbox_props)

    #                     plt.title(f'{station_directories[i][8:14]} {variable} for {year_month} -- 3D PAWS {v} versus TSMS')
    #                     plt.xlabel(f'3D PAWS {v}')
    #                     plt.ylabel(f"TSMS {variable}")

    #                     plt.legend()
    #                     plt.grid(True)
    #                     plt.tight_layout()

    #                     plt.savefig(data_destination+station_directories[i]+f"{variable}/filtered_nulls/{station_directories[i][8:14]}_{v}_{year_month}_FILTERED.png")
    #                 else:
    #                     print("No data for the bme humidity sensor. CSV created in Downloads folder")
    #                     merged_df.to_csv(f"/Users/rzieber/Downloads/empty_df_{station_directories[i][:len(station_directories[i])-1]}_{variable}_{v}")

    #                 plt.clf()
    #                 plt.close()

    #     else: # actual_pressure, sea_level_pressure, wind
    #         if variable == 'wind':
    #             paws_df_speed_FILTERED = paws_df[(paws_df["wind_speed"] > -999.99)].copy().reset_index()
    #             paws_df_dir_FILTERED = paws_df[(paws_df["wind_dir"] > -999.99)].copy().reset_index()
    #             tsms_df_COPY = tsms_df.copy().reset_index()

    #             for year_month, paws_group in paws_df_speed_FILTERED.groupby("year_month"):
    #                 tsms_group = tsms_df_COPY[tsms_df_COPY['year_month'] == year_month]

    #                 merged_speed_df = pd.merge( 
    #                     paws_group[['date', "wind_speed"]],
    #                     tsms_group[['date', "avg_wind_speed"]],
    #                     on='date',
    #                     how='inner'
    #                 )

    #                 # --------------------------------------------------------------------------------------------------- wind speed
    #                 plt.figure(figsize=(20, 12))

    #                 plt.scatter(merged_speed_df["wind_speed"], merged_speed_df["avg_wind_speed"], alpha=0.5, s=10)

    #                 try:
    #                     # Calculate and plot trend line
    #                     m, b = np.polyfit(merged_speed_df["wind_speed"], merged_speed_df["avg_wind_speed"], 1)
    #                     plt.plot(merged_speed_df["wind_speed"], m*merged_speed_df["wind_speed"] + b, color='red', linewidth=2, label='Trend line')

    #                     # Calculate correlation coefficient
    #                     corr_coef, _ = pearsonr(merged_speed_df["wind_speed"], merged_speed_df["avg_wind_speed"])
    #                     plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #                     # Calculate RMSE
    #                     rmse = np.sqrt(mean_squared_error(merged_speed_df["avg_wind_speed"], merged_speed_df["wind_speed"]))
    #                     textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #                     bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #                     plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                             verticalalignment='top', bbox=bbox_props)

    #                     plt.title(f'{station_directories[i][8:14]} Wind Speed for {year_month} -- 3D PAWS versus TSMS')
    #                     plt.xlabel(f'3D PAWS wind_speed')
    #                     plt.ylabel(f"TSMS avg_wind_speed")

    #                     plt.legend()
    #                     plt.grid(True)
    #                     plt.tight_layout()

    #                     plt.savefig(data_destination+station_directories[i]+f"{variable}/filtered_nulls/{station_directories[i][8:14]}_wind_speed_{year_month}_FILTERED.png")

    #                     plt.clf()
    #                     plt.close()
                    
    #                 except np.linalg.LinAlgError as e:
    #                     print(f"{year_month} most likely has a long string of 0.0's for wind speed in 3D PAWS data.\nA csv of the afflicted month has been created in troubleshooting folder.")
    #                     with open ("/Users/rzieber/Documents/3D-PAWS/Turkiye/troubleshooting/WindSpeedZero/afflicted_stations.txt", 'a', encoding='utf-8', errors='replace') as f:
    #                         f.write(f"{station_directories[i][8:14]} {year_month} has a wind speed issue.\n")
    #                     merged_speed_df.to_csv(f"/Users/rzieber/Documents/3D-PAWS/Turkiye/troubleshooting/WindSpeedZero/AfflictedStationsCSV/{station_directories[i][8:14]}_{year_month}_windspeed.csv")

    #             for year_month, paws_group in paws_df_dir_FILTERED.groupby("year_month"):
    #                 tsms_group = tsms_df_COPY[tsms_df_COPY['year_month'] == year_month]

    #                 merged_dir_df = pd.merge( 
    #                     paws_group[['date', "wind_dir"]],
    #                     tsms_group[['date', "avg_wind_dir"]],
    #                     on='date',
    #                     how='inner'
    #                 )

    #                 # --------------------------------------------------------------------------------------------------- wind dir

    #                 plt.figure(figsize=(20, 12))

    #                 plt.scatter(merged_dir_df["wind_dir"], merged_dir_df["avg_wind_dir"], alpha=0.5, s=10)

    #                 try:
    #                     # Calculate and plot trend line
    #                     m, b = np.polyfit(merged_dir_df["wind_dir"], merged_dir_df["avg_wind_dir"], 1)
    #                     plt.plot(merged_dir_df["wind_dir"], m*merged_dir_df["wind_dir"] + b, color='red', linewidth=2, label='Trend line')

    #                     # Calculate correlation coefficient
    #                     corr_coef, _ = pearsonr(merged_dir_df["wind_dir"], merged_dir_df["avg_wind_dir"])
    #                     plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #                     # Calculate RMSE
    #                     rmse = np.sqrt(mean_squared_error(merged_dir_df["avg_wind_dir"], merged_dir_df["wind_dir"]))
    #                     textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #                     bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #                     plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                             verticalalignment='top', bbox=bbox_props)

    #                     plt.title(f'{station_directories[i][8:14]} Wind Direction for {year_month} -- 3D PAWS versus TSMS')
    #                     plt.xlabel(f'3D PAWS wind_dir')
    #                     plt.ylabel(f"TSMS avg_wind_dir")

    #                     plt.legend()
    #                     plt.grid(True)
    #                     plt.tight_layout()

    #                     plt.savefig(data_destination+station_directories[i]+f"{variable}/filtered_nulls/{station_directories[i][8:14]}_wind_dir_{year_month}_FILTERED.png")

    #                     plt.clf()
    #                     plt.close()
                    
    #                 except np.linalg.LinAlgError as e:
    #                     print(f"{year_month} most likely has a long string of 0.0's for wind direction in 3D PAWS data.\nA csv of the afflicted month has been created in troubleshooting folder.")
    #                     with open ("/Users/rzieber/Documents/3D-PAWS/Turkiye/troubleshooting/WindSpeedZero/afflicted_stations.txt", 'a', encoding='utf-8', errors='replace') as f:
    #                         f.write(f"{station_directories[i][8:14]} {year_month} has a wind direction issue.\n")
    #                     merged_speed_df.to_csv(f"/Users/rzieber/Documents/3D-PAWS/Turkiye/troubleshooting/WindSpeedZero/AfflictedStationsCSV/{station_directories[i][8:14]}_{year_month}_winddir.csv")


    #         else:
    #             paws_df_FILTERED = paws_df[(paws_df[variable_mapper[variable]] > -999.99)].copy()
    #             tsms_df_FILTERED = tsms_df[(tsms_df[variable] > 0)].copy() 

    #             for year_month, paws_group in paws_df_FILTERED.groupby("year_month"):
    #                 tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #                 # Reset index to use 'date' as a column for merging
    #                 paws_group = paws_group.reset_index()
    #                 tsms_group = tsms_group.reset_index()

    #                 merged_df = pd.merge( 
    #                     paws_group[['date', f"{variable_mapper[variable]}"]],
    #                     tsms_group[['date', f"{variable}"]],
    #                     on='date',
    #                     how='inner'
    #                 )

    #                 plt.figure(figsize=(20, 12))

    #                 plt.scatter(merged_df[f"{variable_mapper[variable]}"], merged_df[variable], alpha=0.5, s=10)

    #                 # Calculate and plot trend line
    #                 m, b = np.polyfit(merged_df[f"{variable_mapper[variable]}"], merged_df[variable], 1)
    #                 plt.plot(merged_df[f"{variable_mapper[variable]}"], m*merged_df[f"{variable_mapper[variable]}"] + b, color='red', linewidth=2, label='Trend line')

    #                 # Calculate correlation coefficient
    #                 corr_coef, _ = pearsonr(merged_df[f"{variable_mapper[variable]}"], merged_df[variable])
    #                 plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #                 # Calculate RMSE
    #                 rmse = np.sqrt(mean_squared_error(merged_df[variable], merged_df[f"{variable_mapper[variable]}"]))
    #                 textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #                 bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #                 plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                         verticalalignment='top', bbox=bbox_props)

    #                 plt.title(f'{station_directories[i][8:14]} {variable} for {year_month} -- 3D PAWS versus TSMS')
    #                 plt.xlabel(f'3D PAWS {variable_mapper[variable]}')
    #                 plt.ylabel(f"TSMS {variable}")

    #                 plt.legend()
    #                 plt.grid(True)
    #                 plt.tight_layout()

    #                 plt.savefig(data_destination+station_directories[i]+f"{variable}/filtered_nulls/{station_directories[i][8:14]}_{variable_mapper[variable]}_{year_month}_FILTERED.png")

    #                 plt.clf()
    #                 plt.close()

    """
    =============================================================================================================================
    Create scatter plots for each 3D PAWS sensor compared to other 3D PAWS sensors (temp and hum only). MONTHLY RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]}: " \
    #                    "Scatter plots for temperature and humidity -- complete records\n3D PAWS vs 3DPAWS")
    
    # paws_df_bmp_FILTERED = paws_df[(paws_df["bmp2_temp"] > -999.99)].copy().reset_index()
    # paws_df_htu_FILTERED = paws_df[(paws_df["htu_temp"] > -999.99)].copy().reset_index()
    # paws_df_mcp_FILTERED = paws_df[(paws_df["mcp9808"] > -999.99)].copy().reset_index()

    # for year_month, paws_bmp_group in paws_df_bmp_FILTERED.groupby("year_month"):
    #     paws_htu_group = paws_df_htu_FILTERED[paws_df_htu_FILTERED['year_month'] == year_month]

    #     merged_bmp_vs_htu = pd.merge(
    #         paws_bmp_group[['date', "bmp2_temp"]],
    #         paws_htu_group[['date', 'htu_temp']],
    #         on='date',
    #         how='inner'
    #     )

    #     plt.figure(figsize=(20, 12))

    #     plt.scatter(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"], alpha=0.5, s=10)

    #     m, b = np.polyfit(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"], 1)
    #     plt.plot(merged_bmp_vs_htu["htu_temp"], m*merged_bmp_vs_htu["htu_temp"] + b, color='red', linewidth=2, label='Trend line')

    #     corr_coef, _ = pearsonr(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"])
    #     plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #     rmse = np.sqrt(mean_squared_error(merged_bmp_vs_htu["bmp2_temp"], merged_bmp_vs_htu["htu_temp"]))
    #     textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #     bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #     plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #             verticalalignment='top', bbox=bbox_props)

    #     plt.title(f'{station_directories[i][8:14]} Temperature for {year_month} -- 3D PAWS bmp2_temp versus 3D PAWS htu_temp')
    #     plt.xlabel('3D PAWS bmp2_temp')
    #     plt.ylabel('3D PAWS htu_temp')    

    #     plt.legend()
    #     plt.grid(True)
    #     plt.tight_layout()  

    #     plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_bmp_vs_htu_{year_month}_FILTERED.png")    

    #     plt.clf()
    #     plt.close()  


    # for year_month, paws_bmp_group in paws_df_bmp_FILTERED.groupby("year_month"):
    #     paws_mcp_group = paws_df_mcp_FILTERED[paws_df_mcp_FILTERED['year_month'] == year_month]

    #     merged_bmp_vs_mcp = pd.merge(
    #         paws_df_bmp_FILTERED[['date', "bmp2_temp"]],
    #         paws_df_mcp_FILTERED[['date', 'mcp9808']],
    #         on='date',
    #         how='inner'
    #     )

    #     plt.figure(figsize=(20, 12))

    #     plt.scatter(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"], alpha=0.5, s=10)

    #     m, b = np.polyfit(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"], 1)
    #     plt.plot(merged_bmp_vs_mcp["bmp2_temp"], m*merged_bmp_vs_mcp["bmp2_temp"] + b, color='red', linewidth=2, label='Trend line')

    #     corr_coef, _ = pearsonr(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"])
    #     plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #     rmse = np.sqrt(mean_squared_error(merged_bmp_vs_mcp["bmp2_temp"], merged_bmp_vs_mcp["mcp9808"]))
    #     textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #     bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #     plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #             verticalalignment='top', bbox=bbox_props)

    #     plt.title(f'{station_directories[i][8:14]} Temperature for {year_month} -- 3D PAWS bmp2_temp versus 3D PAWS mcp9808')
    #     plt.xlabel('3D PAWS bmp2_temp')
    #     plt.ylabel('3D PAWS mcp9808')    

    #     plt.legend()
    #     plt.grid(True)
    #     plt.tight_layout()  

    #     plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_bmp_vs_mcp9808_{year_month}_FILTERED.png")    

    #     plt.clf()
    #     plt.close()  



    # for year_month, paws_htu_group in paws_df_htu_FILTERED.groupby("year_month"):
    #     paws_mcp_group = paws_df_mcp_FILTERED[paws_df_mcp_FILTERED['year_month'] == year_month]

    #     merged_htu_vs_mcp = pd.merge(
    #         paws_df_htu_FILTERED[['date', "htu_temp"]],
    #         paws_df_mcp_FILTERED[['date', 'mcp9808']],
    #         on='date',
    #         how='inner'
    #     )

    #     plt.figure(figsize=(20, 12))

    #     plt.scatter(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"], alpha=0.5, s=10)

    #     m, b = np.polyfit(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"], 1)
    #     plt.plot(merged_htu_vs_mcp["mcp9808"], m*merged_htu_vs_mcp["mcp9808"] + b, color='red', linewidth=2, label='Trend line')

    #     corr_coef, _ = pearsonr(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"])
    #     plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #     rmse = np.sqrt(mean_squared_error(merged_htu_vs_mcp["mcp9808"], merged_htu_vs_mcp["htu_temp"]))
    #     textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #     bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #     plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #             verticalalignment='top', bbox=bbox_props)

    #     plt.title(f'{station_directories[i]} Temperature for {year_month} -- 3D PAWS mcp9808 versus 3D PAWS htu_temp')
    #     plt.xlabel('3D PAWS mcp9808')
    #     plt.ylabel('3D PAWS htu_temp')    

    #     plt.legend()
    #     plt.grid(True)
    #     plt.tight_layout()  

    #     plt.savefig(data_destination+station_directories[i]+f"temp/filtered_nulls/{station_directories[i][8:14]}_mcp9808_vs_htu_{year_month}_FILTERED.png")    

    #     plt.clf()
    #     plt.close()  
   
    # # ---------------------------------------------------------------------------------------------------------------

    # paws_df_htu_FILTERED = paws_df[(paws_df["htu_hum"] > -999.99)].copy().reset_index()
    # paws_df_bme_FILTERED = paws_df[(paws_df["bme2_hum"] > -999.99)].copy().reset_index()

    # for year_month, paws_bme_group in paws_df_bme_FILTERED.groupby("year_month"):
    #     paws_htu_group = paws_df_htu_FILTERED[paws_df_htu_FILTERED['year_month'] == year_month]

    #     merged_htu_vs_bme = pd.merge(
    #         paws_df_htu_FILTERED[['date', "htu_hum"]],
    #         paws_df_bme_FILTERED[['date', 'bme2_hum']],
    #         on='date',
    #         how='inner'
    #     )

    #     if not merged_htu_vs_bme.empty:
    #         plt.figure(figsize=(20, 12))

    #         plt.scatter(merged_htu_vs_bme["htu_hum"], merged_htu_vs_bme["bme2_hum"], alpha=0.5, s=10)

    #         m, b = np.polyfit(merged_htu_vs_bme["htu_hum"], merged_htu_vs_bme["bme2_hum"], 1)
    #         plt.plot(merged_htu_vs_bme["bme2_hum"], m*merged_htu_vs_bme["bme2_hum"] + b, color='red', linewidth=2, label='Trend line')

    #         corr_coef, _ = pearsonr(merged_htu_vs_bme["htu_hum"], merged_htu_vs_bme["bme2_hum"])
    #         plt.text(0.05, 0.95, f'Correlation: {corr_coef:.2f}', transform=plt.gca().transAxes, fontsize=12, verticalalignment='top')

    #         rmse = np.sqrt(mean_squared_error(merged_htu_vs_bme["htu_hum"], merged_htu_vs_bme["bme2_hum"]))
    #         textstr = f'Correlation: {corr_coef:.2f}\nRMSE: {rmse:.2f}'
    #         bbox_props = dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white", alpha=0.8)
    #         plt.text(0.05, 0.95, textstr, transform=plt.gca().transAxes, fontsize=12,
    #                 verticalalignment='top', bbox=bbox_props)

    #         plt.title(f'{station_directories[i]} Humidity for {year_month} -- 3D PAWS htu_hum versus 3D PAWS bme2_hum')
    #         plt.xlabel('3D PAWS htu_hum')
    #         plt.ylabel('3D PAWS bme2_hum')    

    #         plt.legend()
    #         plt.grid(True)
    #         plt.tight_layout()  

    #         plt.savefig(data_destination+station_directories[i]+f"humidity/filtered_nulls/{station_directories[i][8:14]}_htu_vs_bme_{year_month}_FILTERED.png")    

    #         plt.clf()
    #         plt.close()  
        
    #     else:
    #         print("No data for bme\n")

    """
    =============================================================================================================================
    Create bar charts for monthly 3D PAWS rainfall accumulation compared to TSMS rainfall accumulation. COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]}: " \
    #                    "Bar charts for rainfall accumulation -- complete records")
    
    # paws_df_FILTERED = paws_df[paws_df['tipping'] >= 0].copy().reset_index()
    # tsms_df_FILTERED = tsms_df[(tsms_df['total_rainfall']) >= 0].copy().reset_index()

    # if station_directories[i] == "station_TSMS04/":
    #     exclude_garbage = pd.to_datetime("2022-09-01")
    #     tsms_df_REDUCED = tsms_df_FILTERED[
    #         (tsms_df_FILTERED['date'] >= exclude_garbage) & \
    #         (tsms_df_FILTERED['date'] <= paws_df_FILTERED['date'].iloc[-1])
    #     ]
    #     paws_df_FILTERED = paws_df_FILTERED[
    #         (paws_df_FILTERED['date'] >= exclude_garbage) & \
    #         (paws_df_FILTERED['date'] <= paws_df_FILTERED['date'].iloc[-1])
    #     ]
    # elif station_directories[i] == "station_TSMS08/":
    #     exclude_garbage_start = pd.to_datetime("2023-04-08")
    #     exclude_garbage_end = pd.to_datetime("2023-04-15")
    #     paws_df_FILTERED = paws_df_FILTERED[
    #         ~((paws_df_FILTERED['date'] >= exclude_garbage_start) & (paws_df_FILTERED['date'] <= exclude_garbage_end))
    #     ]
    #     paws_df_FILTERED.to_csv("/Users/rzieber/Downloads/paws_dfe_FILTERED_TSMS08_AprilGarbage.csv")   
    #     tsms_df_REDUCED = tsms_df_FILTERED
    # else:
    #     tsms_df_REDUCED = tsms_df_FILTERED[ # need to filter TSMS s.t. data timeframe equals PAWS
    #         (tsms_df_FILTERED['date'] >= paws_df_FILTERED['date'].iloc[0]) & \
    #         (tsms_df_FILTERED['date'] <= paws_df_FILTERED['date'].iloc[-1])
    #     ]

    # paws_totals = {}
    # tsms_totals = {}

    # for year_month, paws_grouped in paws_df_FILTERED.groupby("year_month"):
    #     tsms_grouped = tsms_df_REDUCED[tsms_df_REDUCED['year_month'] == year_month]

    #     print(f"{station_directories[i][8:14]} at {year_month}")

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

    # plt.figure(figsize=(20, 12))

    # bars1 = plt.bar(index, paws_values, width=0.35, color='blue', label='3DPAWS Rainfall')
    # bars2 = plt.bar([i + 0.35 for i in index], tsms_values, width=0.35, color='orange', label='TSMS Rainfall')

    # # Add labels, title, and legend
    # plt.xlabel('Month')
    # plt.ylabel('Cumulative Rainfall (mm)')
    # plt.title(f'{station_directories[i][8:14]} Monthly Rainfall Comparison: 3DPAWS vs TSMS')
    # plt.xticks([i + 0.35 / 2 for i in index], [str(month) for month in months], rotation=45)
    # plt.legend()

    # # Add numerical values above bars
    # for bar in bars1:
    #     yval = bar.get_height()
    #     plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 2), ha='center', va='bottom', fontsize=12)

    # for bar in bars2:
    #     yval = bar.get_height()
    #     plt.text(bar.get_x() + bar.get_width()/2, yval, round(yval, 2), ha='center', va='bottom', fontsize=12)

    # # Display the plot
    # plt.tight_layout()

    # # Save the plot
    # plt.savefig(data_destination+station_directories[i]+f"total_rainfall/filtered_nulls/{station_directories[i][8:14]}_rainfall_comparison_FILTERED.png")    
    
    # plt.clf()
    # plt.close()   

    """
    =============================================================================================================================
    Create bar charts for daily 3D PAWS rainfall accumulation compared to TSMS rainfall accumulation. MONTHLY RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]}: " \
    #                    "Bar charts for rainfall accumulation -- monthly records")
    
    # paws_df_FILTERED = paws_df[paws_df['tipping'] >= 0].copy().reset_index()
    # tsms_df_FILTERED = tsms_df[(tsms_df['total_rainfall']) >= 0].copy().reset_index()

    # if station_directories[i] == "station_TSMS08/":
    #     exclude_garbage_start = pd.to_datetime("2023-04-08")
    #     exclude_garbage_end = pd.to_datetime("2023-04-15")
    #     paws_df_FILTERED = paws_df_FILTERED[
    #         ~((paws_df_FILTERED['date'] >= exclude_garbage_start) & (paws_df_FILTERED['date'] <= exclude_garbage_end))
    #     ]
    #     paws_df_FILTERED.to_csv("/Users/rzieber/Downloads/paws_dfe_FILTERED_TSMS08_AprilGarbage.csv")   
        
    # for year_month, paws_grouped in paws_df_FILTERED.groupby("year_month"):
    #     tsms_grouped = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

    #     print(f"{station_directories[i][8:14]} at {year_month}")

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
    #     plt.title(f'{station_directories[i][8:14]} Daily Rainfall Comparison: 3DPAWS vs TSMS for {year_month}')
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
    #     plt.savefig(data_destination + station_directories[i] + f"total_rainfall/filtered_nulls/{station_directories[i][8:14]}_{year_month}_daily_rainfall_comparison_FILTERED.png")    
        
    #     plt.clf()
    #     plt.close()


    """
    Zoom in on June 3, 2023 for TSMS00 rainfall agreement w/ TSMS ref. station.
    """
    # paws_df.reset_index(inplace=True)
    # tsms_df.reset_index(inplace=True)

    # # Filter data for June 3, 2023
    # june_3_2023_PAWS = paws_df[(paws_df['date'] >= '2023-06-03 00:00:00') & (paws_df['date'] < '2023-06-04 00:00:00') & (paws_df['tipping'] >= 0)]
    # june_3_2023_TSMS = tsms_df[(tsms_df['date'] >= '2023-06-03 00:00:00') & (tsms_df['date'] < '2023-06-04 00:00:00') & (tsms_df['total_rainfall'] >= 0)]

    # # Plot the time series of rainfall
    # plt.figure(figsize=(20, 12))
    # plt.plot(june_3_2023_PAWS['date'], june_3_2023_PAWS['tipping'], marker='o', linestyle='-', color='blue', markersize=1)
    # plt.plot(june_3_2023_TSMS['date'], june_3_2023_TSMS['total_rainfall'], marker='o', linestyle='-', color='orange', markersize=1)
    # plt.title(f'{station_directories[i][8:14]} Rainfall Time Series on June 3, 2023')
    # plt.xlabel('Time')
    # plt.ylabel('Rainfall (mm)')
    # plt.xticks(rotation=45)
    # plt.grid(True)
    # plt.tight_layout()
    # plt.legend()

    # # Step 4: Show or save the plot
    # #plt.show()
    # plt.savefig(data_destination + station_directories[i] + f"total_rainfall/filtered_nulls/{station_directories[i][8:14]}_June-3-2023.png")    
                        

    """
    Wind direction analysis -- creating csv's with wind direction mapped to compass direction as a new column. Statistical
    analysis performed in Excel, counting all unique instances of the compass dir and comparing to TSMS to see if the raw
    data does in fact reflect what the wind rose is depicting.
    """
    # paws_copy = paws_df.copy()
    # paws_copy.reset_index(inplace=True)
    # paws_copy['date'] = pd.to_datetime(paws_copy['date'])
    # paws_copy.set_index('date', inplace=True)

    # first_timestamp = paws_copy.index[0]
    # last_timestamp = paws_copy.index[-1]

    # paws_copy['compass_direction'] = paws_copy['wind_dir'].apply(functions.get_compass_dir)
    # paws_copy.to_csv(data_destination+station_directories[i]+f"{station_directories[i][8:14]}_3DPAWS_wind_dir_analysis.csv")


    # tsms_copy = tsms_df.copy()
    # tsms_copy.reset_index(inplace=True)
    # tsms_copy['date'] = pd.to_datetime(tsms_copy['date'])

    # tsms_truncated = tsms_copy[(tsms_copy['date'] >= first_timestamp) & (tsms_copy['date'] <= last_timestamp)]
    # tsms_truncated.set_index('date', inplace=True)

    # tsms_truncated['compass_direction'] = tsms_truncated['avg_wind_dir'].apply(functions.get_compass_dir)
    # tsms_truncated.to_csv(data_destination+station_directories[i]+f"{station_directories[i][8:14]}_TSMS_wind_dir_analysis.csv")


    """
    =============================================================================================================================
    How to create aggregated columns
    =============================================================================================================================
    """
    # tsms_FILTERED = tsms_df[paws_df.index[0]: paws_df.index[-1]]

    # paws_stats_df = paws_df.copy()
    # paws_stats_df['the_date'] = paws_stats_df.index.date
    # tsms_stats_df = tsms_FILTERED.copy()
    # tsms_stats_df['the_date'] = tsms_stats_df.index.date

    # paws_stats_df.replace(-999.99, np.nan, inplace=True)
    # paws_stats_df.dropna(subset=['bmp2_temp', 'htu_temp', 'mcp9808', 'htu_hum', 'bme2_hum'], inplace=True)

    # paws_stats_df.to_csv(f"/Users/rzieber/Downloads/{station_directories[i][8:14]}_paws_df.csv")

    # daily_aggregates = paws_stats_df.groupby('the_date').agg({
    #     'bmp2_temp': ['max', 'min', 'median'],
    #     'htu_temp': ['max', 'min', 'median'],
    #     'mcp9808': ['max', 'min', 'median'],
    #     'htu_hum': ['max', 'min', 'median'],
    #     'bme2_hum': ['max', 'min', 'median']
    # })

    # # Flatten the column names
    # daily_aggregates.columns = ['_'.join(col).strip() for col in daily_aggregates.columns.values]

    # # Reset the index to have 'date' as a column again
    # daily_aggregates.reset_index(inplace=True)
    # daily_aggregates.rename(columns={'the_date':'date'}, inplace=True)
    
    # # Rename the columns to be more readable
    # daily_aggregates.columns = [
    #     'date', 
    #     'bmpTemp_max', 'bmpTemp_min', 'bmpTemp_median',
    #     'htuTemp_max', 'htuTemp_min', 'htuTemp_median',
    #     'mcpTemp_max', 'mcpTemp_min', 'mcpTemp_median', 
    #     'htuHum_max', 'htuHum_min', 'htuHum_median',
    #     'bmeHum_max', 'bmeHum_min', 'bmeHum_median'
    # ]

    # daily_aggregates['date'] = pd.to_datetime(daily_aggregates['date'], errors='coerce')
    # daily_aggregates['year_month'] = daily_aggregates['date'].dt.to_period('M')


    """
    =============================================================================================================================
    Creating box plots for temperature, relative humidity, and pressure. COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]} Box Plots")

    # paws_temp_cols = ['bmp2_temp', 'htu_temp', 'mcp9808']
    # paws_hum_cols = ['htu_hum', 'bme2_hum']
    # paws_pres_cols = ['bmp2_pres']
    # tsms_temp_cols = ['temp']
    # tsms_hum_cols = ['humidity']
    # tsms_pres_cols = ['actual_pressure']

    # paws_df_FILTERED = paws_df.replace(-999.99, np.nan)
    # tsms_df_FILTERED = tsms_df.replace(-999.99, np.nan)

    # combined_df = paws_df_FILTERED.merge(tsms_df_FILTERED[tsms_temp_cols + tsms_hum_cols + tsms_pres_cols], left_index=True, right_index=True)
    # combined_temp_df = combined_df[paws_temp_cols + ['temp']].copy()
    # combined_hum_df = combined_df[paws_hum_cols + ['humidity']].copy()
    # combined_pres_df = combined_df[paws_pres_cols + ['actual_pressure']].copy()

    # # temperature box plot
    # plt.figure(figsize=(20, 12))
    # sns.boxplot(data=combined_temp_df)

    # plt.title(f'{station_directories[i][8:14]} Temperature Box Plot: 3D-PAWS & TSMS')
    # plt.xlabel('Temperature Sensors')
    # plt.ylabel('Temperature (°C)')
    # plt.xticks([0, 1, 2, 3], ['BMP2 Temp', 'HTU Temp', 'MCP9808 Temp', 'TSMS Reference Temp'])
    # plt.grid(True)

    # plt.tight_layout()
    # plt.savefig(data_destination+station_directories[i]+f"/temp/filtered_nulls/{station_directories[i][8:14]}.png")
    # plt.clf()
    # plt.close()

    # # humidity boxplot
    # plt.figure(figsize=(20, 12))
    # sns.boxplot(data=combined_hum_df)

    # plt.title(f'{station_directories[i][8:14]} Humidity Box Plot: 3D-PAWS & TSMS')
    # plt.xlabel('Humidity Sensors')
    # plt.ylabel('Humidity (%)')
    # plt.xticks([0, 1, 2], ['HTU Hum', 'BME2 Hum', 'TSMS Reference Hum'])
    # plt.grid(True)

    # plt.tight_layout()
    # plt.savefig(data_destination+station_directories[i]+f"/humidity/filtered_nulls/{station_directories[i][8:14]}.png")
    # plt.clf()
    # plt.close()

    # # pressure box plots
    # plt.figure(figsize=(20, 12))
    # sns.boxplot(data=combined_pres_df)

    # plt.title(f'{station_directories[i][8:14]} Pressure Box Plot: 3D-PAWS & TSMS')
    # plt.xlabel('Pressure Sensors')
    # plt.ylabel('Station Pressure (hPa)')
    # plt.xticks([0, 1], ['BMP2 Pressure', 'TSMS Reference Pressure'])
    # plt.grid(True)

    # plt.tight_layout()
    # plt.savefig(data_destination+station_directories[i]+f"/actual_pressure/filtered_nulls/{station_directories[i][8:14]}.png")
    # plt.clf()
    # plt.close()


    """
    =============================================================================================================================
    Creating difference plots comparing temperature. Inner and outer joins. COMPLETE RECORDS
    =============================================================================================================================
    """
    # print(f"{station_directories[i][8:14]} Difference Plots")

    # paws_df_FILTERED = paws_df.replace(-999.99, np.nan)
    # tsms_df_FILTERED = tsms_df.replace(-999.99, np.nan)

    # # DO YOU WANT TO MERGE WITH TSMS???? OR WITH A DIFFERENT PAWS INSTRUMENT????
    # inner_df = pd.merge(paws_df_FILTERED, tsms_df_FILTERED, on='date', how='inner')  # all reporting simultaneously
    # outer_df = pd.merge(paws_df_FILTERED, tsms_df_FILTERED, on='date', how='outer')  # capture full dataset
   
    # temp_save_path = "/temp/filtered_nulls/"

    # Plot Bland-Altman for each pair of temperature sensors
    # bland_altman_plot(inner_df['bmp2_temp'], inner_df['htu_temp'], 'BMP Temperature', 'HTU Temperature', "inner", temp_save_path)
    # bland_altman_plot(inner_df['bmp2_temp'], inner_df['mcp9808'], 'BMP Temperature', 'MCP Temperature', "inner", temp_save_path)
    # bland_altman_plot(inner_df['htu_temp'], inner_df['mcp9808'], 'HTU Temperature', 'MCP Temperature', "inner", temp_save_path)

    # bland_altman_plot(outer_df['bmp2_temp'], outer_df['htu_temp'], 'BMP Temperature', 'HTU Temperature', "outer", temp_save_path)
    # bland_altman_plot(outer_df['bmp2_temp'], outer_df['mcp9808'], 'BMP Temperature', 'MCP Temperature', "outer", temp_save_path)
    # bland_altman_plot(outer_df['htu_temp'], outer_df['mcp9808'], 'HTU Temperature', 'MCP Temperature', "outer", temp_save_path)

    ##  ---> OTHER SENSORS NEED TO BE COMPARED ACROSS STATIONS SO CAN'T BE IN THIS LOOP

"""
comment this bottom part out when running the one above, or acutally that's dumb and you dont have to do that lol
"""    
# ankara_merged_df = paws_dfs[0].merge(paws_dfs[1], on='date', how='inner').merge(paws_dfs[2], on='date', how='inner')
# konya_merged_df = paws_dfs[3].merge(paws_dfs[4], on='date', how='inner').merge(paws_dfs[5], on='date', how='inner')
# adana_merged_df = paws_dfs[6].merge(paws_dfs[7], on='date', how='inner').merge(paws_dfs[8], on='date', how='inner')

# ankara_merged_df = ankara_merged_df.replace(-999.99, np.nan)
# konya_merged_df = konya_merged_df.replace(-999.99, np.nan)
# adana_merged_df = adana_merged_df.replace(-999.99, np.nan)


# ankara_merged_df = ankara_merged_df[(ankara_merged_df['bmp2_pres'] > -100) & (ankara_merged_df['bmp2_pres'] < 1500 -100)]
# ankara_merged_df = ankara_merged_df[(ankara_merged_df['bmp2_pres_x'] > -100) & (ankara_merged_df['bmp2_pres_x'] < 1500 -100)]
# ankara_merged_df = ankara_merged_df[(ankara_merged_df['bmp2_pres_y'] > -100 )& (ankara_merged_df['bmp2_pres_y'] < 1500 -100)]

# konya_merged_df = konya_merged_df[(konya_merged_df['bmp2_pres'] > -100 )& (konya_merged_df['bmp2_pres'] < 1500 -100)]
# konya_merged_df = konya_merged_df[(konya_merged_df['bmp2_pres_x'] > -100 )& (konya_merged_df['bmp2_pres_x'] < 1500 -100)]
# konya_merged_df = konya_merged_df[(konya_merged_df['bmp2_pres_y'] > -100) & (konya_merged_df['bmp2_pres_y'] < 1500 -100)]

# adana_merged_df = adana_merged_df[(adana_merged_df['bmp2_pres'] > -100) & (adana_merged_df['bmp2_pres'] < 1500 -100)]
# adana_merged_df = adana_merged_df[(adana_merged_df['bmp2_pres_x'] > -100) & (adana_merged_df['bmp2_pres_x'] < 1500 -100)]
# adana_merged_df = adana_merged_df[(adana_merged_df['bmp2_pres_y'] > -100) & (adana_merged_df['bmp2_pres_y'] < 1500 -100)]


# ankara_merged_df = ankara_merged_df[(ankara_merged_df['htu_hum'] > -100) & (ankara_merged_df['htu_hum'] < 1500 -100)]
# ankara_merged_df = ankara_merged_df[(ankara_merged_df['htu_hum_x'] > -100) & (ankara_merged_df['htu_hum_x'] < 1500 -100)]
# ankara_merged_df = ankara_merged_df[(ankara_merged_df['htu_hum_y'] > -100) & (ankara_merged_df['htu_hum_y'] < 1500 -100)]

# konya_merged_df = konya_merged_df[(konya_merged_df['htu_hum'] > -100) & (konya_merged_df['htu_hum'] < 1500 -100)]
# konya_merged_df = konya_merged_df[(konya_merged_df['htu_hum_x'] > -100) & (konya_merged_df['htu_hum_x'] < 1500 -100)]
# konya_merged_df = konya_merged_df[(konya_merged_df['htu_hum_y'] > -100) & (konya_merged_df['htu_hum_y'] < 1500 -100)]

# adana_merged_df = adana_merged_df[(adana_merged_df['htu_hum'] > -100) & (adana_merged_df['htu_hum'] < 1500 -100)]
# adana_merged_df = adana_merged_df[(adana_merged_df['htu_hum_x'] > -100) & (adana_merged_df['htu_hum_x'] < 1500 -100)]
# adana_merged_df = adana_merged_df[(adana_merged_df['htu_hum_y'] > -100) & (adana_merged_df['htu_hum_y'] < 1500 -100)]

# ankara_merged_df.reset_index(inplace=True)
# konya_merged_df.reset_index(inplace=True)
# adana_merged_df.reset_index(inplace=True)

# # ankara_merged_df.to_csv("/Users/rzieber/Downloads/new_ankara.csv")
# # konya_merged_df.to_csv("/Users/rzieber/Downloads/new_konya.csv")
# # adana_merged_df.to_csv("/Users/rzieber/Downloads/new_adana.csv")

# # Calculate differences -- Pressure
# ankara_merged_df['Pressure1-2'] = ankara_merged_df['bmp2_pres'] - ankara_merged_df['bmp2_pres_x']
# ankara_merged_df['Pressure1-3'] = ankara_merged_df['bmp2_pres'] - ankara_merged_df['bmp2_pres_y']
# ankara_merged_df['Pressure2-3'] = ankara_merged_df['bmp2_pres_x'] - ankara_merged_df['bmp2_pres_y']
# konya_merged_df['Pressure1-2'] = konya_merged_df['bmp2_pres'] - konya_merged_df['bmp2_pres_x']
# konya_merged_df['Pressure1-3'] = konya_merged_df['bmp2_pres'] - konya_merged_df['bmp2_pres_y']
# konya_merged_df['Pressure2-3'] = konya_merged_df['bmp2_pres_x'] - konya_merged_df['bmp2_pres_y']
# adana_merged_df['Pressure1-2'] = adana_merged_df['bmp2_pres'] - adana_merged_df['bmp2_pres_x']
# adana_merged_df['Pressure1-3'] = adana_merged_df['bmp2_pres'] - adana_merged_df['bmp2_pres_y']
# adana_merged_df['Pressure2-3'] = adana_merged_df['bmp2_pres_x'] - adana_merged_df['bmp2_pres_y']

# # Calculate differences -- Humidity
# ankara_merged_df['Humidity1-2'] = ankara_merged_df['htu_hum'] - ankara_merged_df['htu_hum_x']
# ankara_merged_df['Humidity1-3'] = ankara_merged_df['htu_hum'] - ankara_merged_df['htu_hum_y']
# ankara_merged_df['Humidity2-3'] = ankara_merged_df['htu_hum_x'] - ankara_merged_df['htu_hum_y']
# konya_merged_df['Humidity1-2'] = konya_merged_df['htu_hum'] - konya_merged_df['htu_hum_x']
# konya_merged_df['Humidity1-3'] = konya_merged_df['htu_hum'] - konya_merged_df['htu_hum_y']
# konya_merged_df['Humidity2-3'] = konya_merged_df['htu_hum_x'] - konya_merged_df['htu_hum_y']
# adana_merged_df['Humidity1-2'] = adana_merged_df['htu_hum'] - adana_merged_df['htu_hum_x']
# adana_merged_df['Humidity1-3'] = adana_merged_df['htu_hum'] - adana_merged_df['htu_hum_y']
# adana_merged_df['Humidity2-3'] = adana_merged_df['htu_hum_x'] - adana_merged_df['htu_hum_y']

# # Create the plot -- Pressure
# plt.figure(figsize=(20, 12))
# plt.plot(ankara_merged_df['date'], ankara_merged_df['Pressure1-2'], label='TSMS00 - TSMS01', marker='o')
# plt.plot(ankara_merged_df['date'], ankara_merged_df['Pressure1-3'], label='TSMS01 - TSMS03', marker='o')
# plt.plot(ankara_merged_df['date'], ankara_merged_df['Pressure2-3'], label='TSMS01 - TSMS03', marker='o')
# plt.title('Ankara Difference Plot: BMP Comparison')
# plt.xlabel('Time')
# plt.ylabel('Pressure Difference (hPa)')
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("/Users/rzieber/Documents/3D-PAWS/Turkiye/plots/difference_plots/cross_station/pressure/diff_plot_ankara.png")
# plt.clf()
# plt.close()

# plt.figure(figsize=(20, 12))
# plt.plot(konya_merged_df['date'], konya_merged_df['Pressure1-2'], label='TSMS03 - TSMS04', marker='o')
# plt.plot(konya_merged_df['date'], konya_merged_df['Pressure1-3'], label='TSMS03 - TSMS05', marker='o')
# plt.plot(konya_merged_df['date'], konya_merged_df['Pressure2-3'], label='TSMS04 - TSMS05', marker='o')
# plt.title('Konya Difference Plot: BMP Comparison')
# plt.xlabel('Time')
# plt.ylabel('Pressure Difference (hPa)')
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("/Users/rzieber/Documents/3D-PAWS/Turkiye/plots/difference_plots/cross_station/pressure/diff_plot_konya.png")
# plt.clf()
# plt.close()

# plt.figure(figsize=(20, 12))
# plt.plot(adana_merged_df['date'], adana_merged_df['Pressure1-2'], label='TSMS06 - TSMS07', marker='o')
# plt.plot(adana_merged_df['date'], adana_merged_df['Pressure1-3'], label='TSMS06 - TSMS08', marker='o')
# plt.plot(adana_merged_df['date'], adana_merged_df['Pressure2-3'], label='TSMS07 - TSMS08', marker='o')
# plt.title('Adana Difference Plot: BMP Comparison')
# plt.xlabel('Time')
# plt.ylabel('Pressure Difference (hPa)')
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("/Users/rzieber/Documents/3D-PAWS/Turkiye/plots/difference_plots/cross_station/pressure/diff_plot_adana.png")
# plt.clf()
# plt.close()

# # Create the plot -- Pressure
# plt.figure(figsize=(20, 12))
# plt.plot(ankara_merged_df['date'], ankara_merged_df['Humidity1-2'], label='TSMS00 - TSMS01', marker='o')
# plt.plot(ankara_merged_df['date'], ankara_merged_df['Humidity1-3'], label='TSMS01 - TSMS03', marker='o')
# plt.plot(ankara_merged_df['date'], ankara_merged_df['Humidity2-3'], label='TSMS01 - TSMS03', marker='o')
# plt.title('Ankara Difference Plot: HTU Comparison')
# plt.xlabel('Time')
# plt.ylabel('Humidity Difference (%)')
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("/Users/rzieber/Documents/3D-PAWS/Turkiye/plots/difference_plots/cross_station/humidity/diff_plot_ankara.png")
# plt.clf()
# plt.close()

# plt.figure(figsize=(20, 12))
# plt.plot(konya_merged_df['date'], konya_merged_df['Humidity1-2'], label='TSMS03 - TSMS04', marker='o')
# plt.plot(konya_merged_df['date'], konya_merged_df['Humidity1-3'], label='TSMS03 - TSMS05', marker='o')
# plt.plot(konya_merged_df['date'], konya_merged_df['Humidity2-3'], label='TSMS04 - TSMS05', marker='o')
# plt.title('Konya Difference Plot: HTU Comparison')
# plt.xlabel('Time')
# plt.ylabel('Humidity Difference (%)')
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("/Users/rzieber/Documents/3D-PAWS/Turkiye/plots/difference_plots/cross_station/humidity/diff_plot_konya.png")
# plt.clf()
# plt.close()

# plt.figure(figsize=(20, 12))
# plt.plot(adana_merged_df['date'], adana_merged_df['Humidity1-2'], label='TSMS06 - TSMS07', marker='o')
# plt.plot(adana_merged_df['date'], adana_merged_df['Humidity1-3'], label='TSMS06 - TSMS08', marker='o')
# plt.plot(adana_merged_df['date'], adana_merged_df['Humidity2-3'], label='TSMS07 - TSMS08', marker='o')
# plt.title('Adana Difference Plot: HTU Comparison')
# plt.xlabel('Time')
# plt.ylabel('Humidity Difference (%)')
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("/Users/rzieber/Documents/3D-PAWS/Turkiye/plots/difference_plots/cross_station/humidity/diff_plot_adana.png")
# plt.clf()
# plt.close()




"""
=============================================================================================================================
Creating pressure time series comparison between all 3 pressure sensors plus TSMS at each site. MONTHLY RECORDS
=============================================================================================================================
"""
# # Here's what you want!!!!!!!!!!!!!!!!!!!!!!!!!!
# ankara_paws = [paws_dfs[0], paws_dfs[1], paws_dfs[2]]
# konya_paws = [paws_dfs[3], paws_dfs[4], paws_dfs[5]]
# adana_paws = [paws_dfs[6], paws_dfs[7], paws_dfs[8]]
# paws_per_site = [ankara_paws, konya_paws, adana_paws]
# tsms_per_site = [tsms_dfs[0], tsms_dfs[3], tsms_dfs[6]]

# i = 0
# for site_dfs in paws_per_site:
#     pressure_df = None
#     site_pressures = []

#     for df in site_dfs:
#         site_pressures.append(df['bmp2_pres'])
#     site_pressures.append(tsms_per_site[i]['actual_pressure'])
#     i += 1
    
#     pressure_df = pd.concat(site_pressures, axis=1, ignore_index=True)
#     pressure_df.to_csv(f"/Users/rzieber/Downloads/testing_{i-1}_pressures.csv")
# # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!









# for i in range(len(paws_dfs)):
#     paws_df = paws_dfs[i]
#     tsms_df = tsms_dfs[i]
#     tsms_df_FILTERED = tsms_df[paws_df.index[0]:paws_df.index[-1]]
#     paws_df_FILTERED = paws_df[(paws_df['bmp2_pres'] > -999.99)]
#     tsms_df_FILTERED = tsms_df_FILTERED[(tsms_df_FILTERED['actual_pressure']) > 0]

#     print("Pressure -- nulls filtered")
    
#     #tsms_df_FILTERED.to_csv("/Users/rzieber/Downloads/tsms_df_pressure_FILTERED.csv")
#     for year_month, paws_group in paws_df_FILTERED.groupby("year_month"):
#         tsms_group = tsms_df_FILTERED[tsms_df_FILTERED['year_month'] == year_month]

#         plt.figure(figsize=(20, 12))

#         plt.plot(paws_group.index, paws_group['bmp2_pres'], marker='.', markersize=1, label="3D PAWS bmp2_pres")
#         plt.plot(tsms_group.index, tsms_group['actual_pressure'], marker='.', markersize=1, label='TSMS')

#         plt.title(f'{station_directories[i][8:14]} Pressure for {year_month}: 3D PAWS bmp2_pres versus TSMS')
#         plt.xlabel('Date')
#         plt.ylabel('Pressure (mbar)')
#         plt.xticks(rotation=45)

#         plt.legend()

#         plt.grid(True)
#         plt.tight_layout()
#         plt.savefig(data_destination+station_directories[i]+f"actual_pressure/filtered_nulls/{station_directories[i][8:14]}_bmp2_pres_{year_month}_FILTERED.png")
        
#         plt.clf()
#         plt.close()



    