"""
Reads in files from specified folder struct. 
Writes to a TSV formatted .dat file specifically designed for the TSMS data analysis.
Creates monthly aggregate files.
"""

import os

data_origin = "/Users/rzieber/Documents/3D-PAWS/Turkiye/output/"
#data_origin = r"C:\\Users\\Becky\\Documents\\UCAR_ImportantStuff\\Turkiye_Comparison\\data\\TSMS\\"
data_destination = "/Users/rzieber/Documents/3D-PAWS/Turkiye/debug/Konya_Monthly/"
#data_destination = r"C:\\Users\\Becky\\Documents\\UCAR_ImportantStuff\\Turkiye_Comparison\\output\\monthly\\"
station_directories = [ # Konya, Ankara
    #"station_TSMS00/", "station_TSMS01/", "station_TSMS02/"      # Adana
    "station_TSMS03/", "station_TSMS04/", "station_TSMS05/"      # Konya
]
station_files = [] # list of lists of filenames under each station directory [[TSMS06 files], [TSMS07 files], [TSMS08 files]]
for station in station_directories:
    # sorted by filename
    station_files.append(sorted([f for f in os.listdir(data_origin + station) if os.path.isfile(os.path.join(data_origin + station, f))]))

files_by_month = []
for i in range(len(station_files)):
    print(f"Reading station {station_directories[i][:len(station_directories[i])-1]}")

    this_month = -1
    new_station = True
    monthly_filenames = []

    for next_file in station_files[i]:
        if next_file == ".DS_Store":
            continue

        year = next_file[7:11]
        mon = next_file[11:13]
        day = next_file[13:15]

        next_month = mon

        if new_station:
            new_station = False
            this_month = mon

        if this_month != next_month:
            this_month = next_month

            files_by_month.append(monthly_filenames)
            monthly_filenames = []
        
        monthly_filenames.append(next_file)

    files_by_month.append(monthly_filenames) # dump the remaining month at the end


   
        
    for j in range(len(files_by_month)): # for each month
        year = files_by_month[j][0][7:11] 
        mon = files_by_month[j][0][11:13]
        day = files_by_month[j][0][13:15]
        filename = station_directories[i][8:14] + '_' + year + '_' + mon + '.dat'
        print(filename)
        
        with open(data_destination+station_directories[i]+filename, 'w', newline='') as outfile:
            outfile.write("year  mon  day  hour  min  int  bmp2_temp  bmp2_pres  bmp2_slp  bmp2_alt  bme2_hum  htu_temp  htu_hum  sth_temp  sth_hum  mcp9808  tipping  vis_light  ir_light  uv_light  wind_dir  wind_speed\n")
            
            for file in files_by_month[j]:
            
                with open(data_origin+station_directories[i]+station_directories[i][8:14]+'_'+file[7:], 'r', newline='') as infile:
                    next(infile) # skip header
                    for row in infile:
                        outfile.write(row)
