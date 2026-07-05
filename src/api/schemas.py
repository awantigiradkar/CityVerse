from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Any, Optional

class LocationSchema(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    description: Optional[str] = None

    class Config:
        from_attributes = True

class WeatherSchema(BaseModel):
    temperature: float
    humidity: float
    wind_speed: float
    precipitation: float
    condition: str

class DomainMetricsSchema(BaseModel):
    traffic: Dict[str, Any]
    tourism: Dict[str, Any]
    energy: Dict[str, Any]
    water: Dict[str, Any]
    air_quality: Dict[str, Any]
    transport: Dict[str, Any]
    carbon: Dict[str, Any]

class LiveStatusResponse(BaseModel):
    location: LocationSchema
    timestamp: datetime
    weather: WeatherSchema
    metrics: DomainMetricsSchema

class ForecastHourResponse(BaseModel):
    timestamp: datetime
    congestion_index: float
    visitor_count: float
    consumption_kwh: float
    consumption_m3: float
    aqi: float
    metro_ridership: float
    emissions_mt_co2: float

class ForecastResponse(BaseModel):
    location_id: int
    location_name: str
    forecasts: List[ForecastHourResponse]

class SimulationRequest(BaseModel):
    temp_delta: float = 0.0
    tourist_growth: float = 0.0
    traffic_growth: float = 0.0

class SimulationResponse(BaseModel):
    scenario_name: str
    timestamp: datetime
    inputs: Dict[str, Any]
    baseline: Dict[str, Any]
    simulated: Dict[str, Any]