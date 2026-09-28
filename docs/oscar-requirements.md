# OSCAR observing requirements relevant to 3D-PAWS

Extract of WMO OSCAR/Requirements (https://space.oscar.wmo.int/observingrequirements), retrieved
2026-09-28 from the variable pages (`/variables/view/<slug>`). Rows are land/global,
non-deprecated application areas. Check OSCAR for updates before citing values.

## How OSCAR expresses requirements

- **Uncertainty is an RMSE at 68% confidence (k = 1).** WMO-No. 8 Annex 1.A / 1.G use 95% (k = 2).
  Annex 1.G converted OSCAR values from k = 1 to k = 2 when building its classes (Vol. I,
  Annex 1.G §4.3), with an allowance for siting uncertainty (§3.6). Its classes don't map exactly
  onto the current OSCAR values of any single application area: Annex 1.G temperature is
  0.2 / 0.6 / 1.0 K, while doubling OSCAR's strictest (climate monitoring, PBL) gives
  0.2 / 1.0 / 2.0 K.
- **Three levels per criterion:** *threshold* = "the minimum requirement to be met to ensure that
  data are useful"; *breakthrough* = an intermediate level giving "a significant improvement";
  *goal* = "an ideal requirement above which further improvements are not necessary".
- **Requirements are per application area** and cover more than uncertainty: horizontal
  resolution (station spacing), observing cycle, and timeliness. For a dense, low-cost network,
  horizontal resolution is where it can add the most.
- **Values below are listed goal / breakthrough / threshold** (as shown in OSCAR).

## Gaps and caveats

- **No near-surface air pressure variable** could be found in OSCAR (API or web lists). Use
  WMO-No. 8 Annex 1.A / 1.G for pressure. Annex 1.G's pressure classes cite OSCAR, so the
  requirement may sit under another name.
- **Temperature and humidity** have no separate "near surface" layer. The closest is the
  **PBL** (planetary boundary layer) layer of *Atmospheric temperature* and *Specific humidity*.
  Humidity is given as specific humidity, not relative humidity, so RH needs conversion (Annex
  1.G has already translated it: 2 / 5 / 10 %RH at k = 2).
- **Annex 1.G is conservative for some variables.** For temperature, pressure and daily rain it's
  based on the *lowest* uncertainty of all application areas (source [1a]). Application-specific
  OSCAR requirements can be much looser. Temperature for nowcasting and high-resolution NWP is
  0.5 / 1 / 3 K (k = 1, i.e. roughly 1 / 2 / 6 K at k = 2), against Annex 1.G's 0.2 / 0.6 / 1.0 K.

## Requirements

| OSCAR Id | Variable | Layer | Application area | Uncertainty goal / breakthrough / threshold | Horizontal res. g/b/t | Observing cycle g/b/t | Timeliness g/b/t | Coverage | Confidence | Validated |
|---|---|---|---|---|---|---|---|---|---|---|
| 318 | Wind speed (near surface) | Near Surface | 2.1 Global Numerical Weather Prediction and Real-time Monitoring | 0.5 m/s 1.5 m/s 2 m/s | 15 km 100 km 250 km | 60 min 6 h 12 h | 6 min 30 min 6 h | Global land | firm | 2009-02-10 |
| 389 | Wind speed (near surface) | Near Surface | 2.2 High-Resolution Numerical Weather Prediction | 0.5 m/s 1 m/s 3 m/s | 0.5 km 5 km 20 km | 30 min 60 min 3 h | 15 min 30 min 2 h | Global land | firm | 2011-08-04 |
| 455 | Wind speed (near surface) | Near Surface | 2.3 Nowcasting / Very Short-Range Forecasting | 1 m/s 1.4 m/s 3 m/s | 1 km 5 km 20 km | 5 min 15 min 60 min | 5 min 15 min 60 min | Global land | reasonable | 2013-04-08 |
| 764 | Wind speed (near surface) | Near Surface | 2.8 Aeronautical Meteorology | 0.2 m/s 0.5 m/s 1 m/s |  | 5 sec 60 sec 2 min | 5 sec 60 sec 2 min | Point | firm | 2014-03-31 |
| 768 | Wind speed (near surface) | Near Surface | 2.5 Atmospheric Climate Monitoring | 0.1 m/s 0.5 m/s 1 m/s 0.5 | 10 km 100 km 500 km 0.5 | 60 min 60 min 3 h 0.5 | 6 h 24 h 30 d 0.5 | Global | firm | 2023-04-28 |
| 320 | Wind vector (near surface) | Near Surface | 2.1 Global Numerical Weather Prediction and Real-time Monitoring | 0.5 m/s 2 m/s 3 m/s | 15 km 100 km 250 km | 60 min 6 h 12 h | 6 min 30 min 6 h | Global land | firm | 2009-02-10 |
| 391 | Wind vector (near surface) | Near Surface | 2.2 High-Resolution Numerical Weather Prediction | 0.5 m/s 1.077 m/s 5 m/s | 2 km 10 km 40 km | 30 min 60 min 3 h | 15 min 30 min 2 h | Global land | firm | 2011-02-01 |
| 457 | Wind vector (near surface) | Near Surface | 2.3 Nowcasting / Very Short-Range Forecasting | 1 m/s 2 m/s 5 m/s | 5 km 10 km 50 km | 5 min 15 min 60 min | 5 min 15 min 60 min | Global land | firm | 2013-04-08 |
| 734 | Wind vector (near surface) | Near Surface | 2.8 Aeronautical Meteorology | 0.5 m/s 1 m/s 5 m/s |  | 5 sec 5 min 10 min | 5 sec 5 min 10 min | Point | firm | 2014-03-27 |
| 765 | Wind vector (near surface) | Near Surface | 2.8 Aeronautical Meteorology | 0.4 m/s 0.7 m/s 2 m/s |  | 5 sec 60 sec 2 min | 5 sec 60 sec 2 min | Point | firm | 2014-03-31 |
| 984 | Wind vector (near surface) | Near Surface | 2.5 Atmospheric Climate Monitoring | 0.1 m/s 0.5 m/s 1 m/s 0.5 | 10 km 100 km 500 km 0.5 | 60 min 60 min 3 h 0.5 | 6 h 24 h 30 d 0.5 | Global | firm | 2023-04-28 |
| 244 | Accumulated precipitation | Near Surface | 2.1 Global Numerical Weather Prediction and Real-time Monitoring | 0.5 mm 2 mm 5 mm | 10 km 30 km 100 km | 60 min 3 h 12 h | 24 h 5 d 30 d | Global | firm | 2009-02-10 |
| 334 | Accumulated precipitation | Near Surface | 2.2 High-Resolution Numerical Weather Prediction | 0.5 mm 2 mm 5 mm | 0.5 km 2 km 10 km | 30 min 2 h 6 h | 6 h 9 h 24 h | Global | firm | 2011-08-04 |
| 1003 | Accumulated precipitation | Near Surface | 2.5 Atmospheric Climate Monitoring | 1 mm 2 mm 5 mm 0.5 | 50 km 125 km 250 km 0.5 | 24 h 30 d 1 y 0.5 | 24 h 7 d 30 d 0.5 | Global | firm | 2023-05-02 |
| 1124 | Accumulated precipitation | Near Surface | 4.1 Hydrological Forecasting and Real-time Monitoring | 0.5 mm 2 mm 5 mm | 10 km 30 km 100 km | 60 sec 3 sec 12 sec | 1 sec 5 sec 30 sec | Global | reasonable | 2024-05-01 |
| 1126 | Accumulated precipitation |  | 2.1 Global Numerical Weather Prediction and Real-time Monitoring | 1 mm 1 mm |  | 60 min 1 sec 1 sec 0.5 | 2 sec 2 h 2 d 0.5 | Global | firm | 2024-11-14 |
| 1166 | Accumulated precipitation | Near Surface | 2.9 Agricultural Meteorology | 2 mm 5 mm 10 mm 0.5 | 0.25 km 20 km 50 km 0.5 | 24 h 36 h 3 d 0.5 | 24 h 30 h 2 d 0.5 | Global | reasonable | 2003-10-20 |
| 289 | Precipitation intensity at surface (liquid or solid) | Near Surface | 2.1 Global Numerical Weather Prediction and Real-time Monitoring | 0.1 mm/h 0.5 mm/h 1 mm/h | 5 km 15 km 50 km | 60 min 3 h 12 h | 6 min 30 min 6 h | Global | reasonable | 2009-02-10 |
| 368 | Precipitation intensity at surface (liquid or solid) | Near Surface | 2.2 High-Resolution Numerical Weather Prediction | 0.1 mm/h 0.2 mm/h 1 mm/h | 0.5 km 2 km 10 km | 15 min 30 min 2 h | 15 min 30 min 2 h | Global | reasonable | 2019-12-04 |
| 442 | Precipitation intensity at surface (liquid or solid) | Near Surface | 2.3 Nowcasting / Very Short-Range Forecasting | 0.1 mm/h 0.3 mm/h 1 mm/h | 1 km 5 km 30 km | 5 min 10 min 60 min | 5 min 10 min 30 min | Global | reasonable | 2013-04-03 |
| 730 | Precipitation intensity at surface (liquid or solid) | Near Surface | 2.8 Aeronautical Meteorology | 0.001 mm/h 0.01 mm/h 0.1 mm/h |  | 30 min 60 min 2 h | 5 min 10 min 30 min | Local | firm | 2014-03-27 |
| 773 | Precipitation intensity at surface (liquid or solid) | Near Surface | 2.5 Atmospheric Climate Monitoring | 0.5 mm/h | 25 km | 30 d |  | Global | reasonable | 2019-09-25 |
| 257 | Atmospheric temperature | PBL | 2.1 Global Numerical Weather Prediction and Real-time Monitoring | 0.5 K 1 K 3 K | 15 km 100 km 500 km | 60 min 6 h 24 h | 6 min 30 min 6 h | Global | firm | 2009-02-10 |
| 341 | Atmospheric temperature | PBL | 2.2 High-Resolution Numerical Weather Prediction | 0.5 K 1 K 3 K | 0.5 km 2 km 10 km | 15 min 60 min 3 h | 10 min 30 min 2 h | Global | firm | 2019-12-04 |
| 427 | Atmospheric temperature | PBL | 2.3 Nowcasting / Very Short-Range Forecasting | 0.5 K 1 K 3 K | 5 km 10 km 50 km | 5 min 10 min 60 min | 5 min 10 min 60 min | Global | firm | 2013-04-03 |
| 778 | Atmospheric temperature | PBL | 2.5 Atmospheric Climate Monitoring | 0.1 K 0.5 K 1 K 0.5 | 15 km 100 km 500 km 0.5 | 60 min 6 h 12 h 0.5 | 60 min 3 h 24 h 0.5 | Global | firm | 2023-04-28 |
| 21 | Specific humidity | PBL | 2.8 Aeronautical Meteorology | 5 g kg -1 7 g kg -1 10 g kg -1 | 50 km 70 km 100 km | 60 min 90 min 3 h | 60 min 90 min 2 h | Global | firm | 2014-03-27 |
| 303 | Specific humidity | PBL | 2.1 Global Numerical Weather Prediction and Real-time Monitoring | 2 g kg -1 5 g kg -1 10 g kg -1 | 15 km 50 km 250 km | 60 min 6 h 12 h | 6 min 30 min 6 h | Global | firm | 2009-02-10 |
| 379 | Specific humidity | PBL | 2.2 High-Resolution Numerical Weather Prediction | 2 g kg -1 5 g kg -1 10 g kg -1 | 0.5 km 5 km 20 km | 15 min 60 min 6 h | 15 min 30 min 2 h | Global | firm | 2011-07-29 |
| 704 | Specific humidity | PBL | 2.3 Nowcasting / Very Short-Range Forecasting | 2 g kg -1 5 g kg -1 10 g kg -1 | 5 km 10 km 50 km | 5 min 10 min 60 min | 5 min 10 min 60 min | Global | reasonable | 2013-04-25 |
| 1130 | Specific humidity | PBL | 2.5 Atmospheric Climate Monitoring | 0.1 g kg -1 0.5 g kg -1 1 g kg -1 0.5 | 15 km 100 km 500 km 0.5 | 50 min 60 min 3 h 0.5 | 60 min 5 d 30 d 0.5 | Global | firm | 2025-04-11 |