"""
==========================================================================================
Side-by-side comparison of our statistics with the TSMS draft report
(docs/TSMS_3D-PAWS_DATA_ANALYSIS_REPORT (2).pdf), computed the way the report does:
    - report period 1 Nov 2022 - 31 Oct 2025, 1-min pairs (both instruments valid)
    - temperature: MCP9808; humidity: the station's active humidity sensor (HTU21D, or SHT31D
      after the Jan 2024 upgrade -- CHORDS labels both "HTU21D_RH"); pressure: BMP280 station pressure
    - wind speed: TSMS adjusted to 2 m (Hellmann), all paired minutes
    - wind direction: minimum circular separation, minutes where both anemometers read > 0
    - precipitation: daily totals on >= 80%-complete days, contingency table, for wet-day thresholds of 0.2 mm (report)
      and 1.0 mm (ETCCDI R1mm), each with all days and with flagged days excluded (a day is excluded when either
      gauge has any QC flag that day: tipping_flag / total_rainfall_flag, docs/qc-framework.md Step 8)
Uses data/cleaned (our QC). Writes CSV tables to data/report-comparison/.
Report values are transcribed from the report's Tables 4, 6, 7, 8 and 9.

Outputs
    continuous-variables.csv, wind-direction.csv, precipitation.csv
        The original side-by-side tables (report sensor only, data/cleaned exactly as written, i.e. after our
        Step 7 daily-completeness removal). Unchanged by the parity-table extension.
    table-NN_pPP_<name>.csv + report-parity-tables.xlsx  ("parity tables", added 2026-09-29)
        One table per table in the report (PDF page PP), our value next to the report's in every cell the report
        has, and a row for every 3D-PAWS sensor (not only the report's). Differences from the originals:
        - "QC-valid" minutes = data/cleaned plus the values our Step 7 removed *only* for daily completeness
          (restored from *_outliers.csv, outlier_type == 'daily_completeness'). The report applies the 80% rule
          only to daily aggregation, not to minute-level statistics or overall completeness (Table 2 note, §3.6).
        - Completeness denominators: 1,578,240 minutes and 1,096 days (report §5.1).
        - Humidity "active sensor" = sth_hum where present, else htu_hum (CHORDS labels both HTU21D_RH).
        - Precipitation is unaffected by the restore (only >= 80%-complete days are used either way).
==========================================================================================
"""
import os
import numpy as np
import pandas as pd
from pathlib import Path

cleaned = Path("data/cleaned")
out = Path(os.environ.get("REPORT_COMPARISON_OUT", "data/report-comparison"))   # override only for dry runs
out.mkdir(parents=True, exist_ok=True)

START, END = "2022-11-01", "2025-10-31 23:59"
sites = {"Ankara": ["TSMS00", "TSMS01", "TSMS02"], "Konya": ["TSMS03", "TSMS04", "TSMS05"], "Adana": ["TSMS06", "TSMS07", "TSMS08"]}
hellman = {"Ankara": 0.30, "Konya": 0.35, "Adana": 0.25}

report = {  # (N, bias, MAE, RMSE, R2) per station, from the report
    "temperature": {"TSMS00": (1514469, 0.056, 0.460, 0.619, 0.997), "TSMS01": (1264441, -0.073, 0.534, 0.714, 0.995),
                    "TSMS02": (1256261, 0.017, 0.445, 0.619, 0.996), "TSMS03": (1314095, 1.097, 1.387, 1.779, 0.980),
                    "TSMS04": (1315400, 0.897, 1.254, 1.634, 0.981), "TSMS05": (1314050, 1.158, 1.415, 1.804, 0.980),
                    "TSMS06": (1351706, 0.204, 0.340, 0.517, 0.998), "TSMS07": (1499507, 0.106, 0.367, 0.514, 0.997),
                    "TSMS08": (1501693, 0.123, 0.298, 0.473, 0.997)},
    "humidity":    {"TSMS00": (1059354, -2.204, 4.101, 6.468, 0.918), "TSMS01": (856603, 0.494, 4.142, 7.220, 0.888),
                    "TSMS02": (968502, 0.262, 2.877, 5.805, 0.926), "TSMS03": (1150722, -2.971, 6.846, 8.757, 0.858),
                    "TSMS04": (1110912, 0.206, 5.840, 7.621, 0.878), "TSMS05": (1155156, -4.147, 6.898, 8.876, 0.871),
                    "TSMS06": (1093229, 0.760, 3.102, 4.031, 0.971), "TSMS07": (1198689, 4.924, 5.427, 6.130, 0.969),
                    "TSMS08": (1042763, 1.801, 3.549, 4.518, 0.968)},
    "pressure":    {"TSMS00": (1351439, 1.028, 1.123, 1.328, 0.975), "TSMS01": (893326, 1.210, 1.214, 1.329, 0.989),
                    "TSMS02": (1260039, 1.255, 1.299, 1.476, 0.977), "TSMS03": (1374546, -1.133, 1.595, 1.783, 0.916),
                    "TSMS04": (1374680, -2.364, 2.727, 2.884, 0.879), "TSMS05": (1375160, -1.861, 2.060, 2.302, 0.916),
                    "TSMS06": (1126789, 0.556, 0.771, 1.080, 0.982), "TSMS07": (1255723, 0.107, 0.665, 0.829, 0.985),
                    "TSMS08": (1251907, 0.310, 0.729, 1.004, 0.978)},
    "wind_speed":  {"TSMS00": (1210010, 0.771, 1.130, 1.603, 0.151), "TSMS01": (1116808, -0.279, 0.405, 0.527, 0.150),
                    "TSMS02": (715155, 0.308, 0.664, 0.862, 0.346), "TSMS03": (790085, -0.528, 0.615, 0.790, 0.161),
                    "TSMS04": (906116, -0.557, 0.638, 0.808, 0.165), "TSMS05": (841917, -0.677, 0.746, 0.934, 0.059),
                    "TSMS06": (924004, 0.288, 0.479, 0.620, 0.531), "TSMS07": (939328, 0.254, 0.468, 0.604, 0.537),
                    "TSMS08": (554519, 0.235, 0.449, 0.588, 0.416)},
}
report_wind_dir = {  # N, mean abs error, median abs error, % within 22.5, 45, 90 (Table 8)
    "TSMS00": (559144, 45.80, 36.00, 32.79, 59.65, 87.32), "TSMS01": (369309, 48.05, 31.87, 37.83, 62.84, 82.08),
    "TSMS02": (380553, 45.58, 33.51, 34.94, 62.25, 86.10), "TSMS03": (197124, 85.99, 84.75, 13.93, 27.14, 53.06),
    "TSMS04": (250482, 93.61, 96.71, 10.92, 21.80, 45.84), "TSMS05": (144822, 84.63, 84.00, 14.57, 27.94, 53.53),
    "TSMS06": (423386, 17.35, 11.50, 72.85, 92.65, 99.16), "TSMS07": (579854, 17.71, 12.90, 71.18, 93.47, 99.45),
    "TSMS08": (331365, 17.08, 10.96, 74.53, 92.49, 98.94)}
