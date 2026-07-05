import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# Ensure imports work from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.schemas import SimulationRequest

def run_simulation(
    location_id: int,
    request: SimulationRequest,
    models: dict,
    db_engine
) -> dict:
    """
    Executes a 'what-if' scenario by altering weather and traffic/tourist baselines
    and running the models recursively, capturing cascading physical effects.
    """
    try:
        with db_engine.connect() as conn:
            # 1. Fetch location details
            loc_row = conn.execute(
                text("SELECT name, latitude, longitude FROM locations WHERE id = :id"),
                {"id": location_id}
            ).fetchone()
            if not loc_row:
                raise ValueError("Location not found")
            loc_name, lat, lon = loc_row[0], float(loc_row[1]), float(loc_row[2])
            
            # 2. Get latest history timestamp
            time_row = conn.execute(
                text("SELECT MAX(timestamp) FROM traffic_conditions WHERE location_id = :id"),
                {"id": location_id}
            ).fetchone()
            
            latest_time = pd.to_datetime(time_row[0]).to_pydatetime()
            
            # 3. Pull last 168 hours of historical data to initialize lags
            start_history_time = latest_time - timedelta(hours=168)
            history_query = text("""
                SELECT t.timestamp, t.congestion_index, tour.visitor_count, e.consumption_kwh,
                       w.consumption_m3, aqi.aqi, pt.metro_ridership, c.emissions_mt_co2
                FROM traffic_conditions t
                JOIN tourism_demand tour ON t.timestamp = tour.timestamp AND t.location_id = tour.location_id
                JOIN energy_consumption e ON t.timestamp = e.timestamp AND t.location_id = e.location_id
                JOIN water_consumption w ON t.timestamp = w.timestamp AND t.location_id = w.location_id
                JOIN air_quality aqi ON t.timestamp = aqi.timestamp AND t.location_id = aqi.location_id
                JOIN public_transport pt ON t.timestamp = pt.timestamp AND t.location_id = pt.location_id
                JOIN carbon_emissions c ON t.timestamp = c.timestamp AND t.location_id = c.location_id
                WHERE t.location_id = :id AND t.timestamp >= :hist_t
                ORDER BY t.timestamp
            """)
            hist_df = pd.read_sql(history_query, conn, params={"id": location_id, "hist_t": start_history_time})
            hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
            
            # 4. Fetch weather forecast for the next 24 hours
            forecast_end_time = latest_time + timedelta(hours=24)
            weather_query = text("""
                SELECT timestamp, temperature, humidity, wind_speed, precipitation
                FROM weather_forecast
                WHERE timestamp > :t AND timestamp <= :end_t
                ORDER BY timestamp
            """)
            weather_df = pd.read_sql(weather_query, conn, params={"t": latest_time, "end_t": forecast_end_time})
            weather_df["timestamp"] = pd.to_datetime(weather_df["timestamp"])

            # 4.5 FALLBACK: Generate synthetic weather if database has no future records
            if len(weather_df) < 24:
                print("Database has no future weather forecast rows. Generating synthetic diurnal weather forecast...")
                latest_weather_row = conn.execute(
                    text("SELECT temperature, humidity, wind_speed, precipitation FROM weather_forecast ORDER BY timestamp DESC LIMIT 1")
                ).fetchone()
                
                if latest_weather_row:
                    base_temp = latest_weather_row[0]
                    base_hum = latest_weather_row[1]
                    base_wind = latest_weather_row[2]
                    base_precip = latest_weather_row[3]
                else:
                    base_temp, base_hum, base_wind, base_precip = 35.0, 50.0, 15.0, 0.0
                    
                synthetic_rows = []
                for h in range(1, 25):
                    future_time = latest_time + timedelta(hours=h)
                    hour = future_time.hour
                    
                    # Diurnal temperature cycle: peak around 14:00 (+5C), low around 04:00 (-5C)
                    temp_fluctuation = 5.0 * np.sin(2 * np.pi * (hour - 8) / 24.0)
                    temp = base_temp + temp_fluctuation + np.random.normal(0, 0.3)
                    hum = np.clip(base_hum - 3.0 * temp_fluctuation + np.random.normal(0, 1), 15, 95)
                    
                    synthetic_rows.append({
                        "timestamp": future_time,
                        "temperature": round(temp, 1),
                        "humidity": round(hum, 1),
                        "wind_speed": round(base_wind + np.random.normal(0, 0.5), 1),
                        "precipitation": base_precip
                    })
                weather_df = pd.DataFrame(synthetic_rows)

        # Set up location dummy indicators (standardizing spaces/parentheses to match new ML features)
        all_locations = ["Downtown Dubai", "Dubai Marina", "Deira", "Palm Jumeirah", 
                         "Jumeirah", "Business Bay", "Al Barsha", "Dubai International Airport (DXB)"]
        loc_dummies = {
            f"loc_{name.replace(' ', '_').replace('(', '_').replace(')', '_')}": 1 if name == loc_name else 0 
            for name in all_locations
        }

        # Initialize separate buffers for baseline and simulated run
        base_buffer = hist_df.copy()
        sim_buffer = hist_df.copy()
        
        # Apply levers to historical simulation buffer values (so lags carry the growth factor)
        sim_buffer["visitor_count"] = sim_buffer["visitor_count"] * (1 + request.tourist_growth / 100.0)
        sim_buffer["congestion_index"] = np.clip(sim_buffer["congestion_index"] * (1 + request.traffic_growth / 100.0), 0.0, 10.0)

        base_hourly = []
        sim_hourly = []

        # 5. Run parallel forecasts hour-by-hour
        for idx in range(24):
            weather_hour = weather_df.iloc[idx]
            target_time = weather_hour["timestamp"]
            
            # Time features
            hour = target_time.hour
            weekday = target_time.weekday()
            month = target_time.month
            is_weekend = 1 if weekday in [5, 6] else 0
            is_rush_hour = 1 if hour in [8, 9, 17, 18] else 0
            hour_sin = np.sin(2 * np.pi * hour / 24.0)
            hour_cos = np.cos(2 * np.pi * hour / 24.0)
            day_sin = np.sin(2 * np.pi * weekday / 7.0)
            day_cos = np.cos(2 * np.pi * weekday / 7.0)
            
            base_weather = {
                "temp": weather_hour["temperature"], "hum": weather_hour["humidity"],
                "wind": weather_hour["wind_speed"], "prec": weather_hour["precipitation"]
            }
            
            # Simulated weather shifts temperature by the temp_delta lever
            sim_weather = {
                "temp": weather_hour["temperature"] + request.temp_delta, "hum": weather_hour["humidity"],
                "wind": weather_hour["wind_speed"], "prec": weather_hour["precipitation"]
            }

            # Helper function to run forecasting on a specific buffer and weather set
            def forecast_step(buffer, weather, apply_multipliers: bool) -> dict:
                thi = weather["temp"] * (weather["hum"] / 100.0)
                temp_wind = weather["temp"] * weather["wind"]
                
                features_dict = {
                    "latitude": lat, "longitude": lon, "hour": hour, "day_of_week": weekday, "month": month,
                    "is_weekend": is_weekend, "is_rush_hour": is_rush_hour,
                    "hour_sin": hour_sin, "hour_cos": hour_cos, "day_sin": day_sin, "day_cos": day_cos,
                    "temperature": weather["temp"], "humidity": weather["hum"], "wind_speed": weather["wind"], "precipitation": weather["prec"],
                    "temp_humidity_index": thi, "temp_wind_interaction": temp_wind,
                    **loc_dummies
                }

                step_pred = {}

                for domain in ["traffic", "tourism", "energy", "water", "air_quality", "public_transport", "carbon"]:
                    target_col = {
                        "traffic": "congestion_index", "tourism": "visitor_count",
                        "energy": "consumption_kwh", "water": "consumption_m3",
                        "air_quality": "aqi", "public_transport": "metro_ridership",
                        "carbon": "emissions_mt_co2"
                    }[domain]

                    series = buffer[target_col].values
                    
                    X = pd.DataFrame([{
                        **features_dict,
                        "lag_1h": series[-1], "lag_2h": series[-2], "lag_24h": series[-24], "lag_168h": series[-168],
                        "rolling_mean_3h": np.mean(series[-3:]), "rolling_mean_24h": np.mean(series[-24:]),
                        "rolling_std_3h": np.std(series[-3:]) + 1e-5
                    }])
                    
                    # Align columns
                    model_features = models[domain].feature_names_in_
                    X = X[model_features]
                    
                    pred_val = float(models[domain].predict(X)[0])
                    
                    if apply_multipliers:
                        if domain == "tourism":
                            pred_val = pred_val * (1 + request.tourist_growth / 100.0)
                        elif domain == "traffic":
                            pred_val = pred_val * (1 + request.traffic_growth / 100.0)
                            
                    pred_val = max(0.0, pred_val)
                    if domain == "traffic":
                        pred_val = min(10.0, pred_val)
                        
                    step_pred[target_col] = pred_val
                    
                return step_pred

            # Run baseline step
            base_pred = forecast_step(base_buffer, base_weather, apply_multipliers=False)
            # Run simulation step
            sim_pred = forecast_step(sim_buffer, sim_weather, apply_multipliers=True)

            # Update buffers
            def update_buffer(buffer, pred_dict):
                new_row = {col: pred_dict.get(col, 0.0) for col in buffer.columns if col != "timestamp"}
                new_row["timestamp"] = target_time
                return pd.concat([buffer, pd.DataFrame([new_row])], ignore_index=True)

            base_buffer = update_buffer(base_buffer, base_pred)
            sim_buffer = update_buffer(sim_buffer, sim_pred)

            # Save hourly values
            base_hourly.append({
                "timestamp": target_time.isoformat(),
                "congestion_index": round(base_pred["congestion_index"], 2),
                "visitor_count": round(base_pred["visitor_count"], 0),
                "consumption_kwh": round(base_pred["consumption_kwh"], 1),
                "consumption_m3": round(base_pred["consumption_m3"], 1),
                "aqi": round(base_pred["aqi"], 0),
                "metro_ridership": round(base_pred["metro_ridership"], 0),
                "emissions_mt_co2": round(base_pred["emissions_mt_co2"], 3)
            })

            sim_hourly.append({
                "timestamp": target_time.isoformat(),
                "congestion_index": round(sim_pred["congestion_index"], 2),
                "visitor_count": round(sim_pred["visitor_count"], 0),
                "consumption_kwh": round(sim_pred["consumption_kwh"], 1),
                "consumption_m3": round(sim_pred["consumption_m3"], 1),
                "aqi": round(sim_pred["aqi"], 0),
                "metro_ridership": round(sim_pred["metro_ridership"], 0),
                "emissions_mt_co2": round(sim_pred["emissions_mt_co2"], 3)
            })

        # Calculate summaries
        def summarize_run(hourly_records):
            df = pd.DataFrame(hourly_records)
            return {
                "avg_congestion": round(df["congestion_index"].mean(), 2),
                "total_visitors": int(df["visitor_count"].sum()),
                "total_energy_kwh": round(df["consumption_kwh"].sum(), 1),
                "total_water_m3": round(df["consumption_m3"].sum(), 1),
                "avg_aqi": round(df["aqi"].mean(), 1),
                "total_metro_ridership": int(df["metro_ridership"].sum()),
                "total_carbon_mt": round(df["emissions_mt_co2"].sum(), 3)
            }

        run_name = f"Sim_T{request.temp_delta}_Tour{request.tourist_growth}_Traf{request.traffic_growth}"
        
        return {
            "scenario_name": run_name,
            "timestamp": datetime.utcnow().isoformat(),
            "location_name": loc_name,
            "inputs": {
                "temp_delta": request.temp_delta,
                "tourist_growth": request.tourist_growth,
                "traffic_growth": request.traffic_growth
            },
            "baseline": summarize_run(base_hourly),
            "simulated": summarize_run(sim_hourly),
            "hourly_comparison": {
                "hours": [h["timestamp"] for h in base_hourly],
                "baseline": base_hourly,
                "simulated": sim_hourly
            }
        }
    except Exception as e:
        print(f"Simulation engine failed: {e}")
        raise e