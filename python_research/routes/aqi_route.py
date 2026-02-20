import logging
import os
from fastapi import APIRouter, HTTPException
from python_research.schemas.schema import JavaRouteRequest, ForecastRequest, ForecastResponse
from python_research.services.aqi_engine import fetch_google_aqi_profile, get_aqi_info, get_multi_station_forecast, interpolate_pollutants, fetch_google_weather_history, fetch_google_aqi_history
import numpy as np
from datetime import datetime, timedelta

router = APIRouter()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

@router.post("/analyze-routes")
async def analyze_routes(data: JavaRouteRequest):
    print(f"DEBUG: Processing {data.routeCount} routes", flush=True)
    
    # 1. Handle API Failures for Start/End points
    try:
        start_p = fetch_google_aqi_profile(data.start_loc[0], data.start_loc[1], GOOGLE_API_KEY)
        end_p = fetch_google_aqi_profile(data.end_loc[0], data.end_loc[1], GOOGLE_API_KEY)
    except Exception as e:  
        logging.error(f"Google API Error: {e}")
        raise HTTPException(status_code=503, detail="Air Quality Service temporarily unavailable")
    
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
    
@router.post("/predict-all-stations")
async def predict_all_stations(data: ForecastRequest):
    weather_res = fetch_google_weather_history(data.lat, data.lon, GOOGLE_API_KEY)
    aqi_res = fetch_google_aqi_history(data.lat, data.lon, GOOGLE_API_KEY)
    try:
        # ✅ Check for errors before touching ["history"]
        if "error" in weather_res:
            return {"status": "error", "message": f"Weather API failed: {weather_res['error']}"}
        if "error" in aqi_res:
            return {"status": "error", "message": f"AQI API failed: {aqi_res['error']}"}

        # Step 2: Sync & Clean — now safe to access ["history"]
        combined_history = []
        limit = min(len(weather_res["history"]), len(aqi_res["history"]))
        
        for i in range(limit):
            w = weather_res["history"][i]
            a = aqi_res["history"][i]
            combined_history.append({
                "pm2_5": a.get("pm25", 0), "pm10": a.get("pm10", 0),
                "no2": a.get("no2", 0), "co": a.get("co", 0),
                "so2": a.get("so2", 0), "o3": a.get("o3", 0),
                "temp_c": w.get("temp_c", 0), "wind": w.get("wind", 0),
                "humidity": w.get("humidity", 0)
            })

        if len(combined_history) < 24:
            return {"status": "error", "message": "Google provided less than 24h data"}

        # 1. Google ke last history point ka time lo (UTC format mein hota hai)
        last_history_time_str = aqi_res["history"][-1]["time"] 
        # 2. Parse UTC and convert to IST (+5:30)
        utc_anchor = datetime.fromisoformat(last_history_time_str.replace("Z", "+00:00"))
        ist_anchor = utc_anchor + timedelta(hours=5, minutes=30)

        # Step 3: Inference for all stations
        raw_forecasts = get_multi_station_forecast(combined_history)

        # Step 4: Time Labels generate karo (Forecast starts from the NEXT hour)
        time_labels = []
        for h in range(1, len(raw_forecasts["station_0"]) + 1):
            future_time = ist_anchor + timedelta(hours=h)
            time_labels.append(future_time.strftime("%I:%M %p")) # Format: 02:00 PM

        # Step 5: Merge Predictions with Time Labels
        final_forecast_data = {}
        for station_id, aqi_values in raw_forecasts.items():
            station_list = []
            for i in range(len(aqi_values)):
                val = round(aqi_values[i], 2)
                # Har point ke liye health info attach karo
                station_list.append({
                    "time": time_labels[i],
                    "aqi": val,
                    "health_info": get_aqi_info(val) # <--- Frontend will use this
                })
            final_forecast_data[station_id] = station_list

        # Step 6: Frontend Response
        return {
            "status": "success",
            "lat": data.lat,
            "lon": data.lon,
            "forecast_data": final_forecast_data,
            "meta": {
                "unit": "AQI",
                "history_ended_at": ist_anchor.strftime("%Y-%m-%d %H:%M:%S"),
                "forecast_start": time_labels[0],
                "forecast_window": f"{len(time_labels)} hours"
            }
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return {"status": "error", "message": f"Pipeline Failure: {str(e)}"}