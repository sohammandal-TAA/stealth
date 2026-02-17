import numpy as np
import time
import matplotlib.pyplot as plt
from python_research.services.aqi_engine import interpolate_pollutants

def evaluate_kriging():
    # --- STATION DATA (UNTOUCHED) ---
    station0 = {"lat": 22.5726, "lon": 88.3639, "aqi": 135, "pm25": 80, "pm10": 120, "co": 0.8, "no2": 40, "o3": 30}
    station1 = {"lat": 22.5720, "lon": 88.3645, "aqi": 100, "pm25": 50, "pm10": 80, "co": 0.5, "no2": 20, "o3": 20}
    station2 = {"lat": 22.5710, "lon": 88.3640, "aqi": 110, "pm25": 65, "pm10": 100, "co": 0.7, "no2": 35, "o3": 25}
    station3 = {"lat": 22.5715, "lon": 88.3650, "aqi": 90, "pm25": 40, "pm10": 70, "co": 0.4, "no2": 15, "o3": 15}
    station4 = {"lat": 22.5715, "lon": 88.3640, "aqi": 185, "pm25": 35, "pm10": 90, "co": 0.6, "no2": 22, "o3": 25} 
    station5 = {"lat": 22.5715, "lon": 88.3640, "aqi": 125, "pm25": 70, "pm10": 110, "co": 0.75, "no2": 32, "o3": 28}

    ground_truth = {"lat": 22.5715, "lon": 88.3640, "aqi": 120, "pm25": 60, "pm10": 90, "co": 0.6, "no2": 30, "o3": 25}
    test_point = [[ground_truth['lat'], ground_truth['lon']]]

    # 1. MEASURE EXECUTION TIME
    start_time = time.time()
    prediction_results = interpolate_pollutants(station0, station1, test_point)
    execution_time = (time.time() - start_time) * 1000 

    # 2. KRIGING PREDICTION
    predicted_aqi = prediction_results[0]['aqi']
    actual_aqi = ground_truth['aqi']

    # 3. BASELINE CALCULATION
    baseline_aqi = (station0['aqi'] + station1['aqi'] + station2['aqi'] + station3['aqi'] + station4['aqi'] + station5['aqi']) / 6

    # 4. ERROR METRICS
    kriging_error = abs(predicted_aqi - actual_aqi)
    baseline_error = abs(baseline_aqi - actual_aqi)
    improvement = ((baseline_error - kriging_error) / baseline_error) * 100

    # --- 5. VISUALIZATION (THE ADDITION) ---
    generate_validation_plot(actual_aqi, predicted_aqi, baseline_aqi, improvement)

    # 6. PRINT THE PROOF (UNTOUCHED)
    print("="*50)
    print("      AQI INTERPOLATION SCIENTIFIC PROOF      ")
    print("="*50)
    print(f"Target Location  : {test_point[0]}")
    print(f"Execution Speed  : {round(execution_time, 2)} ms")
    print("-"*50)
    print(f"METHOD             | AQI VALUE | ERROR (Abs)")
    print(f"Actual (Sensor)    | {actual_aqi}       | 0.00")
    print(f"Simple Average     | {baseline_aqi}     | {round(baseline_error, 2)}")
    print(f"Ordinary Kriging   | {round(predicted_aqi, 2)}    | {round(kriging_error, 2)}")
    print("-"*50)
    print(f"AI Model Accuracy  : {round(100 - (kriging_error/actual_aqi*100), 2)}%")
    print(f"Precision Boost    : +{round(improvement, 2)}% over basic math")
    print("="*50)

def generate_validation_plot(actual, predicted, baseline, boost):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    
    methods = ['Actual Sensor', 'Ordinary Kriging', 'Simple Average']
    values = [actual, predicted, baseline]
    colors = ['#10b981', '#3b82f6', '#ef4444'] # Emerald, Blue, Red

    # Bar plot
    bars = ax.bar(methods, values, color=colors, alpha=0.8, width=0.5)
    
    # Annotate values
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{height:.2f}', ha='center', va='bottom', color='white', fontweight='bold')

    # Add Error Lines (Visualizing the Gap)
    ax.set_ylabel('AQI Value')
    ax.set_title('Spatial Interpolation Validation', fontsize=14, color='#10b981', pad=20)
    
    # Text box for Precision Boost
    props = dict(boxstyle='round', facecolor='white', alpha=0.1)
    ax.text(0.02, 0.95, f'Precision Boost: +{boost:.2f}%', transform=ax.transAxes, 
            fontsize=12, verticalalignment='top', bbox=props, color='#3b82f6')

    plt.tight_layout()
    # plt.savefig('kriging_validation.png', dpi=300)
    # print("\n✅ Plot saved as 'kriging_validation.png'")
    plt.show()

if __name__ == "__main__":
    evaluate_kriging()