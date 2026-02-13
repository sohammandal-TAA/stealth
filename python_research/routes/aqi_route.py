import os
from fastapi import APIRouter, HTTPException
from python_research.schemas.schema import JavaRouteRequest, ForecastRequest, ForecastResponse
from python_research.services.aqi_engine import fetch_google_aqi_profile, interpolate_pollutants
import numpy as np

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