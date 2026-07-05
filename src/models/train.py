import os
import sys
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from dotenv import load_dotenv

# Ensure we can import from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.features.build_features import FeaturePipeline
from src.models.registry import save_model

def calculate_mape(y_true, y_pred) -> float:
    """
    Calculates Mean Absolute Percentage Error (MAPE).
    Handles zero values in target by adding a tiny epsilon.
    """
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    epsilon = 1e-5
    mask = y_true != 0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / (y_true[mask] + epsilon))) * 100

def evaluate_predictions(y_true, y_pred) -> dict:
    """
    Calculates regression metrics.
    """
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = calculate_mape(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    
    return {
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "MAPE": round(mape, 2),
        "R2": round(r2, 4)
    }

def train_and_compare():
    """
    Runs the model training pipeline:
    1. Iterates over 7 smart city domains.
    2. Builds features and splits data chronologically.
    3. Trains and evaluates Linear Regression, Random Forest, XGBoost, and LightGBM.
    4. Automatically registers the best model based on R2 score.
    """
    print("--- STARTING CITYVERSE MODEL TRAINING AND COMPARISON ---")
    
    # Initialize our feature pipeline
    feature_pipeline = FeaturePipeline()
    
    # Define tasks: (table_name, target_column, descriptive_task_name)
    tasks = [
        {"table": "traffic_conditions", "target": "congestion_index", "name": "traffic"},
        {"table": "tourism_demand", "target": "visitor_count", "name": "tourism"},
        {"table": "energy_consumption", "target": "consumption_kwh", "name": "energy"},
        {"table": "water_consumption", "target": "consumption_m3", "name": "water"},
        {"table": "air_quality", "target": "aqi", "name": "air_quality"},
        {"table": "public_transport", "target": "metro_ridership", "name": "public_transport"},
        {"table": "carbon_emissions", "target": "emissions_mt_co2", "name": "carbon"}
    ]
    
    # Store performance logs
    training_summary = []
    
    for task in tasks:
        print(f"\n==================================================")
        print(f"Task: Forecasting {task['target']} (from table '{task['table']}')")
        print(f"==================================================")
        
        # 1. Load data and extract features
        raw_df = feature_pipeline.load_raw_data(task["table"])
        engineered_df = feature_pipeline.engineer_features(raw_df, target_col=task["target"])
        
        # 2. Chronological Split
        X_train, X_test, y_train, y_test = feature_pipeline.prepare_train_test_split(
            engineered_df, target_col=task["target"]
        )
        
        # Define candidate models
        models = {
            "Linear Regression": LinearRegression(),
            "Random Forest": RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1),
            "XGBoost": XGBRegressor(n_estimators=50, random_state=42, n_jobs=-1, eval_metric="rmse"),
            "LightGBM": LGBMRegressor(n_estimators=50, random_state=42, n_jobs=-1, verbose=-1)
        }
        
        best_model = None
        best_r2 = -float("inf")
        best_model_name = ""
        task_results = {}
        
        # 3. Train and evaluate each candidate model
        for model_name, model in models.items():
            print(f"Training {model_name}...")
            model.fit(X_train, y_train)
            
            # Predict on validation set
            y_pred = model.predict(X_test)
            metrics = evaluate_predictions(y_test, y_pred)
            task_results[model_name] = metrics
            
            # Print performance metrics
            print(f"  -> Metrics: MAE={metrics['MAE']}, RMSE={metrics['RMSE']}, MAPE={metrics['MAPE']}%, R2={metrics['R2']}")
            
            # Select winner based on R2
            if metrics["R2"] > best_r2:
                best_r2 = metrics["R2"]
                best_model = model
                best_model_name = model_name
        
        print(f"\nWinning Model for {task['name']}: {best_model_name} (R2 = {best_r2:.4f})")
        
        # 4. Save the winning model to the Registry
        save_model(best_model, task["name"])
        
        # Save results summary
        training_summary.append({
            "Task": task["name"].upper(),
            "Best Model": best_model_name,
            "MAE": task_results[best_model_name]["MAE"],
            "RMSE": task_results[best_model_name]["RMSE"],
            "MAPE": f"{task_results[best_model_name]['MAPE']}%",
            "R2": task_results[best_model_name]["R2"]
        })
        
    # Print the overall model comparison table
    summary_df = pd.DataFrame(training_summary)
    print("\n\n==================================================")
    print("                 TRAINING SUMMARY                 ")
    print("==================================================")
    print(summary_df.to_markdown(index=False))
    print("==================================================")

if __name__ == "__main__":
    load_dotenv()
    train_and_compare()