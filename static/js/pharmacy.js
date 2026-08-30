/**
 * pharmacy.js
 * ---------------------------------------------------------------------------
 * Higala Express — Pharmacy Vertical: Add-to-Cart + Booking
 *
 * Load order: higala-core.js -> config.js -> cart.js -> orders.js -> pharmacy.js
 *
 * Adds, on top of the base add-to-cart pattern:
 *   - Prescription (Rx) photo capture/upload per line item
 *   - Free-text special instructions per line item
 *   - Split-dispatch: if the cart also contains items from other verticals
 *     (e.g. food) or multiple pharmacy merchants, checkout builds a
 *     multi-stop order so one rider can pick up from every merchant in a
 *     single trip instead of the customer placing separate orders.
 *
 * Backend contract:
 *   POST /orders   {
 *     service: 'pharmacy',
 *     merchantStops: [{ merchantId, items, subtotal, requiresPrescription }],
 *     dropoff: { lat, lng, address },
 *     fare: { ...breakdown },
 *     notes
 *   }
 *
 * DOM hooks:
 *   [data-add-to-cart][data-fulfillment-type="pharmacy"]
 *   [data-rx-upload="<productId>"]           <input type="file" accept="image/*">
 *                                             attaches Rx photo to the matching cart line
 *   [data-booking-action="checkout-pharmacy"]
 *   #pharmacy-dropoff-lat / -lng / -address
 *   #pharmacy-booking-lock-banner
 *   #pharmacy-fare-preview
 * ---------------------------------------------------------------------------
 */
