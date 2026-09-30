#!/usr/bin/env python
"""
Diagnostic figures for the sensor failures catalogued in docs/sensor-failures.md.

One function per figure (fig_sf20, fig_sf27, ...); `main()` makes all of them and writes a
README.md with captions into each output folder:

    plots/diagnostics/3dpaws-sensor-failure/   3D-PAWS station failures
    plots/diagnostics/tsms-sensor-failure/     TSMS reference-station failures

The "what the sensor reported" views use the reformatted (pre-QC) minute data in
data/reformatted/; the QC removal / flag logs in data/cleaned/ are only used to shade what
QC removed or flagged. Nothing is written into data/.

Usage:
    python scripts/plotter/plot-sensor-failures.py                 # all figures
    python scripts/plotter/plot-sensor-failures.py SF-20 SF-27     # a subset
    python scripts/plotter/plot-sensor-failures.py --cache-dir /tmp/sfcache   # pickle the parsed CSVs
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

REPO = Path(__file__).resolve().parents[2]
OUT_3DP = REPO / "plots/diagnostics/3dpaws-sensor-failure"
OUT_REF = REPO / "plots/diagnostics/tsms-sensor-failure"
CACHE_DIR = None  # set by --cache-dir

# ----------------------------------------------------------------------------- style
C1, C2, C3 = "#0072B2", "#E69F00", "#009E73"   # first / second / third station of a site
CREF = "#222222"                                # TSMS reference
CBAD = "#D55E00"                                # failing / removed period band
BAD_ALPHA = 0.12
LW, LW_REF = 1.0, 1.5
DPI = 200
SITES = {"Ankara": ["TSMS00", "TSMS01", "TSMS02"],
         "Konya": ["TSMS03", "TSMS04", "TSMS05"],
         "Adana": ["TSMS06", "TSMS07", "TSMS08"]}
COLOR = {s: c for st in SITES.values() for s, c in zip(st, (C1, C2, C3))}
COLOR["ref"] = CREF

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.labelsize": 9,
    "legend.fontsize": 8, "legend.frameon": False, "axes.grid": True, "grid.color": "#dddddd",
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#888888", "xtick.color": "#444444", "ytick.color": "#444444",
    "figure.facecolor": "white", "axes.axisbelow": True,
})

# ----------------------------------------------------------------------------- data
STN_COLS = ["date", "bmp2_temp", "htu_temp", "sth_temp", "mcp9808", "htu_hum", "sth_hum",
            "bmp2_pres", "wind_dir", "wind_speed", "tipping"]
REF_COLS = ["date", "temperature", "humidity", "actual_pressure", "avg_wind_dir",
            "avg_wind_speed", "total_rainfall"]
REF_FILE = {"Ankara": "station_TSMS00/Ankara_Oct22-Dec25.csv",
            "Konya": "station_TSMS03/Konya_Oct22-Dec25.csv",
            "Adana": "station_TSMS06/Adana_Oct22-Dec25.csv"}
_MEM = {}


def _read_csv(path, cols):
    """Read the needed columns, strip names, parse date, drop duplicate dates, <= -990 -> NaN."""
    df = pd.read_csv(path, usecols=lambda c: c.strip() in cols, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df = df.dropna(subset=["date"]).drop_duplicates("date", keep="first")
    df = df.set_index("date").sort_index()
    for c in df.columns:
        v = pd.to_numeric(df[c], errors="coerce").astype("float32")
        df[c] = v.where(v > -990)
    return df


def _load(key, path, cols):
    if key in _MEM:
        return _MEM[key]
    pkl = CACHE_DIR / f"{key}.pkl" if CACHE_DIR else None
    if pkl is not None and pkl.exists():
        df = pd.read_pickle(pkl)
    else:
        df = _read_csv(path, cols)
        if pkl is not None:
            pkl.parent.mkdir(parents=True, exist_ok=True)
            df.to_pickle(pkl)
    _MEM[key] = df
    return df


def station(sid, start=None, end=None):
    """3D-PAWS reformatted minute data for one station, sliced to [start, end]."""
    df = _load(sid, REPO / f"data/reformatted/station_{sid}/{sid}_Nov22-Nov25.csv", STN_COLS)
    return df.loc[start:end]


def reference(site, start=None, end=None):
    """TSMS reference reformatted minute data for a site, sliced to [start, end]."""
    df = _load(f"ref_{site}", REPO / "data/reformatted" / REF_FILE[site], REF_COLS)
    return df.loc[start:end]


def qc_log(name, kind="outliers"):
    """data/cleaned/<name>_<kind>.csv (outliers or flags) with parsed dates."""
    df = pd.read_csv(REPO / f"data/cleaned/{name}_{kind}.csv")
    df.columns = [c.strip() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def minute_runs(times, gap="1min"):
    """Group a set of timestamps into contiguous runs -> DataFrame(start, end, minutes)."""
    t = pd.Series(pd.DatetimeIndex(times).unique().sort_values())
    if t.empty:
        return pd.DataFrame(columns=["start", "end", "minutes"])
    g = (t.diff() > pd.Timedelta(gap)).cumsum()
    r = t.groupby(g.values).agg(["min", "max", "count"])
    r.columns = ["start", "end", "minutes"]
    return r.reset_index(drop=True)


def value_runs(s, value=0.0, min_len=1):
    """Contiguous runs (consecutive rows) of s == value with >= min_len rows."""
    hit = s == value
    g = (hit != hit.shift()).cumsum()
    out = [(grp.index[0], grp.index[-1], len(grp)) for _, grp in s[hit].groupby(g[hit])
           if len(grp) >= min_len]
    return pd.DataFrame(out, columns=["start", "end", "minutes"])


def daily(s, how="mean", min_frac=0.5):
    """Daily aggregate; days with < min_frac of 1440 valid minutes -> NaN."""
    r = s.resample("D")
    n = r.count()
    v = r.mean() if how == "mean" else r.sum()
    return v.where(n >= min_frac * 1440)


# ----------------------------------------------------------------------------- plot helpers
def shade(ax, start, end, label=None):
    ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), color=CBAD, alpha=BAD_ALPHA, lw=0,
               label=label)


def shade_runs(ax, runs, label=None, pad="0min"):
    for i, r in enumerate(runs.itertuples()):
        shade(ax, r.start - pd.Timedelta(pad), r.end + pd.Timedelta(pad),
              label=label if i == 0 else None)


def bad_patch(label):
    return Patch(facecolor=CBAD, alpha=BAD_ALPHA * 2.5, lw=0, label=label)


def time_axis(ax, label="Date (UTC)"):
    loc = mdates.AutoDateLocator(minticks=4, maxticks=10)
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc, show_offset=True))
    ax.set_xlabel(label)


def line(ax, s, key, label, **kw):
    lw = LW_REF if key == "ref" else LW
    if s.notna().sum() == 0:
        label += " (no data)"
    elif isinstance(s.index, pd.DatetimeIndex) and len(s) > 2 and \
            (s.index[-1] - s.index[0]) <= pd.Timedelta("60D") and \
            pd.Series(s.index).diff().median() == pd.Timedelta("1min"):
        s = s.asfreq("min")  # missing minutes -> NaN so the line breaks instead of bridging gaps
    ax.plot(s.index, s.values, color=COLOR.get(key, key), lw=kw.pop("lw", lw), label=label,
            zorder=3 if key == "ref" else 2, **kw)


def dots(ax, s, key, label, size=2.0):
    ax.scatter(s.index, s.values, s=size, color=COLOR.get(key, key), label=label, lw=0,
               zorder=3 if key == "ref" else 2, rasterized=True)


def unswitch(h, win=15, tol=8.0):
    """Mask HTU21D bit-switching spikes (SF-03) for display.

    The switched minutes sit well above the real readings and can be up to about half of them, so a
    median does not work: keep minutes within tol %RH of the rolling 10th percentile.
    """
    base = h.rolling(win, center=True, min_periods=3).quantile(0.1)
    return h.where((h - base) <= tol)


def legend(ax, extra=None, **kw):
    h, l = ax.get_legend_handles_labels()
    if extra:
        for e in extra:
            h.append(e)
            l.append(e.get_label())
    kw.setdefault("loc", "upper left")
    kw.setdefault("ncol", min(len(h), 6))
    ax.legend(h, l, markerscale=4, **kw)


def panel_tag(ax, tag):
    ax.text(0.0, 1.02, tag, transform=ax.transAxes, fontsize=10, fontweight="bold",
            va="bottom", ha="left")


def save(fig, folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    fig.savefig(p, dpi=DPI)
    plt.close(fig)
    print("wrote", p.relative_to(REPO))
    return p


REF_LABEL = {"Ankara": "Ankara reference", "Konya": "Konya reference", "Adana": "Adana reference"}

# ============================================================================= 3D-PAWS figures


def fig_sf20():
    """SF-20: TSMS02 anemometer disconnected (exactly 0 m/s), 2023-03-31 12:17 -> 2024-01-11 10:02."""
    t0, t1 = pd.Timestamp("2023-03-31 12:17"), pd.Timestamp("2024-01-11 10:02")
    a, b = "2023-01-01", "2024-03-31 23:59"
    z0, z1 = "2023-06-12", "2023-06-14 23:59"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6.5), gridspec_kw=dict(height_ratios=[1.4, 1]),
                                   layout="constrained")
    for sid in SITES["Ankara"]:
        line(ax1, daily(station(sid, a, b)["wind_speed"]), sid, sid)
    line(ax1, daily(reference("Ankara", a, b)["avg_wind_speed"]), "ref", "Ankara reference (10 m)")
    shade(ax1, t0, t1, "TSMS02 reports exactly 0 m/s")
    ax1.set_ylabel("Daily mean wind speed (m/s)")
    ax1.set_xlim(pd.Timestamp(a), pd.Timestamp(b))
    ax1.set_ylim(bottom=-0.2)
    time_axis(ax1)
    legend(ax1)
    panel_tag(ax1, "A  daily means")

    for sid in SITES["Ankara"]:
        line(ax2, station(sid, z0, z1)["wind_speed"], sid, sid, lw=0.7)
    line(ax2, reference("Ankara", z0, z1)["avg_wind_speed"], "ref", "Ankara reference (10 m)", lw=1.1)
    ax2.set_ylabel("1-min wind speed (m/s)")
    ax2.set_xlim(pd.Timestamp(z0), pd.Timestamp(z1))
    ax2.set_ylim(bottom=-0.2)
    time_axis(ax2, "Time (UTC)")
    legend(ax2)
    panel_tag(ax2, "B  3 days inside the outage, 1-min")
    fig.suptitle("SF-20 · TSMS02 · anemometer disconnected, wind speed stuck at 0", fontweight="bold")
    return save(fig, OUT_3DP, "SF-20_TSMS02_anemometer_disconnected.png")


def fig_sf27():
    """SF-27: TSMS08 anemometer not responding (zero runs while TSMS06/07 read wind)."""
    a, b = "2023-01-01", "2024-12-31 23:59"
    z0, z1 = "2023-07-05", "2023-07-08 23:59"
    ol = qc_log("3DPAWS_TSMS08_Adana")
    rem = ol.loc[(ol.outlier_type == "anemometer_not_responding") & (ol.column_name == "wind_speed"), "date"]
    per_day = rem.dt.floor("D").value_counts().sort_index()

    fig = plt.figure(figsize=(12, 7), layout="constrained")
    gs = fig.add_gridspec(3, 1, height_ratios=[1.4, 0.45, 1.1])
    ax1 = fig.add_subplot(gs[0])
    axs = fig.add_subplot(gs[1], sharex=ax1)
    ax2 = fig.add_subplot(gs[2])
    for sid in SITES["Adana"]:
        line(ax1, daily(station(sid, a, b)["wind_speed"]), sid, sid)
    ax1.set_ylabel("Daily mean wind\nspeed (m/s)")
    ax1.set_ylim(bottom=0)
    legend(ax1)
    ax1.tick_params(labelbottom=False)
    panel_tag(ax1, "A  daily means (all minutes, before QC)")

    axs.bar(per_day.index, per_day.values, width=1.0, color=CBAD, alpha=0.7, lw=0,
            label="TSMS08 minutes removed as anemometer_not_responding")
    axs.set_ylabel("Removed\nmin/day")
    axs.set_ylim(0, 1440)
    axs.set_yticks([0, 720, 1440])
    axs.set_xlim(pd.Timestamp(a), pd.Timestamp(b))
    time_axis(axs)
    legend(axs)

    for sid in SITES["Adana"]:
        line(ax2, station(sid, z0, z1)["wind_speed"], sid, sid, lw=0.7)
    shade_runs(ax2, minute_runs(rem[(rem >= z0) & (rem <= z1)]), "removed by QC (TSMS08)")
    ax2.set_ylabel("1-min wind speed (m/s)")
    ax2.set_xlim(pd.Timestamp(z0), pd.Timestamp(z1))
    ax2.set_ylim(bottom=-0.2)
    time_axis(ax2, "Time (UTC)")
    legend(ax2)
    panel_tag(ax2, "B  4 days in July 2023, 1-min")
    fig.suptitle("SF-27 · TSMS08 · anemometer not responding (reads 0 while neighbours read wind)",
                 fontweight="bold")
    return save(fig, OUT_3DP, "SF-27_TSMS08_anemometer_not_responding.png")


def fig_sf17():
    """SF-17: TSMS06 logger writing exactly 0.0 on all temperature/humidity sensors."""
    a, b = "2024-08-01", "2025-06-30 23:59"
    z0, z1 = "2025-04-05 12:00", "2025-04-07 12:00"
    s = station("TSMS06", a, b)
    r = reference("Adana", a, b)
    ol = qc_log("3DPAWS_TSMS06_Adana")
    rem = minute_runs(ol.loc[ol.outlier_type == "logger_zeros", "date"], gap="30min")
    rem = rem[(rem.end >= a) & (rem.start <= b)]
    sensors = [("bmp2_temp", C2, "TSMS06 BMP280"), ("sth_temp", C3, "TSMS06 SHT31"),
               ("mcp9808", C1, "TSMS06 MCP9808")]

    def sub(x):  # every 10th minute: keeps the flat 0 runs visible, keeps the file light
        return x.iloc[::10]

    fig = plt.figure(figsize=(12, 8), layout="constrained")
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1])
    axT = fig.add_subplot(gs[0, :])
    axH = fig.add_subplot(gs[1, :], sharex=axT)
    azT = fig.add_subplot(gs[2, 0])
    azH = fig.add_subplot(gs[2, 1], sharex=azT)
    for ax in (axT, axH):
        shade_runs(ax, rem, "removed by QC (logger_zeros)")
    for col, c, lab in sensors:
        axT.plot(sub(s[col]).index, sub(s[col]).values, color=c, lw=0.6, label=lab)
    line(axT, sub(r["temperature"]), "ref", "Adana reference", lw=0.9)
    axT.set_ylabel("Temperature (°C)")
    legend(axT, ncol=5)
    axT.tick_params(labelbottom=False)
    panel_tag(axT, "A  temperature, 1-min (every 10th minute shown)")
    axH.plot(sub(s["sth_hum"]).index, sub(s["sth_hum"]).values, color=C3, lw=0.6,
             label="TSMS06 SHT31")
    line(axH, sub(r["humidity"]), "ref", "Adana reference", lw=0.9)
    axH.set_ylabel("Relative humidity (%)")
    axH.set_xlim(pd.Timestamp(a), pd.Timestamp(b))
    time_axis(axH)
    legend(axH, ncol=4, loc="lower left")
    panel_tag(axH, "B  humidity")

    sz, rz = s.loc[z0:z1], r.loc[z0:z1]
    zr = rem[(rem.end >= z0) & (rem.start <= z1)]
    for ax in (azT, azH):
        shade_runs(ax, minute_runs(ol.loc[(ol.outlier_type == "logger_zeros") &
                                          (ol.date >= z0) & (ol.date <= z1), "date"]),
                   "removed by QC")
    for col, c, lab in sensors:
        azT.plot(sz.index, sz[col], color=c, lw=0.8, label=lab)
    line(azT, rz["temperature"], "ref", "Adana reference")
    azT.set_ylabel("Temperature (°C)")
    azT.set_xlim(pd.Timestamp(z0), pd.Timestamp(z1))
    time_axis(azT, "Time (UTC)")
    legend(azT, ncol=4, loc="lower left", bbox_to_anchor=(0, 1.08))
    panel_tag(azT, "C  zoom 5–7 Apr 2025, temperature")
    azH.plot(sz.index, sz["sth_hum"], color=C3, lw=0.8, label="TSMS06 SHT31")
    line(azH, rz["humidity"], "ref", "Adana reference")
    azH.set_ylabel("Relative humidity (%)")
    time_axis(azH, "Time (UTC)")
    legend(azH, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.08))
    panel_tag(azH, "D  zoom, humidity")
    del zr
    fig.suptitle("SF-17 · TSMS06 · logger writes exactly 0.0 on every temperature and humidity sensor",
                 fontweight="bold")
    return save(fig, OUT_3DP, "SF-17_TSMS06_logger_zeros.png")


def fig_sf22():
    """SF-22: TSMS01 wind vane stuck at 0.0 deg while the cups turn (Oct-Nov 2024)."""
    z0, z1 = "2024-11-03", "2024-11-06 23:59"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True,
                                   gridspec_kw=dict(height_ratios=[1.5, 1]), layout="constrained")
    for sid in SITES["Ankara"]:
        dots(ax1, station(sid, z0, z1)["wind_dir"], sid, sid, size=1.5)
    dots(ax1, reference("Ankara", z0, z1)["avg_wind_dir"], "ref", "Ankara reference (10 m)", size=1.5)
    ax1.set_ylabel("1-min wind direction (°)")
    ax1.set_ylim(-10, 370)
    ax1.set_yticks([0, 90, 180, 270, 360])
    legend(ax1, loc="lower right", bbox_to_anchor=(1, 1.0))
    ax1.tick_params(labelbottom=False)
    panel_tag(ax1, "A  direction")
    line(ax2, station("TSMS01", z0, z1)["wind_speed"], "TSMS01", "TSMS01", lw=0.7)
    ax2.set_ylabel("1-min wind speed (m/s)")
    ax2.set_ylim(bottom=-0.2)
    ax2.set_xlim(pd.Timestamp(z0), pd.Timestamp(z1))
    time_axis(ax2, "Time (UTC)")
    legend(ax2)
    panel_tag(ax2, "B  TSMS01 speed: the cups keep turning")
    fig.suptitle("SF-22 · TSMS01 · wind vane stuck at 0.0°", fontweight="bold")
    return save(fig, OUT_3DP, "SF-22_TSMS01_vane_stuck_at_0.png")


def fig_sf21():
    """SF-21 / SF-16: degraded tipping buckets before the Jan 2024 visits (cumulative rain)."""
    visit = {"Ankara": pd.Timestamp("2024-01-17"), "Adana": pd.Timestamp("2024-01-15")}
    start = {"Ankara": "2022-10-01", "Adana": "2022-11-10"}
    end = "2024-01-31 23:59"
    ankara_x10 = pd.Timestamp("2023-03-06")
    # TSMS08 Apr-May 2023: rain column holds non-rain values (station_event:rain_connector_or_tampering)
    ol8 = qc_log("3DPAWS_TSMS08_Adana")
    bad8 = pd.DatetimeIndex(ol8.loc[(ol8.column_name == "tipping") &
                                    ol8.outlier_type.str.startswith("station_event"), "date"])

    def cum(s):
        d = s.resample("D").sum(min_count=1)
        c = d.fillna(0).cumsum()
        return c.where(d.notna())  # break the line on days with no data

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout="constrained")
    for ax, site in zip(axes, ["Ankara", "Adana"]):
        a = start[site]
        tops = []
        for sid in SITES[site]:
            t = station(sid, a, end)["tipping"]
            if sid == "TSMS08":
                t = t.drop(t.index.intersection(bad8))
            c = cum(t)
            tops.append(c.max())
            line(ax, c, sid, sid, lw=1.3)
        rr = reference(site, a, end)["total_rainfall"]
        cr = cum(rr)
        if site == "Ankara":
            line(ax, cr, "ref", "Ankara reference (off scale, SF-09)")
            fixed = rr.copy()
            fixed[fixed.index >= ankara_x10] /= 10
            ax.plot(cum(fixed).index, cum(fixed).values, color=CREF, lw=1.2, ls="--",
                    label="Ankara reference ÷10 from 6 Mar 2023")
            tops.append(cum(fixed).max())
            # TSMS02: no tips at all during its anemometer outage (SF-20)
            shade(ax, "2023-03-31 12:17", "2024-01-04 19:52", "TSMS02 records no tips")
        else:
            line(ax, cr, "ref", "Adana reference")
            tops.append(cr.max())
        ax.axvline(visit[site], color="#555555", lw=1, ls=":")
        ax.text(visit[site], 0.3, "visit " + visit[site].strftime("%d %b %Y") + " ",
                transform=ax.get_xaxis_transform(), rotation=90, va="bottom", ha="right",
                fontsize=8, color="#555555")
        ax.set_ylim(0, np.nanmax(tops) * 1.12)
        ax.set_xlim(pd.Timestamp(a), pd.Timestamp(end))
        ax.set_ylabel("Cumulative rainfall (mm)")
        ax.set_title(site, fontsize=10)
        time_axis(ax)
        legend(ax, ncol=1)
    fig.suptitle("SF-21 / SF-16 · Ankara and Adana tipping buckets · rain caught before the Jan 2024 visits",
                 fontweight="bold")
    return save(fig, OUT_3DP, "SF-21_SF-16_degraded_rain_gauges_pre_visit.png")


# ============================================================================= TSMS reference figures


def fig_sf23():
    """SF-23: Ankara reference frozen record (every variable repeats), Jun-Aug 2025."""
    a, b = "2025-08-15 03:00", "2025-08-15 12:00"
    ol = qc_log("TSMS_Reference_Ankara")
    fr = minute_runs(ol.loc[ol.outlier_type == "logger_frozen", "date"])
    r = reference("Ankara", a, b)
    S = {sid: station(sid, a, b) for sid in SITES["Ankara"]}

    def hum(df):
        if df["htu_hum"].notna().sum() >= df["sth_hum"].notna().sum():
            return unswitch(df["htu_hum"])
        return df["sth_hum"]

    rows = [("Temperature (°C)", "temperature", lambda d: d["mcp9808"]),
            ("RH (%)", "humidity", hum),
            ("Pressure (hPa)", "actual_pressure", lambda d: d["bmp2_pres"]),
            ("Wind speed (m/s)", "avg_wind_speed", lambda d: d["wind_speed"])]
    fig = plt.figure(figsize=(12, 7), layout="constrained")
    gs = fig.add_gridspec(4, 2, width_ratios=[2.3, 1])
    fr_day = fr[(fr.end >= a) & (fr.start <= b)]
    first = None
    for i, (ylab, rc, fn) in enumerate(rows):
        ax = fig.add_subplot(gs[i, 0], sharex=first)
        first = first or ax
        shade_runs(ax, fr_day, "reference frozen (removed)" if i == 0 else None)
        for sid, d in S.items():
            v = fn(d)
            if v.notna().any():
                line(ax, v, sid, sid, lw=0.8)
        line(ax, r[rc], "ref", "Ankara reference")
        ax.set_ylabel(ylab)
        if i == 0:
            legend(ax, ncol=5, loc="lower left", bbox_to_anchor=(0, 1.0))
        if i < 3:
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xlim(pd.Timestamp(a), pd.Timestamp(b))
            time_axis(ax, "Time on 15 Aug 2025 (UTC)")

    ax = fig.add_subplot(gs[:, 1])
    day = fr.start.dt.normalize()
    h0 = (fr.start - day) / pd.Timedelta("1h")
    h1 = (fr.end + pd.Timedelta("1min") - day) / pd.Timedelta("1h")
    ax.vlines(day, h0, h1, color=CBAD, lw=3.0, alpha=0.8, label="frozen period")
    ax.set_ylim(12, 4)
    ax.set_yticks(range(4, 13, 1))
    ax.set_ylabel("Time of day (UTC)")
    ax.set_xlim(pd.Timestamp("2025-06-25"), pd.Timestamp("2025-08-26"))
    time_axis(ax)
    ax.set_title(f"All {len(fr)} frozen periods (logger_frozen)", fontsize=9)
    legend(ax, loc="lower left")
    fig.suptitle("SF-23 · Ankara reference · frozen record: every variable repeats its last value",
                 fontweight="bold")
    return save(fig, OUT_REF, "SF-23_Ankara_reference_frozen_record.png")


def fig_sf24():
    """SF-24: Ankara reference humidity flat at exactly 10% (2023-08-15)."""
    a, b = "2023-08-15 00:00", "2023-08-15 23:59"
    ol = qc_log("TSMS_Reference_Ankara")
    run = minute_runs(ol.loc[(ol.outlier_type == "persistence") & (ol.column_name == "humidity") &
                             (ol.date >= a) & (ol.date <= b), "date"])
    r = reference("Ankara", a, b)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True, layout="constrained")
    for ax in (ax1, ax2):
        shade_runs(ax, run, "reference RH flat at 10% (removed)" if ax is ax1 else None)
    for sid in SITES["Ankara"]:
        d = station(sid, a, b)
        h = unswitch(d["htu_hum"]) if d["htu_hum"].notna().any() else d["sth_hum"]
        line(ax1, h, sid, sid, lw=0.8)
        line(ax2, d["mcp9808"], sid, sid, lw=0.8)
    line(ax1, r["humidity"], "ref", "Ankara reference")
    line(ax2, r["temperature"], "ref", "Ankara reference")
    ax1.axhline(10, color="#888888", lw=0.6, ls="--")
    ax1.set_ylabel("Relative humidity (%)")
    ax1.set_ylim(bottom=0)
    ax2.set_ylabel("Temperature (°C)")
    ax2.set_xlim(pd.Timestamp(a), pd.Timestamp(b))
    time_axis(ax2, "Time on 15 Aug 2023 (UTC)")
    legend(ax1, ncol=5, loc="upper center")
    legend(ax2, ncol=4, loc="lower center")
    fig.suptitle("SF-24 · Ankara reference · humidity stuck at exactly 10% while temperature changes",
                 fontweight="bold")
    return save(fig, OUT_REF, "SF-24_Ankara_reference_humidity_floor_10pct.png")


def fig_sf25():
    """SF-25: Ankara reference vane at 0 deg while speed ~2.8 m/s (2025-06-10/11)."""
    a, b = "2025-06-10 12:00", "2025-06-11 12:00"
    ol = qc_log("TSMS_Reference_Ankara")
    run = minute_runs(ol.loc[(ol.outlier_type == "persistence") & (ol.column_name == "avg_wind_dir") &
                             (ol.date >= a) & (ol.date <= b), "date"], gap="60min")
    r = reference("Ankara", a, b)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True,
                                   gridspec_kw=dict(height_ratios=[1.4, 1]), layout="constrained")
    for ax in (ax1, ax2):
        shade_runs(ax, run, "reference vane at 0° (removed)" if ax is ax1 else None)
    for sid in SITES["Ankara"]:
        d = station(sid, a, b)
        dots(ax1, d["wind_dir"], sid, sid, size=2)
        line(ax2, d["wind_speed"], sid, sid, lw=0.6)
    dots(ax1, r["avg_wind_dir"], "ref", "Ankara reference (10 m)", size=3)
    line(ax2, r["avg_wind_speed"], "ref", "Ankara reference (10 m)")
    ax1.set_ylabel("1-min wind direction (°)")
    ax1.set_ylim(-10, 370)
    ax1.set_yticks([0, 90, 180, 270, 360])
    legend(ax1, ncol=5, loc="lower left", bbox_to_anchor=(0, 1.0))
    ax2.set_ylabel("1-min wind speed (m/s)")
    ax2.set_ylim(bottom=0)
    ax2.set_xlim(pd.Timestamp(a), pd.Timestamp(b))
    time_axis(ax2, "Time (UTC)")
    legend(ax2, ncol=4, loc="upper right")
    fig.suptitle("SF-25 · Ankara reference · wind vane stuck at 0° while the wind blows",
                 fontweight="bold")
    return save(fig, OUT_REF, "SF-25_Ankara_reference_vane_stuck_at_0.png")


def fig_sf28():
    """SF-28: courtyard watering tips the Konya 3D-PAWS gauges on dry days (Jul-Aug 2023); the reference is right."""
    a, b = "2023-06-01", "2023-09-30 23:59"
    wat0, wat1 = pd.Timestamp("2023-07-01"), pd.Timestamp("2023-09-03")   # courtyard_watering event (station-events.csv)
    r = reference("Konya", a, b)
    series = [("ref", "Konya reference", r["total_rainfall"])] + \
             [(sid, sid, station(sid, a, b)["tipping"]) for sid in SITES["Konya"]]
    fig = plt.figure(figsize=(12, 6.5), layout="constrained")
    gs = fig.add_gridspec(4, 2, width_ratios=[2.4, 1])
    first = None
    top = max(daily(s, "sum", 0.25).max() for _, _, s in series)
    for i, (key, lab, s) in enumerate(series):
        ax = fig.add_subplot(gs[i, 0], sharex=first, sharey=first)
        first = first or ax
        if i > 0:
            shade(ax, wat0, wat1, "flagged courtyard_watering" if i == 1 else None)
        d = daily(s, "sum", 0.25)
        ax.bar(d.index + pd.Timedelta("12h"), d.values, width=0.8, color=COLOR[key], lw=0, label=lab)
        ax.set_ylim(0, top * 1.1)
        ax.set_ylabel("mm/day")
        legend(ax, loc="upper right")
        if i < 3:
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xlim(pd.Timestamp(a), pd.Timestamp(b) + pd.Timedelta("1min"))
            time_axis(ax)

    # when did the 3D-PAWS gauges tip, and how humid was it? (Jul-Aug 2023)
    ax = fig.add_subplot(gs[:, 1])
    j0, j1 = "2023-07-05", "2023-08-31 23:59"
    rj = reference("Konya", j0, j1)["humidity"]
    for sid in SITES["Konya"]:
        t = station(sid, j0, j1)["tipping"]
        t = t[t > 0]
        h = t.index.hour + t.index.minute / 60
        ax.scatter(h, rj.reindex(t.index).values, s=6, color=COLOR[sid], lw=0, alpha=0.7, label=sid)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.set_ylim(0, 100)
    ax.set_xlabel("Hour of tip (UTC)")
    ax.set_ylabel("Reference RH at tip minute (%)")
    ax.set_title("3D-PAWS tips, 5 Jul – 31 Aug 2023", fontsize=9)
    legend(ax, ncol=3, loc="upper left")
    fig.suptitle("SF-28 · Konya 3D-PAWS gauges · courtyard watering tips the buckets on dry days", fontweight="bold")
    return save(fig, OUT_3DP, "SF-28_Konya_3DPAWS_courtyard_watering.png")


def fig_sf29():
    """SF-29: TSMS02 rain gauge records (almost) nothing during its anemometer outage."""
    a, b = "2023-01-01", "2024-03-31 23:59"
    o0, o1 = pd.Timestamp("2023-03-31 12:17"), pd.Timestamp("2024-01-05")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6.5), layout="constrained", sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    for ax in (ax1, ax2):
        shade(ax, o0, o1, "TSMS02 gauge dead (flagged rain_gauge_dead)" if ax is ax1 else None)
    for sid in SITES["Ankara"]:
        t = station(sid, a, b)["tipping"]
        line(ax1, t.fillna(0).cumsum().where(t.notna()), sid, sid)
        tips = (t > 0).resample("W").sum()
        ax2.step(tips.index, tips.values, where="post", color=COLOR[sid], lw=LW, label=sid)
    r = reference("Ankara", a, b)["total_rainfall"]
    r = r.where(r.index < "2023-03-06", r / 10)          # SF-09: divide the x10 period for comparison
    line(ax1, r.fillna(0).cumsum().where(r.notna()), "ref", "Ankara reference (÷10 from 6 Mar 2023, SF-09)", ls="--")
    ax1.set_ylabel("Cumulative rain (mm)")
    ax2.set_ylabel("Minutes with a tip\nper week")
    legend(ax1); legend(ax2, loc="upper right")
    panel_tag(ax1, "A  cumulative rain before QC"); panel_tag(ax2, "B  tipping activity")
    time_axis(ax2)
    fig.suptitle("SF-29 · TSMS02 · rain gauge dead during the anemometer outage (7 tips in 9 months)", fontweight="bold")
    return save(fig, OUT_3DP, "SF-29_TSMS02_rain_gauge_dead.png")


def fig_sf30():
    """SF-30: TSMS01 anemometer reads ~30% of TSMS00, 10 m away."""
    a, b = "2022-09-01", "2025-11-30 23:59"
    w = pd.DataFrame({sid: station(sid, a, b)["wind_speed"] for sid in SITES["Ankara"]})
    w.loc["2023-03-31 12:17":"2024-01-11 10:02", "TSMS02"] = np.nan    # SF-20 outage
    windy = w[w["TSMS00"] > 1]
    fig = plt.figure(figsize=(12, 6), layout="constrained")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.8, 1])
    ax = fig.add_subplot(gs[0, 0])
    for sid in ["TSMS01", "TSMS02"]:
        ratio = (windy[sid] / windy["TSMS00"]).resample("ME").median()
        n = windy[sid].notna().resample("ME").sum()
        ratio = ratio.where(n >= 500)
        ax.plot(ratio.index, ratio.values, color=COLOR[sid], lw=1.6, marker="o", ms=3, label=f"{sid} ÷ TSMS00")
    ax.axhline(1, color="#888888", lw=0.8, ls=":")
    ax.set_ylim(0, 1.6)
    ax.set_ylabel("Monthly median speed ratio\n(minutes with TSMS00 > 1 m/s)")
    legend(ax, loc="upper right")
    panel_tag(ax, "A  speed relative to TSMS00, 10 m away")
    time_axis(ax)
    ax2 = fig.add_subplot(gs[0, 1])
    h = w["2024-01-01":"2024-12-31"].resample("h").mean().dropna(subset=["TSMS00", "TSMS01"])
    ax2.scatter(h["TSMS00"], h["TSMS01"], s=3, color=COLOR["TSMS01"], lw=0, alpha=0.4, rasterized=True, label="TSMS01 (hourly, 2024)")
    m = max(h["TSMS00"].max(), 1)
    ax2.plot([0, m], [0, m], color="#888888", lw=0.8, ls=":", label="1:1")
    ax2.set_xlim(0, m); ax2.set_ylim(0, m)
    ax2.set_xlabel("TSMS00 wind speed (m/s)"); ax2.set_ylabel("TSMS01 wind speed (m/s)")
    legend(ax2, ncol=1, loc="upper left")
    panel_tag(ax2, "B  hourly means, 2024")
    fig.suptitle("SF-30 · TSMS01 · anemometer reads about 30% of its neighbour (suspected)", fontweight="bold")
    return save(fig, OUT_3DP, "SF-30_TSMS01_anemometer_low_reading.png")


def fig_sf31():
    """SF-31: Adana reference reports many days with small rain amounts that 3D-PAWS gauges don't."""
    a, b = "2022-11-10", "2025-11-30 23:59"
    series = [("ref", "Adana reference", reference("Adana", a, b)["total_rainfall"])] + \
             [(sid, sid, station(sid, a, b)["tipping"]) for sid in SITES["Adana"]]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.5), layout="constrained")
    bins = [0.2, 0.4, 0.6, 0.8, 1.0, 2.0, 5.0, 10.0]
    labels = ["0.2–0.4", "0.4–0.6", "0.6–0.8", "0.8–1.0", "1–2", "2–5", "5–10"]
    x = np.arange(len(labels))
    for k, (key, lab, s) in enumerate(series):
        d = daily(s, "sum", 0.8)
        if key == "TSMS08":                              # tampering / connector periods (station-events.csv)
            d = d.where(~d.index.isin(pd.date_range("2023-04-08", "2023-04-14").append(pd.date_range("2023-05-15", "2023-05-17"))))
        counts = pd.cut(d.dropna(), bins, right=False, labels=labels).value_counts().reindex(labels)
        ax1.bar(x + (k - 1.5) * 0.2, counts.values, width=0.2, color=COLOR[key], lw=0, label=lab)
        small = ((d >= 0.2) & (d < 1.0)).resample("QE").sum().where(d.resample("QE").count() >= 60)
        ax2.plot(small.index, small.values, color=COLOR[key], lw=LW_REF if key == "ref" else LW, marker="o", ms=3, label=lab)
    ax1.set_xticks(x, labels)
    ax1.set_xlabel("Daily total (mm)"); ax1.set_ylabel("Days")
    legend(ax1, ncol=2, loc="upper right")
    panel_tag(ax1, "A  wet days by daily total, 80%-complete days")
    ax2.set_ylabel("Days with 0.2–1.0 mm per quarter")
    legend(ax2, ncol=2, loc="upper left")
    panel_tag(ax2, "B  small-amount days over time")
    time_axis(ax2)
    fig.suptitle("SF-31 · Adana reference · many days with 0.2–1 mm that the 3D-PAWS gauges don't record (suspected)", fontweight="bold")
    return save(fig, OUT_REF, "SF-31_Adana_reference_small_rain_amounts.png")


