"""
==========================================================================================
Replaces the Dec 2024 -> Nov 2025 portion of each 3D-PAWS reformatted file with the
correctly labeled CHORDS download for that period.

Why (docs/sensor-failures.md SF-10): the Jan 2024 -> Nov 2025 CHORDS csv for each station was
built by pasting a later CHORDS batch under the header of an earlier one. The pasted rows use a
different column order, so from 2024-12-01 every value at TSMS02, 03, 04, 05 and 08 sits under
the wrong column name in data/reformatted. The Dec 2024 -> Nov 2025 batch in
data/raw/3D-PAWS/Dec-2024_Nov-2025 has its own, correct header, so it's mapped here by column
NAME (never by position).

Conventions, matching final_paws_reformatter.py (verified against the existing files, which
match this batch 100% at TSMS00, 01, 06 and 07 where they were never scrambled):
    - timestamps floored to the minute, then shifted back 1 minute (SD card / CHORDS offset)
    - CHORDS names every humidity sensor "HTU21D". On stations upgraded to the SHT31D the
      values go to sth_temp / sth_hum, otherwise to htu_temp / htu_hum. Which one is decided
      from the columns the station actually used in Oct-Nov 2024.
    - Adana (Particle loggers) has no SLP column; SLP is approximated with func.calc_slp,
      as in final_paws_reformatter.py.

Also re-maps the CHORDS rows from the start of the CHORDS record (mid-Jan 2024, when the SD-card
record ends) up to 2024-03-11 00:00 UTC. At TSMS02, 03, 04, 05 and 08 those rows are in a
different column order than the header too. This is not a copy-paste; it's a suspected
firmware/software change, and the switch is at the same instant at all five stations. The
mapping (header label -> true variable) was inferred from value signatures, chip dropouts, and
stable inter-sensor offsets (docs/sensor-failures.md SF-10). This period can't be re-downloaded
(CHORDS keeps 2 years).
    - TSMS04's three temperature series in this window can't be assigned to a sensor with
      confidence, so they're written as missing (docs/sensor-failures.md SF-15, docs/methods.md).

Originals are copied to data/reformatted_backup_pre-chords-splice/ (outside data/reformatted,
so outlier-removal.py never picks them up) before anything is overwritten. The script always
starts from those originals, so it can be re-run safely.
==========================================================================================
"""
import sys
import shutil
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from dev import functions as func


reformatted = Path("data/reformatted")
backup = Path("data/reformatted_backup_pre-chords-splice")
chords_dec = Path("data/raw/3D-PAWS/Dec-2024_Nov-2025")

name_map = {    # CHORDS Dec 2024 batch header : reformatted column
    "BMP280_T (degC)":      "bmp2_temp",
    "BMP280_SP (mbar)":     "bmp2_pres",
    "BMP280_SLP (mbar)":    "bmp2_slp",
    "MCP9808_T (degC)":     "mcp9808",
    "precipitation (mm)":   "tipping",
    "windspeed (m/s)":      "wind_speed",
    "winddirection (degN)": "wind_dir",
}
# Early-2024 re-mapping: raw CHORDS header label -> reformatted column, for rows before LAYOUT_SWITCH.
# None = the column holds a temperature whose sensor can't be identified -> written as missing.
LAYOUT_SWITCH = pd.Timestamp("2024-03-11 00:00:00")    # UTC, raw CHORDS time
chords_raw = Path("data/raw/3D-PAWS/Jan-2024_Nov-2025")
early_2024_maps = {
    "TSMS02": {"rain": "bmp2_temp", "wind_speed": "mcp9808", "bmp_temp": "bmp2_slp", "mcp9808": "bmp2_pres",
               "bmp_slp": "tipping", "bmp_pressure": "wind_speed", "si1145_vis": "wind_dir",
               "wind_direction": "sth_temp", "wind_direction_compass_dir": "sth_hum"},
    "TSMS03": {"bmp_temp": "tipping", "mcp9808": "wind_speed", "bmp_slp": "wind_dir", "rain": "bmp2_temp",
               "wind_speed": "mcp9808", "wind_direction": "bmp2_slp", "wind_direction_compass_dir": "bmp2_pres",
               "sth31d_temp": "sth_temp", "sth31d_humidity": "sth_hum"},
    "TSMS04": {"htu21d_temp": "tipping", "bmp_temp": "wind_speed", "mcp9808": "wind_dir", "wind_speed": "htu_hum",
               "wind_direction": "bmp2_slp", "wind_direction_compass_dir": "bmp2_pres",
               "bmp_slp": None, "bmp_pressure": None, "rain": None},     # three unidentifiable temperatures (SF-15)
    "TSMS05": {"bmp_temp": "tipping", "mcp9808": "wind_speed", "bmp_slp": "wind_dir", "rain": "bmp2_temp",
               "wind_speed": "mcp9808", "wind_direction": "bmp2_slp", "wind_direction_compass_dir": "bmp2_pres",
               "sth31d_temp": "sth_temp", "sth31d_humidity": "sth_hum"},
    "TSMS08": {"bmp_temp": "bmp2_temp", "mcp9808": "mcp9808", "bmp_pressure": "sth_temp", "rain": "sth_hum",
               "wind_speed": "bmp2_pres", "wind_direction": "tipping", "wind_direction_compass_dir": "wind_speed",
               "wg": "wind_dir"},   # no SLP in this file -> approximated below, as in final_paws_reformatter.py
}


