import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

reformatted_data = Path("data/reformatted")
qc_data = Path("data/cleaned")

print("Reformatted ------------------------")

# Build dataframes for Adana
reformatted_dfs = []
tsms_flag = False
for csv in reformatted_data.rglob("*.csv"):
    name = str(csv.stem)
    
    if name.__contains__("Ankara") and not tsms_flag:
        df = pd.read_csv(csv, parse_dates=['date'])

        df_2024_feb = df[
            (df['date'].dt.year == 2024) & 
            (df['date'].dt.month == 2)
        ]

        rain_sum = df_2024_feb['total_rainfall'].sum()
        print("\tTSMS Reference:", round(rain_sum, 1), "mm")

        reformatted_dfs.append((df_2024_feb, "TSMS_Reference_Raw"))

        tsms_flag = True
    elif name in ['TSMS00_CompleteRecord', 'TSMS01_CompleteRecord', 'TSMS02_CompleteRecord']:
        df = pd.read_csv(csv, parse_dates=['date'])

        df_2024_feb = df[
            (df['date'].dt.year == 2024) & 
            (df['date'].dt.month == 2)
        ]

        rain_sum = df_2024_feb['tipping'].sum()
        print(f"\t3D-PAWS {name[:6]}:", round(rain_sum, 1), "mm")
        
        reformatted_dfs.append((df_2024_feb, f"3DPAWS_{name[:6]}_Raw"))

print("QC-ed ------------------------------")

qc_dfs = []
for csv in qc_data.rglob("*_Adana_final.csv"):
    name = str(csv.stem)

    df = pd.read_csv(csv, parse_dates=['date'])

    df_2024_feb = df[
        (df['date'].dt.year == 2024) & 
        (df['date'].dt.month == 2)
    ]

    if name.startswith("TSMS"):
        rain_sum = df_2024_feb['total_rainfall'].sum()
        qc_dfs.append((df_2024_feb, f"TSMS_Reference_QC"))
        print("\tTSMS Reference:", round(rain_sum, 1), "mm")
    else:
        rain_sum = df_2024_feb['tipping'].sum()
        print(f"\t3DPAWS {name[7:13]}:", round(rain_sum, 1), "mm")
        qc_dfs.append((df_2024_feb, f"3DPAWS_{name[7:13]}_QC"))



# Create time series accumulation plots [web:381][web:383]
fig, ax = plt.subplots(figsize=(15, 8))

# Sort all dataframes by date for proper accumulation
for df, label in reformatted_dfs: # + qc_dfs:
    df_sorted = df.sort_values('date').copy()
    
    # Column mapping: raw vs QC
    if 'total_rainfall' in df_sorted.columns:
        rain_col = 'total_rainfall'
    else:
        rain_col = 'tipping'
    
    # Cumulative sum
    df_sorted['cumulative_rain'] = df_sorted[rain_col].cumsum()
    
    # Plot
    linestyle = '-' if 'Raw' in label else '--'
    linewidth = 2.5 if 'TSMS' in label else 2.0
    alpha = 0.9 if 'TSMS' in label else 0.7
    
    ax.plot(df_sorted['date'], df_sorted['cumulative_rain'], 
            label=label, linestyle=linestyle, linewidth=linewidth, alpha=alpha,
            marker='o', markersize=3)

ax.set_xlabel('Date (Feb 2024)')
ax.set_ylabel('Cumulative Rainfall (mm)')
ax.set_title('Adana Feb 2024: Raw vs QC Rainfall Accumulation')
ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
ax.grid(True, alpha=0.3)
plt.tight_layout()
# plt.savefig(output_plots / "adana_feb2024_rainfall_accumulation_raw_vs_qc.png", dpi=300, bbox_inches='tight')
plt.show()
