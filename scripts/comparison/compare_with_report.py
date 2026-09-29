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
==========================================================================================
"""
import numpy as np
import pandas as pd
from pathlib import Path

cleaned = Path("data/cleaned")
out = Path("data/report-comparison")
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


rows, wd_rows, pr_rows = [], [], []
for site, stations in sites.items():
    ref = load(cleaned / f"TSMS_Reference_{site}_final.csv",
               ['temperature', 'humidity', 'actual_pressure', 'avg_wind_speed', 'avg_wind_dir', 'total_rainfall',
                'total_rainfall_flag'])
    ref['ws2'] = ref['avg_wind_speed'] * (2 / 10) ** hellman[site]
    for stn in stations:
        paws = load(cleaned / f"3DPAWS_{stn}_{site}_final.csv",
                    ['mcp9808', 'htu_hum', 'sth_hum', 'bmp2_pres', 'wind_speed', 'wind_dir', 'tipping', 'tipping_flag'])
        paws['hum'] = paws['sth_hum'].combine_first(paws['htu_hum'])
        m = ref.join(paws, how='inner')
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

pd.DataFrame(rows).round(3).to_csv(out / "continuous-variables.csv", index=False)
pd.DataFrame(wd_rows).round(2).to_csv(out / "wind-direction.csv", index=False)
pd.DataFrame(pr_rows).round(3).to_csv(out / "precipitation.csv", index=False)
print("Wrote", *(p.name for p in sorted(out.glob("*.csv"))))