report_precip = {  # paired days, hits, misses, false alarms, correct negatives, POD, FAR, CSI (Table 9)
    "TSMS00": (1028, 87, 17, 133, 791, 0.837, 0.605, 0.367), "TSMS01": (868, 43, 33, 69, 723, 0.566, 0.616, 0.297),
    "TSMS02": (873, 55, 37, 107, 674, 0.598, 0.660, 0.276), "TSMS03": (973, 127, 53, 310, 483, 0.706, 0.709, 0.259),
    "TSMS04": (939, 124, 57, 261, 497, 0.685, 0.678, 0.281), "TSMS05": (938, 142, 37, 221, 538, 0.793, 0.609, 0.355),
    "TSMS06": (1014, 74, 6, 115, 819, 0.925, 0.608, 0.379), "TSMS07": (1046, 77, 4, 202, 763, 0.951, 0.724, 0.272),
    "TSMS08": (1047, 63, 18, 108, 858, 0.778, 0.632, 0.333)}

# ------------------------------------------------------------------ further report transcriptions (parity tables)
ref_id = {"Ankara": "17130", "Konya": "17245", "Adana": "17351"}
report_t2 = {  # Table 2 (PDF p.16): overall completeness %, temperature, RH, pressure, wind speed
    "17130": (98.33, 85.53, 98.24, 98.07), "TSMS00": (97.48, 77.43, 87.14, 90.72), "TSMS01": (81.48, 62.87, 57.03, 85.46),
    "TSMS02": (80.94, 70.97, 81.32, 52.77), "17245": (94.28, 82.74, 97.81, 99.28), "TSMS03": (88.82, 87.62, 89.11, 66.40),
    "TSMS04": (88.82, 83.56, 89.12, 73.64), "TSMS05": (88.80, 87.94, 89.16, 70.82), "17351": (98.62, 80.29, 98.83, 81.95),
    "TSMS06": (86.41, 85.42, 71.87, 90.25), "TSMS07": (95.81, 91.99, 80.23, 91.20), "TSMS08": (95.94, 81.11, 79.83, 55.15)}
report_t3 = {  # Table 3 (PDF p.17): % of the 1,096 days with >= 1,152 valid minutes
    "17130": (98.18, 83.03, 97.99, 98.27), "TSMS00": (98.08, 46.72, 86.95, 88.59), "TSMS01": (81.20, 41.97, 56.39, 85.13),
    "TSMS02": (80.29, 59.58, 80.38, 49.54), "17245": (91.97, 78.19, 99.18, 99.91), "TSMS03": (88.59, 87.68, 88.69, 56.84),
    "TSMS04": (88.41, 78.47, 88.50, 56.30), "TSMS05": (88.32, 88.32, 88.41, 52.10), "17351": (97.90, 65.05, 97.99, 64.42),
    "TSMS06": (85.86, 84.76, 71.26, 88.32), "TSMS07": (95.89, 88.59, 80.29, 89.87), "TSMS08": (95.89, 80.93, 79.65, 50.27)}
report_t9_valid = {  # Table 9 (PDF p.57): 3D-PAWS station-specific Valid Days, Wet Days (>= 0.2 mm)
    "TSMS00": (1047, 221), "TSMS01": (886, 114), "TSMS02": (890, 164), "TSMS03": (973, 437), "TSMS04": (939, 385),
    "TSMS05": (938, 363), "TSMS06": (1025, 190), "TSMS07": (1057, 280), "TSMS08": (1058, 173)}
report_fig10_2 = {  # Fig. 10.2 (PDF p.62): monthly precipitation R2 and bias (mm), from the text only (figure not machine-readable)
    "TSMS00": (0.68, -7.0), "TSMS01": (0.08, np.nan), "TSMS02": (0.22, np.nan), "TSMS03": (0.21, np.nan),
    "TSMS04": (0.01, 22.9), "TSMS05": (0.28, np.nan), "TSMS06": (0.82, np.nan), "TSMS07": (0.62, np.nan),
    "TSMS08": (np.nan, np.nan)}
N_MIN, N_DAYS, DAY_MIN = 1_578_240, 1_096, 1_152         # report §5.1 / §5.2


WET_THRESHOLDS = [0.2, 1.0]    # mm/day: report parity, ETCCDI R1mm (docs/potential-fixes.md PF-40)


