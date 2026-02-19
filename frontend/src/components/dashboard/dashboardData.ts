export interface RouteOption {
  id: string;
  name: string;
  duration: number;
  distance: string;
  pollutionLevel: 'low' | 'medium' | 'high';
  label: string;
  // optional raw path returned by backend (array of {lat,lng})
  path?: Array<{ lat: number; lng: number }>;
  avgExposureAqi?: number;
}

export interface SensorData {
  humidity: number;
  temperature: number;
  windSpeed: number;
  pm25?: number | null;
  pm10?: number | null;
}

export interface ForecastBar {
  time: string;
  value: number;
  level: 'low' | 'medium' | 'high';
}

export interface DashboardRouteInfo {
  distance: string;
  duration: string;
}

