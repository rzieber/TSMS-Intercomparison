def main():
    ...
    """
    1. Link the SD Card reformatted data and the CSV data downloaded from CHORDS to final_paws_reformatter.py.
       This creates a comprehensive CSV which may be ingested by the other scripts.
    
    2. Clean data by passing reformatted data through outlier-removal.py 
       (relative paths already configured)

    3. Generate statistical analysis with error-analysis.py
       (must specify the timeframe to aggregate data to!)

    4. Create plots with plot-gen-final.py
       (uncomment the portion you wish to generate plots for)
    """