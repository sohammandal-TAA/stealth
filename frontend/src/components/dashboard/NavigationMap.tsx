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
}) => {
  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY,
    libraries: ["places"],
  });

  const mapRef = useRef<google.maps.Map | null>(null);
  const markerRef = useRef<google.maps.Marker | null>(null);
  const destinationMarkerRef = useRef<google.maps.Marker | null>(null); // ✅ ADDED

  const [currentLocation, setCurrentLocation] =
    useState<google.maps.LatLngLiteral | null>(null);

  const [directions, setDirections] =
    useState<google.maps.DirectionsResult | null>(null);

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
  }, []);

  // ---------------------------
  // REQUEST ROUTE
  // ---------------------------
  const requestRoute = useCallback(
    (origin: google.maps.LatLngLiteral) => {
      if (!window.google || !destinationOverride) return;

      const service = new window.google.maps.DirectionsService();

      service.route(
        {
          origin,
          destination: destinationOverride,
          travelMode: window.google.maps.TravelMode.DRIVING,
        },
        (result, status) => {
          if (status === "OK" && result) {
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
    [destinationOverride, onRouteCalculated]
  );

  // 🔥 Only calculate route when both exist
  useEffect(() => {
    if (!currentLocation || !destinationOverride) return;
    requestRoute(currentLocation);
  }, [currentLocation, destinationOverride]);

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
    }
  }, [destinationOverride]);

  const onLoad = useCallback((map: google.maps.Map) => {
    mapRef.current = map;
  }, []);

  // Prevent center error
  if (!isLoaded || !currentLocation) {
    return <p>Loading Map...</p>;
  }

  return (
    <GoogleMap
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
          directions={directions}
          options={{ suppressMarkers: true }}
        />
      )}
    </GoogleMap>
  );
};

export default React.memo(NavigationMap);