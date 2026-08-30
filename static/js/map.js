/**
 * map.js
 * ---------------------------------------------------------------------------
 * Higala Express — Godlike SuperApp Map Engine (CDO Optimized)
 * ---------------------------------------------------------------------------
 * Features integrated:
 * 1. Customer-side dropoff picker with Geofencing boundary check (CDO limits)
 * 2. Reverse geocoding via OpenStreetMap Nominatim (Zero API Key)
 * 3. CDO Quick Landmarks Presets utility for instant map centering
 * 4. Driver-side live GPS tracking with 5s Background Heartbeat
 * 5. GPS Anomaly Detection & Fraud Check (HigalaOrders.Fraud)
 * 6. Split-Dispatch Multi-Stop Route rendering (renderOrderRoute)
 * ---------------------------------------------------------------------------
 */
(function (window, document) {
  'use strict';

  if (typeof window.L === 'undefined') {
    console.error('[HigalaMap] Leaflet (window.L) must be loaded before map.js');
    return;
  }
  if (!window.HigalaCore) {
    console.error('[HigalaMap] HigalaCore must be loaded before map.js');
    return;
  }
  if (window.HigalaMap) return;

  const { Api, EventBus, Toast } = window.HigalaCore;
  const Orders = window.HigalaOrders; // optional — for Fraud checks / heartbeat POSTs

  // Default view centers on Cagayan de Oro city proper.
  const CDO_CENTER = { lat: 8.4542, lng: 124.6319 };
  const DEFAULT_ZOOM = 14;
  const HEARTBEAT_INTERVAL_MS = 5000;

  const TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
  const TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  // CDO Service Area Geofencing Boundary Box (Approximate Urban & Suburban Limits)
  const CDO_BOUNDS = {
    minLat: 8.3500,
    maxLat: 8.5500,
    minLng: 124.5500,
    maxLng: 124.7800
  };

  // CDO Hyper-Local Landmarks Preset Coordinates
  const CDO_LANDMARKS = {
    limketkai: { lat: 8.4848, lng: 124.6465, name: 'Limketkai Center' },
    centrio: { lat: 8.4772, lng: 124.6431, name: 'Centrio Ayala Mall' },
    smdowntown: { lat: 8.4842, lng: 124.6530, name: 'SM Downtown Premier' },
    cogon: { lat: 8.4756, lng: 124.6492, name: 'Cogon Public Market' },
    divisoria: { lat: 8.4789, lng: 124.6367, name: 'Divisoria / Gaston Park' },
    carmen: { lat: 8.4651, lng: 124.6218, name: 'Carmen Market' },
    ustp: { lat: 8.4862, lng: 124.6521, name: 'USTP Campus' },
    xavier: { lat: 8.4795, lng: 124.6398, name: 'Xavier University' }
  };

  function setAddressElement(el, address) {
    if (!el) return;
    const text = address || '';
    if ('value' in el && el.tagName !== 'DIV') {
      el.value = text;
    } else {
      el.textContent = text;
    }
    el.dispatchEvent(new Event('change'));
  }

  function makeDivIcon(className, label) {
    return L.divIcon({
      className: `higala-map-marker ${className}`,
      html: `<span>${label || ''}</span>`,
      iconSize: [28, 28],
      iconAnchor: [14, 28],
    });
  }

  const ICONS = {
    dropoff: makeDivIcon('higala-map-marker--dropoff', '📍'),
    pickup: makeDivIcon('higala-map-marker--pickup', '🏪'),
    driver: makeDivIcon('higala-map-marker--driver', '🛵'),
    driverFlagged: makeDivIcon('higala-map-marker--driver-flagged', '⚠️'),
  };

  // ===========================================================================
  // Geofencing Helper
  // ===========================================================================
  function isWithinCdoServiceArea(lat, lng) {
    return (
      lat >= CDO_BOUNDS.minLat &&
      lat <= CDO_BOUNDS.maxLat &&
      lng >= CDO_BOUNDS.minLng &&
      lng <= CDO_BOUNDS.maxLng
    );
  }

  // ===========================================================================
  // 1. Customer-side dropoff picker with Geofencing & Landmarks
  // ===========================================================================
  function initPicker(containerId, opts) {
    const options = opts || {};
    const container = document.getElementById(containerId);
    if (!container) {
      console.error(`[HigalaMap] initPicker: no element with id "${containerId}"`);
      return null;
    }

    const center = options.initialCenter || CDO_CENTER;
    const map = L.map(containerId).setView([center.lat, center.lng], DEFAULT_ZOOM);
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map);

    let marker = null;

    function setDropoff(latlng) {
      // Optional Geofence validation check
      if (options.enforceGeofence && !isWithinCdoServiceArea(latlng.lat, latlng.lng)) {
        if (Toast && typeof Toast.error === 'function') {
          Toast.error('Selected location is outside Higala Express CDO service coverage area.');
        } else {
          console.warn('[HigalaMap] Location outside CDO service bounds.');
        }
        EventBus.emit('map:geofenceViolation', { lat: latlng.lat, lng: latlng.lng });
        return;
      }

      if (marker) {
        marker.setLatLng(latlng);
      } else {
        marker = L.marker(latlng, { icon: ICONS.dropoff, draggable: true }).addTo(map);
        marker.on('dragend', () => setDropoff(marker.getLatLng()));
      }

      const latEl = options.latInputId && document.getElementById(options.latInputId);
      const lngEl = options.lngInputId && document.getElementById(options.lngInputId);
      if (latEl) { latEl.value = latlng.lat; latEl.dispatchEvent(new Event('change')); }
      if (lngEl) { lngEl.value = latlng.lng; lngEl.dispatchEvent(new Event('change')); }

      reverseGeocode(latlng).then((address) => {
        const addrEl = options.addressInputId && document.getElementById(options.addressInputId);
        setAddressElement(addrEl, address);
        EventBus.emit('map:dropoffSelected', { lat: latlng.lat, lng: latlng.lng, address });
      });
    }

    map.on('click', (event) => setDropoff(event.latlng));

    // Try to center on user's geolocation first if permitted
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const userLat = pos.coords.latitude;
          const userLng = pos.coords.longitude;
          if (isWithinCdoServiceArea(userLat, userLng)) {
            map.setView([userLat, userLng], DEFAULT_ZOOM);
          }
        },
        () => { /* fallback to CDO center */ },
        { timeout: 8000 }
      );
    }

    // Helper function to pan to a specific CDO landmark key
    function panToLandmark(landmarkKey) {
      const landmark = CDO_LANDMARKS[landmarkKey];
      if (landmark) {
        const target = L.latLng(landmark.lat, landmark.lng);
        map.setView(target, 16);
        setDropoff(target);
      }
    }

    return { 
      map, 
      setDropoff: (lat, lng) => setDropoff(L.latLng(lat, lng)),
      panToLandmark
    };
  }

  // Reverse geocoding via OpenStreetMap Nominatim
  async function reverseGeocode(latlng) {
    try {
      const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${latlng.lat}&lon=${latlng.lng}`;
      const response = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!response.ok) return null;
      const data = await response.json();
      return data && data.display_name ? data.display_name : null;
    } catch (err) {
      console.error('[HigalaMap] reverse geocode failed:', err);
      return null;
    }
  }

  // ===========================================================================
  // 2. Driver-side live tracking / heartbeat + anomaly detection
  // ===========================================================================
  let liveState = {
    map: null,
    driverMarker: null,
    watchId: null,
    heartbeatTimer: null,
    lastFix: null,
    orderId: null,
    driverId: null,
  };

  function initLiveTracking(containerId, opts) {
    const options = opts || {};
    if (!options.orderId || !options.driverId) {
      console.error('[HigalaMap] initLiveTracking requires opts.orderId and opts.driverId');
      return null;
    }
    if (!navigator.geolocation) {
      if (Toast) Toast.error('This device does not support GPS tracking.');
      return null;
    }

    stopLiveTracking();

    const container = document.getElementById(containerId);
    const map = container ? L.map(containerId).setView([CDO_CENTER.lat, CDO_CENTER.lng], DEFAULT_ZOOM) : null;
    if (map) {
      L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map);
    }

    liveState.map = map;
    liveState.orderId = options.orderId;
    liveState.driverId = options.driverId;
    liveState.lastFix = null;

    liveState.watchId = navigator.geolocation.watchPosition(
      (pos) => handleFix(pos, options.onFix),
      (err) => {
        console.error('[HigalaMap] geolocation error:', err);
        if (Toast) Toast.error('Could not get your GPS location. Please check location permissions.');
      },
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 10000 }
    );

    // Steady 5-second background heartbeat timer
    liveState.heartbeatTimer = setInterval(() => {
      if (liveState.lastFix) sendHeartbeat(liveState.lastFix);
    }, HEARTBEAT_INTERVAL_MS);

    return { map };
  }

  function handleFix(position, onFix) {
    const nextFix = {
      lat: position.coords.latitude,
      lng: position.coords.longitude,
      accuracy: position.coords.accuracy,
      timestamp: position.timestamp || Date.now(),
    };

    let anomaly = { suspicious: false, reasons: [], impliedSpeedKmh: null };
    if (Orders && Orders.Fraud) {
      anomaly = Orders.Fraud.checkGpsUpdate(liveState.orderId, liveState.driverId, liveState.lastFix, nextFix);
    }

    renderDriverPosition(nextFix, anomaly.suspicious);
    liveState.lastFix = nextFix;

    if (anomaly.suspicious) {
      console.warn('[HigalaMap] GPS anomaly flagged:', anomaly.reasons.join('; '));
    }

    if (typeof onFix === 'function') onFix(nextFix, anomaly);
    EventBus.emit('map:driverFix', { orderId: liveState.orderId, fix: nextFix, anomaly });
  }

  function renderDriverPosition(fix, flagged) {
    if (!liveState.map) return;
    const latlng = L.latLng(fix.lat, fix.lng);
    const icon = flagged ? ICONS.driverFlagged : ICONS.driver;

    if (liveState.driverMarker) {
      liveState.driverMarker.setLatLng(latlng);
      liveState.driverMarker.setIcon(icon);
    } else {
      liveState.driverMarker = L.marker(latlng, { icon }).addTo(liveState.map);
      liveState.map.setView(latlng, DEFAULT_ZOOM);
    }

    if (flagged) {
      liveState.driverMarker.bindPopup('⚠️ Unusual GPS movement detected — flagged for review').openPopup();
    }
  }

  async function sendHeartbeat(fix) {
    if (!liveState.orderId || !liveState.driverId) return;
    try {
      await Api.request(`/orders/${encodeURIComponent(liveState.orderId)}/location`, {
        method: 'POST',
        body: {
          driverId: liveState.driverId,
          lat: fix.lat,
          lng: fix.lng,
          accuracy: fix.accuracy,
          timestamp: fix.timestamp,
        },
        silent: true,
      });
    } catch (err) {
      // Silently skip offline ticks
    }
  }

  function stopLiveTracking() {
    if (liveState.watchId != null && navigator.geolocation) {
      navigator.geolocation.clearWatch(liveState.watchId);
    }
    if (liveState.heartbeatTimer) {
      clearInterval(liveState.heartbeatTimer);
    }
    if (liveState.map) {
      liveState.map.remove();
    }
    liveState = {
      map: null,
      driverMarker: null,
      watchId: null,
      heartbeatTimer: null,
      lastFix: null,
      orderId: null,
      driverId: null,
    };
  }

  // ===========================================================================
  // 3. Static multi-stop route rendering (split-dispatch visualization)
  // ===========================================================================
  function renderOrderRoute(containerId, stops) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error(`[HigalaMap] renderOrderRoute: no element with id "${containerId}"`);
      return null;
    }
    if (!Array.isArray(stops) || stops.length === 0) {
      console.error('[HigalaMap] renderOrderRoute requires at least one stop');
      return null;
    }

    const map = L.map(containerId);
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map);

    const latlngs = stops.map((s) => L.latLng(s.lat, s.lng));
    stops.forEach((stop, index) => {
      const isDropoff = stop.type === 'dropoff' || index === stops.length - 1;
      L.marker(latlngs[index], { icon: isDropoff ? ICONS.dropoff : ICONS.pickup })
        .addTo(map)
        .bindPopup(`${index + 1}. ${stop.label || (isDropoff ? 'Drop-off' : 'Pickup')}`);
    });

    if (latlngs.length > 1) {
      L.polyline(latlngs, { color: '#1f6feb', weight: 4, opacity: 0.8, dashArray: '6 8' }).addTo(map);
    }

    const bounds = L.latLngBounds(latlngs);
    map.fitBounds(bounds, { padding: [32, 32] });

    return { map };
  }

  // ===========================================================================
  // Public export
  // ===========================================================================
  window.HigalaMap = Object.freeze({
    initPicker,
    initLiveTracking,
    stopLiveTracking,
    renderOrderRoute,
    reverseGeocode,
    CDO_LANDMARKS,
    isWithinCdoServiceArea,
  });
})(window, document);