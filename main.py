def main():
    ...
    """
    Below is a step-by-step overview of the workflow for the TSMS Intercomparison project:
    
    1. Link the SD Card reformatted data and the CSV data downloaded from CHORDS to final_paws_reformatter.py.
       This creates a comprehensive CSV which may be ingested by the other scripts.

    1b. Run scripts/reformatting/splice_chords_dec2024.py to replace Dec 2024 -> Nov 2025 with the correctly
        labeled CHORDS batch (data/raw/3D-PAWS/Dec-2024_Nov-2025). In the Jan24-Nov25 CHORDS files the rows
        from Dec 2024 on are in a different column order than the header (docs/sensor-failures.md SF-10).
        The same script also re-maps the CHORDS rows before 2024-03-11 00:00 UTC at TSMS02, 03, 04, 05, 08, which
        are out of order too (suspected firmware/software change), and excludes TSMS04's temperatures for that
        window (docs/methods.md).

    2. Clean data by passing reformatted data through outlier-removal.py 
       (relative paths already configured)

    3. Generate statistical analysis with error-analysis.py
       (must specify the timeframe to aggregate data to!)

    4. Create plots with plot-gen-final.py
       (uncomment the portion you wish to generate plots for)
    """