def fig_sf09():
    """SF-09: Ankara reference rain inflated (monthly totals and a 1-min spike day)."""
    a, b = "2022-10-01", "2025-11-30 23:59"
    x10 = pd.Timestamp("2023-03-06")
    rr = reference("Ankara", a, b)["total_rainfall"]
    M = {"ref": rr.resample("MS").sum(min_count=1)}
    for sid in SITES["Ankara"]:
        M[sid] = station(sid, a, b)["tipping"].resample("MS").sum(min_count=1)
    M = pd.DataFrame(M)
    fig = plt.figure(figsize=(12, 7), layout="constrained")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1])
    ax = fig.add_subplot(gs[0, :])
    x = np.arange(len(M))
    w = 0.2
    for k, (key, lab) in enumerate([("ref", "Ankara reference"), ("TSMS00", "TSMS00"),
                                    ("TSMS01", "TSMS01"), ("TSMS02", "TSMS02")]):
        ax.bar(x + (k - 1.5) * w, M[key].values, width=w, color=COLOR[key], lw=0, label=lab)
    after = M.index >= x10.to_period("M").to_timestamp()
    ax.step(x[after], (M["ref"] / 10).values[after], where="mid", color=CREF, lw=1, ls="--",
            label="reference ÷10")
    ax.axvline(np.searchsorted(M.index, x10) - 0.5 + 0.1, color="#555555", lw=1, ls=":",
               label="scale and resolution change, 6–11 Mar 2023")
    lab = [d.strftime("%b\n%Y") if d.month == 1 or i == 0 else d.strftime("%b") for i, d in enumerate(M.index)]
    ax.set_xticks(x[::2])
    ax.set_xticklabels(lab[::2], fontsize=7.5)
    ax.set_xlim(-0.6, len(M) - 0.4)
    ax.set_ylim(0, M.max().max() * 1.25)
    ax.set_ylabel("Monthly rainfall (mm)")
    ax.set_xlabel("Month (UTC)")
    legend(ax, ncol=3, loc="upper right")
    panel_tag(ax, "A  monthly totals (before QC)")

    d0, d1 = "2023-05-29 10:00", "2023-05-29 17:00"
    r1 = reference("Ankara", d0, d1)["total_rainfall"]
    axm = fig.add_subplot(gs[1, 0])
    axc = fig.add_subplot(gs[1, 1], sharex=axm)
    for sid in SITES["Ankara"]:
        t = station(sid, d0, d1)["tipping"]
        line(axm, t, sid, sid, lw=0.8, drawstyle="steps-mid")
        line(axc, t.fillna(0).cumsum().where(t.notna()), sid, sid)
    line(axm, r1, "ref", "Ankara reference", drawstyle="steps-mid")
    line(axc, r1.fillna(0).cumsum(), "ref", "Ankara reference")
    axm.set_ylabel("1-min rainfall (mm)")
    axc.set_ylabel("Cumulative rainfall (mm)")
    for a_ in (axm, axc):
        a_.set_xlim(pd.Timestamp(d0), pd.Timestamp(d1))
        time_axis(a_, "Time on 29 May 2023 (UTC)")
        legend(a_, ncol=2)
    panel_tag(axm, "B  spike day, 1-min")
    panel_tag(axc, "C  same day, cumulative")
    fig.suptitle("SF-09 · Ankara reference · rainfall inflated about ×10 from March 2023",
                 fontweight="bold")
    return save(fig, OUT_REF, "SF-09_Ankara_reference_rain_inflated.png")


