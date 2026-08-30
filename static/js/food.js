/**
 * food.js
 * ---------------------------------------------------------------------------
 * Higala Express — Food Vertical: Add-to-Cart + Booking
 *
 * Load order: higala-core.js -> config.js -> cart.js -> orders.js -> food.js
 *
 * Backend contract this file expects:
 *   POST /orders   {
 *     service: 'food',
 *     merchantStops: [{ merchantId, items: [...], subtotal }],
 *     dropoff: { lat, lng, address },
 *     fare: { ...breakdown from HigalaConfig.Fare.compute },
 *     notes
 *   }  -> { id, state: 'searching', ... }
 *
 * DOM hooks (all optional/defensive — missing ones simply mean that part of
 * the page isn't present):
 *   [data-add-to-cart]                      product "Add" buttons (see pharmacy.js for shape)
 *   [data-booking-action="checkout-food"]    the "Place order" / checkout button
 *   #food-dropoff-lat / #food-dropoff-lng / #food-dropoff-address   hidden inputs set by map.js
 *   #food-booking-lock-banner               shown while ActiveLock is engaged
 *   #food-fare-preview                      live fare breakdown display
 * ---------------------------------------------------------------------------
 */
(function (window, document) {
  'use strict';

  if (!window.HigalaCore || !window.HigalaCart || !window.HigalaOrders || !window.HigalaConfig) {
    console.error('[HigalaFood] HigalaCore, HigalaConfig, HigalaCart, and HigalaOrders must be loaded before food.js');
    return;
  }
  if (window.HigalaFood) return;

  const { Api, EventBus, Toast } = window.HigalaCore;
  const { Fare } = window.HigalaConfig;
  const { addItem, getMerchantGroups, getTotals } = window.HigalaCart;
  const { Dispatch, ActiveLock } = window.HigalaOrders;

  const VERTICAL = 'food';
  const ADD_BUTTON_SELECTOR = '[data-add-to-cart]';
  const CHECKOUT_SELECTOR = '[data-booking-action="checkout-food"]';

  // ===========================================================================
  // Add-to-cart (mirrors pharmacy.js's pattern; food-specific metadata is
  // add-ons + spice level + free-text notes rather than prescriptions)
  // ===========================================================================
  function extractItemFromButton(buttonEl) {
    const ds = buttonEl.dataset;
    const errors = [];

    const id = (ds.id || '').trim();
    if (!id) errors.push('missing data-id');

    const name = (ds.name || '').trim();
    if (!name) errors.push('missing data-name');

    const price = Number(ds.price);
    if (!Number.isFinite(price) || price < 0) errors.push('missing/invalid data-price');

    const merchantId = (ds.merchantId || '').trim();
    if (!merchantId) errors.push('missing data-merchant-id');

    const stock = ds.stock != null ? Number(ds.stock) : null;
    if (stock != null && Number.isFinite(stock) && stock <= 0) errors.push('out of stock');

    if (errors.length) return { ok: false, errors };

    let addOns = [];
    if (ds.addons) {
      try {
        addOns = JSON.parse(ds.addons); // e.g. data-addons='[{"name":"Extra rice","price":15}]'
      } catch (err) {
        console.warn('[HigalaFood] could not parse data-addons JSON, ignoring add-ons:', err);
      }
    }

    return {
      ok: true,
      item: {
        id,
        name,
        price,
        merchantId,
        fulfillment_type: VERTICAL,
        quantity: 1,
        imageUrl: ds.imageUrl || '',
        meta: {
          variant: ds.variant || undefined,
          notes: ds.spiceLevel ? `Spice level: ${ds.spiceLevel}` : '',
          addOns,
        },
      },
    };
  }

  function handleAddClick(event) {
    const buttonEl = event.target instanceof Element ? event.target.closest(ADD_BUTTON_SELECTOR) : null;
    if (!buttonEl) return;
    // Only handle buttons explicitly marked for food; pharmacy.js/grocery.js
    // etc. each own their own fulfillment_type so both scripts can share a page.
    if (buttonEl.dataset.fulfillmentType !== VERTICAL) return;
    if (buttonEl.disabled) return;

    const result = extractItemFromButton(buttonEl);
    if (!result.ok) {
      console.error('[HigalaFood] cannot add item:', result.errors, buttonEl);
      Toast.error(result.errors.includes('out of stock') ? 'This item is currently out of stock.' : 'Sorry, this item is not available right now.');
      return;
    }

    buttonEl.disabled = true;
    try {
      addItem(result.item);
    } finally {
      setTimeout(() => { buttonEl.disabled = false; }, 150);
    }
  }

  // ===========================================================================
  // Booking / checkout
  // ===========================================================================
  function readDropoff() {
    const latEl = document.getElementById('food-dropoff-lat');
    const lngEl = document.getElementById('food-dropoff-lng');
    const addrEl = document.getElementById('food-dropoff-address');

    const lat = latEl ? Number(latEl.value) : NaN;
    const lng = lngEl ? Number(lngEl.value) : NaN;

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return { lat, lng, address: addrEl ? addrEl.value : '' };
  }

  /**
   * Recomputes and displays the live fare estimate as soon as a dropoff
   * point is available and there's at least one food item in the cart.
   * Pickup point defaults to the first merchant's registered coordinates
   * (data-merchant-lat/lng on the checkout button, set by the page) if present.
   */
  async function updateFarePreview() {
    const previewEl = document.getElementById('food-fare-preview');
    if (!previewEl) return;

    const dropoff = readDropoff();
    const groups = getMerchantGroups().filter((g) => g.verticals.includes(VERTICAL));
    if (!dropoff || groups.length === 0) {
      previewEl.textContent = '';
      return;
    }

    const checkoutBtn = document.querySelector(CHECKOUT_SELECTOR);
    const pickupLat = checkoutBtn ? Number(checkoutBtn.dataset.merchantLat) : NaN;
    const pickupLng = checkoutBtn ? Number(checkoutBtn.dataset.merchantLng) : NaN;
    const pickup = Number.isFinite(pickupLat) && Number.isFinite(pickupLng) ? { lat: pickupLat, lng: pickupLng } : dropoff;

    const distanceKm = window.HigalaConfig.Geo.distanceKmBetween(pickup, dropoff);
    const weather = await window.HigalaConfig.Surge.getWeatherMultiplier();

    const fare = Fare.compute({
      service: 'food',
      distanceKm,
      pickupPoint: pickup,
      weatherMultiplier: weather.multiplier,
    });

    const cartTotals = getTotals();
    const grandTotal = round2(cartTotals.subtotal - cartTotals.discount + fare.total);

    previewEl.innerHTML = `
      Food subtotal: \u20b1${cartTotals.subtotal.toFixed(2)}<br>
      Delivery fare: \u20b1${fare.total.toFixed(2)} (${distanceKm.toFixed(1)} km${fare.surge.combinedMultiplier > 1 ? `, \u00d7${fare.surge.combinedMultiplier} surge` : ''})<br>
      <strong>Estimated total: \u20b1${grandTotal.toFixed(2)}</strong>
    `;
  }

  function round2(n) {
    return Math.round((n + Number.EPSILON) * 100) / 100;
  }

  async function handleCheckout(event) {
    const buttonEl = event.currentTarget;

    if (ActiveLock.isLocked()) {
      Toast.error('You already have an active order in progress. Finish it before booking another.');
      return;
    }

    const dropoff = readDropoff();
    if (!dropoff) {
      Toast.error('Please select a delivery location on the map first.');
      return;
    }

    const groups = getMerchantGroups().filter((g) => g.verticals.includes(VERTICAL));
    if (groups.length === 0) {
      Toast.error('Your cart has no food items to check out.');
      return;
    }

    const pickupLat = Number(buttonEl.dataset.merchantLat);
    const pickupLng = Number(buttonEl.dataset.merchantLng);
    const pickup = Number.isFinite(pickupLat) && Number.isFinite(pickupLng) ? { lat: pickupLat, lng: pickupLng } : dropoff;
    const distanceKm = window.HigalaConfig.Geo.distanceKmBetween(pickup, dropoff);
    const weather = await window.HigalaConfig.Surge.getWeatherMultiplier();

    const fare = Fare.compute({
      service: 'food',
      distanceKm,
      pickupPoint: pickup,
      weatherMultiplier: weather.multiplier,
    });

    buttonEl.disabled = true;
    buttonEl.textContent = 'Placing order...';

    try {
      const order = await Api.post('/orders', {
        service: VERTICAL,
        merchantStops: groups.map((g) => ({ merchantId: g.merchantId, items: g.items, subtotal: g.subtotal })),
        dropoff,
        fare,
        notes: (document.getElementById('food-order-notes') || {}).value || '',
      });

      ActiveLock.setActive({ id: order.id, service: VERTICAL, state: order.state || 'searching' });
      Dispatch.broadcast(order);
      EventBus.emit('food:orderPlaced', { order });
      Toast.success('Order placed! Looking for a nearby rider...');
      window.HigalaCart.clear();
    } catch (err) {
      console.error('[HigalaFood] checkout failed:', err);
      // Api already toasts network/server errors; nothing further needed here.
    } finally {
      buttonEl.disabled = ActiveLock.isLocked();
      buttonEl.textContent = 'Place order';
    }
  }

  // ===========================================================================
  // Active Ride Lock wiring — keeps the checkout button, dropoff picker, and
  // any other [data-booking-action] control in sync with lock state at all
  // times, not just at page load.
  // ===========================================================================
  function syncLockUI() {
    ActiveLock.syncBookingUI({
      selector: '[data-booking-action]',
      bannerEl: document.getElementById('food-booking-lock-banner'),
    });
  }

  function init() {
    document.addEventListener('click', handleAddClick);

    const checkoutBtn = document.querySelector(CHECKOUT_SELECTOR);
    if (checkoutBtn) checkoutBtn.addEventListener('click', handleCheckout);

    ['food-dropoff-lat', 'food-dropoff-lng'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('change', updateFarePreview);
    });

    EventBus.on('cart:change', updateFarePreview);
    EventBus.on('map:dropoffSelected', updateFarePreview); // emitted by map.js
    EventBus.on('activeLock:set', syncLockUI);
    EventBus.on('activeLock:clear', syncLockUI);
    EventBus.on('activeLock:update', syncLockUI);

    syncLockUI();
    updateFarePreview();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.HigalaFood = Object.freeze({
    vertical: VERTICAL,
    extractItemFromButton,
    updateFarePreview,
  });
})(window, document);