(function (window, document) {
  'use strict';

  if (!window.HigalaCore || !window.HigalaCart || !window.HigalaOrders || !window.HigalaConfig) {
    console.error('[HigalaPharmacy] HigalaCore, HigalaConfig, HigalaCart, and HigalaOrders must be loaded before pharmacy.js');
    return;
  }
  if (window.HigalaPharmacy) return;

  const { Api, EventBus, Toast } = window.HigalaCore;
  const { Fare } = window.HigalaConfig;
  const { addItem, setLinePrescription, setLineNotes, getMerchantGroups, getTotals, getState } = window.HigalaCart;
  const { Dispatch, ActiveLock } = window.HigalaOrders;

  const VERTICAL = 'pharmacy';
  const ADD_BUTTON_SELECTOR = '[data-add-to-cart]';
  const RX_UPLOAD_SELECTOR = '[data-rx-upload]';
  const CHECKOUT_SELECTOR = '[data-booking-action="checkout-pharmacy"]';
  const MAX_RX_PHOTO_BYTES = 6 * 1024 * 1024; // 6MB, generous for a phone camera shot

  // ===========================================================================
  // Add-to-cart
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
          requiresPrescription: ds.requiresPrescription === 'true',
          notes: '',
        },
      },
    };
  }

  function handleAddClick(event) {
    const buttonEl = event.target instanceof Element ? event.target.closest(ADD_BUTTON_SELECTOR) : null;
    if (!buttonEl) return;
    if (buttonEl.dataset.fulfillmentType !== VERTICAL) return;
    if (buttonEl.disabled) return;

    const result = extractItemFromButton(buttonEl);
    if (!result.ok) {
      console.error('[HigalaPharmacy] cannot add item:', result.errors, buttonEl);
      Toast.error(result.errors.includes('out of stock') ? 'This item is currently out of stock.' : 'Sorry, this item is not available right now.');
      return;
    }

    if (result.item.meta.requiresPrescription) {
      Toast.info(`${result.item.name} requires a valid prescription — attach a photo before checkout.`);
    }

    buttonEl.disabled = true;
    try {
      addItem(result.item);
    } finally {
      setTimeout(() => { buttonEl.disabled = false; }, 150);
    }
  }

  // ===========================================================================
  // Prescription photo capture
  // ===========================================================================
  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error || new Error('Failed to read file'));
      reader.readAsDataURL(file);
    });
  }

  async function handleRxUploadChange(event) {
    const inputEl = event.target;
    if (!(inputEl instanceof HTMLInputElement) || !inputEl.matches(RX_UPLOAD_SELECTOR)) return;

    const productId = inputEl.getAttribute('data-rx-upload');
    const file = inputEl.files && inputEl.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      Toast.error('Please upload an image of your prescription (JPG or PNG).');
      inputEl.value = '';
      return;
    }
    if (file.size > MAX_RX_PHOTO_BYTES) {
      Toast.error('That photo is too large — please upload one under 6MB.');
      inputEl.value = '';
      return;
    }

    // Find the matching cart line(s) for this product across all merchants.
    const matchingLines = getState().items.filter((l) => l.fulfillment_type === VERTICAL && l.id === productId);
    if (matchingLines.length === 0) {
      Toast.error('Add the medicine to your cart first, then attach the prescription.');
      inputEl.value = '';
      return;
    }

    try {
      const dataUrl = await readFileAsDataUrl(file);
      matchingLines.forEach((line) => setLinePrescription(line.lineId, dataUrl));
    } catch (err) {
      console.error('[HigalaPharmacy] failed to read Rx photo:', err);
      Toast.error('Could not read that photo. Please try again.');
    }
  }

  // ===========================================================================
  // Special instructions — reuses the cart's generic notes editor, but
  // pharmacy.js also exposes a direct setter for a dedicated notes field on
  // the product card, if the page has one (data-pharmacy-notes-for).
  // ===========================================================================
  function handleNotesChange(event) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const productId = target.getAttribute('data-pharmacy-notes-for');
    if (!productId) return;

    const matchingLines = getState().items.filter((l) => l.fulfillment_type === VERTICAL && l.id === productId);
    matchingLines.forEach((line) => setLineNotes(line.lineId, target.value));
  }

  // ===========================================================================
  // Checkout readiness — every pharmacy line that requires a prescription
  // must have a photo attached before checkout is allowed. This is checked
  // fresh at click time, not just cached at add-time, since a photo can be
  // removed or a merged line can pick up a new quantity later.
  // ===========================================================================
  function getMissingPrescriptions() {
    return getState().items.filter(
      (l) => l.fulfillment_type === VERTICAL && l.meta.requiresPrescription && !l.meta.prescriptionImageDataUrl
    );
  }

  function round2(n) {
    return Math.round((n + Number.EPSILON) * 100) / 100;
  }

  function readDropoff() {
    const latEl = document.getElementById('pharmacy-dropoff-lat');
    const lngEl = document.getElementById('pharmacy-dropoff-lng');
    const addrEl = document.getElementById('pharmacy-dropoff-address');

    const lat = latEl ? Number(latEl.value) : NaN;
    const lng = lngEl ? Number(lngEl.value) : NaN;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return { lat, lng, address: addrEl ? addrEl.value : '' };
  }

  /**
   * Builds the multi-stop pickup list for this order: every merchant
   * represented in the cart (pharmacy AND any other vertical already
   * present, e.g. food) becomes one pickup stop, so a single rider can
   * fulfill a mixed cart in one trip. This is the "split-dispatch" the
   * booking flow hands to the backend/dispatcher.
   */
  function buildMerchantStops() {
    return getMerchantGroups().map((g) => ({
      merchantId: g.merchantId,
      verticals: g.verticals,
      items: g.items,
      subtotal: g.subtotal,
      requiresPrescription: g.requiresPrescription,
    }));
  }

  async function estimateFareForStops(stops, dropoff) {
    const checkoutBtn = document.querySelector(CHECKOUT_SELECTOR);
    const primaryPickupLat = checkoutBtn ? Number(checkoutBtn.dataset.merchantLat) : NaN;
    const primaryPickupLng = checkoutBtn ? Number(checkoutBtn.dataset.merchantLng) : NaN;
    const primaryPickup = Number.isFinite(primaryPickupLat) && Number.isFinite(primaryPickupLng)
      ? { lat: primaryPickupLat, lng: primaryPickupLng }
      : dropoff;

    // Multi-stop distance = sum of leg distances (pickup1 -> pickup2 -> ... -> dropoff).
    // Without per-merchant coordinates wired up on the page, we fall back to
    // treating the primary pickup as the sole stop; pass merchant coordinates
    // via data-merchant-lat/lng on each stop's DOM node to get true multi-leg
    // distance once your merchant catalog exposes them.
    const distanceKm = window.HigalaConfig.Geo.distanceKmBetween(primaryPickup, dropoff);
    const weather = await window.HigalaConfig.Surge.getWeatherMultiplier();

    return Fare.compute({
      service: stops.length > 1 ? 'delivery' : 'pharmacy',
      distanceKm,
      pickupPoint: primaryPickup,
      weatherMultiplier: weather.multiplier,
    });
  }

  async function updateFarePreview() {
    const previewEl = document.getElementById('pharmacy-fare-preview');
    if (!previewEl) return;

    const dropoff = readDropoff();
    const stops = buildMerchantStops();
    if (!dropoff || stops.length === 0) {
      previewEl.textContent = '';
      return;
    }

    const fare = await estimateFareForStops(stops, dropoff);
    const cartTotals = getTotals();
    const grandTotal = round2(cartTotals.subtotal - cartTotals.discount + fare.total);
    const missing = getMissingPrescriptions();

    previewEl.innerHTML = `
      Pharmacy subtotal: \u20b1${cartTotals.subtotal.toFixed(2)}<br>
      Delivery fare: \u20b1${fare.total.toFixed(2)}${stops.length > 1 ? ` (${stops.length} pickup stops)` : ''}<br>
      <strong>Estimated total: \u20b1${grandTotal.toFixed(2)}</strong>
      ${missing.length ? `<p class="higala-fare-warning">${missing.length} item(s) still need a prescription photo.</p>` : ''}
    `;
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

    const stops = buildMerchantStops();
    if (stops.length === 0) {
      Toast.error('Your cart has no items to check out.');
      return;
    }

    const missing = getMissingPrescriptions();
    if (missing.length > 0) {
      Toast.error(`Attach a prescription photo for: ${missing.map((l) => l.name).join(', ')}`);
      return;
    }

    const fare = await estimateFareForStops(stops, dropoff);

    buttonEl.disabled = true;
    buttonEl.textContent = 'Placing order...';

    try {
      const order = await Api.post('/orders', {
        service: VERTICAL,
        merchantStops: stops,
        dropoff,
        fare,
        notes: (document.getElementById('pharmacy-order-notes') || {}).value || '',
      });

      ActiveLock.setActive({ id: order.id, service: VERTICAL, state: order.state || 'searching' });
      Dispatch.broadcast(order);
      EventBus.emit('pharmacy:orderPlaced', { order, multiStop: stops.length > 1 });
      Toast.success(
        stops.length > 1
          ? `Order placed across ${stops.length} stops! Looking for a nearby rider...`
          : 'Order placed! Looking for a nearby rider...'
      );
      window.HigalaCart.clear();
    } catch (err) {
      console.error('[HigalaPharmacy] checkout failed:', err);
      // Api already toasts network/server errors.
    } finally {
      buttonEl.disabled = ActiveLock.isLocked();
      buttonEl.textContent = 'Place order';
    }
  }

  // ===========================================================================
  // Active Ride Lock wiring
  // ===========================================================================
  function syncLockUI() {
    ActiveLock.syncBookingUI({
      selector: '[data-booking-action]',
      bannerEl: document.getElementById('pharmacy-booking-lock-banner'),
    });
  }

  function init() {
    document.addEventListener('click', handleAddClick);
    document.addEventListener('change', handleRxUploadChange);
    document.addEventListener('change', handleNotesChange);

    const checkoutBtn = document.querySelector(CHECKOUT_SELECTOR);
    if (checkoutBtn) checkoutBtn.addEventListener('click', handleCheckout);

    ['pharmacy-dropoff-lat', 'pharmacy-dropoff-lng'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('change', updateFarePreview);
    });

    EventBus.on('cart:change', updateFarePreview);
    EventBus.on('map:dropoffSelected', updateFarePreview);
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

  window.HigalaPharmacy = Object.freeze({
    vertical: VERTICAL,
    extractItemFromButton,
    getMissingPrescriptions,
    updateFarePreview,
  });
})(window, document);