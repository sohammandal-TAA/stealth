import React from 'react';
import { DashboardRouteInfo, RouteOption } from './dashboardData';

interface AlternativeRoutesProps {
  isDarkMode: boolean;
  routeInfo: DashboardRouteInfo | null;
  routes?: RouteOption[];
  selectedRouteIndex?: number | null;
  onRouteSelect?: (index: number | null) => void;
}

const AlternativeRoutes: React.FC<AlternativeRoutesProps> = ({
  routeInfo,
  routes = [],
  selectedRouteIndex = null,
  onRouteSelect,
}) => {

  const badgeColor = (level: 'low' | 'medium' | 'high') => {
    if (level === 'low') return 'badge-low';
    if (level === 'medium') return 'badge-medium';
    return 'badge-high';
  };

  const durationSuffix = routeInfo ? routeInfo.duration : undefined;

  return (
    <section className="dashboard-card routes-card">
      <header className="routes-header">
        <div>
          <h2>Alternative Routes</h2>
          <p className="muted">
            Choose the cleanest way to your destination, powered by live AQI.
          </p>
        </div>
        <span className="eco-pill">Eco</span>
      </header>

      <div className="routes-list">
        {routes.map((route, idx) => (
          <article
            key={route.id}
            className={`route-item ${selectedRouteIndex === idx ? 'route-selected' : ''}`}
            onClick={() => onRouteSelect?.(selectedRouteIndex === idx ? null : idx)}
            style={{
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              border: selectedRouteIndex === idx ? '2px solid #1A73E8' : '2px solid transparent',
              borderRadius: '10px',
              backgroundColor: selectedRouteIndex === idx ? 'rgba(26, 115, 232, 0.12)' : '',
              boxShadow: selectedRouteIndex === idx ? '0 0 0 3px rgba(26, 115, 232, 0.2)' : '',
            }}
          >
            <div className={`route-label ${badgeColor(route.pollutionLevel)}`}>{route.label}</div>
            <div className="route-main">
              <div>
                <p className="route-name">{route.name}</p>
                <p className="route-meta">
                  {(durationSuffix ?? route.duration) != null && (
                    <span>● {(durationSuffix ?? route.duration)} min</span>
                  )}
                  {route.distance != null && (
                    <span>● {route.distance}</span>
                  )}
                  {route.pollutionLevel === 'low' && <span>🍃 Eco</span>}
                </p>
              </div>
              <div className={`route-score ${badgeColor(route.pollutionLevel)}`}>
                {route.avgExposureAqi != null ? route.avgExposureAqi.toFixed(2) : '—'}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
};

export default AlternativeRoutes;