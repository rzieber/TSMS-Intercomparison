# """
# The file mgm_kaynak.txt is a complete and comprehensive data record for all the TSMS data.
# The data period for each station extends from October 1 2022 into December 2025.

# Old TSMS file reformatters required concatenation of files to create a complete record.
# This one does not.

# Break apart the mgm_kaynak.txt into separate files for each site. This includes a site with
# the ID 18213, which is not relevant for this analysis and may be ignored.

# Once the files are broken apart, reformat the data frame so that it matches the format created
# by the old file reformatters. 

# mgm_kaynak.txt headers:
# stationid,obstime,temp,humidity,slp,pressure,rain,wind_speed,wind_direction,si1145_vis,si1145_ir,si1145_uv

# Expected TSMS headers for analysis scripts:
# date,temperature,humidity,actual_pressure,sea_level_pressure,avg_wind_dir,avg_wind_speed,total_rainfall
# """


# import pandas as pd
# from pathlib import Path

# base = "data/raw/TSMS"

# df = pd.read_csv("data/raw/TSMS/mgm_kaynak.txt")

# station_ids = df["stationid"].unique()

# for sid in station_ids:
#     df_station = df[df["stationid"] == sid]
    
#     renamed = df_station(columns={
#         "obstime": "date",
#         "temp": "temperature",
#         "humidity": "humidity",
#         "pressure": "actual_pressure",
#         "slp": "sea_level_pressure",
#         "wind_direction": "avg_wind_dir",
#         "wind_speed": "avg_wind_speed",
#         "rain": "total_rainfall"
#     })

#     out =renamed[[
#         "date",
#         "temperature",
#         "humidity",
#         "actual_pressure",
#         "sea_level_pressure",
#         "avg_wind_dir",
#         "avg_wind_speed",
#         "total_rainfall"
#     ]]

#     if sid == 17130: station_name = "Ankara"
#     if sid == 17245: station_name = "Konya"
#     if sid == 17351: station_name = "Adana"
    
#     outname = Path(base, f"{station_name}_Oct22-Dec25.csv")
#     out.to_csv(outname, index=False)
#     print("wrote", outname)


"""
The file mgm_kaynak.txt is a complete and comprehensive data record for all the TSMS data.
The data period for each station extends from October 1 2022 into December 2025.

Old TSMS file reformatters required concatenation of files to create a complete record.
This one does not.

Break apart the mgm_kaynak.txt into separate files for each site. This includes a site with
the ID 18213, which is not relevant for this analysis and may be ignored.

Once the files are broken apart, reformat the data frame so that it matches the format created
by the old file reformatters.

mgm_kaynak.txt headers:
stationid,obstime,temp,humidity,slp,pressure,rain,wind_speed,wind_direction,si1145_vis,si1145_ir,si1145_uv

Expected TSMS headers for analysis scripts:
date,temperature,humidity,actual_pressure,sea_level_pressure,avg_wind_dir,avg_wind_speed,total_rainfall
"""

import pandas as pd
from pathlib import Path

base = Path("data/raw/TSMS")

df = pd.read_csv(base / "mgm_kaynak.txt")

df = df[df["stationid"] != 18213]

station_ids = df["stationid"].unique()

station_name_map = {
    17130: "Ankara",
    17245: "Konya",
    17351: "Adana",
}

for sid in station_ids:
    if sid not in station_name_map:
        print(f"Skipping unknown station ID {sid}")
        continue

    station_name = station_name_map[sid]

    df_station = df[df["stationid"] == sid]

    renamed = df_station.rename(columns={
        "obstime":        "date",
        "temp":           "temperature",
        "humidity":       "humidity",
        "pressure":       "actual_pressure",
        "slp":            "sea_level_pressure",
        "wind_direction": "avg_wind_dir",
        "wind_speed":     "avg_wind_speed",
        "rain":           "total_rainfall",
    })

    out = renamed[[
        "date",
        "temperature",
        "humidity",
        "actual_pressure",
        "sea_level_pressure",
        "avg_wind_dir",
        "avg_wind_speed",
        "total_rainfall",
    ]]

    outname = base / f"{station_name}_Oct22-Dec25.csv"
    out.to_csv(outname, index=False)
    print("wrote", outname)
