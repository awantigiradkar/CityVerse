import pydeck as pdk
import pandas as pd
import numpy as np
from typing import Dict, List, Any

def get_default_view_state() -> pdk.ViewState:
    """
    Returns the default Pydeck camera view state centered on Dubai.
    Angled at 50 degrees pitch for premium 3D column views.
    """
    return pdk.ViewState(
        latitude=25.15,
        longitude=55.22,
        zoom=10.5,
        pitch=50,
        bearing=-15
    )

def render_traffic_map(df: pd.DataFrame) -> pdk.Deck:
    """
    Renders a 3D Column Map of traffic congestion levels across Dubai.
    Taller, red columns represent gridlock congestion.
    """
    # 1. Map color gradients (Green to Red) based on congestion (0.0 to 10.0)
    # R = congestion * 25.5, G = (10 - congestion) * 25.5, B = 0
    df["color_r"] = (df["congestion_index"] * 25.5).astype(int)
    df["color_g"] = ((10.0 - df["congestion_index"]) * 25.5).astype(int)
    df["color_b"] = 0
    
    # 2. Scale column height (height in meters: congestion * 250)
    df["column_height"] = df["congestion_index"] * 250.0

    # 3. Create the DeckGL Column Layer
    layer = pdk.Layer(
        "ColumnLayer",
        df,
        get_position=["longitude", "latitude"],
        get_elevation="column_height",
        elevation_scale=1,
        radius=300,
        get_fill_color=["color_r", "color_g", "color_b", 180],  # 180 is alpha opacity
        pickable=True,
        auto_highlight=True
    )
    
    tooltip = {
        "html": "<b>Zone:</b> {location_name}<br/>"
                "<b>Congestion Index:</b> {congestion_index}/10.0<br/>"
                "<b>Average Speed:</b> {avg_speed} km/h<br/>"
                "<b>Vehicle Count:</b> {vehicle_count} cars",
        "style": {"color": "white", "backgroundColor": "#1E1E1E"}
    }

    return pdk.Deck(
        layers=[layer],
        initial_view_state=get_default_view_state(),
        map_style="mapbox://styles/mapbox/dark-v9",  # Sleek dark mode map
        tooltip=tooltip
    )

def render_tourism_map(df: pd.DataFrame) -> pdk.Deck:
    """
    Renders a Scatterplot map showing visitor density in Dubai.
    Larger, brighter circles represent tourist hotspots.
    """
    # 1. Circle radius proportional to visitor count (radius in meters)
    df["radius_size"] = np.clip(df["visitor_count"] * 0.4, 200, 2000)
    
    # 2. Color gradient based on hotel occupancy (0 to 100)
    # High occupancy = bright HSL blue/pink. We'll use RGB: [41, 121, 255] to [255, 41, 121]
    df["color_r"] = (df["hotel_occupancy"] * 2.1 + 45).astype(int)
    df["color_g"] = (120 - df["hotel_occupancy"] * 0.8).astype(int)
    df["color_b"] = 255

    layer = pdk.Layer(
        "ScatterplotLayer",
        df,
        get_position=["longitude", "latitude"],
        get_radius="radius_size",
        get_fill_color=["color_r", "color_g", "color_b", 160],
        pickable=True,
        auto_highlight=True
    )

    tooltip = {
        "html": "<b>Zone:</b> {location_name}<br/>"
                "<b>Estimated Visitors:</b> {visitor_count}<br/>"
                "<b>Hotel Occupancy:</b> {hotel_occupancy}%",
        "style": {"color": "white", "backgroundColor": "#1E1E1E"}
    }

    return pdk.Deck(
        layers=[layer],
        initial_view_state=get_default_view_state(),
        map_style="mapbox://styles/mapbox/dark-v9",
        tooltip=tooltip
    )

def render_air_quality_map(df: pd.DataFrame) -> pdk.Deck:
    """
    Renders a Scatterplot map colored by Air Quality Index (AQI).
    Uses standard EPA color code proxies: Green (good) -> Yellow (moderate) -> Red (poor).
    """
    def aqi_color(aqi: float) -> List[int]:
        if aqi <= 50:
            return [46, 204, 113, 160]   # Green
        elif aqi <= 100:
            return [241, 196, 15, 160]   # Yellow
        elif aqi <= 150:
            return [230, 126, 34, 160]   # Orange
        else:
            return [231, 76, 60, 180]    # Red

    df["color"] = df["aqi"].apply(aqi_color)
    df["radius_size"] = 1000  # Fixed 1km radius for zones

    layer = pdk.Layer(
        "ScatterplotLayer",
        df,
        get_position=["longitude", "latitude"],
        get_radius="radius_size",
        get_fill_color="color",
        pickable=True,
        auto_highlight=True
    )

    tooltip = {
        "html": "<b>Zone:</b> {location_name}<br/>"
                "<b>AQI Index:</b> {aqi}<br/>"
                "<b>PM2.5:</b> {pm25} µg/m³<br/>"
                "<b>NO2 Level:</b> {no2} ppm",
        "style": {"color": "white", "backgroundColor": "#1E1E1E"}
    }

    return pdk.Deck(
        layers=[layer],
        initial_view_state=get_default_view_state(),
        map_style="mapbox://styles/mapbox/dark-v9",
        tooltip=tooltip
    )

def render_carbon_map(df: pd.DataFrame) -> pdk.Deck:
    """
    Renders a 3D column map representing Carbon Emissions (MT CO2/hr).
    """
    # 1. Height scales with carbon emissions (emissions * 1000 meters)
    df["column_height"] = df["emissions_mt_co2"] * 800.0
    
    # 2. Color maps to carbon output (Red/Purple gradient)
    df["color_r"] = np.clip(100 + df["emissions_mt_co2"] * 50, 100, 255).astype(int)
    df["color_g"] = 40
    df["color_b"] = np.clip(255 - df["emissions_mt_co2"] * 30, 50, 255).astype(int)

    layer = pdk.Layer(
        "ColumnLayer",
        df,
        get_position=["longitude", "latitude"],
        get_elevation="column_height",
        elevation_scale=1,
        radius=350,
        get_fill_color=["color_r", "color_g", "color_b", 170],
        pickable=True,
        auto_highlight=True
    )

    tooltip = {
        "html": "<b>Zone:</b> {location_name}<br/>"
                "<b>Carbon Emissions:</b> {emissions_mt_co2} MT CO2/hr<br/>"
                "<b>Geographical Coordinates:</b> ({latitude}, {longitude})",
        "style": {"color": "white", "backgroundColor": "#1E1E1E"}
    }

    return pdk.Deck(
        layers=[layer],
        initial_view_state=get_default_view_state(),
        map_style="mapbox://styles/mapbox/dark-v9",
        tooltip=tooltip
    )