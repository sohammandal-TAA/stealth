import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Topbar from '../components/dashboard/Topbar';
import NavigationMap from '../components/dashboard/NavigationMap';
import AlternativeRoutes from '../components/dashboard/AlternativeRoutes';
import AirQualityCard from '../components/dashboard/AirQualityCard';
import ForecastChart from '../components/dashboard/ForecastChart';
import SensorReadings from '../components/dashboard/SensorReadings';
import EcoProCard from '../components/dashboard/EcoProCard';
import type { ForecastBar, RouteOption, SensorData } from '../components/dashboard/dashboardData';
import '../styles/dashboard.css';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [routeInfo, setRouteInfo] = useState<{ distance: string; duration: string } | null>(null);
  const [userName, setUserName] = useState<string>('Guest');
  const [selectedRoute, setSelectedRoute] = useState<number | null>(null);
  const [originCoords, setOriginCoords] = useState<google.maps.LatLngLiteral | null>(null);
  const [destinationCoords, setDestinationCoords] = useState<google.maps.LatLngLiteral | null>(null);
  const [routes, setRoutes] = useState<RouteOption[]>([]);
  const [airQuality, setAirQuality] = useState<{
    aqiIndex?: number | null;
    kgSaved?: number | null;
    goalPercent?: number | null;
  } | null>(null);
  const [sensors, setSensors] = useState<SensorData | null>(null);
  const [forecast, setForecast] = useState<ForecastBar[] | null>(null);

  useEffect(() => {
    const storedName = window.localStorage.getItem('userName');
    if (storedName?.trim()) {
      setUserName(storedName);
    }
  }, []);

  // --- REAL-TIME BACKEND SYNC ---
  // This triggers every time the origin (user moving) OR destination (user searching) changes
  const fetchEcoData = useCallback(async (origin: google.maps.LatLngLiteral, dest: google.maps.LatLngLiteral) => {
    try {
      const response = await fetch('http://localhost:8080/api/routes/process', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sLat: origin.lat,
          sLon: origin.lng,
          dLat: dest.lat,
          dLon: dest.lng,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Backend error: ${response.status} - ${JSON.stringify(errorData)}`);
      }
      const data = await response.json();

      // Flexible Data Hydration
      // 1) Routes: backend may return `routes` array OR `route_analysis` object (Route_1, Route_2...)
      let backendRoutes: any[] = [];
      if (data.route_analysis && typeof data.route_analysis === 'object') {
        backendRoutes = Object.keys(data.route_analysis).map((key, idx) => {
          const entry = data.route_analysis[key];
          const details = entry?.details ?? [];
          const path = details
            .map((pt: any) => {
              const loc = pt.location;
              if (!loc) return null;
              // backend commonly returns [lat, lon] but be defensive and normalize
              let a = Number(loc[0]);
              let b = Number(loc[1]);
              if (Number.isNaN(a) || Number.isNaN(b)) return null;
              // detect if values look like swapped (lon, lat) by range test
              const looksLikeLatA = Math.abs(a) <= 90;
              const looksLikeLatB = Math.abs(b) <= 90;
              // prefer lat in [-90,90], lon in [-180,180]
              let lat = a, lng = b;
              if (!looksLikeLatA && looksLikeLatB) {
                // swap
                lat = b;
                lng = a;
              }
              return { lat: Number(lat), lng: Number(lng) };
            })
            .filter(Boolean);

          const avgAqi = entry?.avg_exposure_aqi ?? entry?.avg_aqi ?? null;
          const pollutionLevel = avgAqi == null ? 'medium' : (avgAqi <= 100 ? 'low' : avgAqi <= 150 ? 'medium' : 'high');

          return {
            id: key,
            name: key,
            // prefer backend-provided duration/distance when available
            duration: entry?.duration ?? entry?.duration_minutes ?? entry?.duration_min ?? undefined,
            distance: entry?.distance_human ?? entry?.distance ?? undefined,
            pollutionLevel,
            label: key,
            path,
            avgExposureAqi: avgAqi,
          };
        });
      } else {
        backendRoutes = data.routes || data.routeOptions || [];
      }

      setRoutes(backendRoutes);

      // 2) Air quality: prefer ground_truth if available
      const gtStart = data?.ground_truth?.start_point;
      const gtEnd = data?.ground_truth?.end_point;
      if (gtStart || gtEnd) {
        const aqiStart = gtStart?.aqi ?? null;
        const aqiEnd = gtEnd?.aqi ?? null;
        const avg = aqiStart != null && aqiEnd != null ? Math.round((aqiStart + aqiEnd) / 2) : (aqiStart ?? aqiEnd ?? null);
        setAirQuality({
          aqiIndex: avg,
          kgSaved: null,
          goalPercent: null,
        });
      } else {
        const aq = data.airQuality ?? data.air_quality;
        if (aq) {
          setAirQuality({
            aqiIndex: aq.aqiIndex ?? aq.aqi_index ?? aq.currentAqi ?? null,
            kgSaved: aq.kgSaved ?? aq.kg_saved ?? null,
            goalPercent: aq.goalPercent ?? aq.goal_percent ?? null,
          });
        }
      }

      // 3) Sensors / pollutant mapping: prefer ground_truth start_point for pm25/pm10
      // Also try to extract common weather fields from route_analysis details if available
      const extractFromDetail = () => {
        // pick first available detail point from any route_analysis entry
        if (data.route_analysis && typeof data.route_analysis === 'object') {
          for (const k of Object.keys(data.route_analysis)) {
            const first = data.route_analysis[k]?.details?.[0];
            if (first) return first;
          }
        }
        return null;
      };

      const detailSample = extractFromDetail();

      const pickHumidity = (obj: any) => obj?.humidity ?? obj?.hum ?? obj?.rh ?? obj?.relative_humidity ?? obj?.relativeHumidity ?? obj?.humid ?? null;
      const pickTemp = (obj: any) => obj?.temperature ?? obj?.temp ?? obj?.temp_c ?? obj?.air_temp ?? obj?.temperature_c ?? obj?.t ?? null;
      const pickWind = (obj: any) => obj?.windSpeed ?? obj?.wind_speed ?? obj?.wind_kph ?? obj?.wind_mps ?? obj?.wind ?? obj?.wind_m_s ?? null;

      if (gtStart) {
        setSensors({
          humidity: pickHumidity(gtStart) ?? (detailSample ? pickHumidity(detailSample) : null),
          temperature: pickTemp(gtStart) ?? (detailSample ? pickTemp(detailSample) : null),
          windSpeed: pickWind(gtStart) ?? (detailSample ? pickWind(detailSample) : null),
          pm25: gtStart.pm25 ?? gtStart.pm_2_5 ?? null,
          pm10: gtStart.pm10 ?? gtStart.pm_10 ?? null,
        });
      } else {
        const snsr = data.sensors ?? data.sensorData ?? data.sensor_data;
        if (snsr) {
          setSensors({
            humidity: pickHumidity(snsr) ?? (detailSample ? pickHumidity(detailSample) : null),
            temperature: pickTemp(snsr) ?? (detailSample ? pickTemp(detailSample) : null),
            windSpeed: pickWind(snsr) ?? (detailSample ? pickWind(detailSample) : null),
            pm25: snsr.pm25 ?? snsr.pm_2_5 ?? snsr.pm2_5 ?? snsr.pm_2dot5 ?? null,
            pm10: snsr.pm10 ?? snsr.pm_10 ?? snsr.pm10_ug ?? null,
          });
        } else if (detailSample) {
          setSensors({
            humidity: pickHumidity(detailSample) ?? null,
            temperature: pickTemp(detailSample) ?? null,
            windSpeed: pickWind(detailSample) ?? null,
            pm25: detailSample.pm25 ?? detailSample.pm_2_5 ?? null,
            pm10: detailSample.pm10 ?? detailSample.pm_10 ?? null,
          });
        }
      }

      // Forecast: prefer explicit forecast arrays
      setForecast(data.forecast || data.forecastBars || []);

      // 🔥 Fetch AI predictions after route processing
      try {
        const predictionResponse = await fetch('http://localhost:8080/api/routes/predict', {
          method: 'GET',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        });

        if (predictionResponse.ok) {
          const predictionData = await predictionResponse.json();
          if (predictionData.forecast_data?.station_0) {
            const forecastArray = predictionData.forecast_data.station_0.map((item: { time: string; aqi: number; health_info?: { category: string; color: string } }) => ({
              time: item.time,
              value: item.aqi,
              level: item.health_info?.category?.toLowerCase() === 'low' ? 'low' :
                item.health_info?.category?.toLowerCase() === 'high' ? 'high' :
                  'medium',
            }));
            setForecast(forecastArray);
          }
        }
      } catch (predictionError) {
        console.warn('AI prediction fetch failed, using default forecast:', predictionError);
      }
    } catch (error) {
      console.error('Error fetching EcoRoute data:', error);
    }
  }, []);

  // Effect to watch for coordinate changes and trigger the backend
  useEffect(() => {
    if (!originCoords || !destinationCoords) return;

    const timeout = setTimeout(() => {
      fetchEcoData(originCoords, destinationCoords);
    }, 800); // throttle backend calls

    return () => clearTimeout(timeout);
  }, [originCoords, destinationCoords]);

  // 🔥 Handle logo click to redirect to landing page
  const handleLogoClick = useCallback(() => {
    navigate('/');
  }, [navigate]);

  const handleSearchDestination = useCallback(async (
    placeIdOrQuery: string,
    description?: string
  ) => {
    if (!window.google?.maps) return;

    // 🔥 Clear old data when new search begins
    setRoutes([]);
    setAirQuality(null);
    setSensors(null);
    setForecast(null);
    setRouteInfo(null);

    // 🔥 If it looks like a place_id, use PlacesService
    if (placeIdOrQuery.startsWith("ChIJ") && window.google.maps.places) {
      const service = new window.google.maps.places.PlacesService(
        document.createElement("div")
      );

      service.getDetails(
        { placeId: placeIdOrQuery },
        (place, status) => {
          if (
            status === window.google.maps.places.PlacesServiceStatus.OK &&
            place?.geometry?.location
          ) {
            const loc = place.geometry.location;

            setDestinationCoords({
              lat: loc.lat(),
              lng: loc.lng(),
            });
          } else {
            console.error("Place details failed:", status);
          }
        }
      );

      return;
    }

    // 🔥 Otherwise fallback to normal address search
    const geocoder = new window.google.maps.Geocoder();

    geocoder.geocode({ address: placeIdOrQuery }, (results, status) => {
      if (status === "OK" && results?.[0]?.geometry?.location) {
        const loc = results[0].geometry.location;

        setDestinationCoords({
          lat: loc.lat(),
          lng: loc.lng(),
        });
      } else {
        console.error("Failed to geocode destination", status);
      }
    });
  }, []);


  return (
    <div className={`dashboard ${isDarkMode ? 'dark' : 'light'}`}>
      <Topbar
        isDarkMode={isDarkMode}
        onToggleTheme={() => setIsDarkMode((prev) => !prev)}
        userName={userName}
        onSearchDestination={handleSearchDestination}
        onLogoClick={handleLogoClick}
      />

      <NavigationMap
        isDarkMode={isDarkMode}
        onRouteCalculated={setRouteInfo}
        destinationOverride={destinationCoords}
        onOriginChange={setOriginCoords} // Map updates Dashboard's originCoords in real-time
        backendRoutes={routes}
        selectedRouteIndex={selectedRoute}
        onRouteSelect={setSelectedRoute}
      />

      <main className="dashboard-content">
        <div className="dashboard-columns">
          <AlternativeRoutes
            isDarkMode={isDarkMode}
            routeInfo={routeInfo}
            routes={routes}
            selectedRouteIndex={selectedRoute}
            onRouteSelect={setSelectedRoute}
          />
          <div className="dashboard-right-col">
            <AirQualityCard isDarkMode={isDarkMode} data={airQuality} />
            <ForecastChart isDarkMode={isDarkMode} data={forecast} />
          </div>
        </div>

        <SensorReadings isDarkMode={isDarkMode} data={sensors} />
        <EcoProCard isDarkMode={isDarkMode} />
      </main>
    </div>
  );
};

export default Dashboard;