def load(path, cols):
    d = pd.read_csv(path, usecols=['date'] + cols, parse_dates=['date'], keep_default_na=False,
                    na_values={c: [''] for c in cols if not c.endswith('_flag')})
    for c in cols:
        if not c.endswith('_flag'): d[c] = pd.to_numeric(d[c], errors='coerce')
    return d.drop_duplicates('date').set_index('date').loc[START:END]


def stats(t, p):
    d = p - t
    r = np.corrcoef(t, p)[0, 1] if len(t) > 2 else np.nan
    return len(d), d.mean(), np.abs(d).mean(), np.sqrt((d ** 2).mean()), r ** 2


def load_qc(stem, d, cols):
    """Report-definition ("QC-valid") values and a before-QC availability mask for `cols` of the cleaned frame d.
    QC-valid = d plus values our Step 7 removed only for daily completeness (restored from *_outliers.csv).
    Before QC = QC-valid or removed by any other QC reason (null markers, i.e. missing values, stay missing)."""
    o = pd.read_csv(cleaned / f"{stem}_outliers.csv", usecols=['date', 'column_name', 'original_value', 'outlier_type'],
                    parse_dates=['date'])
    o = o[o['column_name'].isin(cols) & (o['date'] >= START) & (o['date'] <= END)]
    o = o.drop_duplicates(['date', 'column_name', 'outlier_type'])
    q, raw = d[cols].copy(), pd.DataFrame(index=d.index)
    for c in cols:
        oc = o[o['column_name'] == c]
        dc = oc[oc['outlier_type'] == 'daily_completeness'].drop_duplicates('date').set_index('date')['original_value']
        q[c] = q[c].combine_first(pd.to_numeric(dc, errors='coerce').reindex(q.index))
        other = oc.loc[~oc['outlier_type'].isin(['daily_completeness', 'null_marker']), 'date'].unique()
        raw[c] = q[c].notna() | q.index.isin(other)
    return q, raw


def minute_pct(mask):
    return 100 * mask.sum() / N_MIN


def day_stats(mask):
    per_day = mask.resample('D').sum().reindex(pd.date_range(START, END[:10], freq='D'), fill_value=0)
    n = int((per_day >= DAY_MIN).sum())
    return n, 100 * n / N_DAYS


def stat_cols(ours, rep=None):
    """ours/rep = (N, bias, MAE, RMSE, R2); report cells blank when rep is None."""
    rep = rep if rep is not None else (np.nan,) * 5
    row = {}
    for i, k in enumerate(['N', 'Bias', 'MAE', 'RMSE', 'R2']):
        row[f'{k} (report)'], row[f'{k} (ours)'] = rep[i], ours[i]
    return row


REF_VARS = ['temperature', 'humidity', 'actual_pressure', 'avg_wind_speed', 'avg_wind_dir']
T_SENSORS = [('mcp9808', 'MCP9808'), ('bmp2_temp', 'BMP280'), ('htu_temp', 'HTU21D'), ('sth_temp', 'SHT31D')]
H_SENSORS = [('hum', 'Active sensor (SHT31D, else HTU21D)'), ('htu_hum', 'HTU21D'), ('sth_hum', 'SHT31D')]
PAWS_VARS = [s for s, _ in T_SENSORS] + ['htu_hum', 'sth_hum', 'bmp2_pres', 'wind_speed', 'wind_dir']
REPORT_SENSOR = {'mcp9808', 'hum', 'bmp2_pres', 'wind_speed'}           # report Table 1
comp_rows, cont_rows, wdq_rows, t9_rows, mp_rows = [], {'temperature': [], 'humidity': [], 'pressure': [],
                                                        'wind_speed': []}, [], [], []


def completeness_row(site, station, masks, raws, spec):
    """spec: list of (report index or None, column label, mask key)."""
    r2, r3 = report_t2.get(station), report_t3.get(station)
    c2, c3 = {'Site': site, 'Station': station}, {'Site': site, 'Station': station}
    for idx, label, key in spec:
        if idx is not None:
            c2[f'{label} (report)'] = r2[idx]
            c3[f'{label} (report)'] = r3[idx]
        c2[f'{label} (ours)'] = minute_pct(masks[key])
        nd, pdays = day_stats(masks[key])
        c3[f'{label} (ours)'] = pdays
        c3[f'{label} days (ours)'] = nd
        if idx is not None:
            c2[f'{label} before QC removals (ours)'] = minute_pct(raws[key])
            c3[f'{label} before QC removals (ours)'] = day_stats(raws[key])[1]
    return c2, c3


