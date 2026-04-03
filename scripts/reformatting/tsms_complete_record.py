import pandas as pd
import os
import csv

"""
Setting up the csv's from the original giant ASCII file.
"""
# =============================================================================================================================== 

# data_directory = "/Users/rzieber/Documents/3D-PAWS/Turkiye/raw/TSMS/"
# data_destination = "/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/TSMS/complete_record_UPDATED/"

# tsms_df_initial = pd.read_csv(
#     data_directory+"export_3dpaws_2023_07_01.txt",
#     delimiter=';',
#     header=0
# )
# tsms_df_initial.rename(
#     columns={
#         "ISTNO":"Station Number",
#         "YIL":"Year",
#         "AY":"Month",
#         "GUN":"Day",
#         "SAAT":"Hour",
#         "DAKIKA":"Minute",
#         "SICAKLIK":"Temperature",
#         "NEM":"Humidity",
#         "AKTUEL_BASINC":"Actual Pressure",
#         "DENIZE_INDIRGENMIS_BASINC":"Sea Level Pressure",
#         "GUNESLENME_SURESI":"Sunshine Duration",
#         "ORT_KURESEL_GUNES_RADYASYONU":"Mean Global Solar Radiation",
#         "DIREKT_GUNESLENME_SIDDETI":"Direct Solar Radiation Intensity",
#         "DIFUZ_GUNESLENME_SIDDETI":"Diffuse Solar Radiation Intensity",
#         "UVA_RADYASYON_SIDDETI":"UVA Radiation Intensity",
#         "UVB_RADYASYON_SIDDETI":"UVB Radiation Intensity",
#         "ORT_RUZGAR_HIZI_10M":"Mean Wind Speed at 10m",
#         "MAKS_RUZGAR_HIZI_10M":"Maximum Wind Speed at 10m",
#         "NRT_DUZELTILMIS_YAGIS":"NRT Corrected Rainfall",
#         "PWS_HALIHAZIR_YAGIS":"PWS Current Rainfall",
#         "ORT_RUZGAR_YONU":"Mean Wind Direction",
#         "ORT_RUZGAR_HIZI":"Mean Wind Speed",
#         "MAKS_RUZGAR_YONU":"Maximum Wind Direction",
#         "MAKS_RUZGAR_HIZI":"Maximum Wind Speed",
#         "MAKS_RUZGAR_ZAMANI":"Maximum Wind Time",
#         "TOPLAM_YAGIS":"Total Rainfall"
#     }, inplace=True  
# )

# station_number_lookup = {
#     17130:"Ankara",
#     17245:"Konya",
#     17351:"Adana"
# }
# for station, group in tsms_df_initial.groupby('Station Number'):
#     if station == 18250:
#         continue

#     paws_site_name = station_number_lookup[station]
#     df = group
#     df.to_csv(data_directory+f"{paws_site_name}_{station}.csv")

#tsms_df_initial.to_csv("/Users/rzieber/Downloads/tsms_test.csv")

"""
Formatting to TSV -- Joey format
"""
# ===============================================================================================================================

data_directory = "/Users/rzieber/Documents/3D-PAWS/Turkiye/raw/TSMS/"
data_destination = "/Users/rzieber/Documents/3D-PAWS/Turkiye/reformatted/TSMS/complete_record_UPDATED/"

csv_files = [f for f in os.listdir(data_directory) if os.path.isfile(os.path.join(data_directory, f)) and f.endswith('.csv')]

for file in csv_files:
    df = pd.read_csv(
        data_directory+file,
        header=0
    )

    df.drop(
        columns=[
            "Station Number", "Sunshine Duration", "Mean Global Solar Radiation", "Direct Solar Radiation Intensity",
            "Diffuse Solar Radiation Intensity", "UVA Radiation Intensity", "UVB Radiation Intensity", "Mean Wind Speed at 10m",
            "Maximum Wind Speed at 10m", "Maximum Wind Direction", "Maximum Wind Speed", "Maximum Wind Time", 
            "NRT Corrected Rainfall", "PWS Current Rainfall", "Unnamed: 0", "Total Rainfall"
        ], inplace=True
    )

    df.to_csv(data_destination+file[:len(file)-4]+'_TEMP.csv', index=False)

    # reformat tsv 
    with open(data_destination+file[:len(file)-4]+'_TEMP.csv', 'r', newline='') as infile, \
            open(data_destination+file[:len(file)-4]+'.dat', 'w', newline='') as outfile:
        reader = csv.reader(infile)
        writer = csv.writer(outfile, delimiter='\t')

        header_row = "year  mon  day  hour  min  temp  humidity  actual_pressure  sea_level_pressure  avg_wind_dir  avg_wind_speed\n"
        reformat = "{:>4.0f}  {:>3.0f}  {:>3.0f}  {:>4.0f}  {:>3.0f}  {:>4.1f}  {:>8.1f}  {:>15.1f}  {:>18.1f}  {:>12.1f}  {:>14.1f}"

        next(reader) # skip header
        outfile.write(header_row)

        l = 1
        for row in reader:
            l += 1
            try:
                numeric_values = [float(v) if v else 0.0 for v in row]
                formatted_row = reformat.format(*numeric_values)
                writer.writerow(formatted_row.split('/t')) 
            except ValueError as v:
                zzzzzz = None

    os.remove(data_destination+file[:len(file)-4]+'_TEMP.csv')















"""
NOTE: You can't do this. Pandas won't accept a remote file path from which to create a dataframe, 
      you have to have the data downloaded directly on your local machine >:/
"""
# import pandas as pd
# import paramiko

# hostname = "spidey.comet.ucar.edu"
# username = "REDACTED"
# password = "REDACTED"
# port = 22

# data_directory = r"/home/rzieber/Documents/TSMS_Data/TSMS/"

# ssh_client = paramiko.SSHClient()
# ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# try:
#     ssh_client.connect(hostname, port=port, username=username, password=password)
#     stdin, stdout, stderr = ssh_client.exec_command(f"ls {data_directory}")
#     files = stdout.read().decode().splitlines()

#     for filename in files:
#         if filename.endswith('.txt'):
#             df = pd.read_csv(
#                 ssh_client.exec_command(f"ls{data_directory+filename}"), 
#                 delimiter=';',
#                 header=0
#             )

#             print(df)

# finally:
#    ssh_client.close()
