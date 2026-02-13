import os
from fastapi import APIRouter, HTTPException
from python_research.schemas.schema import JavaRouteRequest, ForecastRequest, ForecastResponse
from python_research.services.aqi_engine import fetch_google_aqi_profile, interpolate_pollutants, fetch_google_weather_history, fetch_google_aqi_history
import numpy as np
from datetime import datetime, timedelta

router = APIRouter()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

@router.post("/analyze-routes")
async def analyze_routes(data: JavaRouteRequest):
    print(f"DEBUG: Processing {data.routeCount} routes", flush=True)
    
    start_p = fetch_google_aqi_profile(data.start_loc[0], data.start_loc[1], GOOGLE_API_KEY)
    end_p = fetch_google_aqi_profile(data.end_loc[0], data.end_loc[1], GOOGLE_API_KEY)
    
    comparisons = {}
    for i, route in enumerate(data.routes):
        points = [[c.lat, c.lng] for c in route.coordinates]
        path_details = interpolate_pollutants(start_p, end_p, points)
        
        aqis = [p['aqi'] for p in path_details if isinstance(p['aqi'], (int, float))]
        avg_exposure = sum(aqis)/len(aqis) if aqis else 0
        
        comparisons[f"Route_{i+1}"] = {
            "avg_exposure_aqi": round(avg_exposure, 2),
            "details": path_details
        }
    return {"status": "success", 
            "ground_truth": {"start_point": start_p, "end_point": end_p},
            "route_analysis": comparisons}

# @router.post("/predict-forecast", response_model=ForecastResponse)
# async def predict_forecast(data: ForecastRequest):
#     # For hackathon: simulate fetching last 24h of 16 features from Google/DB
#     # In production, replace with real 24x16 matrix fetch
#     dummy_history = np.random.rand(24, 16) 
    
#     predictions = get_lstm_forecast(dummy_history, data.station_id)
    
#     return {
#         "status": "success",
#         "next_hour_prediction": round(predictions[0], 2),
#         "twelve_hour_forecast": [round(p, 2) for p in predictions],
#         "message": "Pollution spike expected" if predictions[-1] > predictions[0] else "Stable conditions"
#     }


@router.post("/history_data_all")
async def history_data_all(data: ForecastRequest):
    print(f"DEBUG: Aggregating 24h history for Lat: {data.lat}, Lon: {data.lon}", flush=True)
    
    try:
        # 1. Fetch both histories
        # Make sure the pollutant code for PM2.5 in your helper matches 'pm25' from API
        weather_res = fetch_google_weather_history(data.lat, data.lon, GOOGLE_API_KEY)
        aqi_res = fetch_google_aqi_history(data.lat, data.lon, GOOGLE_API_KEY)
        
        if "error" in weather_res:
            raise HTTPException(status_code=500, detail=f"Weather API: {weather_res['error']}")
        if "error" in aqi_res:
            raise HTTPException(status_code=500, detail=f"AQI API: {aqi_res['error']}")

        # 2. Synchronize and format the data
        # We assume both APIs return 24 hours. We'll zip them to align by time.
        combined_history = []
        
        # Google APIs usually return data from oldest to newest or vice-versa.
        # We pair them index by index.
        for w_hour, a_hour in zip(weather_res["history"], aqi_res["history"]):
            utc_time = datetime.fromisoformat(a_hour["time"].replace("Z", "+00:00"))
            ist_time = utc_time + timedelta(hours=5, minutes=30)
            readable_ist = ist_time.strftime("%Y-%m-%d %H:%M:%S")
            combined_history.append({
                "time": readable_ist,
                # Pollutants
                "pm2_5": a_hour.get("pm25", 0), 
                "pm10": a_hour.get("pm10", 0),
                "no2": a_hour.get("no2", 0),
                "co": a_hour.get("co", 0),
                "so2": a_hour.get("so2", 0),
                "o3": a_hour.get("o3", 0),
                # Weather - FIXED KEYS BELOW
                "temp_c": w_hour.get("temp_c", 0),   
                "wind": w_hour.get("wind", 0),       
                "humidity": w_hour.get("humidity", 0)
            })

        return {
            "status": "success",
            "location": {"lat": data.lat, "lon": data.lon},
            "history_count": len(combined_history),
            "data": combined_history
        }

    except Exception as e:
        print(f"ERROR: Combined History failed: {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))