rows, wd_rows, pr_rows = [], [], []
for site, stations in sites.items():
    ref = load(cleaned / f"TSMS_Reference_{site}_final.csv", REF_VARS + ['total_rainfall', 'total_rainfall_flag'])
    ref['ws2'] = ref['avg_wind_speed'] * (2 / 10) ** hellman[site]
    refq, refraw = load_qc(f"TSMS_Reference_{site}", ref, REF_VARS)
    refq['ws2'] = refq['avg_wind_speed'] * (2 / 10) ** hellman[site]
    spec_ref = [(0, 'Temperature', 'temperature'), (1, 'RH', 'humidity'), (2, 'Pressure', 'actual_pressure'),
                (3, 'Wind speed', 'avg_wind_speed')]
    c2, c3 = completeness_row(site, ref_id[site], {k: refq[k].notna() for _, _, k in spec_ref},
                              {k: refraw[k] for _, _, k in spec_ref}, spec_ref)
    comp_rows.append((c2, c3))
    for stn in stations:
        paws = load(cleaned / f"3DPAWS_{stn}_{site}_final.csv", PAWS_VARS + ['tipping', 'tipping_flag'])
        paws['hum'] = paws['sth_hum'].combine_first(paws['htu_hum'])
        m = ref.join(paws, how='inner')

        # ---- parity tables: QC-valid (report-definition) values
        pq, praw = load_qc(f"3DPAWS_{stn}_{site}", paws, PAWS_VARS)
        pq['hum'] = pq['sth_hum'].combine_first(pq['htu_hum'])
        praw['hum'] = praw['sth_hum'] | praw['htu_hum']
        spec = ([(0, 'Temperature', 'mcp9808'), (1, 'RH', 'hum'), (2, 'Pressure', 'bmp2_pres'), (3, 'Wind speed', 'wind_speed')]
                + [(None, f'Temp {l}', c) for c, l in T_SENSORS[1:]] + [(None, 'RH HTU21D', 'htu_hum'), (None, 'RH SHT31D', 'sth_hum')])
        comp_rows.append(completeness_row(site, stn, {k: pq[k].notna() for _, _, k in spec},
                                          {k: praw[k] for _, _, k in spec}, spec))
        mq = refq.join(pq, how='inner')
        groups = [('temperature', 'temperature', T_SENSORS), ('humidity', 'humidity', H_SENSORS),
                  ('pressure', 'actual_pressure', [('bmp2_pres', 'BMP280 station pressure')]),
                  ('wind_speed', 'ws2', [('wind_speed', '3D-PAWS anemometer (2 m)')])]
        for var, rc, sensors in groups:
            for pc, label in sensors:
                x = mq[[rc, pc]].dropna()
                variants = [('all QC-valid paired minutes (report method)', x)]
                if var == 'wind_speed':
                    variants.append(('sensitivity: calm excluded (both anemometers > 0)',
                                     x[(x[rc] > 0) & (x[pc] > 0)]))
                for vname, xx in variants:
                    ours = stats(xx[rc].to_numpy(), xx[pc].to_numpy()) if len(xx) else (0,) + (np.nan,) * 4
                    is_rep = pc in REPORT_SENSOR and vname.endswith('(report method)')
                    row = {'Site': site, 'Station': stn, 'Sensor': label,
                           'In report?': 'yes (report sensor)' if is_rep else 'no (extra sensor/variant)'}
                    if var == 'wind_speed':
                        row['Pairing'] = vname
                    row.update(stat_cols(ours, report[var][stn] if is_rep else None))
                    cont_rows[var].append(row)

        xq = mq[['avg_wind_dir', 'wind_dir', 'avg_wind_speed', 'wind_speed']].dropna()
        xq = xq[(xq['avg_wind_speed'] > 0) & (xq['wind_speed'] > 0)]
        aq = np.abs(xq['wind_dir'] - xq['avg_wind_dir']) % 360
        aq = np.minimum(aq, 360 - aq)
        rw = report_wind_dir[stn]
        wdq_rows.append({'Site': site, 'Station': stn, 'N (report)': rw[0], 'N (ours)': len(aq),
                         'Mean abs error ° (report)': rw[1], 'Mean abs error ° (ours)': aq.mean(),
                         'Median abs error ° (report)': rw[2], 'Median abs error ° (ours)': aq.median(),
                         'Within ±22.5° % (report)': rw[3], 'Within ±22.5° % (ours)': 100 * (aq <= 22.5).mean(),
                         'Within ±45° % (report)': rw[4], 'Within ±45° % (ours)': 100 * (aq <= 45).mean(),
                         'Within ±90° % (report)': rw[5], 'Within ±90° % (ours)': 100 * (aq <= 90).mean()})
        for var, rc, pc in [("temperature", "temperature", "mcp9808"), ("humidity", "humidity", "hum"),
                            ("pressure", "actual_pressure", "bmp2_pres"), ("wind_speed", "ws2", "wind_speed")]:
            x = m[[rc, pc]].dropna()
            n, b, mae, rmse, r2 = stats(x[rc].to_numpy(), x[pc].to_numpy())
            rn, rb, rmae, rrmse, rr2 = report[var][stn]
            rows.append({'Variable': var, 'Site': site, 'Station': stn, 'N (ours)': n, 'N (report)': rn,
                         'Bias (ours)': b, 'Bias (report)': rb, 'MAE (ours)': mae, 'MAE (report)': rmae,
                         'RMSE (ours)': rmse, 'RMSE (report)': rrmse, 'R2 (ours)': r2, 'R2 (report)': rr2})

        x = m[['avg_wind_dir', 'wind_dir', 'avg_wind_speed', 'wind_speed']].dropna()
        x = x[(x['avg_wind_speed'] > 0) & (x['wind_speed'] > 0)]
        a = np.abs(x['wind_dir'] - x['avg_wind_dir']) % 360
        a = np.minimum(a, 360 - a)
        rw = report_wind_dir[stn]
        wd_rows.append({'Site': site, 'Station': stn, 'N (ours)': len(a), 'N (report)': rw[0],
                        'Mean abs (ours)': a.mean(), 'Mean abs (report)': rw[1],
                        'Median abs (ours)': a.median(), 'Median abs (report)': rw[2],
                        '% ≤22.5 (ours)': 100 * (a <= 22.5).mean(), '% ≤22.5 (report)': rw[3],
                        '% ≤45 (ours)': 100 * (a <= 45).mean(), '% ≤45 (report)': rw[4],
                        '% ≤90 (ours)': 100 * (a <= 90).mean(), '% ≤90 (report)': rw[5]})

        # precipitation: daily totals on >= 80%-complete days for each gauge
        def daily(s):
            g = s.resample('D').agg(['sum', 'count'])
            return g['sum'].where(g['count'] >= 1152)
        def flagged_day(f):
            return (f.astype(str).str.len() > 0).resample('D').max().astype(bool)
        dd = pd.DataFrame({'ref': daily(ref['total_rainfall']), 'paws': daily(paws['tipping'])}).dropna()
        dd['flag'] = (flagged_day(ref['total_rainfall_flag']).reindex(dd.index, fill_value=False) |
                      flagged_day(paws['tipping_flag']).reindex(dd.index, fill_value=False))
        rp = report_precip[stn]
        for subset, days in [("all days", dd), ("flagged days excluded", dd[~dd['flag']])]:
            for thr in WET_THRESHOLDS:
                rw_, pw_ = days['ref'] >= thr, days['paws'] >= thr
                h, mi, fa, cn = (rw_ & pw_).sum(), (rw_ & ~pw_).sum(), (~rw_ & pw_).sum(), (~rw_ & ~pw_).sum()
                parity = (thr == 0.2 and subset == "all days")     # the report's definition: compare with Table 9
                pr_rows.append({'Site': site, 'Station': stn, 'Wet threshold (mm)': thr, 'Days': subset,
                                'Paired days (ours)': len(days), 'Paired days (report)': rp[0] if parity else np.nan,
                                'Ref wet days (ours)': h + mi, 'Ref wet days (report)': rp[1] + rp[2] if parity else np.nan,
                                '3D-PAWS wet days (ours)': h + fa, '3D-PAWS wet days (report)': rp[1] + rp[3] if parity else np.nan,
                                'Hits': h, 'Misses': mi, 'False alarms': fa, 'Correct negatives': cn,
                                'POD (ours)': h / (h + mi) if h + mi else np.nan, 'POD (report)': rp[5] if parity else np.nan,
                                'FAR (ours)': fa / (h + fa) if h + fa else np.nan, 'FAR (report)': rp[6] if parity else np.nan,
                                'CSI (ours)': h / (h + mi + fa) if h + mi + fa else np.nan, 'CSI (report)': rp[7] if parity else np.nan,
                                'Ref total mm (ours)': days['ref'].sum(), '3D-PAWS total mm (ours)': days['paws'].sum()})

        # ---- parity Table 9: station-specific valid/wet days (independent of the reference) + contingency
        pdaily = daily(paws['tipping']).loc[START:END[:10]].dropna()
        rdaily = daily(ref['total_rainfall']).loc[START:END[:10]].dropna()
        pflag = flagged_day(paws['tipping_flag']).reindex(pdaily.index, fill_value=False)
        rflag = flagged_day(ref['total_rainfall_flag']).reindex(rdaily.index, fill_value=False)
        rv = report_t9_valid[stn]
        caveat = ("NOT COMPARABLE: our Ankara reference rain is x10 too high from 2023-03-06 (SF-09, newer TSMS export); "
                  "the report used correct data. Not corrected here (team decision)." if site == "Ankara" else "")
        for subset, days, pd_, rd_ in [("all days", dd, pdaily, rdaily),
                                       ("flagged days excluded", dd[~dd['flag']], pdaily[~pflag], rdaily[~rflag])]:
            for thr in WET_THRESHOLDS:
                rw_, pw_ = days['ref'] >= thr, days['paws'] >= thr
                h, mi, fa, cn = (rw_ & pw_).sum(), (rw_ & ~pw_).sum(), (~rw_ & pw_).sum(), (~rw_ & ~pw_).sum()
                par = (thr == 0.2 and subset == "all days")
                rr = lambda v: v if par else np.nan
                t9_rows.append({
                    'Site': site, 'Station': stn, 'Reference': ref_id[site], 'Wet threshold (mm/day)': thr,
                    'Days used': subset + (" (report definition)" if par else ""),
                    'Valid days, 3D-PAWS (report)': rr(rv[0]), 'Valid days, 3D-PAWS (ours)': len(pd_),
                    'Wet days, 3D-PAWS (report)': rr(rv[1]), 'Wet days, 3D-PAWS (ours)': int((pd_ >= thr).sum()),
                    'Valid days, reference (ours)': len(rd_), 'Wet days, reference (ours)': int((rd_ >= thr).sum()),
                    'Paired days (report)': rr(rp[0]), 'Paired days (ours)': len(days),
                    'Hits (report)': rr(rp[1]), 'Hits (ours)': h, 'Misses (report)': rr(rp[2]), 'Misses (ours)': mi,
                    'False alarms (report)': rr(rp[3]), 'False alarms (ours)': fa,
                    'Correct negatives (report)': rr(rp[4]), 'Correct negatives (ours)': cn,
                    'POD (report)': rr(rp[5]), 'POD (ours)': h / (h + mi) if h + mi else np.nan,
                    'FAR (report)': rr(rp[6]), 'FAR (ours)': fa / (h + fa) if h + fa else np.nan,
                    'CSI (report)': rr(rp[7]), 'CSI (ours)': h / (h + mi + fa) if h + mi + fa else np.nan,
                    'Caveat': caveat})

        # ---- Fig. 10.2 (text values): monthly totals over paired >= 80%-complete days
        mon = dd[['ref', 'paws']].resample('MS').agg(['sum', 'count'])
        mon = mon[mon[('ref', 'count')] > 0]
        mr, mp = mon[('ref', 'sum')].to_numpy(), mon[('paws', 'sum')].to_numpy()
        rf = report_fig10_2[stn]
        mp_rows.append({'Site': site, 'Station': stn, 'Months (ours)': len(mr),
                        'Bias mm/month (report)': rf[1], 'Bias mm/month (ours)': (mp - mr).mean(),
                        'R2 (report)': rf[0], 'R2 (ours)': np.corrcoef(mr, mp)[0, 1] ** 2 if len(mr) > 2 else np.nan,
                        'Ref total mm (ours)': mr.sum(), '3D-PAWS total mm (ours)': mp.sum(), 'Caveat': caveat})

