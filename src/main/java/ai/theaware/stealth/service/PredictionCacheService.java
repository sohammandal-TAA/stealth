package ai.theaware.stealth.service;

import org.springframework.cache.annotation.CachePut;
import org.springframework.stereotype.Service;

@Service
public class PredictionCacheService {

    @CachePut(value = "aqi_predict", key = "#userEmail")
    public Object store(String userEmail, Object result) {
        return result;
    }
}