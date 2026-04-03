"""
This is specifically for stations 6-8 whose data are in the CHORDS format.
Reads in files from specified folder struct. 
Processes files line by line, extracting measurement information.
Writes to a TSV formatted .dat file specifically designed for the TSMS data analysis.
Creates daily files.
"""

import os
import json
import dev
import numpy as np
import csv

data_origin = "/Users/rzieber/Documents/3D-PAWS/Turkiye/Turkiye/3DPAWS/"
data_destination = "/Users/rzieber/Documents/3D-PAWS/Turkiye/debug/Adana_Daily/"
station_directories = [ # from data_origin
    "station_TSMS06/", "station_TSMS07/", "station_TSMS08/"
]
original_file_count = [ # Adana
    429, 435, 432
]
station_files = [] # list of lists of filenames under each station directory [[TSMS06 files], [TSMS07 files], [TSMS08 files]]
for station in station_directories:
    # sorted by filename
    station_files.append(sorted([f for f in os.listdir(data_origin + station) if os.path.isfile(os.path.join(data_origin + station, f))]))


for i in range(len(station_files)):
    file_count = 0
    print(f"Reading station {station_directories[i][:len(station_directories[i])-1]}\nOriginal file count:\t{original_file_count[i]}")

    for next_file in station_files[i]:
        if next_file == ".DS_Store":
            continue
        
        file_name = station_directories[i][8:14] + "_" + next_file[:len(next_file)-4] + ".dat"
        temp_file_name = file_name[:len(file_name)-4] + "_TEMP.dat"
        destination = os.path.join(data_destination, station_directories[i][8:], file_name)
        temp_file_path = os.path.join(data_destination, station_directories[i][8:], temp_file_name)

        time = [] # list of strings  (e.g. '2023-12-17T00:00:04Z')
        measurements = [] # list of dictionaries  (e.g. {'t1': 25.3, 'uv1': 2, 'rh1': 92.7, 'sp1': 1007.43, 't2': 26.9, 'vis1': 260})
        
        with open(data_origin + station_directories[i] + next_file, 'r', encoding='utf-8', errors='replace') as file:
            l = 1
            for line in file:
                try:
                    dictionary_data = json.loads(line) # a dictionary containing all the variables in each line in file
                    time.append(dictionary_data.pop('at'))
                    keys = list(dictionary_data.keys())
                    if 'bp1' in keys:
                        slp = dictionary_data['bp1']*(1+(48/44330))**(5.255) # SLP = observed pressure * (1 + (altitude/44330))^5.255
                        dictionary_data['msl1'] = slp
                    dictionary_data['alt'] = 48
                    dictionary_data['int'] = 900
                    measurements.append(dictionary_data)

                except json.JSONDecodeError:
                    print("============================================================")
                    print(f"Error decoding JSON on line number {l} for file {next_file}")
                    print("============================================================\n")
                
                l += 1
            
            headers = [
                'year', 'mon', 'day', 'hour', 'min', 'int', 
                'bmp2_temp', 'bmp2_pres', 'bmp2_slp', 'bmp2_alt', 'bme2_hum',
                'htu_temp', 'htu_hum', 'sth_temp', 'sth_hum', 'mcp9808',
                'tipping', 'vis_light', 'ir_light', 'uv_light', 'wind_dir', 'wind_speed'
            ]
            time = np.array(time)
            measurements = np.array(measurements)

            dev.csv_builder(headers, time, measurements, temp_file_path, -999.99)

            # reformat tsv 
            with open(temp_file_path, 'r', newline='') as infile, open(destination, 'w', newline='') as outfile:
                reader = csv.reader(infile, delimiter='\t')
                writer = csv.writer(outfile, delimiter='\t')
                header_row = "year  mon  day  hour  min  int  bmp2_temp  bmp2_pres  bmp2_slp  bmp2_alt  bme2_hum  htu_temp  htu_hum  sth_temp  sth_hum  mcp9808  tipping  vis_light  ir_light  uv_light  wind_dir  wind_speed\n"
                reformat = "{:>4.0f}  {:>3.0f}  {:>3.0f}  {:>4.0f}  {:>3.0f}  {:>3.0f}  {:>9}  {:>9}  {:>8.2f}  {:>8}  {:>8}  {:>8}  {:>7}  {:>8}  {:>5}  {:>7}  {:>7}  {:>9}  {:>8}  {:>8}  {:>8}  {:>10}"
                next(reader) # skip header row
                outfile.write(header_row)
                l = 1
                for row in reader:
                    l += 1
                    try:   
                        formatted_row = reformat.format(*[float(cell) if cell.strip() and cell.strip() != -999.99 else 0.0 for cell in row])
                        writer.writerow(formatted_row.split('\t'))
                    except ValueError as v:
                        zzzzzzzzz = None
            
            os.remove(temp_file_path)
        file_count += 1

    print(f"Total # files read:\t{file_count}\n")