pd.DataFrame(rows).round(3).to_csv(out / "continuous-variables.csv", index=False)
pd.DataFrame(wd_rows).round(2).to_csv(out / "wind-direction.csv", index=False)
pd.DataFrame(pr_rows).round(3).to_csv(out / "precipitation.csv", index=False)


# ================================================================================================= parity tables
def ordered(rows_, first=('Site', 'Station')):
    """DataFrame with the report/ours columns in the order they first appear across all rows."""
    cols = list(first)
    for r in rows_:
        cols += [k for k in r if k not in cols]
    return pd.DataFrame(rows_)[cols]


t2 = ordered([c2 for c2, _ in comp_rows]).round(2)
t3 = ordered([c3 for _, c3 in comp_rows]).round(2)
t_cont = {k: pd.DataFrame(v).pipe(lambda d: d[d['N (ours)'] > 0]).round(3)   # drop sensors a station doesn't have
          for k, v in cont_rows.items()}
t8 = pd.DataFrame(wdq_rows).round(2)
t9 = pd.DataFrame(t9_rows).round(3)
fig102 = pd.DataFrame(mp_rows).round(3)

QC_OURS = "Ours = data/cleaned plus the minutes our Step 7 removed only for daily completeness (report definition)."
t1 = pd.DataFrame([  # Table 1 (PDF p.10) transcribed, next to our QC (docs/qc-framework.md; IDs in method-differences.md)
    ("Step test", "Temperature", "Difference > 2 °C", "Same limit, flag only; kept if a co-located instrument shows the same change (Steps 4a, 6a)", "G20, G22"),
    ("Step test", "Relative humidity", "Difference > 15%", "Same limit, flag only (Steps 4a, 6a); separate HTU21D bit-switching removal", "G11, G20"),
    ("Step test", "Actual pressure", "Difference > 0.5 mb", "Same limit, flag only (Steps 4a, 6a)", "G20"),
    ("Step test", "Precipitation", "Difference > 5 mm", "Same limit, flag only (rain is never removed)", "G20"),
    ("Step test", "Wind speed", "Difference > 8 m/s", "Same limit, flag only; wind flags are never removed", "G20"),
    ("Step test", "Wind direction", "–", "Not tested (same)", "G20"),
    ("Interval test", "Temperature", "−50 ≤ x ≤ 50; varies by month", "Fixed instrument/physical limits; monthly climatological limits not yet implemented (report's values not given)", "PF-39"),
    ("Interval test", "Relative humidity", "0 ≤ x ≤ 105; 5 ≤ x ≤ 100", "Fixed limits; stuck sensors removed as documented failures", "G14"),
    ("Interval test", "Actual pressure", "700 ≤ x ≤ 1070; varies by month", "Fixed limits", "PF-39"),
    ("Interval test", "Precipitation", "0 ≤ x ≤ 12; x ≤ 5", "Fixed limits", ""),
    ("Interval test", "Wind speed", "0 ≤ x ≤ 100; x ≤ 17.2", "Fixed limits", ""),
    ("Interval test", "Wind direction", "0 ≤ x ≤ 360", "0–360", ""),
    ("Logic test", "Precipitation", "When it is raining, humidity should be above 60%", "Flag only (rain_low_rh), not removed", "G19"),
    ("Logic test", "Wind speed / direction", "When wind speed is measured, direction should be measured; when speed is 0, direction cannot be 0", "Not a QC removal; in these tables direction is compared only where both anemometers read > 0", "WD5"),
    ("Logic test", "Solar radiation (VIS, IR)", "Measurement between sunrise and sunset", "Solar radiation not analysed", ""),
    ("Persistence test", "Temperature", "Value repeated 100 consecutive times (−50 ≤ x ≤ 50)", "Removed if unchanged for 3 h; plus frozen-logger test (all variables unchanged ≥ 60 min)", "G21"),
    ("Persistence test", "Relative humidity", "Value repeated 100 consecutive times (0 < x ≤ 105)", "Removed if unchanged for 3 h and below 80% (saturation plateaus are real)", "G21"),
    ("Persistence test", "Actual pressure", "Value repeated 100 consecutive times (700 ≤ x ≤ 1070)", "Removed if unchanged for 3 h", "G21"),
    ("Persistence test", "Precipitation", "Not applicable", "Not applied (same); dead gauges found by the daily neighbour check (flag)", "G21"),
    ("Persistence test", "Wind speed", "Value repeated 100 consecutive times (1 ≤ x ≤ 100)", "Not tested; calm runs ≥ 3 h removed when ≥ 2 other 3D-PAWS anemometers read ≥ 1.5 m/s (Step 6b)", "G21"),
    ("Persistence test", "Wind direction", "Value repeated 120 consecutive times (1 ≤ x ≤ 360)", "Removed if unchanged through a run with ≥ 60 min of wind ≥ 1 m/s", "G21"),
    ("Persistence test", "Solar radiation (VIS, IR)", "Value repeated 100 consecutive times (1 ≤ x ≤ 20000)", "Solar radiation not analysed", ""),
    ("Statistical outliers (§4.4)", "All", "61-point centred window; MAD score > 3.5 or |z| > 3.0; flagged values excluded", "21-min centred window, Hampel k = 3 (MAD × 1.4826) or |z| > 3 with a resolution floor; flag only, removed if no co-located instrument corroborates; not applied to wind or rain", "G12, G15, G18, G22, G23"),
    ("Spatial consistency (§4.5)", "All (3D-PAWS only)", "Deviation from the 3D-PAWS site median > variable threshold (not given), ≥ 3 valid observations; flagged values excluded", "Each instrument's deviation from its own 21-min median compared across all co-located instruments incl. the reference; confirms/clears flags", "G24"),
    ("Daily completeness (§5.2)", "All", "≥ 1,152 of 1,440 minutes; used for daily aggregation and event analyses only", "Step 7 blanks < 80% days in data/cleaned for every analysis; the parity tables restore those minutes", "G3"),
], columns=['Test', 'Variable', 'Report criterion (Table 1)', 'Ours (docs/qc-framework.md)', 'method-differences.md'])