def remap_early_2024(station, n, chords_start):
    """Rebuild the CHORDS rows [chords_start, LAYOUT_SWITCH) from the raw file with the corrected column mapping."""
    raw = pd.read_csv(next((chords_raw / f"station_{station}").glob("*.csv")), low_memory=False)
    raw_time = pd.to_datetime(raw['time'], utc=True, errors='coerce').dt.tz_localize(None)
    raw = raw[raw_time < LAYOUT_SWITCH]
    out = pd.DataFrame({'date': raw_time[raw_time < LAYOUT_SWITCH].dt.floor('min') - pd.Timedelta(minutes=1)})
    for col in ['bmp2_temp', 'bmp2_pres', 'bmp2_slp', 'bme2_hum', 'htu_temp', 'htu_hum', 'sth_temp', 'sth_hum',
                'mcp9808', 'tipping', 'wind_dir', 'wind_speed']:
        out[col] = np.nan
    for label, dst in early_2024_maps[station].items():
        if dst is not None: out[dst] = pd.to_numeric(raw[label], errors='coerce')
    if station == "TSMS08":
        out['bmp2_slp'] = func.calc_slp(out, 48, 'mcp9808', 'bmp2_pres')
    out = out[out['date'] >= chords_start].dropna(subset=['date'])
    return out.sort_values('date').drop_duplicates('date', keep='first')


reformatted_columns = [
    'bmp2_temp', 'bmp2_pres', 'bmp2_slp', 'bme2_hum', 'htu_temp', 'htu_hum', 'sth_temp', 'sth_hum',
    'mcp9808', 'tipping', 'wind_dir', 'wind_speed', 'date', 'year_month', 'year_month_day', 'year_month_day_hour'
]


for n in range(9):
    station = f"TSMS0{n}"
    ref_path = next((reformatted / f"station_{station}").glob("TSMS*.csv"))
    dec_path = chords_dec / f"Calibration_Instrument-{n + 2}_2024-12-01_2025-11-30.csv"
    print(f"{station}: {ref_path.name} + {dec_path.name}")

    # back up the original once
    (backup / f"station_{station}").mkdir(parents=True, exist_ok=True)
    backup_path = backup / f"station_{station}" / ref_path.name
    if not backup_path.exists(): shutil.copy2(ref_path, backup_path)

    old = pd.read_csv(backup_path, low_memory=False)   # always start from the untouched original
    old['date'] = pd.to_datetime(old['date'], errors='coerce')

    # final_paws_reformatter.py wrote the SD-card part first, then the CHORDS part, each with its own
    # source index -- the first drop in the index marks where the CHORDS part starts
    idx = old.iloc[:, 0].to_numpy()
    chords_first_row = int(np.where(np.diff(idx) < 0)[0][0]) + 1
    chords_start = old['date'].iloc[chords_first_row]

    n_bad_dates = old['date'].isna().sum()
    old = old.dropna(subset=['date'])

    early = None
    if station in early_2024_maps:
        early = remap_early_2024(station, n, chords_start)
        early_end = early['date'].max()
        in_window = (old['date'] >= chords_start) & (old['date'] <= early_end)
        print(f"\tearly 2024: replaced {in_window.sum()} CHORDS rows {chords_start} -> {early_end} "
              f"with {len(early)} re-mapped rows"
              + ("; temperatures written as missing (SF-15)" if station == "TSMS04" else ""))
        old = pd.concat([old[~in_window], early], ignore_index=True)

    # which humidity/temperature pair this station used just before the batch
    recent = old[(old['date'] >= "2024-10-01") & (old['date'] < "2024-12-01")]
    uses_sht = pd.to_numeric(recent['sth_temp'], errors='coerce').notna().sum() > \
               pd.to_numeric(recent['htu_temp'], errors='coerce').notna().sum()
    t_col, rh_col = ("sth_temp", "sth_hum") if uses_sht else ("htu_temp", "htu_hum")

    # correctly labeled Dec 2024 -> Nov 2025 batch, mapped by name
    dec = pd.read_csv(dec_path, low_memory=False)
    new = pd.DataFrame({'date': pd.to_datetime(dec['Time'], errors='coerce').dt.floor('min') - pd.Timedelta(minutes=1)})
    for src, dst in name_map.items():
        new[dst] = pd.to_numeric(dec[src], errors='coerce') if src in dec.columns else np.nan
    new[t_col] = pd.to_numeric(dec['HTU21D_T (degC)'], errors='coerce')
    new[rh_col] = pd.to_numeric(dec['HTU21D_RH (%)'], errors='coerce')
    for col in ['htu_temp', 'htu_hum', 'sth_temp', 'sth_hum', 'bme2_hum']:
        if col not in new.columns: new[col] = np.nan
    if 'BMP280_SLP (mbar)' not in dec.columns:
        new['bmp2_slp'] = func.calc_slp(new, 48, 'mcp9808', 'bmp2_pres')
    new = new.dropna(subset=['date']).sort_values('date').drop_duplicates('date', keep='first')

    cut = new['date'].min()     # 2024-11-30 23:59 after the 1-minute shift
    kept = old[old['date'] < cut]

    spliced = pd.concat([kept[reformatted_columns[:-3]], new[reformatted_columns[:-3]]], ignore_index=True)
    spliced = spliced.sort_values('date').reset_index(drop=True)
    spliced['year_month'] = spliced['date'].dt.to_period('M')
    spliced['year_month_day'] = spliced['date'].dt.to_period('D')
    spliced['year_month_day_hour'] = spliced['date'].dt.to_period('h')

    spliced[reformatted_columns].to_csv(ref_path)

    print(f"\tkept {len(kept)} rows before {cut}, replaced {(old['date'] >= cut).sum()} rows with {len(new)} "
          f"from the Dec batch; humidity sensor -> {t_col}/{rh_col}; SLP "
          f"{'from file' if 'BMP280_SLP (mbar)' in dec.columns else 'approximated'}; dropped {n_bad_dates} rows with no date")
