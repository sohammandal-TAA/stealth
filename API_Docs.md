# Stealth API Documentation

This document provides technical details for the Stealth Java Backend API.

## Base URL
The application runs on `http://localhost:8080` (default Spring Boot port).

## Authentication
The API uses **OAuth2 (Google)** for authentication.
- **Login:** Handled via Spring Security OAuth2.
- **Security:** Most endpoints under `/api/**` require an authenticated session.
- **Success Redirect:** After a successful Google login, the user is redirected to the frontend dashboard.

## Endpoints

### 1. Route Processing
Processes a routing request between two coordinates, triggers an AI prediction, and returns results from the AI service.

*   **URL:** `/api/routes/process`
*   **Method:** `POST`
*   **Authentication:** Required
*   **Request Body:**
    ```json
    {
      "sLat": 23.5204,
      "sLon": 87.3119,
      "dLat": 23.5500,
      "dLon": 87.2900
    }
    ```
*   **Success Response:** Returns the JSON response from the internal AI service.
*   **Notes:** This call triggers an asynchronous prediction via the `PredictionService` and saves the route to the database if it's not a duplicate of the user's last request.

### 2. Get Prediction
Retrieves the result of the background prediction triggered by the `/process` endpoint.

*   **URL:** `/api/routes/predict`
*   **Method:** `GET`
*   **Authentication:** Required
*   **Success Response:** Returns the prediction object.
*   **Error Response:** 
    *   `401 Unauthorized` if not logged in.
    *   `{"error": "No prediction found..."}` if called before `/process`.
    *   `{"error": "Prediction still processing..."}` if the background task isn't finished within 30 seconds.

### 3. Raw Google Routes (Test)
Directly fetches raw routing data from Google Maps API without AI processing.

*   **URL:** `/`
*   **Method:** `GET`
*   **Authentication:** Required
*   **Query Parameters:**
    *   `sLat` (Double): Source Latitude
    *   `sLon` (Double): Source Longitude
    *   `dLat` (Double): Destination Latitude
    *   `dLon` (Double): Destination Longitude
*   **Success Response:** Returns a Google `DirectionsResult` object.

## Data Models

### RouteRequestDTO
| Field | Type | Description |
| :--- | :--- | :--- |
| `sLat` | Double | Starting latitude |
| `sLon` | Double | Starting longitude |
| `dLat` | Double | Destination latitude |
| `dLon` | Double | Destination longitude |

### RouteResponseDTO (Internal Structure)
Used for communication between the backend and the AI service.
- **routeCount:** Number of alternative routes found.
- **routes:** List of `RouteDetail` objects.
    - **distance:** Human-readable distance (e.g., "5.2 km").
    - **distanceValue:** Distance in meters.
    - **duration:** Human-readable duration (e.g., "12 mins").
    - **coordinates:** List of `lat`/`lng` points resampled at 1km intervals.

## Infrastructure & Configuration
- **Database:** PostgreSQL with PostGIS for spatial data (`geom` field in `Route` entity).
- **Caching:** Caffeine cache is enabled for routing results and predictions (5-minute expiration).
- **CORS:** Configured to allow requests from `http://localhost:5173`.
- **API Documentation:** Swagger UI is available at `/swagger-ui.html` (if enabled in development).