# ---- internal-consistency checks of the report's own tables
chk = []
t3_int = [f"{k}:{v}" for k, vals in report_t3.items() for v in vals if abs(round(v * N_DAYS / 100) / N_DAYS * 100 - v) > 0.006]
chk.append(("Table 3 % × 1,096 days gives whole days", "3", "OK" if not t3_int else "FAIL", ", ".join(t3_int) or "all 48 cells"))
bad = []
for k in report_t2:
    for i, v in enumerate(['T', 'RH', 'P', 'WS']):
        dpc, mpc = report_t3[k][i], report_t2[k][i]
        lo, hi = 0.8 * dpc, dpc + (DAY_MIN - 1) / 1440 * (100 - dpc)
        if not lo - 0.01 <= mpc <= hi + 0.01:
            bad.append(f"{k} {v}: {mpc}% minutes vs {dpc}% days (allowed {lo:.2f}–{hi:.2f})")
chk.append(("Table 2 minute % is possible given Table 3 day %", "2, 3", "OK" if not bad else "FAIL", "; ".join(bad) or "all 48 cells"))
text_ranges = {0: ("temperature", 80.94, 98.62), 1: ("RH", 62.87, 91.99), 2: ("pressure", 57.03, 98.83),
               3: ("wind speed", 52.77, 99.28)}                                            # §5.1 text, PDF p.15
