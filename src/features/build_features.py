import os
import sys
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Ensure we can import from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import settings

class FeaturePipeline:
    """
    Retrieves smart city datasets, joins them with weather and location data,
    and engineers features for machine learning models.
    """
    def __init__(self):
        self.engine = create_engine(settings.database_url)

    def load_raw_data(self, target_table: str) -> pd.DataFrame:
        """
        Loads raw data for a specific domain table, joined with weather and location metrics.
        """
        query = f"""
            SELECT t.*, l.name as location_name, l.latitude, l.longitude,
                   w.temperature, w.humidity, w.wind_speed, w.precipitation, w.condition
            FROM {target_table} t
            JOIN locations l ON t.location_id = l.id
            LEFT JOIN weather_forecast w ON t.timestamp = w.timestamp
            ORDER BY t.location_id, t.timestamp
        """
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        
        # Convert timestamp to datetime object
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def engineer_features(self, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """
        Transforms raw data into an engineered feature set.
        Performs temporal encoding, lag creation, rolling windows, and one-hot encoding.
        """
        # Copy to avoid modifying original dataframe
        data = df.copy()
        
        # 1. Calendar/Temporal Features
        data["hour"] = data["timestamp"].dt.hour
        data["day_of_week"] = data["timestamp"].dt.weekday
        data["month"] = data["timestamp"].dt.month
        data["is_weekend"] = data["day_of_week"].apply(lambda x: 1 if x in [5, 6] else 0)
        data["is_rush_hour"] = data["hour"].apply(lambda h: 1 if h in [8, 9, 17, 18] else 0)
        
        # Cyclical Temporal Encoding (Sine/Cosine)
        data["hour_sin"] = np.sin(2 * np.pi * data["hour"] / 24.0)
        data["hour_cos"] = np.cos(2 * np.pi * data["hour"] / 24.0)
        data["day_sin"] = np.sin(2 * np.pi * data["day_of_week"] / 7.0)
        data["day_cos"] = np.cos(2 * np.pi * data["day_of_week"] / 7.0)
        
        # 2. Lag Features (grouped by location so values don't bleed between zones)
        # Shift values backwards in time to capture auto-regressive trends
        data["lag_1h"] = data.groupby("location_id")[target_col].shift(1)
        data["lag_2h"] = data.groupby("location_id")[target_col].shift(2)
        data["lag_24h"] = data.groupby("location_id")[target_col].shift(24)
        data["lag_168h"] = data.groupby("location_id")[target_col].shift(168)  # 1 week ago lag
        
        # 3. Rolling Statistics
        # 3-hour and 24-hour moving averages
        data["rolling_mean_3h"] = data.groupby("location_id")[target_col].transform(
            lambda x: x.shift(1).rolling(window=3).mean()
        )
        data["rolling_mean_24h"] = data.groupby("location_id")[target_col].transform(
            lambda x: x.shift(1).rolling(window=24).mean()
        )
        data["rolling_std_3h"] = data.groupby("location_id")[target_col].transform(
            lambda x: x.shift(1).rolling(window=3).std()
        )
        
        # 4. Weather Interactions
        # Comfort Index: Temp-Humidity index
        data["temp_humidity_index"] = data["temperature"] * (data["humidity"] / 100.0)
        data["temp_wind_interaction"] = data["temperature"] * data["wind_speed"]
        
        # 5. Drop NaN rows (first few rows of each location that don't have historical lags)
        data = data.dropna(subset=["lag_168h"])
        
        # 6. One-Hot Encode Location names (helps regression models capture spatial biases)
        # E.g. Downtown will get its own binary indicator column
        location_dummies = pd.get_dummies(data["location_name"], prefix="loc", dtype=int)
        data = pd.concat([data, location_dummies], axis=1)
        
        return data

    def prepare_train_test_split(self, df: pd.DataFrame, target_col: str, test_ratio: float = 0.20):
        """
        Splits data chronologically (temporal split) to avoid future-leakage.
        """
        # Determine split index based on timestamps
        unique_timestamps = sorted(df["timestamp"].unique())
        split_idx = int(len(unique_timestamps) * (1 - test_ratio))
        split_time = unique_timestamps[split_idx]
        
        print(f"Temporal Split Time Threshold: {split_time}")
        
        # Features to drop from X (target, keys, strings)
        drop_cols = ["id", "timestamp", "location_id", "location_name", "condition", "created_at", target_col]
        # Handle transport table which might contain multiple sub-targets
        if "metro_ridership" in df.columns and target_col != "metro_ridership":
            drop_cols.extend(["metro_ridership", "bus_ridership", "taxi_ridership"])
        
        # Train Split
        train_df = df[df["timestamp"] < split_time]
        test_df = df[df["timestamp"] >= split_time]
        
        X_train = train_df.drop(columns=drop_cols, errors="ignore")
        y_train = train_df[target_col]
        
        X_test = test_df.drop(columns=drop_cols, errors="ignore")
        y_test = test_df[target_col]
        
        return X_train, X_test, y_train, y_test

if __name__ == "__main__":
    load_dotenv()
    pipeline = FeaturePipeline()
    
    # Run test on traffic conditions table
    print("Testing Feature Pipeline on 'traffic_conditions'...")
    df_raw = pipeline.load_raw_data("traffic_conditions")
    print(f"Raw Data Shape: {df_raw.shape}")
    
    df_features = pipeline.engineer_features(df_raw, target_col="congestion_index")
    print(f"Features Data Shape: {df_features.shape}")
    
    X_train, X_test, y_train, y_test = pipeline.prepare_train_test_split(df_features, target_col="congestion_index")
    print(f"Train Features Shape: {X_train.shape}, Test Features Shape: {X_test.shape}")
    print(f"Target variable statistics:\n{y_train.describe()}")
    print("\nFeature Engineering test passed successfully!")