def fig_sf26():
    """SF-26 (suspected): Adana reference 0 m/s runs while 3D-PAWS show wind (Aug-Oct 2025)."""
    a, b = "2025-07-01", "2025-11-30 23:59"
    z0, z1 = "2025-08-08 12:00", "2025-08-10 12:00"
    r = reference("Adana", a, b)["avg_wind_speed"]
    runs = value_runs(r.dropna(), 0.0, min_len=24 * 60)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6.5), gridspec_kw=dict(height_ratios=[1.2, 1]),
                                   layout="constrained")
    shade_runs(ax1, runs, "reference exactly 0 m/s for ≥ 24 h")
    for sid in SITES["Adana"]:
        line(ax1, daily(station(sid, a, b)["wind_speed"]), sid, sid)
    line(ax1, daily(r), "ref", "Adana reference (10 m)")
    ax1.set_ylabel("Daily mean wind speed (m/s)")
    ax1.set_ylim(bottom=0)
    ax1.set_xlim(pd.Timestamp(a), pd.Timestamp(b))
    time_axis(ax1)
    legend(ax1, ncol=5, loc="upper right")
    panel_tag(ax1, "A  daily means")
    rz = reference("Adana", z0, z1)["avg_wind_speed"]
    shade_runs(ax2, value_runs(rz.dropna(), 0.0, min_len=180), "reference exactly 0 m/s")
    for sid in SITES["Adana"]:
        line(ax2, station(sid, z0, z1)["wind_speed"], sid, sid, lw=0.7)
    line(ax2, rz, "ref", "Adana reference (10 m)")
    ax2.set_ylabel("1-min wind speed (m/s)")
    ax2.set_ylim(bottom=-0.1)
    ax2.set_xlim(pd.Timestamp(z0), pd.Timestamp(z1))
    time_axis(ax2, "Time (UTC)")
    legend(ax2, ncol=5, loc="upper left")
    panel_tag(ax2, "B  2 days around the onset, 1-min")
    fig.suptitle("SF-26 (suspected) · Adana reference · anemometer reads 0 m/s for days while 3D-PAWS read wind",
                 fontweight="bold")
    return save(fig, OUT_REF, "SF-26_Adana_reference_zero_wind_runs.png")


