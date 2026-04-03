"""
This script is for stations 0-5 whose data are already formatted as a TSV. 
Reads in files from specified folder and reformats to eliminate variable length tab formatting.
Writes to a TSV formatted .dat file.
Creates daily files.

NOTE: TSMS00 has space separated files for first few days -- study starts at Aug 16
"""

import os
import pandas as pd
import csv

data_origin = r"/Users/rzieber/Documents/3D-PAWS/Turkiye/residual/"
#data_origin = r"C:\\Users\\Becky\\Documents\\UCAR_ImportantStuff\\Turkiye_Comparison\\data\\residual\\"
data_destination = r"/Users/rzieber/Documents/3D-PAWS/Turkiye/residual/"
#data_destination = r"C:\\Users\\Becky\\Documents\\UCAR_ImportantStuff\\Turkiye_Comparison\\output\\daily2\\"
station_directories = [
    #"station_TSMS00/", "station_TSMS01/", "station_TSMS02/"         # Ankara
    "station_TSMS03/", "station_TSMS04/", "station_TSMS05/"          # Konya
]
original_file_count = [
    #513, 519, 503,      # Ankara
    488, 488, 488       # Konya
]

station_files = [] # list of lists of filenames under each station directory [[TSMS00 files], [TSMS01 files], [TSMS02 files]]
for station in station_directories:
    # sorted by filename
    station_files.append(sorted([f for f in os.listdir(data_origin + station) if os.path.isfile(os.path.join(data_origin + station, f))]))

for i in range(len(station_files)): # loop through each station
    file_count = 0
    print(f"Reading station {station_directories[i][8:len(station_directories[i])-1]}")

    for next_file in station_files[i]: # loop through each daily file at station
        if next_file == ".DS_Store":
            continue

        file_name = station_directories[i][8:14] + "_" + next_file[11:len(next_file)]
        temp = os.path.join(data_destination, station_directories[i])
        destination = os.path.join(data_destination, station_directories[i])

        # Joey format is variable length TSV -- standardize to \t sep ------------------------------------------------------------
        lines = None
        standardized_lines = []

        with open(data_origin+station_directories[i]+next_file, 'r', encoding='utf-8', errors='replace') as file:
            lines = file.readlines()

        for line in lines:
            next_line = line.split(' ')
            standardized_line = [x for x in next_line if x != '']
            
            for l in range(len(standardized_line)-1):
                standardized_lines.append(standardized_line[l])
                standardized_lines.append('\t')
            
            standardized_lines.append(standardized_line[-1])

        with open(temp+file_name[:len(file_name)-4]+'.csv', 'w', encoding='utf-8', errors='replace') as file:
            file.writelines(standardized_lines)   
        # -----------------------------------------------------------------------------------------------------------------------
        try:
            df = pd.read_csv(
                    temp+file_name[:len(file_name)-4]+'.csv', 
                    delimiter="\t",
                    header=None,
                    skiprows=1,
                    names=["year", "mon", "day", "hour", "min", "bmp2_temp", "bmp2_pres", "bmp2_slp", "bmp2_alt", "bme_temp",
                                "bme_pres", "bme_slp", "bme_alt", "bme2_hum", "htu_temp", "htu_hum", "mcp9808", "tipping", 
                                    "vis_light", "ir_light", "uv_light", "wind_dir", "wind_speed"]
            )
            df.drop(columns=["bme_temp", "bme_pres", "bme_slp", "bme_alt"], inplace=True)
            df.insert(5, 'int', 900)
            df.insert(13, 'sth_temp', -999.99)
            df.insert(14, 'sth_hum', -999.99)
            df.to_csv(temp + file_name[:len(file_name)-4]+'_TEMP.csv', sep='\t', columns=df.columns, header=True, index=False, na_rep='')
            os.remove(temp+file_name[:len(file_name)-4]+'.csv')

            # reformat tsv 
            with open(temp + file_name[:len(file_name)-4]+'_TEMP.csv', 'r', newline='') as infile, \
                 open(destination+file_name, 'w', newline='') as outfile:
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

            os.remove(temp + file_name[:len(file_name)-4]+'_TEMP.csv')
            file_count += 1
        except pd.errors.ParserError:
            print(file_name)

    print("Processed ", file_count, " files out of ", original_file_count[i])
