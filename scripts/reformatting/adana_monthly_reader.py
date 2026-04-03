"""
This is specifically for stations 6-8 whose data are in the CHORDS format.
Reads in files from specified folder struct. 
Processes files line by line, extracting measurement information.
Writes to a TSV formatted .dat file specifically designed for the TSMS data analysis.
Creates monthly aggregate files.
"""

import os
import json
import dev
import numpy as np
import csv

data_origin = "/Users/rzieber/Documents/3D-PAWS/Turkiye/Turkiye/3DPAWS/"
data_destination = "/Users/rzieber/Documents/3D-PAWS/Turkiye/debug/Adana_Monthly/"
station_directories = [
    "station_TSMS06/", "station_TSMS07/", "station_TSMS08/"
]
station_files = [] # list of lists of filenames under each station directory [[TSMS06 files], [TSMS07 files], [TSMS08 files]]
for station in station_directories:
    # sorted by filename
    station_files.append(sorted([f for f in os.listdir(data_origin + station) if os.path.isfile(os.path.join(data_origin + station, f))]))


time = [] # list of lists which contain all the timestamp for each month [[Month 1 Timestamps], [Month 2 Timestamps], ...]
measurements = [] # list of lists which contain all the measurements for each month [[Month 1 Measurements], [Month 2 Measurements], ...]
filename_metadata = [] #  list of lists containing file naming metadata [[Month 1, Year], [Month 2, Year], ...]
for i in range(len(station_files)):
    print(f"Reading station {station_directories[i][:len(station_directories[i])-1]}")

    monthly_time = [] # list of strings (e.g. '2023-12-17T00:00:04Z')
    monthly_measurements = [] # list of dictionaries (e.g. {'t1': 25.3, 'uv1': 2, 'rh1': 92.7, 'sp1': 1007.43, 't2': 26.9, 'vis1': 260})
    monthly_metadata = [] # list of integers (e.g. ['01', '2022']) time metadata for filename gen
    this_month = -1
    new_station = True

    for next_file in station_files[i]:
        if next_file == ".DS_Store":
            continue
        
        with open(data_origin + station_directories[i] + next_file, 'r', encoding='utf-8', errors='replace') as file:
            l = 1 
            fl_dictionary_data = json.loads(file.readline())
            t = dev.get_timestamp(fl_dictionary_data['at'])
            next_month = t.month

            if new_station: 
                new_station = False
                this_month = t.month

            if this_month != next_month:
                this_month = next_month

                monthly_time = np.array(monthly_time)
                monthly_measurements = np.array(monthly_measurements)
                monthly_metadata = np.array(monthly_metadata)

                file_name = station_directories[i][8:14] + "_" + str(monthly_metadata[1]) + '_' + str(monthly_metadata[0]) + ".dat"
                temp_file_name = file_name[:len(file_name)-4] + "_TEMP.dat"
                destination = os.path.join(data_destination, station_directories[i][8:], file_name)
                temp_file_path = os.path.join(data_destination, station_directories[i][8:], temp_file_name)

                headers = [
                    'year', 'mon', 'day', 'hour', 'min', 'int', 
                    'bmp2_temp', 'bmp2_pres', 'bmp2_slp', 'bmp2_alt', 'bme2_hum',
                    'htu_temp', 'htu_hum', 'sth_temp', 'sth_hum', 'mcp9808',
                    'tipping', 'vis_light', 'ir_light', 'uv_light', 'wind_dir', 'wind_speed'
                ]

                dev.csv_builder(headers, monthly_time, monthly_measurements, temp_file_path, -999.99)

                # reformat tsv 
                with open(temp_file_path, 'r', newline='') as infile, open(destination, 'w', newline='') as outfile:
                    reader = csv.reader(infile, delimiter='\t')
                    writer = csv.writer(outfile, delimiter='\t')
                            #    year    mon     day     hour    min     int      bmp_t    bmp_p    bmp_s   bmp_alt  bme_hum  htu_t   htu_h    sth_t   sth_h     mcp      tip     vis     ir       uv       dir      speed                  
                    reformat = "{:4.0f} {:6.0f} {:7.0f} {:7.0f} {:7.0f} {:7.0f} {:13.2f} {:15.2f} {:14.2f} {:15.2f} {:15.2f} {:15.2f} {:14.2f} {:8.2f} {:14.2f} {:7.2f} {:7.2f} {:9.2f} {:14.2f} {:15.2f} {:15.0f} {:17.2f}"
                    header_row = next(reader) 
                    writer.writerow(header_row)
                    for row in reader:
                        formatted_row = reformat.format(*[float(cell) if cell else 0.0 for cell in row])
                        writer.writerow([formatted_row])

                os.remove(temp_file_path)

                monthly_time = []
                monthly_measurements = []
                monthly_metadata = []


            file.seek(0) # reset line reader to beginning
            monthly_metadata.append(t.month)
            monthly_metadata.append(t.year)
            for line in file:
                try:
                    dictionary_data = json.loads(line) # a dictionary containing all the variables in each line in file
                    monthly_time.append(dictionary_data.pop('at'))
                    keys = list(dictionary_data.keys())
                    if 'bp1' in keys:
                        slp = dictionary_data['bp1']*(1+(48/44330))**(5.255) # SLP = observed pressure * (1 + (altitude/44330))^5.255
                        dictionary_data['msl1'] = slp
                    dictionary_data['alt'] = 48
                    dictionary_data['int'] = 900
                    monthly_measurements.append(dictionary_data)
                except json.JSONDecodeError:
                    print("============================================================")
                    print(f"Error decoding JSON on line number {l} for file {next_file}")
                    print("============================================================\n")
            
                l += 1

                
    monthly_time = np.array(monthly_time)
    monthly_measurements = np.array(monthly_measurements)
    monthly_metadata = np.array(monthly_metadata)

    file_name = station_directories[i][8:14] + "_" + str(monthly_metadata[1]) + '_' + str(monthly_metadata[0]) + ".dat"
    temp_file_name = file_name[:len(file_name)-4] + "_TEMP.dat"
    destination = os.path.join(data_destination, station_directories[i][8:], file_name)
    temp_file_path = os.path.join(data_destination, station_directories[i][8:], temp_file_name)

    headers = [
        'year', 'mon', 'day', 'hour', 'min', 'int', 
        'bmp2_temp', 'bmp2_pres', 'bmp2_slp', 'bmp2_alt', 'bme2_hum',
        'htu_temp', 'htu_hum', 'sth_temp', 'sth_hum', 'mcp9808',
        'tipping', 'vis_light', 'ir_light', 'uv_light', 'wind_dir', 'wind_speed'
    ]

    dev.csv_builder(headers, monthly_time, monthly_measurements, temp_file_path, -999.99)

    # reformat tsv 
    with open(temp_file_path, 'r', newline='') as infile, open(destination, 'w', newline='') as outfile:
        reader = csv.reader(infile, delimiter='\t')
        writer = csv.writer(outfile, delimiter='\t')
        header_row = "year  mon  day  hour  min  int  bmp2_temp  bmp2_pres  bmp2_slp  bmp2_alt  bme2_hum  htu_temp  htu_hum  sth_temp  sth_hum  mcp9808  tipping  vis_light  ir_light  uv_light  wind_dir  wind_speed\n"
        reformat = "{:>4.0f}  {:>3.0f}  {:>3.0f}  {:>4.0f}  {:>3.0f}  {:>3.0f}  {:>9}  {:>9}  {:>8}  {:>8}  {:>8}  {:>8}  {:>7}  {:>8}  {:>5}  {:>7}  {:>7}  {:>9}  {:>8}  {:>8}  {:>8}  {:>10}"
        next(reader) # skip header
        outfile.write(header_row)
        l = 1
        for row in reader:
            l += 1
            try:
                formatted_row = reformat.format(*[float(cell) if cell.strip() and cell.strip() != -999.99 else 0.0 for cell in row])
                writer.writerow(formatted_row.split('\t'))
            except ValueError as v:
                zzzzzz = None

    os.remove(temp_file_path)
