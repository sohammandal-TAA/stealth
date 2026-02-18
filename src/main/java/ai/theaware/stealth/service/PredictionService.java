package ai.theaware.stealth.service;

import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import lombok.extern.slf4j.Slf4j;

@Service
@Slf4j
public class PredictionService {

    @Value("${app.ai.predict-url}")
    private String predictUrl;

    private final RestTemplate restTemplate;
    private final ConcurrentHashMap<String, CompletableFuture<Object>> pendingPredictions = new ConcurrentHashMap<>();

    public PredictionService(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    @Async
    public void triggerPrediction(String userEmail, Double lat, Double lon) {
        CompletableFuture<Object> future = new CompletableFuture<>();
        pendingPredictions.put(userEmail, future);

        try {
            Map<String, Object> payload = Map.of("lat", lat, "lon", lon);

            log.info("Triggering AI Prediction at: {}", predictUrl);
            Object result = restTemplate.postForObject(predictUrl, payload, Object.class);

            future.complete(result);
        } catch (RestClientException e) {
            future.completeExceptionally(e);
            log.error("Prediction error: {}", e.getMessage());
        }
    }

    public Object getPrediction(String userEmail) {
        CompletableFuture<Object> future = pendingPredictions.get(userEmail);

        if (future == null) {
            return Map.of("error", "No prediction found. Please call /process first.");
        }

        try {
            Object result = future.get(30, java.util.concurrent.TimeUnit.SECONDS);
            pendingPredictions.remove(userEmail);
            return result;

        } catch (java.util.concurrent.TimeoutException e) {
            return Map.of("error", "Prediction still processing, try again in a moment.");
        } catch (InterruptedException | ExecutionException e) {
            pendingPredictions.remove(userEmail);
            log.error("Prediction failed for {}: {}", userEmail, e.getMessage());
            return Map.of("error", "Prediction failed: " + e.getMessage());
        }
    }
}