# ============================================================================= READMEs
FIGS = {  # id: (function, folder, caption)
    "SF-20": (fig_sf20, OUT_3DP,
              "TSMS02's anemometer was unplugged after a short circuit, so its wind speed is exactly 0 m/s in "
              "all 407,009 minutes from 2023-03-31 12:17 to 2024-01-11 10:02 UTC (shaded), while TSMS00, "
              "TSMS01 and the Ankara reference (10 m) show normal wind; (B) 12–14 Jun 2023 at 1-min: TSMS02 "
              "is a flat line at zero."),
    "SF-27": (fig_sf27, OUT_3DP,
              "TSMS08's anemometer reads 0 m/s in 93–100% of minutes May–Dec 2023 and 90–100% Jun–Oct 2024 "
              "(daily mean near 0) while TSMS06/07 keep reading wind; QC removed only the 58,189 minutes when "
              "the neighbours were windy (red strip, anemometer_not_responding), so the slack-wind zeros "
              "remain; (B) 5–8 Jul 2023 at 1-min, removed spans shaded. After the Jan 2024 visit it also reads "
              "a near-constant 0.6–0.7 m/s for days (17–27 Jan 2024)."),
    "SF-17": (fig_sf17, OUT_3DP,
              "TSMS06's MCP9808, BMP280 and SHT31 all report exactly 0.0 °C / 0 %RH at the same minutes "
              "(lines overlap at 0; MCP9808 drawn on top), continuously 26 Sep–21 Oct 2024 and on and off "
              "26 Feb–end of May 2025 (shaded = removed as logger_zeros), far from the Adana reference; "
              "(C, D) 5–7 Apr 2025, where the drops to 0 come and go. Both periods come from the CHORDS "
              "download, not the SD cards (suspected database bug, PF-44)."),
    "SF-22": (fig_sf22, OUT_3DP,
              "TSMS01's vane reports exactly 0.0° (the flat row of orange dots) from 21 Oct to 21 Nov 2024 "
              "while the TSMS00, TSMS02 and Ankara reference directions vary and TSMS01's cups keep turning "
              "(B); shown 3–6 Nov 2024 at 1-min."),
    "SF-21": (fig_sf21, OUT_3DP,
              "Cumulative 1-min rain (before QC) up to the Jan 2024 visits (dotted line). Ankara: TSMS01 catches "
              "almost nothing through 2023 (bucket stuck), TSMS02 records no tips from 31 Mar 2023 to "
              "4 Jan 2024 (shaded, the same span as its SF-20 anemometer outage), and TSMS00 (off-level gauge) "
              "runs below the reference once the reference's ×10 error (SF-09) is divided out (dashed). "
              "Adana (from 10 Nov 2022, when all three report): TSMS06 (pebbles) runs above the reference and "
              "TSMS07 (missing screens) below it, with most divergence in spring 2023; TSMS08's Apr–May 2023 "
              "non-rain values (rain_connector_or_tampering) are left out. Line gaps = days with no data."),
    "SF-23": (fig_sf23, OUT_REF,
              "On 15 Aug 2025 the Ankara reference repeats one record (25.7 °C, 28 %, 913.3 hPa, 4.8 m/s) "
              "from 06:04 to 09:59 UTC (shaded) while TSMS00–02 keep changing (TSMS01 has no pressure that "
              "day; HTU21D bit-switching spikes, SF-03, masked). Right: all 25 logger_frozen runs "
              "(22 mornings, 30 Jun–21 Aug 2025) by date and time of day."),
    "SF-24": (fig_sf24, OUT_REF,
              "On 15 Aug 2023 the Ankara reference humidity sits at exactly 10% from 07:14 to 16:06 UTC "
              "(shaded) while the three 3D-PAWS HTU21Ds read 3–8% and keep varying, and the reference "
              "temperature rises and falls normally (HTU21D bit-switching spikes, SF-03, masked); the same "
              "happens on 16 Aug 2023 and 23–24 Jun 2024."),
    "SF-25": (fig_sf25, OUT_REF,
              "From 10 Jun 18:56 to 11 Jun 06:20 UTC 2025 the Ankara reference vane reads 0° (shaded = the 643 "
              "removed minutes) while its own anemometer reports 2–5 m/s and the TSMS00–02 vanes point "
              "east; the vane actually stays at 0° until 07:39 and again from 11:26."),
    "SF-28": (fig_sf28, OUT_3DP,
              "Daily rain Jun–Sep 2023: from July the three Konya 3D-PAWS gauges record a few mm on many dry "
              "days while the reference records 0.6 mm in Jul–Aug (shaded = flagged courtyard_watering, "
              "1 Jul – 2 Sep 2023). Right: the tips fall at reference RH of 10–60% and bunch at about "
              "09:50–10:00 and 13:50 UTC every day, a watering schedule in the courtyard. The reference is right."),
    "SF-29": (fig_sf29, OUT_3DP,
              "TSMS02's rain gauge records 7 tips from 31 Mar 2023 to 4 Jan 2024 (shaded, flagged "
              "rain_gauge_dead) while TSMS00 and the Ankara reference (÷10 during SF-09, dashed) keep "
              "accumulating (TSMS01 barely does either: its stuck bucket, SF-21); the same span as its SF-20 anemometer outage, so possibly the same "
              "disconnected harness. (B) minutes with a tip per week."),
    "SF-30": (fig_sf30, OUT_3DP,
              "(A) Monthly median of TSMS01's (and TSMS02's) wind speed divided by TSMS00's, 10 m away, over "
              "minutes when TSMS00 reads > 1 m/s: TSMS02 sits at about 0.5–0.9, TSMS01 at about 0.24–0.35 from "
              "2023 (0.4–0.5 in late 2022). (B) Hourly means in 2024 fall far below the 1:1 line. Suspected assembly (SMN "
              "found a misplaced magnet halves the reading) or bearing fault; not removed."),
    "SF-31": (fig_sf31, OUT_REF,
              "(A) Days by daily total on 80%-complete days: the Adana reference has many more days with "
              "0.2–1.0 mm than TSMS06–08 (≈ 290 of its 429 wet days at the 0.2 mm threshold); above 1 mm the "
              "counts are closer. (B) Small-amount days per quarter: the reference peaks in summer, 73 of 92 "
              "days in Jul–Sep 2023 and 60 in Jul–Sep 2024, when Adana is dry, then fades in 2025. Likely "
              "dew or condensation counted as rain; suspected, not flagged. TSMS08's "
              "tampering days are left out."),
    "SF-09": (fig_sf09, OUT_REF,
              "Monthly rain (before QC): the Ankara reference matches TSMS00/02 until early March 2023, then "
              "reads about 10 times more every month (dashed = reference ÷10, which tracks the 3D-PAWS); "
              "between 6 and 11 Mar 2023 its 1-min resolution also changes from 0.01 to 0.1 mm, which points "
              "to a scaling change rather than weighing-gauge noise; (B, C) 29 May 2023: 45 mm in one minute "
              "and 240 mm in the afternoon against 12 mm at TSMS00 (TSMS01 no data)."),
    "SF-26": (fig_sf26, OUT_REF,
              "The Adana reference anemometer drops from a normal ~1.9 m/s daily mean to exactly 0 m/s on "
              "9–10 Aug 2025 and stays at 0 (≤ 54 nonzero minutes a day) until 13 Oct 2025, while TSMS06–08 "
              "carry on as before (shaded = reference zero runs ≥ 24 h); (B) 8–10 Aug 2025 at 1-min, "
              "the onset."),
}


