import logging
import numpy as np
import os
import requests
from pykrige.ok import OrdinaryKriging
import tensorflow as tf
import joblib
import httpx
import asyncio
import math

http_client = httpx.AsyncClient(timeout=5)
from dotenv import load_dotenv, dotenv_values

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir)) 
parent_dir = os.path.dirname(current_dir)
env_path = os.path.join(root_dir, '.env')


# Models folder ka path
# Final paths pointing to the correct internal models folder
model_path_str = os.path.join(parent_dir, "models", "durgapur_aqi_v1.h5")
scaler_path_str = os.path.join(parent_dir, "models", "scaler_x.pkl")

# --- 2. LOAD OBJECTS ---
try:
    if not os.path.exists(model_path_str):
        raise FileNotFoundError(f"Missing Model at: {model_path_str}")
        
    lstm_model = tf.keras.models.load_model(model_path_str)
    loaded_scaler = joblib.load(scaler_path_str)
    print(f" SUCCESS: Loaded from {model_path_str}")
except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    lstm_model = None
    loaded_scaler = None


# Method 1: load_dotenv
load_dotenv(dotenv_path=env_path,override=True)

# # Method 2: Manual Parse (Back-up)
# env_vars = dotenv_values(env_path)
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or env_vars.get("GOOGLE_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
# logging.info(f"GOOGLE_API_KEY Loaded: {'Yes' if GOOGLE_API_KEY else 'No'}")
# print("DEBUG API KEY:", GOOGLE_API_KEY)


# if GOOGLE_API_KEY:
#     print(f"✅ SUCCESS: Key found! (Starts with: {GOOGLE_API_KEY[:4]})", flush=True)
# else:
#     print(f"❌ STILL NONE: Path is {env_path}, but no key found inside.", flush=True)

def fetch_google_aqi_profile(lat, lon, api_key=None):
    # Use the passed key, or fallback to the one loaded above
    key = api_key or GOOGLE_API_KEY
    
    url = f"https://airquality.googleapis.com/v1/currentConditions:lookup?key={key}"
    payload = {
        "location": {"latitude": lat, "longitude": lon},
        "universalAqi": False,
        "extraComputations": ["POLLUTANT_CONCENTRATION", "LOCAL_AQI"],
        "languageCode": "en"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        pollutants = {p['code']: p['concentration']['value'] for p in data.get('pollutants', [])}
        
        return {
            "lat": lat, "lon": lon,
            "aqi": data.get('indexes', [{}])[0].get('aqi', 0),
            "pm25": pollutants.get('pm25', 0),
            "pm10": pollutants.get('pm10', 0),
            "no2": pollutants.get('no2', 0),
            "co": pollutants.get('co', 0),
            "so2": pollutants.get('so2', 0),
            "o3": pollutants.get('o3', 0)
        }
    except Exception as e:
        print(f"⚠️ API Fetch Failed for ({lat}, {lon}): {e}", flush=True)
        # CRITICAL: Return a dict, NOT the error object, so interpolate_pollutants doesn't crash
        return {"lat": lat, "lon": lon, "error": str(e)}

# --- 2. KRIGING CALCULATION ENGINE ---
def interpolate_pollutants(start_data, end_data, route_points):
    # Now start_data['lat'] will always work because it's a dict!
    mid_lat, mid_lon = (start_data['lat'] + end_data['lat'])/2, (start_data['lon'] + end_data['lon'])/2
    
    dist = np.sqrt((start_data['lat'] - end_data['lat'])**2 + (start_data['lon'] - end_data['lon'])**2)
    offset = dist * 0.1 if dist > 0 else 0.005
    
    lats = np.array([start_data['lat'], end_data['lat'], mid_lat + offset, mid_lat - offset])
    lons = np.array([start_data['lon'], end_data['lon'], mid_lon, mid_lon])

    target_pollutants = ['aqi', 'pm25', 'pm10', 'co', 'no2', 'o3']
    route_profiles = [{"location": p} for p in route_points]

    for p_type in target_pollutants:
        v_start, v_end = float(start_data[p_type]), float(end_data[p_type])
        z_values = np.array([v_start, v_end, (v_start+v_end)/2, (v_start+v_end)/2], dtype=float)
        
        try:
            OK = OrdinaryKriging(lons, lats, z_values, variogram_model='gaussian', 
                                 variogram_parameters=[1.0, 0.1, 0.1], verbose=False)
            for i, (p_lat, p_lon) in enumerate(route_points):
                z_pred, _ = OK.execute('points', np.array([p_lon]), np.array([p_lat]))
                route_profiles[i][p_type] = round(float(z_pred[0]), 2)
        except Exception as e:
            print(f"Kriging failed for {p_type}: {e}", flush=True)
            for i in range(len(route_profiles)): route_profiles[i][p_type] = v_start
            
    return route_profiles

async def fetch_google_weather_history(lat, lon, http_client, api_key=None):
    # Use the passed key, or fallback to your global variable
    key = api_key or GOOGLE_API_KEY
    
    # Endpoint for 24-hour historical weather
    url = "https://weather.googleapis.com/v1/history/hours:lookup"
    
    # These must be sent as URL parameters for a GET request
    params = {
        "key": key,
        "location.latitude": lat,
        "location.longitude": lon,
        "hours": 24, 
        "unitsSystem": "METRIC",
        "languageCode": "en"
    }
    
    try:
        
        response = await http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        history_list = []
        # The API returns an array of 'historyHours'
        for hour in data.get('historyHours', []):
            history_list.append({
                "time": hour.get('interval', {}).get('startTime'),
                "temp_c": hour.get('temperature', {}).get('degrees', 0),
                "wind": hour.get('wind', {}).get('speed', {}).get('value', 0),
                "humidity": hour.get('relativeHumidity', 0)
            })
            
        return {
            "lat": lat,
            "lon": lon,
            "history": history_list
        }
    except Exception as e:
        print(f"⚠️ Weather History Fetch Failed for ({lat}, {lon}): {e}", flush=True)
        return {"lat": lat, "lon": lon, "error": str(e)}


async def fetch_google_aqi_history(lat, lon, http_client, api_key=None):
    key = api_key or GOOGLE_API_KEY
    
    # Endpoint for historical lookups
    url = f"https://airquality.googleapis.com/v1/history:lookup?key={key}"
    
    payload = {
        "location": {"latitude": lat, "longitude": lon},
        "hours": 24,  
        "pageSize": 24,
        "universalAqi": False, 
        "extraComputations": ["POLLUTANT_CONCENTRATION", "LOCAL_AQI"],
        "languageCode": "en"
    }
    
    try:
        response = await http_client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        history_list = []
        # The API returns a list of 'hoursInfo' objects
        for hour_info in data.get('hoursInfo', []):
            # SAFELY fetch concentrations using .get() to avoid KeyError
            pollutants = {
                p['code']: p.get('concentration', {}).get('value', 0) 
                for p in hour_info.get('pollutants', [])
            }
            
            history_list.append({
                "time": hour_info.get('dateTime'),
                "aqi": hour_info.get('indexes', [{}])[0].get('aqi', 0),
                "pm25": pollutants.get('pm25', 0),
                "pm10": pollutants.get('pm10', 0),
                "no2": pollutants.get('no2', 0),
                "co": pollutants.get('co', 0),
                "so2": pollutants.get('so2', 0),
                "o3": pollutants.get('o3', 0)
            })
            
        return {
            "lat": lat,
            "lon": lon,
            "history": history_list
        }
    except Exception as e:
        print(f"⚠️ AQI History Fetch Failed for ({lat}, {lon}): {e}", flush=True)
        return {"lat": lat, "lon": lon, "error": str(e)}
    
def get_multi_station_forecast(combined_history_list):
    """
    Input: 24 combined history dicts
    Output: Predictions for 4 stations (single forward pass)
    """

    # 1️⃣ Feature Alignment (Vectorized)
    feature_matrix = np.array([
        [
            h.get("pm2_5", 0), h.get("pm10", 0), h.get("no2", 0),
            h.get("co", 0), h.get("so2", 0), h.get("o3", 0),
            h.get("temp_c", 0), h.get("wind", 0), h.get("humidity", 0),
            0, 0, 0, 0, 0, 0, 0
        ]
        for h in combined_history_list
    ], dtype=float)

    # 2️⃣ Scale once
    scaled_matrix = loaded_scaler.transform(feature_matrix)

    # 3️⃣ Reshape for LSTM
    lstm_input = scaled_matrix.reshape(1, 24, 16)

    # 4️⃣ Batch station IDs (VERY IMPORTANT)
    station_ids = np.array([[0], [1], [2], [3]])  # shape (4,1)

    # Repeat input 4 times (batch size = 4)
    lstm_batch = np.repeat(lstm_input, 4, axis=0)

    # 5️⃣ Single Forward Pass
    raw_pred = lstm_model.predict([lstm_batch, station_ids], verbose=0)

    # raw_pred shape: (4, forecast_steps)

    all_results = {}

    for i in range(4):
        all_results[f"station_{i}"] = [
            round(float(p), 2) for p in raw_pred[i]
        ]

    return all_results


def get_aqi_info(aqi):
    """
    Standard Indian AQI Color Mapping for Frontend
    """
    if aqi <= 50:
        return {"category": "Good", "color": "#00E400"}       # Green
    elif aqi <= 100:
        return {"category": "Satisfactory", "color": "#FFFF00"} # Yellow
    elif aqi <= 200:
        return {"category": "Moderate", "color": "#FF7E00"}     # Orange
    elif aqi <= 300:
        return {"category": "Poor", "color": "#FF0000"}         # Red
    elif aqi <= 400:
        return {"category": "Very Poor", "color": "#8F3F97"}    # Purple
    else:
        return {"category": "Severe", "color": "#7E0023"}
    

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat/2)**2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(dlon/2)**2
    )

    return 2 * R * math.asin(math.sqrt(a))

def weighted_average(aqiA, aqiB, lat, lon,
                     latA, lonA, latB, lonB):

    dA = haversine(lat, lon, latA, lonA)
    dB = haversine(lat, lon, latB, lonB)

    if dA == 0:
        return aqiA
    if dB == 0:
        return aqiB

    wA = 1 / dA
    wB = 1 / dB

    return (aqiA * wA + aqiB * wB) / (wA + wB)