for idx, (label, lo, hi) in text_ranges.items():
    vals = [v[idx] for v in report_t2.values()]
    chk.append((f"§5.1 text range for {label} matches Table 2", "2", "OK" if (min(vals), max(vals)) == (lo, hi) else "FAIL",
                f"text {lo}–{hi}%; Table 2 {min(vals)}–{max(vals)}%"))
bad = []
for var, idx in [("temperature", 0), ("humidity", 1), ("pressure", 2), ("wind_speed", 3)]:
    for site, stns in sites.items():
        for s in stns:
            share = 100 * report[var][s][0] / N_MIN
            cap = min(report_t2[s][idx], report_t2[ref_id[site]][idx])
            if share > cap + 0.01:
                bad.append(f"{var} {s}: N = {share:.2f}% of minutes > min completeness {cap}%")
chk.append(("Paired N (Tables 4–7) ≤ lower of station and reference completeness (Table 2)", "2, 4, 6, 6, 7",
            "OK" if not bad else "FAIL", "; ".join(bad) or "all 36 cells"))
bad = []
for s, (n, h, mi, fa, cn, pod, far, csi) in report_precip.items():
    if h + mi + fa + cn != n: bad.append(f"{s}: H+M+FA+CN = {h + mi + fa + cn} ≠ {n}")
    for nm, a, b in [("POD", h / (h + mi), pod), ("FAR", fa / (h + fa), far), ("CSI", h / (h + mi + fa), csi)]:
        if abs(round(a, 3) - b) > 0.0015: bad.append(f"{s}: {nm} {a:.3f} ≠ {b}")
    if report_t9_valid[s][1] < h + fa: bad.append(f"{s}: wet days {report_t9_valid[s][1]} < H+FA {h + fa}")
    if report_t9_valid[s][0] < n: bad.append(f"{s}: valid days {report_t9_valid[s][0]} < paired {n}")
chk.append(("Table 9 counts sum to paired days; POD/FAR/CSI recompute; wet/valid days ≥ paired subset", "9",
            "OK" if not bad else "FAIL", "; ".join(bad) or "all 9 stations"))
chk.append(("Table 9 implied reference wet days (H + M)", "9", "note",
            "; ".join(f"{s}: {report_precip[s][1] + report_precip[s][2]} of {report_precip[s][0]}" for s in report_precip)
            + ". Konya: Valid Days = Paired Days at all three stations, i.e. the reference was valid on every day the "
              "3D-PAWS station was."))
chk.append(("Table numbering", "5, 6", "FAIL", "There is no Table 5; 'Table 6' is used for both relative humidity "
            "(PDF p.30) and atmospheric pressure (PDF p.38). Humidity should presumably be Table 5."))
chk.append(("Humidity sensor label", "1, 6 (RH)", "note", "Table 1 names HTU21D_RH; TSMS03–08 report SHT31D values under that "
            "CHORDS label after the Jan 2024 upgrade, so the report's RH mixes two sensors (ours: 'active sensor')."))
checks = pd.DataFrame(chk, columns=['Check', 'Report table(s)', 'Result', 'Detail'])

