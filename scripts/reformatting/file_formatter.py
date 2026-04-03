"""
File reformatter that takes TSV files of variable spacing and converts them into a TSV with 
consistently-spaced data points.
"""

import os
import re

data_origin = r"/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/TSMS/complete_record/"
file_output = r"/Users/rzieber/Documents/3D-PAWS/Turkiye/output/"

station_directories = [
    "station_TSMS00/", "station_TSMS01/", "station_TSMS02/",
    "station_TSMS03/", "station_TSMS04/", "station_TSMS05/",
    "station_TSMS06/", "station_TSMS07/", "station_TSMS08/"
]
station_files = [] # list of lists of filenames under each station directory [[TSMS00 files], [TSMS01 files], [TSMS02 files]...]
for station in station_directories:
    station_files.append(sorted([f for f in os.listdir(data_origin + station) # sorted by filename
                                    if os.path.isfile(os.path.join(data_origin + station, f)) and f != ".DS_Store"]))

# turn Joey's TSV format into standard TSV format
lines = None
standardized_lines = []    

for i in range(len(station_files)):
    for file in station_files[i]:

        with open(data_origin+station_directories[i]+file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        for line in lines:
            standardized_line = re.split(r'\s+', line.strip())
            formatted_line = '\t'.join(standardized_line)
            standardized_lines.append(formatted_line + '\n')
        
        with open(file_output+station_directories[i]+file[:len(file)-4]+".dat", 'w', encoding='utf-8', errors='replace') as f:
            f.writelines(standardized_lines)

        lines = None
        standardized_lines = []
