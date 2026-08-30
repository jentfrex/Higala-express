/**
 * orders.js
 * ---------------------------------------------------------------------------
 * Higala Express — Order Dispatch, Offline Queue & Anti-Fraud Engine
 *
 * Load order: higala-core.js -> config.js -> orders.js
 *
 * This file assumes a backend exposes (adjust paths in Endpoints below to
 * match your actual API):
 *   POST   /orders/:id/broadcast          { radiusKm }
 *   POST   /orders/:id/accept             { driverId }
 *   POST   /orders/:id/picked-up          { photoDataUrl? }
 *   POST   /orders/:id/delivered          { otp, photoDataUrl }
 *   GET    /orders/:id                    -> current order status
 *   POST   /admin/fraud-alerts            { orderId, driverId, reason, evidence }
 *
 * It does NOT assume a WebSocket server. Live status is obtained by polling
 * GET /orders/:id — swap POLL_INTERVAL_MS-driven polling for a socket
 * listener later without touching the public API of this module (everything
 * downstream reacts to EventBus events, not to the transport).
 *
 * Exposes window.HigalaOrders:
 *   Dispatch.broadcast(order)             start broadcast + radius fallback loop
 *   Dispatch.stop(orderId)
 *   State.accept(orderId, driverId)
 *   State.pickedUp(orderId, opts)
 *   State.delivered(orderId, opts)
 *   OfflineQueue.enqueue / flush / size
 *   Fraud.checkGpsUpdate(orderId, driverId, prevFix, nextFix)
 * ---------------------------------------------------------------------------
 */