def write_readmes(ids):
    for folder, title in [(OUT_3DP, "3D-PAWS sensor failures"), (OUT_REF, "TSMS reference sensor failures")]:
        rows = []
        for sf, (fn, fo, cap) in FIGS.items():
            if fo != folder:
                continue
            name = fn.__name__
            png = next((p for p in folder.glob(f"{sf}_*.png")), None)
            if png is None:
                continue
            rows.append(f"| [{png.name}]({png.name}) | {sf} | {cap} |")
        text = (f"# {title}\n\nDiagnostic figures for the failures in "
                "[docs/sensor-failures.md](../../../docs/sensor-failures.md). Made by "
                "`scripts/plotter/plot-sensor-failures.py` from the reformatted (pre-QC) minute data; "
                "red bands are the failing period or what QC removed/flagged. Times are UTC.\n\n"
                "| Figure | SF ID | Caption |\n|---|---|---|\n" + "\n".join(rows) + "\n")
        (folder / "README.md").write_text(text)
        print("wrote", (folder / "README.md").relative_to(REPO))


def main():
    global CACHE_DIR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="SF IDs to plot (default: all)")
    ap.add_argument("--cache-dir", type=Path, default=None,
                    help="optional folder to pickle parsed CSVs (outside data/)")
    args = ap.parse_args()
    CACHE_DIR = args.cache_dir
    ids = args.ids or list(FIGS)
    for sf in ids:
        FIGS[sf][0]()
    write_readmes(ids)


if __name__ == "__main__":
    main()
