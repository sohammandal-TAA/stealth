import asyncio
import logging
import os
from fastapi import APIRouter, HTTPException
from python_research.schemas.schema import JavaRouteRequest, ForecastRequest, ForecastResponse, RouteRequest
from python_research.services.aqi_engine import fetch_google_aqi_profile, get_aqi_info, get_multi_station_forecast, haversine, interpolate_pollutants, fetch_google_weather_history, fetch_google_aqi_history, weighted_average
import numpy as np
from datetime import datetime, timedelta
import httpx
http_client = httpx.AsyncClient(timeout=5)

router = APIRouter()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Fixed Station Coordinates
STATIONS = {
    "station_0": {"lat": 23.51905342888936, "lon": 87.34565136450719},
    "station_1": {"lat": 23.564018931392827, "lon": 87.31123928017463},
    "station_2": {"lat": 23.5391718044899, "lon": 87.30401858752859},
    "station_3": {"lat": 23.554806202241476, "lon": 87.24681601086061},
}

def find_nearest_station(lat, lon):
    min_dist = float("inf")
    nearest_station = None

    for station_id, coords in STATIONS.items():
        d = haversine(lat, lon, coords["lat"], coords["lon"])
        if d < min_dist:
            min_dist = d
            nearest_station = station_id

    return nearest_station
    
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

        pm25_vals = [p['pm25'] for p in path_details if isinstance(p.get('pm25'), (int, float))]
        pm10_vals = [p['pm10'] for p in path_details if isinstance(p.get('pm10'), (int, float))]
        co_vals   = [p['co']   for p in path_details if isinstance(p.get('co'), (int, float))]

        avg_pm25 = round(sum(pm25_vals) / len(pm25_vals), 2) if pm25_vals else 0
        avg_pm10 = round(sum(pm10_vals) / len(pm10_vals), 2) if pm10_vals else 0
        avg_co   = round(sum(co_vals)   / len(co_vals), 2) if co_vals else 0

        
        # aqis = [p['aqi'] for p in path_details if isinstance(p['aqi'], (int, float))]
        # # avg_exposure = sum(aqis)/len(aqis) if aqis else 0
       
        comparisons[f"Route_{i+1}"] = {
            # "avg_exposure_aqi": round(avg_exposure, 2),
            "distance": route.distance,
            "duration": route.duration,
            "avg_pm25": avg_pm25,
            "avg_pm10": avg_pm10,
            "avg_co": avg_co,
            "details": path_details
        }
    return {"status": "success", 
            "ground_truth": {"start_point": start_p, "end_point": end_p},
            "route_analysis": comparisons}


@router.post("/history_data_all")
async def history_data_all():
    try:
        async def process_station(station_id, coords):
            
            try:
                # Fetch weather + AQI in parallel
                weather_task = fetch_google_weather_history(
                    coords["lat"], coords["lon"], http_client
                )

                aqi_task = fetch_google_aqi_history(
                    coords["lat"], coords["lon"], http_client
                )

                weather_res, aqi_res = await asyncio.gather(
                    weather_task, aqi_task
                )

                # Basic API failure check
                if "error" in weather_res or "error" in aqi_res:
                    print(f"API error for station {station_id}", flush=True)
                    return station_id, {"error": "API failure"}

                combined_history = []

                for w, a in zip(weather_res.get("history", []),
                                aqi_res.get("history", [])):

                    combined_history.append({
                        "time": a.get("time"),
                        "pm2_5": a.get("pm25", 0),
                        "pm10": a.get("pm10", 0),
                        "no2": a.get("no2", 0),
                        "co": a.get("co", 0),
                        "so2": a.get("so2", 0),
                        "o3": a.get("o3", 0),
                        "temp_c": w.get("temp_c", 0),
                        "wind": w.get("wind", 0),
                        "humidity": w.get("humidity", 0)
                    })

                return station_id, {
                    "location": coords,
                    "history_count": len(combined_history),
                    "data": combined_history
                }

            except Exception as e:
                print(f"Station processing failed: {station_id} | {str(e)}", flush=True)
                return station_id, {"error": str(e)}

        tasks = [
            process_station(station_id, coords)
            for station_id, coords in STATIONS.items()
        ]

        results = await asyncio.gather(*tasks)

        return {
            "status": "success",
            "data": dict(results)
        }

    except Exception as e:
        print(f"history_data_all failed: {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/predict-all-stations")
