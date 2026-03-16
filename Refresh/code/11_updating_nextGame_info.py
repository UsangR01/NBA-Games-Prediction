"""
Step 11 — Next-game info update.

This is a thin wrapper: the DataPreprocessor logic that merges game stats,
player stats, and lineups lives in 6_data_preparation.py.  Running this
script re-runs that merge so the preprocessed file stays current before
schedule/injury data is layered on top by step 10.
"""
import sys
import os

# Allow importing from the same directory regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from importlib import import_module

if __name__ == "__main__":
    prep = import_module("6_data_preparation")
    prep.main()
