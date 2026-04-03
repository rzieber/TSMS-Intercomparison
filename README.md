# Summary
This codebase features the scripts used to perform a data comparison of 9 3D-PAWS weather stations with 3 co-located commercial reference stations operated by TSMS. This project contains the logic used to format the data, the statistical analysis used to quantify station performance, and the plotting scripts to generate images.

## Data Period
November 1, 2022 through November 30, 2025.

## Data Formats
Raw data for 3D-PAWS were retrieved from two sources:
- SD cards stored locally on 3D-PAWS stations (Nov. 2022 - Jan. 2024)
    - daily `.log` files
- downloaded from the cloud-hosted CHORDS database at `https://3d-calibration.chordsrt.com`
    - comprehensive `.csv` files

TSMS reference data was provided in a comprehensive plaintext file `.txt`.

## Station Configurations
### Sites
Each of these sites throughout Turkiye were strategically chosen to represent a variety of climatological zones. There are 3 3D-PAWS stations present along with 1 co-located reference station (operated by TSMS).
- Ankara
- Konya
- Adana
### Parameters
- temperature (BMP280/HTU21D/SHT31D/MCP9808)
- relative humidity (HTU21D/SHT31D)
- pressure (BMP280)
- wind (anemometer: SS451A Hall Effect | wind vane: AS5600 Potentiometer)
- rainfall (tipping bucket: SS451A Hall Effect)
### 3D-PAWS Reference Stations
The following stations received no changes, other than routine maintenance.
- Ankara: TSMS00, TSMS01
- Konya: TSMS04
- Adana: TSMS07

### Important Notes
#### Sensor Upgrade
Due to an observed sensor malfunction involving the HTU21D, an upgrade to the SHT31D was made on <b>non-reference</b> stations during mid-January 2024.
- Ankara: January 17, 2024
- Konya: January 12, 2024
- Adana: January 15, 2024

#### Wind Sampling Height Discrepancy
3D-PAWS stations sample wind at 2 meters, while the TSMS-operated reference stations sample wind at the standard 10 meters. To resolve this, a Hellman reduction was performed with the following exponents:
- Ankara: 0.3 (urban environment)
- Konya: 0.32 (urban environment + many obstacles)
- Adana: 0.25 (suburban environment + grass)

# Workflow
1. Reformat all files (SD card, CHORDS, TSMS reference) to a common `.csv` format (see `scripts/reformatting`).
2. Explore data visually (see `scripts/plotter/plot-gen-exploratory.py`).
3. Perform outlier categorization and removal (see `scripts/outliers/outlier-removal.py`).
4. Quantify station performance (see `scripts/error/error-analysis.py`).
5. Generate final plots (see `scripts/plotter/plot-gen-final.py`).

# Dependencies
Install the required Python packages with:

```bash
pip install -r requirements.txt
```

Current third-party dependencies:

```txt
numpy
pandas
scipy
scikit-learn
matplotlib
seaborn
windrose
```
