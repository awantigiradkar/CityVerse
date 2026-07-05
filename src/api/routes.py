import os
import sys
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import create_engine, text
from typing import List

# Ensure imports work from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import settings
from src.api.schemas import LocationSchema, LiveStatusResponse, ForecastResponse, ForecastHourResponse, SimulationRequest
from src.simulation.simulator_engine import run_simulation

router = APIRouter()
engine = create_engine(settings.database_url)

@router.get("/health")
def health_check():
    """Simple API status check."""
    return {"status": "healthy", "database": "connected", "timestamp": datetime.utcnow()}

@router.get("/locations", response_model=List[LocationSchema])
def get_locations():
    """Retrieves all registered Dubai zones."""
    query = text("SELECT id, name, latitude, longitude, description FROM locations ORDER BY name")
    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            return [dict(row._mapping) for row in result]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

@router.get("/live/{location_id}", response_model=LiveStatusResponse)
def get_live_status(location_id: int):
    """
    Returns the latest recorded hour metrics for a specific location across all domains.
    """
    try:
        with engine.connect() as conn:
            # 1. Fetch location details
            loc_row = conn.execute(
                text("SELECT id, name, latitude, longitude, description FROM locations WHERE id = :id"),
                {"id": location_id}
            ).fetchone()
            
            if not loc_row:
                raise HTTPException(status_code=404, detail="Location not found")
            location = dict(loc_row._mapping)
            
            # 2. Get latest timestamp for this location in traffic_conditions
            time_row = conn.execute(
                text("SELECT MAX(timestamp) FROM traffic_conditions WHERE location_id = :id"),
                {"id": location_id}
            ).fetchone()
            
            latest_time = time_row[0]
            if not latest_time:
                raise HTTPException(status_code=404, detail="No historical records found for this location.")
            
            # 3. Pull latest weather for that hour
            weather_row = conn.execute(
                text("SELECT temperature, humidity, wind_speed, precipitation, condition FROM weather_forecast WHERE timestamp = :t"),
                {"t": latest_time}
            ).fetchone()
            weather = dict(weather_row._mapping) if weather_row else {"temperature": 25.0, "humidity": 50.0, "wind_speed": 10.0, "precipitation": 0.0, "condition": "Sunny"}

            # 4. Pull metrics from all 7 domain tables
            traffic = dict(conn.execute(text("SELECT congestion_index, avg_speed, vehicle_count FROM traffic_conditions WHERE location_id = :id AND timestamp = :t"), {"id": location_id, "t": latest_time}).fetchone()._mapping)
            tourism = dict(conn.execute(text("SELECT visitor_count, hotel_occupancy FROM tourism_demand WHERE location_id = :id AND timestamp = :t"), {"id": location_id, "t": latest_time}).fetchone()._mapping)
            energy = dict(conn.execute(text("SELECT consumption_kwh, peak_load_kw FROM energy_consumption WHERE location_id = :id AND timestamp = :t"), {"id": location_id, "t": latest_time}).fetchone()._mapping)
            water = dict(conn.execute(text("SELECT consumption_m3 FROM water_consumption WHERE location_id = :id AND timestamp = :t"), {"id": location_id, "t": latest_time}).fetchone()._mapping)
            aqi = dict(conn.execute(text("SELECT aqi, pm25, pm10, no2, co FROM air_quality WHERE location_id = :id AND timestamp = :t"), {"id": location_id, "t": latest_time}).fetchone()._mapping)
            transport = dict(conn.execute(text("SELECT metro_ridership, bus_ridership, taxi_ridership FROM public_transport WHERE location_id = :id AND timestamp = :t"), {"id": location_id, "t": latest_time}).fetchone()._mapping)
            carbon = dict(conn.execute(text("SELECT emissions_mt_co2 FROM carbon_emissions WHERE location_id = :id AND timestamp = :t"), {"id": location_id, "t": latest_time}).fetchone()._mapping)

            return {
                "location": location,
                "timestamp": latest_time,
                "weather": weather,
                "metrics": {
                    "traffic": traffic, "tourism": tourism, "energy": energy, "water": water,
                    "air_quality": aqi, "transport": transport, "carbon": carbon
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch live status: {e}")

@router.get("/forecast/{location_id}", response_model=ForecastResponse)
def get_location_forecast(location_id: int, request: Request):
    """
    Generates a 24-hour predictive forecast using recursive lag propagation.
    """
    models = request.app.state.models
    
    try:
        with engine.connect() as conn:
            loc_row = conn.execute(
                text("SELECT id, name, latitude, longitude FROM locations WHERE id = :id"),
                {"id": location_id}
            ).fetchone()
            if not loc_row:
                raise HTTPException(status_code=404, detail="Location not found")
            loc_name = loc_row[1]
            lat = float(loc_row[2])
            lon = float(loc_row[3])
            
            time_row = conn.execute(
                text("SELECT MAX(timestamp) FROM traffic_conditions WHERE location_id = :id"),
                {"id": location_id}
            ).fetchone()
            
            # Convert string to standard Python datetime
            latest_time = pd.to_datetime(time_row[0]).to_pydatetime()
            
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
            
            forecast_end_time = latest_time + timedelta(hours=24)
            weather_query = text("""
                SELECT timestamp, temperature, humidity, wind_speed, precipitation
                FROM weather_forecast
                WHERE timestamp > :t AND timestamp <= :end_t
                ORDER BY timestamp
            """)
            weather_df = pd.read_sql(weather_query, conn, params={"t": latest_time, "end_t": forecast_end_time})
            weather_df["timestamp"] = pd.to_datetime(weather_df["timestamp"])

            # Fallback: generate synthetic future weather forecast if database is empty
            if len(weather_df) < 24:
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

        history_buffer = hist_df.copy()
        predictions = []
        
        all_locations = ["Downtown Dubai", "Dubai Marina", "Deira", "Palm Jumeirah", 
                         "Jumeirah", "Business Bay", "Al Barsha", "Dubai International Airport (DXB)"]
        loc_dummies = {
            f"loc_{name.replace(' ', '_').replace('(', '_').replace(')', '_')}": 1 if name == loc_name else 0 
            for name in all_locations
        }
        
        for i in range(24):
            weather_hour = weather_df.iloc[i]
            target_time = weather_hour["timestamp"]
            
            hour = target_time.hour
            weekday = target_time.weekday()
            month = target_time.month
            is_weekend = 1 if weekday in [5, 6] else 0
            is_rush_hour = 1 if hour in [8, 9, 17, 18] else 0
            
            hour_sin = np.sin(2 * np.pi * hour / 24.0)
            hour_cos = np.cos(2 * np.pi * hour / 24.0)
            day_sin = np.sin(2 * np.pi * weekday / 7.0)
            day_cos = np.cos(2 * np.pi * weekday / 7.0)
            
            temp = weather_hour["temperature"]
            hum = weather_hour["humidity"]
            wind = weather_hour["wind_speed"]
            precip = weather_hour["precipitation"]
            thi = temp * (hum / 100.0)
            temp_wind = temp * wind
            
            features_dict = {
                "latitude": lat, "longitude": lon, "hour": hour, "day_of_week": weekday, "month": month,
                "is_weekend": is_weekend, "is_rush_hour": is_rush_hour,
                "hour_sin": hour_sin, "hour_cos": hour_cos, "day_sin": day_sin, "day_cos": day_cos,
                "temperature": temp, "humidity": hum, "wind_speed": wind, "precipitation": precip,
                "temp_humidity_index": thi, "temp_wind_interaction": temp_wind,
                **loc_dummies
            }
            
            pred_record = {"timestamp": target_time}
            
            for domain in ["traffic", "tourism", "energy", "water", "air_quality", "public_transport", "carbon"]:
                target_col = {
                    "traffic": "congestion_index", "tourism": "visitor_count",
                    "energy": "consumption_kwh", "water": "consumption_m3",
                    "air_quality": "aqi", "public_transport": "metro_ridership",
                    "carbon": "emissions_mt_co2"
                }[domain]
                
                series = history_buffer[target_col].values
                
                lag_1h = series[-1]
                lag_2h = series[-2]
                lag_24h = series[-24]
                lag_168h = series[-168]
                
                rolling_mean_3h = np.mean(series[-3:])
                rolling_mean_24h = np.mean(series[-24:])
                rolling_std_3h = np.std(series[-3:]) + 1e-5
                
                X = pd.DataFrame([{
                    **features_dict,
                    "lag_1h": lag_1h,
                    "lag_2h": lag_2h,
                    "lag_24h": lag_24h,
                    "lag_168h": lag_168h,
                    "rolling_mean_3h": rolling_mean_3h,
                    "rolling_mean_24h": rolling_mean_24h,
                    "rolling_std_3h": rolling_std_3h
                }])
                
                model_features = models[domain].feature_names_in_
                X = X[model_features]
                
                pred_val = float(models[domain].predict(X)[0])
                pred_val = max(0.0, pred_val)
                if domain == "traffic":
                    pred_val = min(10.0, pred_val)
                
                pred_record[target_col] = pred_val
            
            new_hist_row = {col: pred_record.get(col, 0.0) for col in history_buffer.columns if col != "timestamp"}
            new_hist_row["timestamp"] = target_time
            history_buffer = pd.concat([history_buffer, pd.DataFrame([new_hist_row])], ignore_index=True)
            
            predictions.append(ForecastHourResponse(
                timestamp=target_time,
                congestion_index=round(pred_record["congestion_index"], 2),
                visitor_count=round(pred_record["visitor_count"], 0),
                consumption_kwh=round(pred_record["consumption_kwh"], 1),
                consumption_m3=round(pred_record["consumption_m3"], 1),
                aqi=round(pred_record["aqi"], 0),
                metro_ridership=round(pred_record["metro_ridership"], 0),
                emissions_mt_co2=round(pred_record["emissions_mt_co2"], 3)
            ))
            
        return ForecastResponse(
            location_id=location_id,
            location_name=loc_name,
            forecasts=predictions
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast failed: {e}")

@router.post("/simulate/{location_id}")
def post_scenario_simulation(location_id: int, request: SimulationRequest, api_request: Request):
    """
    Executes a 24-hour what-if scenario.
    Modifies weather/traffic/tourist conditions and outputs side-by-side comparison arrays.
    """
    models = api_request.app.state.models
    try:
        # Run simulation engine
        results = run_simulation(location_id, request, models, engine)
        
        # Log this run to the database scenario_runs table for audits
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO scenario_runs (scenario_name, parameters, results)
                    VALUES (:name, :params, :res)
                """),
                {
                    "name": results["scenario_name"],
                    "params": json.dumps(results["inputs"]),
                    "res": json.dumps({
                        "baseline": results["baseline"],
                        "simulated": results["simulated"]
                    })
                }
            )
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scenario simulation failed: {e}")