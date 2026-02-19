import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  GoogleMap,
  useJsApiLoader,
  DirectionsRenderer,
} from '@react-google-maps/api';

interface NavigationMapProps {
  isDarkMode: boolean;
  onRouteCalculated: (info: { distance: string; duration: string }) => void;
  destinationOverride?: google.maps.LatLngLiteral | null;
  onOriginChange?: (origin: google.maps.LatLngLiteral) => void;
  // optional backend-provided alternate routes — flexible shape
  backendRoutes?: any[];
  selectedRouteIndex?: number | null;
  onRouteSelect?: (index: number | null) => void;
}

const mapContainerStyle = {
  width: '100%',
  height: '400px',
};

const NavigationMap: React.FC<NavigationMapProps> = ({
  isDarkMode,
  onRouteCalculated,
  destinationOverride,
  onOriginChange,
  backendRoutes,
  selectedRouteIndex: externalSelectedIndex,
  onRouteSelect,
}) => {
  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY,
    libraries: ["places", "geometry"],
  });

  const mapRef = useRef<google.maps.Map | null>(null);
  const markerRef = useRef<google.maps.Marker | null>(null);
  const destinationMarkerRef = useRef<google.maps.Marker | null>(null);
  const requestIdRef = useRef<number>(0);

  const [currentLocation, setCurrentLocation] =
    useState<google.maps.LatLngLiteral | null>(null);

  const [directions, setDirections] =
    useState<google.maps.DirectionsResult | null>(null);

  const polylinesRef = useRef<google.maps.Polyline[]>([]);
  const polyRequestIdRef = useRef<number>(0);
  const distancesRef = useRef<number[]>([]);
  const [selectedPolyIndex, setSelectedPolyIndex] = useState<number | null>(null);

  // Sync external selection → internal polyline highlight
  useEffect(() => {
    if (externalSelectedIndex !== undefined) {
      setSelectedPolyIndex(externalSelectedIndex ?? null);
    }
  }, [externalSelectedIndex]);

  const [zoom, setZoom] = useState(15);

  // ---------------------------
  // GEOLOCATION
  // ---------------------------
  useEffect(() => {
    if (!navigator.geolocation) return;

    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        const next = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        };

        setCurrentLocation(next);
        onOriginChange?.(next);
      },
      console.error,
      { enableHighAccuracy: true }
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [onOriginChange]);

  // ---------------------------
  // REQUEST ROUTE
  // ---------------------------
  const requestRoute = useCallback(
    (origin: google.maps.LatLngLiteral, destinationOverride: google.maps.LatLngLiteral | null | undefined) => {
      if (!window.google || !destinationOverride) return;

      const currentRequestId = ++requestIdRef.current;
      const service = new window.google.maps.DirectionsService();

      service.route(
        {
          origin,
          destination: destinationOverride,
          travelMode: window.google.maps.TravelMode.DRIVING,
        },
        (result, status) => {
          if (status === "OK" && result && currentRequestId === requestIdRef.current) {
            setDirections(result);

            const leg = result.routes[0].legs[0];
            onRouteCalculated({
              distance: leg.distance?.text || "",
              duration: leg.duration?.text || "",
            });
          }
        }
      );
    },
    [onRouteCalculated]
  );

  useEffect(() => {
    if (!currentLocation || !destinationOverride) return;
    setDirections(null);
    requestRoute(currentLocation, destinationOverride);
  }, [currentLocation, destinationOverride, requestRoute]);

  // ---------------------------
  // USER BLUE DOT MARKER
  // ---------------------------
  useEffect(() => {
    if (!mapRef.current || !currentLocation || !window.google) return;

    if (!markerRef.current) {
      markerRef.current = new window.google.maps.Marker({
        position: currentLocation,
        map: mapRef.current,
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: "#4285F4",
          fillOpacity: 1,
          strokeColor: "#FFFFFF",
          strokeWeight: 3,
        },
        zIndex: 999,
      });
    } else {
      markerRef.current.setPosition(currentLocation);
      // Ensure marker is attached to the current map instance
      markerRef.current.setMap(mapRef.current);
    }

    mapRef.current.panTo(currentLocation);
  }, [currentLocation]);

  // ---------------------------
  // DESTINATION RED MARKER
  // ---------------------------
  useEffect(() => {
    if (!mapRef.current || !destinationOverride || !window.google) return;

    if (!destinationMarkerRef.current) {
      destinationMarkerRef.current = new window.google.maps.Marker({
        position: destinationOverride,
        map: mapRef.current,
      });
    } else {
      destinationMarkerRef.current.setPosition(destinationOverride);
      // Ensure marker is attached to the current map instance
      destinationMarkerRef.current.setMap(mapRef.current);
    }
  }, [destinationOverride]);

  // Render backend alternative routes (if provided) as polylines
  useEffect(() => {
    // clear previous polylines and listeners
    polylinesRef.current.forEach((p) => {
      try {
        if (window.google && window.google.maps && window.google.maps.event) {
          window.google.maps.event.clearInstanceListeners(p);
        }
      } catch (e) { }
      p.setMap(null);
    });
    // keep array sized to backendRoutes length to preserve index mapping
    polylinesRef.current = [];
    distancesRef.current = [];
    // reset selected index when routes change
    setSelectedPolyIndex(null);

    if (!mapRef.current || !window.google || !Array.isArray(backendRoutes)) return;

    const currentPolyRequest = ++polyRequestIdRef.current;

    backendRoutes.forEach((r: any, idx: number) => {
      // try common path field names
      const pathArrRaw: any = r.path || r.cleaned || r.coordinates || r.coords || r.polyline || r.overview_polyline || [];
      let pathArr: any[] = [];

      // handle encoded polyline string
      if (typeof pathArrRaw === 'string' && window.google && window.google.maps && window.google.maps.geometry && window.google.maps.geometry.encoding) {
        try {
          const decoded = window.google.maps.geometry.encoding.decodePath(pathArrRaw);
          pathArr = decoded.map((p: any) => ({ lat: p.lat(), lng: p.lng() }));
        } catch (e) {
          pathArr = [];
        }
      } else if (Array.isArray(pathArrRaw)) {
        pathArr = pathArrRaw;
      } else if (pathArrRaw && pathArrRaw.points && typeof pathArrRaw.points === 'string' && window.google && window.google.maps && window.google.maps.geometry && window.google.maps.geometry.encoding) {
        try {
          const decoded = window.google.maps.geometry.encoding.decodePath(pathArrRaw.points);
          pathArr = decoded.map((p: any) => ({ lat: p.lat(), lng: p.lng() }));
        } catch (e) {
          pathArr = [];
        }
      }
      if (!Array.isArray(pathArr) || pathArr.length === 0) return;

      const coords = pathArr.map((pt: any) => {
        if (pt.lat !== undefined && pt.lng !== undefined) return { lat: Number(pt.lat), lng: Number(pt.lng) };
        if (pt[0] !== undefined && pt[1] !== undefined) return { lat: Number(pt[0]), lng: Number(pt[1]) };
        return null;
      }).filter(Boolean) as google.maps.LatLngLiteral[];

      if (coords.length < 2) return;

      // Use backend coords as waypoints to request a Google Directions path that matches Google's routing
      const service = new window.google.maps.DirectionsService();

      // Build origin, destination, and waypoints. If there are too many intermediate points,
      // sample evenly to keep the number reasonable for the Directions API.
      const origin = coords[0];
      const destination = coords[coords.length - 1];
      let intermediate = coords.slice(1, coords.length - 1);

      // Directions API waypoint limits exist; keep within Google's limits but prefer
      // to send as many ordered intermediate points as possible so the returned
      // Google route follows the backend coordinates closely.
      const MAX_WAYPOINTS = 23; // conservative upper bound for client-side usage
      if (intermediate.length > MAX_WAYPOINTS) {
        // pick evenly-spaced points but always include first/last intermediates
        const sampled: google.maps.LatLngLiteral[] = [];
        const step = intermediate.length / MAX_WAYPOINTS;
        for (let i = 0; i < MAX_WAYPOINTS; i++) {
          const idxSample = Math.min(intermediate.length - 1, Math.floor(i * step));
          sampled.push(intermediate[idxSample]);
        }
        intermediate = sampled;
      }

      // Use stopover=true to instruct DirectionsService to pass through each waypoint
      const waypoints = intermediate.map((p) => ({ location: p as google.maps.LatLngLiteral, stopover: true }));

      service.route(
        {
          origin,
          destination,
          waypoints,
          travelMode: window.google.maps.TravelMode.DRIVING,
          optimizeWaypoints: false,
        },
        (result, status) => {
          // ignore stale requests
          if (currentPolyRequest !== polyRequestIdRef.current) return;
          if (status !== 'OK' || !result) return;

          // clear any previous polyline at this index (we already cleared all at start)
          const routePath = result.routes[0].overview_path || [];
          const latLngs = routePath.map((p: any) => ({ lat: p.lat(), lng: p.lng() }));

          if (latLngs.length === 0) return;

          // ensure polyline starts at origin and ends at destination to avoid visual gaps
          const approxEqual = (a: google.maps.LatLngLiteral, b: google.maps.LatLngLiteral) => {
            const eps = 1e-6;
            return Math.abs(a.lat - b.lat) < eps && Math.abs(a.lng - b.lng) < eps;
          };

          // add origin if missing at start
          if (coords.length > 0) {
            const originCoord = coords[0];
            if (!approxEqual(latLngs[0], originCoord)) {
              latLngs.unshift({ lat: originCoord.lat, lng: originCoord.lng });
            }
            const destCoord = coords[coords.length - 1];
            if (!approxEqual(latLngs[latLngs.length - 1], destCoord)) {
              latLngs.push({ lat: destCoord.lat, lng: destCoord.lng });
            }
          }

          // remove consecutive duplicate points which can confuse rendering
          for (let i = latLngs.length - 1; i > 0; i--) {
            if (approxEqual(latLngs[i], latLngs[i - 1])) {
              latLngs.splice(i, 1);
            }
          }

          // determine total distance for this returned route (sum of legs)
          let totalMeters = 0;
          try {
            totalMeters = result.routes[0].legs.reduce((acc: number, leg: any) => acc + (leg.distance?.value || 0), 0);
          } catch (e) {
            totalMeters = 0;
          }

          distancesRef.current[idx] = totalMeters;

          // determine color: selected (dark blue) vs unselected (light blue)
          const DARK_BLUE = '#1A73E8'; // selected route
          const LIGHT_BLUE = '#8AB4F8'; // alternate routes
          const selected = selectedPolyIndex !== null ? idx === selectedPolyIndex : false;
          // if none selected yet, we'll choose the shortest route once we have at least one distance
          if (selectedPolyIndex === null) {
            // compute shortest among known distances
            const known = distancesRef.current.map((d, i) => (typeof d === 'number' ? { d, i } : null)).filter(Boolean) as { d: number; i: number }[];
            if (known.length > 0) {
              const min = known.reduce((a, b) => (a.d <= b.d ? a : b));
              setSelectedPolyIndex((prev) => (prev === null ? min.i : prev));
            }
          }

          const strokeWeight = selected ? 6 : 4;
          const strokeOpacity = selected ? 0.95 : 0.7;
          const color = selected ? DARK_BLUE : LIGHT_BLUE;

          const poly = new window.google.maps.Polyline({
            path: latLngs,
            strokeColor: color,
            strokeOpacity,
            strokeWeight,
            zIndex: selected ? 100 : 5 + idx,
          });

          poly.setMap(mapRef.current);

          // ensure polylinesRef maps idx -> poly so we can update by index later
          polylinesRef.current[idx] = poly;

          // click toggles selection to this route (mimic Google Maps behavior)
          poly.addListener('click', () => {
            setSelectedPolyIndex(idx);
            onRouteSelect?.(idx);
          });
        }
      );
    });
  }, [backendRoutes]);

  const onLoad = useCallback((map: google.maps.Map) => {
    mapRef.current = map;
    // When map remounts, re-attach existing markers immediately
    if (markerRef.current) markerRef.current.setMap(map);
    if (destinationMarkerRef.current) destinationMarkerRef.current.setMap(map);
  }, []);

  // Update polyline styles when selection changes
  useEffect(() => {
    if (!window.google) return;
    const DARK_BLUE = '#1A73E8';
    const LIGHT_BLUE = '#8AB4F8';

    polylinesRef.current.forEach((poly, idx) => {
      if (!poly) return;
      const selected = selectedPolyIndex === idx;
      poly.setOptions({
        strokeColor: selected ? DARK_BLUE : LIGHT_BLUE,
        strokeWeight: selected ? 6 : 4,
        strokeOpacity: selected ? 0.95 : 0.7,
        zIndex: selected ? 100 : 5 + idx,
      });
    });
  }, [selectedPolyIndex]);

  const handleResetPosition = useCallback(() => {
    if (mapRef.current && currentLocation) {
      mapRef.current.panTo(currentLocation);
      mapRef.current.setZoom(15);
    }
  }, [currentLocation]);

  if (!isLoaded || !currentLocation) {
    return <p>Loading Map...</p>;
  }

  return (
    <div style={{ position: 'relative' }}>
      <GoogleMap
        key={destinationOverride ? `${destinationOverride.lat}-${destinationOverride.lng}` : 'no-dest'}
        mapContainerStyle={mapContainerStyle}
        center={currentLocation}
        zoom={zoom}
        onLoad={onLoad}
        options={{
          disableDefaultUI: true,
          gestureHandling: "greedy",
          clickableIcons: false,
          zoomControl: true,
          streetViewControl: false,
          mapTypeControl: false,
          fullscreenControl: false,
        }}
      >
        {directions && (
          <DirectionsRenderer
            key={`dir-${destinationOverride?.lat}-${destinationOverride?.lng}`}
            directions={directions}
            options={{ suppressMarkers: true }}
          />
        )}
      </GoogleMap>
      <button
        onClick={handleResetPosition}
        style={{
          position: 'absolute',
          bottom: '20px',
          right: '20px',
          zIndex: 10,
          padding: '8px 12px',
          backgroundColor: '#4285F4',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontSize: '12px',
          fontWeight: 'bold',
          boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
        }}
      >
        📍 My Location
      </button>
    </div>
  );
};

export default NavigationMap;