tables = [  # (file stem, sheet name, frame, title, note)
    ("table-01_p10_qc-criteria", "T1 p10 QC", t1, "Table 1 (PDF p.10): QC tests and criteria, report vs ours",
     "Report column transcribed from Table 1; 'Ours' summarises docs/qc-framework.md. Solar radiation is not analysed by us."),
    ("table-02_p16_completeness", "T2 p16 completeness", t2,
     "Table 2 (PDF p.16): overall data completeness %, 1 Nov 2022 – 31 Oct 2025",
     "(report) = transcribed; (ours) = QC-valid minutes / 1,578,240. " + QC_OURS + " 'before QC removals' also counts "
     "values our QC removed (missing/null markers stay missing), bracketing the report's undefined 'availability'. "
     "3D-PAWS: Temperature = MCP9808, RH = active sensor (SHT31D, else HTU21D), Pressure = BMP280 (report Table 1); "
     "'Temp/RH <sensor>' columns are extra sensors the report doesn't show. Reference rows: 17130, 17245, 17351."),
    ("table-03_p17_daily-completeness", "T3 p17 daily", t3,
     "Table 3 (PDF p.17): % of the 1,096 days with ≥ 1,152 valid minutes (80% criterion)",
     "(report) = transcribed; (ours) = days with ≥ 1,152 QC-valid minutes / 1,096; 'days' = the count. Same sensors and "
     "'before QC removals' definition as Table 2. The report's percentages all correspond to whole day counts."),
    ("table-04_p18_temperature", "T4 p18 temperature", t_cont['temperature'],
     "Table 4 (PDF p.18): air temperature after QC, 3D-PAWS − TSMS, 1-min pairs",
     "Report values only on the MCP9808 row (the report's sensor, Table 1); BMP280/HTU21D/SHT31D rows are ours only "
     "(SHT31D only where installed: TSMS02, 03, 05, 06, 08). "
     "N = paired minutes where both are QC-valid. " + QC_OURS + " The same comparison on data/cleaned as written "
     "(≥ 80% days only) is in continuous-variables.csv."),
    ("table-06a_p30_humidity", "T6a p30 humidity", t_cont['humidity'],
     "Report 'Table 6' (PDF p.30; presumably Table 5): relative humidity after QC",
     "Report values beside the active-sensor row (SHT31D where present, else HTU21D; CHORDS labels both HTU21D_RH). "
     "HTU21D and SHT31D rows are ours only (SHT31D only where installed: TSMS02, 03, 05, 06, 08). " + QC_OURS),
    ("table-06b_p38_pressure", "T6b p38 pressure", t_cont['pressure'],
     "Report 'Table 6' (PDF p.38): atmospheric (station) pressure after QC",
     "BMP280 station pressure vs reference actual pressure (hPa). The report gives no sea-level-pressure table, so "
     "bmp2_slp is not compared. " + QC_OURS),
    ("table-07_p47_wind-speed", "T7 p47 wind speed", t_cont['wind_speed'],
     "Table 7 (PDF p.47): wind speed after QC, TSMS 10 m adjusted to 2 m (Hellmann α = 0.30 / 0.35 / 0.25)",
     "Report method (§3.2, §3.8): only TSMS adjusted, U2 = U10 (2/10)^α, all paired minutes (calms kept); report values "
     "beside that row. The 'calm excluded' row is a sensitivity check: the report's N can't be reproduced by any single "
     "rule, but calm-excluded N is within −15% to +3% of it at every station while all pairs is 1.2–1.8× it, so the report "
     "probably dropped calm minutes (perhaps via Table 1's 'speed 0 → direction cannot be 0' logic test). " + QC_OURS),
    ("table-08_p55_wind-direction", "T8 p55 wind dir", t8,
     "Table 8 (PDF p.55): circular wind-direction comparison",
     "Minimum circular separation |3D-PAWS − TSMS| at minutes where both anemometers read > 0 (the report doesn't state "
     "its calm rule; our N is 1.4–5× the report's). " + QC_OURS + " wind-direction.csv has the same on data/cleaned."),
    ("table-09_p57_precipitation", "T9 p57 precipitation", t9,
     "Table 9 (PDF p.57): daily precipitation detection (wet day ≥ threshold), contingency counts and scores",
     "Report values only beside the 0.2 mm / all-days row (the report's definition). Valid/Wet days = station-specific "
     "≥ 80%-complete days; Paired days and H/M/FA/CN = days both gauges are ≥ 80% complete. 'Flagged days excluded' "
     "drops days with any tipping/total_rainfall flag (for Valid/Wet days, only the station's own flag). ANKARA ROWS ARE "
     "NOT COMPARABLE: our Ankara reference rain is ×10 too high from 6 Mar 2023 (SF-09; the report used correct data); "
     "not corrected here pending the team's decision."),
    ("figure-10-2_p62_monthly-precipitation", "Fig10.2 p62 monthly rain", fig102,
     "Figure 10.2 (PDF p.62, not a table): monthly precipitation totals, bias and R²",
     "Report values from the text only (R² for TSMS00–07; bias only for TSMS00 −7.0 and TSMS04 +22.9 mm). Ours: monthly "
     "sums over paired ≥ 80%-complete days, bias = mean(3D-PAWS − TSMS) per month. Ankara not comparable (SF-09)."),
    ("report-consistency-checks", "Report checks", checks, "Internal-consistency checks of the report's tables",
     "Computed from the transcribed report values only (no data of ours). Unnumbered table on PDF p.59 "
     "(contingency interpretation) is descriptive text with no numbers, so it has no parity table."),
]
for stem, _, df, _, _ in tables:
    df.to_csv(out / f"{stem}.csv", index=False)

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

grey = PatternFill("solid", fgColor="E7E6E6")
with pd.ExcelWriter(out / "report-parity-tables.xlsx", engine="openpyxl") as xw:
    for stem, sheet, df, title, note in tables:
        df.to_excel(xw, sheet_name=sheet, index=False, startrow=3)
        ws = xw.sheets[sheet]
        ncol = max(len(df.columns), 1)
        ws["A1"], ws["A2"] = title, "Note: " + note + f"  [CSV: data/report-comparison/{stem}.csv]"
        ws["A1"].font = Font(bold=True, size=12)
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(ncol, 8))
        ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[2].height = 15 * max(2, len(ws["A2"].value) // 140 + 1)
        ws.row_dimensions[4].height = 45
        for j, col in enumerate(df.columns, start=1):
            cell = ws.cell(row=4, column=j)
            cell.font, cell.alignment = Font(bold=True), Alignment(wrap_text=True, vertical="top")
            longest = max([len(str(v)) for v in df[col].tolist()] + [0])
            width = min(max(longest + 2, min(len(str(col)), 16) + 2, 9), 60)
            ws.column_dimensions[get_column_letter(j)].width = width
            if "(report)" in str(col):
                for i in range(4, len(df) + 5):
                    ws.cell(row=i, column=j).fill = grey
            if longest > 60:
                for i in range(5, len(df) + 5):
                    ws.cell(row=i, column=j).alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = ws.cell(row=5, column=3)
print("Wrote", *(p.name for p in sorted(out.glob("*.csv"))), "report-parity-tables.xlsx")
