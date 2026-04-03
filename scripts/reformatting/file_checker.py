"""
If given raw station data in TSV format, this script will return any files that contain random indents.
"""

import os

folder = r"C:\\Users\\Becky\\Documents\\UCAR_ImportantStuff\\Turkiye_Comparison\\output\\"
stations = [
    #"station_TSMS00\\", "station_TSMS01\\", "station_TSMS02\\"
    "station_TSMS03\\", "station_TSMS04\\", "station_TSMS05\\",
    # "station_TSMS06\\", "station_TSMS07\\", "station_TSMS08\\"
]

station_files = [] # list of lists of filenames under each station directory [[TSMS00 files], [TSMS01 files], [TSMS02 files]]
for station in stations:
    # sorted by filename
    station_files.append(sorted([f for f in os.listdir(folder+station) if os.path.isfile(os.path.join(folder+station, f))]))

for i in range(len(stations)):
    for station in station_files[i]:
        with open(folder+stations[i]+station, 'r', encoding='utf-8', errors='replace') as file:
            l = 0
            for line in file:
                l += 1
                if line.strip() == '""':
                    print("File: ", file)
                    print("Indent found on line ", l)
