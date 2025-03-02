import pandas as pd
import numpy as np
import plotly.express as px
import math
import requests
from io import StringIO

def load_data():
    """Load data from GitHub"""
    try:
        # Your CSV URL
        url = "https://raw.githubusercontent.com/JARAWA/JOSAA_login/refs/heads/main/josaa2024_cutoff.csv"
        
        try:
            # Fetch data from GitHub
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad status codes
            
            # Read CSV data
            df = pd.read_csv(StringIO(response.text))
            
            # Print debug information
            print(f"Data loaded successfully. Shape: {df.shape}")
            print("Columns:", df.columns.tolist())
            
            # Ensure column names match exactly
            required_columns = [
                "Institute", "College Type", "Location", 
                "Academic Program Name", "Category", 
                "Opening Rank", "Closing Rank", "Round"
            ]
            
            # Check if all required columns exist
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing columns: {missing_columns}")
            
            # Preprocess data
            df["Opening Rank"] = pd.to_numeric(df["Opening Rank"], errors="coerce").fillna(9999999)
            df["Closing Rank"] = pd.to_numeric(df["Closing Rank"], errors="coerce").fillna(9999999)
            df["Round"] = df["Round"].astype(str)
            
            print("Data preprocessing completed successfully")
            return df
            
        except requests.RequestException as e:
            print(f"Error fetching data from GitHub: {e}")
            return None
            
    except Exception as e:
        print(f"Error in load_data: {e}")
        return None

def get_unique_branches():
    """Get list of unique branches"""
    try:
        df = load_data()
        if df is not None:
            unique_branches = sorted(df["Academic Program Name"].dropna().unique().tolist())
            return ["All"] + unique_branches
        return ["All"]
    except Exception as e:
        print(f"Error getting branches: {e}")
        return ["All"]

def hybrid_probability_calculation(rank, opening_rank, closing_rank):
    try:
        M = (opening_rank + closing_rank) / 2
        S = (closing_rank - opening_rank) / 10
        if S == 0:
            S = 1
        logistic_prob = 1 / (1 + math.exp((rank - M) / S)) * 100

        if rank < opening_rank:
            improvement = (opening_rank - rank) / opening_rank
            if improvement >= 0.5:
                piece_wise_prob = 99.0
            else:
                piece_wise_prob = 96 + (improvement * 6)
        elif rank == opening_rank:
            piece_wise_prob = 95.0
        elif rank < closing_rank:
            range_width = closing_rank - opening_rank
            position = (rank - opening_rank) / range_width
            if position <= 0.2:
                piece_wise_prob = 94 - (position * 70)
            elif position <= 0.5:
                piece_wise_prob = 80 - ((position - 0.2) / 0.3 * 20)
            elif position <= 0.8:
                piece_wise_prob = 60 - ((position - 0.5) / 0.3 * 20)
            else:
                piece_wise_prob = 40 - ((position - 0.8) / 0.2 * 20)
        elif rank == closing_rank:
            piece_wise_prob = 15.0
        elif rank <= closing_rank + 10:
            piece_wise_prob = 5.0
        else:
            piece_wise_prob = 0.0

        if rank < opening_rank:
            improvement = (opening_rank - rank) / opening_rank
            final_prob = max(logistic_prob, 95) if improvement > 0.5 else (logistic_prob * 0.4 + piece_wise_prob * 0.6)
        elif rank <= closing_rank:
            final_prob = (logistic_prob * 0.7 + piece_wise_prob * 0.3)
        else:
            final_prob = 0.0 if rank > closing_rank + 100 else min(logistic_prob, 5)

        return round(final_prob, 2)
    except Exception as e:
        print(f"Error in probability calculation: {str(e)}")
        return 0.0

def get_probability_interpretation(probability):
    if probability >= 95:
        return "Very High Chance"
    elif probability >= 80:
        return "High Chance"
    elif probability >= 60:
        return "Moderate Chance"
    elif probability >= 40:
        return "Low Chance"
    elif probability > 0:
        return "Very Low Chance"
    else:
        return "No Chance"
