import numpy as np
import os
import requests
from pykrige.ok import OrdinaryKriging
from dotenv import load_dotenv, dotenv_values

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir)) 
env_path = os.path.join(root_dir, '.env')

# Method 1: load_dotenv
load_dotenv(dotenv_path=env_path)

# Method 2: Manual Parse (Back-up)
env_vars = dotenv_values(env_path)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or env_vars.get("GOOGLE_API_KEY")

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
            "co": pollutants.get('co', 0),
            "no2": pollutants.get('no2', 0),
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