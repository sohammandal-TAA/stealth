import React, { useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fixing default icon issue in Leaflet
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
let DefaultIcon = L.icon({ iconUrl: icon, shadowUrl: iconShadow, iconSize: [25, 41], iconAnchor: [12, 41] });
L.Marker.prototype.options.icon = DefaultIcon;

const stations = [
  { id: 0, name: "Industrial Zone (Station 0)", pos: [23.5300, 87.3000], aqi: 145 },
  { id: 1, name: "City Center (Station 1)", pos: [23.5500, 87.3200], aqi: 112 },
  { id: 2, name: "Residential Hub (Station 2)", pos: [23.5200, 87.2800], aqi: 85 },
  { id: 3, name: "Green Park (Station 3)", pos: [23.5100, 87.3100], aqi: 65 },
];

const ExplorePage: React.FC = () => {
  const [selectedPoint, setSelectedPoint] = useState<{lat: number, lng: number, aqi: number} | null>(null);

  // Click Handler Component
  const MapEvents = () => {
    useMapEvents({
      click(e) {
        const { lat, lng } = e.latlng;
        // MOCK LOGIC: Jab tak API ready nahi hai, hum random AQI dikhayenge
        const mockAqi = Math.floor(Math.random() * (150 - 50 + 1)) + 50;
        setSelectedPoint({ lat, lng, aqi: mockAqi });
      },
    });
    return null;
  };

  return (
    <div className="h-screen w-full bg-page-bg text-white flex flex-col">
      {/* Header for Map Page */}
      <header className="p-4 border-b border-soft flex justify-between items-center bg-card-bg">
        <h1 className="text-xl font-bold text-accent-green-soft">EcoRoute Live Explore</h1>
        <button onClick={() => window.history.back()} className="text-xs secondary-cta">Go Back</button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <div className="w-80 bg-card-bg p-6 overflow-y-auto border-r border-soft">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-text mb-4">Active Stations</h2>
          <div className="space-y-4">
            {stations.map(s => (
              <div key={s.id} className="p-3 rounded-2xl border border-soft bg-white/5">
                <p className="text-xs font-bold text-white">{s.name}</p>
                <p className="text-lg text-accent-green">AQI: {s.aqi}</p>
              </div>
            ))}
          </div>

          {selectedPoint && (
            <div className="mt-10 p-4 rounded-3xl bg-accent-green/10 border border-accent-green/30">
              <h3 className="text-xs font-bold text-accent-green-soft uppercase italic">Point Analysis</h3>
              <p className="mt-2 text-2xl font-bold">AQI: {selectedPoint.aqi}</p>
              <p className="text-[10px] text-muted-text">Location: {selectedPoint.lat.toFixed(4)}, {selectedPoint.lng.toFixed(4)}</p>
              <p className="mt-2 text-xs text-white/70">"This value is calculated via Kriging Spatial Interpolation."</p>
            </div>
          )}
        </div>

        {/* The Map */}
        <div className="flex-1 relative">
          <MapContainer center={[23.53, 87.30]} zoom={13} style={{ height: '100%', width: '100%' }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <MapEvents />
            
            {stations.map(s => (
              <Marker key={s.id} position={s.pos as [number, number]}>
                <Popup>{s.name} - AQI: {s.aqi}</Popup>
              </Marker>
            ))}

            {selectedPoint && (
              <Marker position={[selectedPoint.lat, selectedPoint.lng]}>
                <Popup>Predicted AQI: {selectedPoint.aqi}</Popup>
              </Marker>
            )}
          </MapContainer>
        </div>
      </div>
    </div>
  );
};

export default ExplorePage;