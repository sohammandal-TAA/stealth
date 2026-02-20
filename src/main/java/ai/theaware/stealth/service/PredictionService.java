package ai.theaware.stealth.service;

import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;

import lombok.extern.slf4j.Slf4j;

@Service
@Slf4j
public class PredictionService {

    @Value("${app.ai.predict-url}")
    private String predictUrl;

    private final RestTemplate restTemplate;
    private final PredictionCacheService predictionCacheService;

    private final Cache<String, CompletableFuture<Object>> pendingPredictions =
            Caffeine.newBuilder()
                    .expireAfterWrite(2, TimeUnit.MINUTES)
                    .maximumSize(1000)
                    .build();

    public PredictionService(@Qualifier("aiRestTemplate") RestTemplate restTemplate,
                             PredictionCacheService predictionCacheService) {
        this.restTemplate = restTemplate;
        this.predictionCacheService = predictionCacheService;
    }

    @Async
    public void triggerPrediction(String userEmail, Double sLat, Double sLon, Double dLat, Double dLon) {
        if (sLat == null || sLon == null || dLat == null || dLon == null) {
            log.warn("Skipping prediction for {}: null coordinates", userEmail);
            return;
        }

        if (pendingPredictions.getIfPresent(userEmail) != null) {
            log.info("Prediction already in-flight for {}, skipping duplicate trigger", userEmail);
            return;
        }

        CompletableFuture<Object> future = new CompletableFuture<>();
        pendingPredictions.put(userEmail, future);

        try {
            Map<String, Object> payload = Map.of("sLat", sLat, "sLon", sLon, "dLat", dLat, "dLon", dLon);
            log.info("Triggering AI Prediction at: {}", predictUrl);
            Object result = restTemplate.postForObject(predictUrl, payload, Object.class);

            future.complete(result);
            predictionCacheService.store(userEmail, result);
            pendingPredictions.invalidate(userEmail);
            log.info("Prediction completed for {}: {}", userEmail, result);

        } catch (RestClientException e) {
            future.completeExceptionally(e);
            pendingPredictions.invalidate(userEmail);
            log.error("Prediction error: {}", e.getMessage());
        }
    }

    @Cacheable(value = "aqi_predict", key = "#userEmail",
            unless = "#result instanceof T(java.util.Map) && 'error'.equals(#result.get('status'))")
    public Object getPrediction(String userEmail) {

        CompletableFuture<Object> future = pendingPredictions.getIfPresent(userEmail);

        if (future == null) {
            return Map.of("status", "error", "message", "No prediction found. Please call /process first.");
        }

        try {
            Object result = future.get(30, TimeUnit.SECONDS);
            pendingPredictions.invalidate(userEmail);
            return result;

        } catch (java.util.concurrent.TimeoutException e) {
            return Map.of("status", "error", "message", "Prediction still processing, try again in a moment.");
        } catch (InterruptedException | ExecutionException e) {
            pendingPredictions.invalidate(userEmail);
            log.error("Prediction failed for {}: {}", userEmail, e.getMessage());
            return Map.of("status", "error", "message", "Prediction failed: " + e.getMessage());
        }
    }
}