(function (window, document) {
  'use strict';

  if (!window.HigalaCore) {
    console.error('[HigalaOrders] HigalaCore must be loaded before orders.js');
    return;
  }
  if (window.HigalaOrders) return; // already initialized

  const { Api, EventBus, Toast, Config: CoreConfig } = window.HigalaCore;

  const Endpoints = Object.freeze({
    broadcast: (orderId) => `/orders/${encodeURIComponent(orderId)}/broadcast`,
    accept: (orderId) => `/orders/${encodeURIComponent(orderId)}/accept`,
    pickedUp: (orderId) => `/orders/${encodeURIComponent(orderId)}/picked-up`,
    delivered: (orderId) => `/orders/${encodeURIComponent(orderId)}/delivered`,
    status: (orderId) => `/orders/${encodeURIComponent(orderId)}`,
    fraudAlert: () => `/admin/fraud-alerts`,
  });

  // ===========================================================================
  // Offline-first queue — CDO signal is unreliable, especially indoors in
  // malls (Limketkai, Centrio) and along the coastal barangays. Any mutating
  // order-state call that fails due to a *network* error (not a server
  // rejection) is queued to localStorage and retried automatically.
  // ===========================================================================
  const OfflineQueue = (function () {
    const STORAGE_KEY = 'higala_offline_order_queue';
    const MAX_RETRIES = 8;
    const RETRY_BACKOFF_BASE_MS = 3000;

    function load() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
      } catch (err) {
        console.error('[HigalaOrders.OfflineQueue] corrupt queue, resetting:', err);
        return [];
      }
    }

    function save(queue) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
      } catch (err) {
        console.error('[HigalaOrders.OfflineQueue] failed to persist queue:', err);
      }
    }

    /**
     * @param {{endpoint: string, method: string, body: Object, tag: string}} action
     */
    function enqueue(action) {
      const queue = load();
      queue.push(Object.assign({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        attempts: 0,
        queuedAt: Date.now(),
      }, action));
      save(queue);
      EventBus.emit('order:offlineQueued', { action });
      Toast.warning('You appear to be offline. This action will sync automatically once connected.');
      return queue[queue.length - 1].id;
    }

    function size() {
      return load().length;
    }

    async function flush() {
      let queue = load();
      if (queue.length === 0) return { flushed: 0, remaining: 0 };

      const stillQueued = [];
      let flushed = 0;

      for (const action of queue) {
        try {
          await Api.request(action.endpoint, {
            method: action.method,
            body: action.body,
            silent: true,
          });
          flushed += 1;
          EventBus.emit('order:offlineSynced', { action });
        } catch (err) {
          const isNetworkErr = err && err.status === 0;
          action.attempts += 1;
          if (isNetworkErr && action.attempts < MAX_RETRIES) {
            stillQueued.push(action); // retry later, still offline
          } else if (!isNetworkErr) {
            // Server explicitly rejected it (e.g. 409 order already picked up
            // by someone else) — don't retry forever, surface it instead.
            EventBus.emit('order:offlineSyncFailed', { action, error: err });
            Toast.error(`A queued action for order ${action.body && action.body.orderId ? action.body.orderId : ''} could not be synced: ${err.message}`);
          } else {
            EventBus.emit('order:offlineSyncGaveUp', { action });
          }
        }
      }

      queue = stillQueued;
      save(queue);
      return { flushed, remaining: queue.length };
    }

    // Retry automatically when the browser regains connectivity, and on a
    // slow background interval as a safety net (the 'online' event isn't
    // always reliable on mobile carriers).
    window.addEventListener('online', () => { flush(); });
    setInterval(() => {
      if (navigator.onLine !== false) flush();
    }, RETRY_BACKOFF_BASE_MS * 10);

    return { enqueue, flush, size, STORAGE_KEY };
  })();

  /**
   * Wraps an Api call: on network failure, transparently queues it for
   * later instead of throwing. On server-side (non-network) failure, still
   * throws so the caller can react immediately.
   */
  async function mutateWithOfflineFallback({ endpoint, method, body, tag }) {
    try {
      return await Api.request(endpoint, { method, body });
    } catch (err) {
      if (err && err.status === 0) {
        OfflineQueue.enqueue({ endpoint, method, body, tag });
        return { queuedOffline: true };
      }
      throw err;
    }
  }

  // ===========================================================================
  // Dispatch — automated broadcast with expanding-radius fallback timer
  // ===========================================================================
  const Dispatch = (function () {
    const RADIUS_STEPS_KM = [1, 3, 5, 8, 12];
    const STEP_TIMEOUT_MS = 20000; // time to wait for acceptance before expanding
    const STATUS_POLL_MS = 4000;

    /** @type {Map<string, { stepIndex: number, timeoutHandle: any, pollHandle: any }>} */
    const activeBroadcasts = new Map();

    async function requestBroadcastAtRadius(orderId, radiusKm) {
      try {
        await Api.request(Endpoints.broadcast(orderId), {
          method: 'POST',
          body: { radiusKm },
          silent: true,
        });
        EventBus.emit('order:broadcast', { orderId, radiusKm });
      } catch (err) {
        console.error(`[HigalaOrders.Dispatch] broadcast request failed for ${orderId}:`, err);
        EventBus.emit('order:broadcastFailed', { orderId, radiusKm, error: err });
      }
    }

    async function pollStatus(orderId) {
      try {
        const status = await Api.request(Endpoints.status(orderId), { method: 'GET', silent: true });
        if (status && status.state && status.state !== 'searching') {
          // A driver accepted (or the order was cancelled) — stop expanding.
          stop(orderId);
          EventBus.emit('order:statusChange', { orderId, status });
        }
        return status;
      } catch (err) {
        // Network hiccup while polling is expected on CDO mobile data —
        // don't spam errors, just skip this tick.
        return null;
      }
    }

    /**
     * Starts the broadcast loop for an order: broadcasts at the first
     * radius, and if unaccepted within STEP_TIMEOUT_MS, automatically
     * expands to the next radius step. Stops once accepted/cancelled or the
     * radius steps are exhausted.
     * @param {{ id: string }} order
     */
    function broadcast(order) {
      const orderId = order && order.id;
      if (!orderId) {
        console.error('[HigalaOrders.Dispatch] broadcast() requires order.id');
        return;
      }
      if (activeBroadcasts.has(orderId)) {
        stop(orderId); // restart cleanly if already running
      }

      const entry = { stepIndex: 0, timeoutHandle: null, pollHandle: null };
      activeBroadcasts.set(orderId, entry);

      requestBroadcastAtRadius(orderId, RADIUS_STEPS_KM[0]);

      entry.pollHandle = setInterval(() => pollStatus(orderId), STATUS_POLL_MS);

      function scheduleExpansion() {
        entry.timeoutHandle = setTimeout(async () => {
          const status = await pollStatus(orderId);
          if (!activeBroadcasts.has(orderId)) return; // stopped in the meantime
          if (status && status.state && status.state !== 'searching') return; // stop() already ran

          entry.stepIndex += 1;
          if (entry.stepIndex >= RADIUS_STEPS_KM.length) {
            EventBus.emit('order:broadcastExhausted', { orderId });
            Toast.error('No available drivers found nearby. Please try again shortly.');
            stop(orderId);
            return;
          }

          const nextRadius = RADIUS_STEPS_KM[entry.stepIndex];
          await requestBroadcastAtRadius(orderId, nextRadius);
          EventBus.emit('order:radiusExpanded', { orderId, radiusKm: nextRadius, step: entry.stepIndex });
          scheduleExpansion();
        }, STEP_TIMEOUT_MS);
      }

      scheduleExpansion();
    }

    function stop(orderId) {
      const entry = activeBroadcasts.get(orderId);
      if (!entry) return;
      if (entry.timeoutHandle) clearTimeout(entry.timeoutHandle);
      if (entry.pollHandle) clearInterval(entry.pollHandle);
      activeBroadcasts.delete(orderId);
    }

    function isActive(orderId) {
      return activeBroadcasts.has(orderId);
    }

    return { broadcast, stop, isActive, RADIUS_STEPS_KM, STEP_TIMEOUT_MS };
  })();

  // ===========================================================================
  // State handlers — Accept / Picked Up / Delivered, offline-queued
  // ===========================================================================
  const State = (function () {
    async function accept(orderId, driverId) {
      if (!orderId || !driverId) throw new Error('accept() requires orderId and driverId');
      const result = await mutateWithOfflineFallback({
        endpoint: Endpoints.accept(orderId),
        method: 'POST',
        body: { orderId, driverId },
        tag: 'order:accept',
      });
      Dispatch.stop(orderId);
      EventBus.emit('order:accepted', { orderId, driverId, queuedOffline: !!result.queuedOffline });
      if (!result.queuedOffline) Toast.success('Order accepted.');
      return result;
    }

    /**
     * @param {string} orderId
     * @param {{ photoDataUrl?: string }} [opts]  Photo Proof of Delivery is
     *   optional at pickup, required at delivery (see `delivered`).
     */
    async function pickedUp(orderId, opts) {
      const options = opts || {};
      const result = await mutateWithOfflineFallback({
        endpoint: Endpoints.pickedUp(orderId),
        method: 'POST',
        body: { orderId, photoDataUrl: options.photoDataUrl || null },
        tag: 'order:pickedUp',
      });
      EventBus.emit('order:pickedUp', { orderId, queuedOffline: !!result.queuedOffline });
      if (!result.queuedOffline) Toast.success('Marked as picked up.');
      return result;
    }

    /**
     * Delivery requires BOTH the 4-digit OTP the customer shares in person
     * and a photo proof of delivery, per spec.
     * @param {string} orderId
     * @param {{ otp: string, photoDataUrl: string }} opts
     */
    async function delivered(orderId, opts) {
      const options = opts || {};
      const otp = String(options.otp || '').trim();

      if (!/^\d{4}$/.test(otp)) {
        Toast.error('Enter the 4-digit delivery PIN provided by the customer.');
        throw new Error('delivered() requires a 4-digit otp');
      }
      if (!options.photoDataUrl) {
        Toast.error('A photo proof of delivery is required before completing this order.');
        throw new Error('delivered() requires photoDataUrl');
      }

      const result = await mutateWithOfflineFallback({
        endpoint: Endpoints.delivered(orderId),
        method: 'POST',
        body: { orderId, otp, photoDataUrl: options.photoDataUrl },
        tag: 'order:delivered',
      });
      EventBus.emit('order:delivered', { orderId, queuedOffline: !!result.queuedOffline });
      if (!result.queuedOffline) Toast.success('Delivery completed. Great work!');
      return result;
    }

    return { accept, pickedUp, delivered };
  })();

  // ===========================================================================
  // Anti-fraud — GPS anomaly heuristics
  //
  // IMPORTANT: the browser Geolocation API does not expose whether a
  // position came from a mock-location provider (that flag only exists in
  // native Android APIs). These checks instead flag *behaviorally*
  // implausible movement, which is what's actually available client-side:
  //   - implied speed between two fixes exceeding a sane urban ceiling
  //   - a position "teleporting" further than physically possible for the
  //     elapsed time, even accounting for GPS drift
  //   - reported accuracy oscillating wildly between consecutive fixes
  // Flag events are sent to the admin dashboard for a human (or a stronger
  // server-side model) to review — this module never auto-bans a driver.
  // ===========================================================================
  const Fraud = (function () {
    const MAX_PLAUSIBLE_SPEED_KMH = 100; // generous ceiling for CDO city/highway mix
    const MIN_INTERVAL_SEC_FOR_CHECK = 1; // ignore fixes that arrive faster than this (noisy)
    const ACCURACY_JUMP_THRESHOLD_M = 500; // sudden huge accuracy swing looks synthetic

    /**
     * @param {string} orderId
     * @param {string} driverId
     * @param {{lat:number,lng:number,accuracy?:number,timestamp:number}|null} prevFix
     * @param {{lat:number,lng:number,accuracy?:number,timestamp:number}} nextFix
     * @returns {{ suspicious: boolean, reasons: string[], impliedSpeedKmh: number|null }}
     */
    function checkGpsUpdate(orderId, driverId, prevFix, nextFix) {
      const reasons = [];
      let impliedSpeedKmh = null;

      if (prevFix && nextFix) {
        const elapsedSec = (nextFix.timestamp - prevFix.timestamp) / 1000;
        if (elapsedSec >= MIN_INTERVAL_SEC_FOR_CHECK) {
          const distKm = window.HigalaConfig
            ? window.HigalaConfig.Geo.distanceKmBetween(prevFix, nextFix)
            : haversineFallback(prevFix, nextFix);
          impliedSpeedKmh = distKm / (elapsedSec / 3600);

          if (impliedSpeedKmh > MAX_PLAUSIBLE_SPEED_KMH) {
            reasons.push(`implausible speed: ${impliedSpeedKmh.toFixed(1)} km/h over ${elapsedSec.toFixed(1)}s`);
          }
        }

        if (
          typeof prevFix.accuracy === 'number' &&
          typeof nextFix.accuracy === 'number' &&
          Math.abs(nextFix.accuracy - prevFix.accuracy) > ACCURACY_JUMP_THRESHOLD_M
        ) {
          reasons.push(`accuracy jumped by ${Math.abs(nextFix.accuracy - prevFix.accuracy).toFixed(0)}m between fixes`);
        }
      }

      const suspicious = reasons.length > 0;
      if (suspicious) {
        reportFraudAlert({ orderId, driverId, reason: reasons.join('; '), evidence: { prevFix, nextFix, impliedSpeedKmh } });
      }

      return { suspicious, reasons, impliedSpeedKmh };
    }

    function haversineFallback(a, b) {
      const R = 6371;
      const toRad = (d) => (d * Math.PI) / 180;
      const dLat = toRad(b.lat - a.lat);
      const dLng = toRad(b.lng - a.lng);
      const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
      return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
    }

    async function reportFraudAlert(payload) {
      EventBus.emit('fraud:suspected', payload);
      try {
        await Api.request(Endpoints.fraudAlert(), {
          method: 'POST',
          body: payload,
          silent: true,
        });
      } catch (err) {
        // If the alert itself can't reach the server, queue it — admin
        // visibility into fraud should never be silently dropped.
        OfflineQueue.enqueue({
          endpoint: Endpoints.fraudAlert(),
          method: 'POST',
          body: payload,
          tag: 'fraud:alert',
        });
      }
    }

    return { checkGpsUpdate, MAX_PLAUSIBLE_SPEED_KMH };
  })();

  // Flush any queued actions once core signals it's ready / on load.
  document.addEventListener('DOMContentLoaded', () => OfflineQueue.flush());

  window.HigalaOrders = Object.freeze({
    Dispatch,
    State,
    OfflineQueue,
    Fraud,
    Endpoints,
  });
})(window, document);