async def predict_all_stations(data: RouteRequest):
    print(f"DEBUG: Starting multi-station forecast", flush=True)
    try:
        # ---- Step 1: Fetch weather + AQI in parallel for ALL stations ----

        async def fetch_station_data(station_id, coords):
            weather_task = fetch_google_weather_history(coords["lat"], coords["lon"], http_client)
            aqi_task = fetch_google_aqi_history(coords["lat"], coords["lon"], http_client)

            weather_res, aqi_res = await asyncio.gather(weather_task, aqi_task)

            return station_id, weather_res, aqi_res

        fetch_tasks = [
            fetch_station_data(station_id, coords)
            for station_id, coords in STATIONS.items()
        ]

        station_results = await asyncio.gather(*fetch_tasks)

        # ---- Step 2: Use FIRST station history as base (same like old code) ----

        base_station_id, weather_res, aqi_res = station_results[0]

        if "error" in weather_res or "error" in aqi_res:
            return {"status": "error", "message": "API failure"}

        combined_history = []

        for w, a in zip(weather_res.get("history", []),
                        aqi_res.get("history", [])):

            combined_history.append({
                "pm2_5": a.get("pm25", 0),
                "pm10": a.get("pm10", 0),
                "no2": a.get("no2", 0),
                "co": a.get("co", 0),
                "so2": a.get("so2", 0),
                "o3": a.get("o3", 0),
                "temp_c": w.get("temp_c", 0),
                "wind": w.get("wind", 0),
                "humidity": w.get("humidity", 0)
            })

        if len(combined_history) < 24:
            return {"status": "error", "message": "Less than 24h data"}

        # ---- Step 3: Time anchor (OLD LOGIC SAME) ----

        last_history_time_str = aqi_res["history"][-1]["time"]
        utc_anchor = datetime.fromisoformat(
            last_history_time_str.replace("Z", "+00:00")
        )
        ist_anchor = utc_anchor + timedelta(hours=5, minutes=30)

        # ---- Step 4: Single model inference (FAST) ----

        raw_forecasts = get_multi_station_forecast(combined_history)

        # ---- Step 5: Generate time labels ----

        time_labels = []
        for h in range(1, len(raw_forecasts["station_0"]) + 1):
            future_time = ist_anchor + timedelta(hours=h)
            time_labels.append(future_time.strftime("%I:%M %p"))

        # ---- Step 6: SAME OLD OUTPUT STRUCTURE ----
        final_forecast_data = {}

        for station_id, aqi_values in raw_forecasts.items():
            station_list = []

            for i in range(len(aqi_values)):
                val = round(aqi_values[i], 2)

                station_list.append({
                    "time": time_labels[i],
                    "aqi": val,
                    "health_info": get_aqi_info(val)
                })

            final_forecast_data[station_id] = station_list


        # ---- Step 7: NEW → Route-based weighted forecast ----

        start_station = find_nearest_station(data.sLat, data.sLon)
        end_station = find_nearest_station(data.dLat, data.dLon)

        route_mid_lat = (data.sLat + data.dLat) / 2
        route_mid_lon = (data.sLon + data.dLon) / 2
        route_forecast = []

        for i in range(len(final_forecast_data[start_station])):

            aqiA = final_forecast_data[start_station][i]["aqi"]
            aqiB = final_forecast_data[end_station][i]["aqi"]

            blended = weighted_average(
                aqiA,
                aqiB,
                route_mid_lat,
                route_mid_lon,
                STATIONS[start_station]["lat"],
                STATIONS[start_station]["lon"],
                STATIONS[end_station]["lat"],
                STATIONS[end_station]["lon"]
            )

            route_forecast.append({
                "time": final_forecast_data[start_station][i]["time"],
                "aqi": round(blended, 2),
                "health_info": get_aqi_info(blended)
            })


        return {
            "status": "success",
            "forecast_data": final_forecast_data,   # OLD structure untouched
            "route_forecast": route_forecast,       # NEW
            "start_station": start_station,
            "end_station": end_station
        }


    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return {"status": "error", "message": f"Pipeline Failure: {str(e)}"}

