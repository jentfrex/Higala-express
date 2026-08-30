/**
 * config.js
 * ---------------------------------------------------------------------------
 * Higala Express — Shared Config & Fare Calculation Engine
 *
 * Load this BEFORE higala-core.js (it has zero dependencies), or right
 * after — order relative to core doesn't matter, but everything else
 * (orders.js, driver.js, courier.js, map.js) depends on this file.
 *
 * Exposes window.HigalaConfig:
 *   Fare.compute(input)          full fare breakdown for a single trip/order
 *   Fare.computeDistanceFare(km)
 *   Fare.computeParcelWeightFare(kg)
 *   Surge.getPeakMultiplier(date)
 *   Surge.getZoneMultiplier(zoneName)
 *   Surge.getWeatherMultiplier()      async, backed by Open-Meteo (no API key)
 *   Zones.CDO_HIGH_TRAFFIC
 * ---------------------------------------------------------------------------
 */
(function (window) {
  'use strict';

  if (window.HigalaConfig) return; // already initialized

  // ===========================================================================
  // Core fare constants (PHP)
  // ===========================================================================
  const BASE_FARE = 50.00;          // flat rate, covers first BASE_KM
  const BASE_KM = 2;                // km included in base fare
  const PER_KM_RATE = 12.00;        // PHP per km beyond BASE_KM

  const PARCEL_BASE_WEIGHT_KG = 3;  // kg included at no extra charge
  const PER_KG_RATE = 8.00;         // PHP per kg beyond PARCEL_BASE_WEIGHT_KG

  const MIN_FARE = BASE_FARE;       // fare never drops below the flat base
  const MAX_SURGE_MULTIPLIER = 2.5; // hard ceiling regardless of stacked surge factors

  // ===========================================================================
  // Cagayan de Oro geography — coordinates are approximate barangay/landmark
  // centers, used for zone-radius surge lookups (haversine distance).
  // ===========================================================================
  const CDO_HIGH_TRAFFIC = Object.freeze([
    { name: 'Divisoria', lat: 8.4778, lng: 124.6458, radiusKm: 1.2, multiplier: 1.15 },
    { name: 'Cogon Market', lat: 8.4761, lng: 124.6478, radiusKm: 1.0, multiplier: 1.20 },
    { name: 'Limketkai / Lapasan', lat: 8.4837, lng: 124.6549, radiusKm: 1.5, multiplier: 1.15 },
    { name: 'Carmen', lat: 8.4886, lng: 124.6301, radiusKm: 1.2, multiplier: 1.10 },
    { name: 'Velez / Capitol', lat: 8.4844, lng: 124.6415, radiusKm: 1.0, multiplier: 1.10 },
  ]);

  // Local time (Asia/Manila) windows treated as peak hours.
  const PEAK_WINDOWS = Object.freeze([
    { startHour: 7, endHour: 9, multiplier: 1.20 },   // morning rush
    { startHour: 11, endHour: 13, multiplier: 1.10 }, // lunch
    { startHour: 17, endHour: 20, multiplier: 1.25 }, // evening rush
  ]);

  const WEATHER = Object.freeze({
    // Open-Meteo is free and keyless — safe to call directly from the client.
    API_URL: 'https://api.open-meteo.com/v1/forecast?latitude=8.4542&longitude=124.6319&current=precipitation,rain,weather_code',
    HEAVY_RAIN_MM_THRESHOLD: 2.5, // mm/hr considered "heavy rain" for surge purposes
    SURGE_MULTIPLIER: 1.30,
    CACHE_TTL_MS: 5 * 60 * 1000, // re-check weather at most every 5 minutes
  });

  // ===========================================================================
  // Geo helpers
  // ===========================================================================
  function toRad(deg) {
    return (deg * Math.PI) / 180;
  }

  /** Haversine distance in km between two lat/lng points. */
  function distanceKmBetween(a, b) {
    const R = 6371; // Earth radius, km
    const dLat = toRad(b.lat - a.lat);
    const dLng = toRad(b.lng - a.lng);
    const lat1 = toRad(a.lat);
    const lat2 = toRad(b.lat);
    const h =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function round2(n) {
    return Math.round((n + Number.EPSILON) * 100) / 100;
  }

  // ===========================================================================
  // Surge
  // ===========================================================================
  const Surge = (function () {
    let cachedWeather = { multiplier: 1, checkedAt: 0, isHeavyRain: false };

    /** @param {Date} [date] defaults to now, in the browser's local time. */
    function getPeakMultiplier(date) {
      const d = date || new Date();
      const hour = d.getHours();
      const window_ = PEAK_WINDOWS.find((w) => hour >= w.startHour && hour < w.endHour);
      return window_ ? window_.multiplier : 1;
    }

    /**
     * @param {{lat:number, lng:number}} point
     * @returns {{ multiplier: number, zone: string|null }}
     */
    function getZoneMultiplier(point) {
      if (!point || typeof point.lat !== 'number' || typeof point.lng !== 'number') {
        return { multiplier: 1, zone: null };
      }
      for (const zone of CDO_HIGH_TRAFFIC) {
        const d = distanceKmBetween(point, zone);
        if (d <= zone.radiusKm) {
          return { multiplier: zone.multiplier, zone: zone.name };
        }
      }
      return { multiplier: 1, zone: null };
    }

    /**
     * Fetches current precipitation for CDO from Open-Meteo (no API key
     * required) and returns a surge multiplier if it counts as heavy rain.
     * Falls back to the last known value (or 1x) on network failure so a
     * flaky connection never blocks fare calculation.
     * @returns {Promise<{ multiplier: number, isHeavyRain: boolean }>}
     */
    async function getWeatherMultiplier() {
      const now = Date.now();
      if (now - cachedWeather.checkedAt < WEATHER.CACHE_TTL_MS) {
        return { multiplier: cachedWeather.multiplier, isHeavyRain: cachedWeather.isHeavyRain };
      }

      try {
        const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
        const timer = controller ? setTimeout(() => controller.abort(), 6000) : null;
        const response = await fetch(WEATHER.API_URL, { signal: controller ? controller.signal : undefined });
        if (timer) clearTimeout(timer);

        if (!response.ok) throw new Error(`weather fetch failed: ${response.status}`);
        const data = await response.json();
        const rainMm = data && data.current ? Number(data.current.rain ?? data.current.precipitation ?? 0) : 0;
        const isHeavyRain = Number.isFinite(rainMm) && rainMm >= WEATHER.HEAVY_RAIN_MM_THRESHOLD;

        cachedWeather = {
          multiplier: isHeavyRain ? WEATHER.SURGE_MULTIPLIER : 1,
          checkedAt: now,
          isHeavyRain,
        };
      } catch (err) {
        console.error('[HigalaConfig.Surge] weather lookup failed, using last known value:', err);
        // Don't refresh checkedAt on failure — retry sooner instead of caching a failure.
      }

      return { multiplier: cachedWeather.multiplier, isHeavyRain: cachedWeather.isHeavyRain };
    }

    return { getPeakMultiplier, getZoneMultiplier, getWeatherMultiplier, distanceKmBetween };
  })();

  // ===========================================================================
  // Fare
  // ===========================================================================
  const Fare = (function () {
    function computeDistanceFare(distanceKm) {
      const km = Number(distanceKm);
      if (!Number.isFinite(km) || km <= 0) return 0;
      const billableKm = Math.max(0, km - BASE_KM);
      return round2(billableKm * PER_KM_RATE);
    }

    function computeParcelWeightFare(weightKg) {
      const kg = Number(weightKg);
      if (!Number.isFinite(kg) || kg <= 0) return 0;
      const billableKg = Math.max(0, kg - PARCEL_BASE_WEIGHT_KG);
      return round2(billableKg * PER_KG_RATE);
    }

    /**
     * Full fare breakdown for one order/trip.
     *
     * @param {Object} input
     * @param {'food'|'parcel'|'rides'|'delivery'|'grocery'|'pharmacy'|'water'|'gifts'|'party'} input.service
     * @param {number} input.distanceKm            trip distance in km
     * @param {number} [input.weightKg]             only meaningful for 'parcel'
     * @param {{lat:number,lng:number}} [input.pickupPoint]  for zone-based surge
     * @param {boolean} [input.isHeavyRain]          precomputed weather flag (skip async lookup)
     * @param {number} [input.weatherMultiplier]     precomputed weather multiplier (skip async lookup)
     * @param {Date} [input.timestamp]               defaults to now
     * @returns {Object} breakdown
     */
    function compute(input) {
      const opts = input || {};
      const service = opts.service || 'delivery';
      const timestamp = opts.timestamp || new Date();

      const distanceFee = computeDistanceFare(opts.distanceKm);
      const weightFee = service === 'parcel' ? computeParcelWeightFare(opts.weightKg) : 0;

      const preSurgeSubtotal = round2(BASE_FARE + distanceFee + weightFee);

      const peakMultiplier = Surge.getPeakMultiplier(timestamp);
      const zoneResult = Surge.getZoneMultiplier(opts.pickupPoint);
      const weatherMultiplier = typeof opts.weatherMultiplier === 'number'
        ? opts.weatherMultiplier
        : (opts.isHeavyRain ? WEATHER.SURGE_MULTIPLIER : 1);

      // Multipliers stack multiplicatively but are capped so a "perfect
      // storm" (peak + zone + rain) never runs away.
      const rawCombinedMultiplier = peakMultiplier * zoneResult.multiplier * weatherMultiplier;
      const combinedMultiplier = Math.min(rawCombinedMultiplier, MAX_SURGE_MULTIPLIER);

      const surgeAmount = round2(preSurgeSubtotal * (combinedMultiplier - 1));
      const total = Math.max(MIN_FARE, round2(preSurgeSubtotal + surgeAmount));

      return {
        service,
        baseFare: BASE_FARE,
        distanceFee,
        weightFee,
        preSurgeSubtotal,
        surge: {
          peakMultiplier,
          zoneMultiplier: zoneResult.multiplier,
          zoneName: zoneResult.zone,
          weatherMultiplier,
          combinedMultiplier: round2(combinedMultiplier),
          cappedAt: rawCombinedMultiplier > MAX_SURGE_MULTIPLIER ? MAX_SURGE_MULTIPLIER : null,
          amount: surgeAmount,
        },
        total,
      };
    }

    return { compute, computeDistanceFare, computeParcelWeightFare, BASE_FARE, BASE_KM, PER_KM_RATE, PARCEL_BASE_WEIGHT_KG, PER_KG_RATE, MIN_FARE, MAX_SURGE_MULTIPLIER };
  })();

  window.HigalaConfig = Object.freeze({
    Fare,
    Surge,
    Zones: { CDO_HIGH_TRAFFIC },
    Geo: { distanceKmBetween },
  });
})(window);