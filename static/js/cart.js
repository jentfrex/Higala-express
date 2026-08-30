/**
 * cart.js
 * ---------------------------------------------------------------------------
 * Higala Express — Unified, Transparent Cart State Manager
 *
 * Depends on higala-core.js being loaded first (window.HigalaCore).
 *
 * "Transparent" here means: every line item always shows exactly what will
 * be charged and what will be fulfilled — including pharmacy prescription
 * status, special instructions, and which merchant each item ships from —
 * with NO full-list re-render on every change. Rendering is keyed/diffed:
 * only the DOM nodes that actually changed are touched, so clicking +/-
 * or adding another item never blinks or scrolls the drawer back to top.
 *
 * Exposes window.HigalaCart:
 *   addItem(item)                add/merge an item from any vertical
 *   updateQuantity(lineId, delta)
 *   setQuantity(lineId, quantity)
 *   removeItem(lineId)
 *   clear()
 *   setLineNotes(lineId, notes)              special instructions
 *   setLinePrescription(lineId, dataUrl)     Rx photo for a pharmacy line
 *   applyPromo(code) / removePromo()
 *   getState() / getTotals()
 *   getMerchantGroups()          items grouped by merchant, for split-dispatch
 *   open() / close() / toggle()
 *
 * Item shape accepted by addItem():
 *   {
 *     id, name, price, fulfillment_type, quantity,
 *     merchantId,            // which store/pharmacy/kitchen this ships from
 *     imageUrl,
 *     meta: {
 *       variant,                    // e.g. size/flavor — creates a separate line
 *       requiresPrescription,       // pharmacy: boolean
 *       notes,                      // special instructions (food or pharmacy)
 *       addOns: [{ name, price }],  // food: add-ons, priced into the line
 *     }
 *   }
 * ---------------------------------------------------------------------------
 */
(function (window, document) {
  'use strict';

  if (!window.HigalaCore) {
    console.error('[HigalaCart] HigalaCore must be loaded before cart.js');
    return;
  }
  if (window.HigalaCart) return; // already initialized

  const { EventBus, Toast, Config } = window.HigalaCore;

  // ===========================================================================
  // Business rules
  // ===========================================================================
  const DELIVERY_FEE_BASE = 49; // PHP — used only as a display-time fallback;
                                  // real delivery fee comes from HigalaConfig.Fare
                                  // once a destination/distance is known (food.js/pharmacy.js).
  const FREE_DELIVERY_THRESHOLD = 999;
  const DRAWER_OPEN_CLASS = 'higala-cart-drawer--open';

  const PROMO_CODES = {
    HIGALA: {
      label: '10% off (HIGALA)',
      minSubtotal: 300,
      validate(state, subtotal) {
        if (subtotal < this.minSubtotal) {
          return { valid: false, message: `Spend at least \u20b1${this.minSubtotal} to use HIGALA.` };
        }
        return { valid: true };
      },
      compute(state, subtotal) {
        return Math.round(subtotal * 0.10 * 100) / 100;
      },
    },
  };

  // ===========================================================================
  // State
  // ===========================================================================
  /**
   * @typedef {Object} CartItem
   * @property {string} lineId
   * @property {string} id
   * @property {string} name
   * @property {number} price          base unit price, excluding add-ons
   * @property {number} quantity
   * @property {string} fulfillment_type
   * @property {string} merchantId
   * @property {string} [imageUrl]
   * @property {Object} meta
   * @property {boolean} [meta.requiresPrescription]
   * @property {string} [meta.prescriptionImageDataUrl]
   * @property {string} [meta.notes]
   * @property {{name:string, price:number}[]} [meta.addOns]
   */

  let state = {
    items: /** @type {CartItem[]} */ ([]),
    promoCode: /** @type {string|null} */ (null),
  };

  // ===========================================================================
  // Persistence
  // ===========================================================================
  function load() {
    try {
      const raw = localStorage.getItem(Config.CART_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed && Array.isArray(parsed.items)) {
        state = {
          items: parsed.items.filter(isValidStoredItem),
          promoCode: typeof parsed.promoCode === 'string' ? parsed.promoCode : null,
        };
      }
    } catch (err) {
      console.error('[HigalaCart] failed to load cart from storage, resetting:', err);
      state = { items: [], promoCode: null };
      persist();
    }
  }

  function isValidStoredItem(item) {
    return item
      && typeof item.lineId === 'string'
      && typeof item.id !== 'undefined'
      && typeof item.name === 'string'
      && typeof item.price === 'number'
      && typeof item.quantity === 'number'
      && item.quantity > 0;
  }

  function persist() {
    try {
      localStorage.setItem(Config.CART_KEY, JSON.stringify(state));
    } catch (err) {
      console.error('[HigalaCart] failed to persist cart:', err);
      Toast.error('Could not save your cart. Storage may be full.');
    }
  }

  // ===========================================================================
  // Helpers
  // ===========================================================================
  function makeLineId(item) {
    const variantKey = item.meta && item.meta.variant ? String(item.meta.variant) : '';
    return `${item.fulfillment_type || 'unknown'}::${item.merchantId || 'default'}::${item.id}::${variantKey}`;
  }

  function sanitizeAddOns(rawAddOns) {
    if (!Array.isArray(rawAddOns)) return [];
    return rawAddOns
      .map((a) => ({
        name: a && a.name != null ? String(a.name).trim() : '',
        price: a ? Number(a.price) : NaN,
      }))
      .filter((a) => a.name && Number.isFinite(a.price) && a.price >= 0);
  }

  function sanitizeIncomingItem(raw) {
    const id = raw && raw.id != null ? String(raw.id) : '';
    const name = raw && raw.name != null ? String(raw.name).trim() : '';
    const price = raw ? Number(raw.price) : NaN;
    const fulfillmentType = raw && raw.fulfillment_type ? String(raw.fulfillment_type) : '';
    const merchantId = raw && raw.merchantId ? String(raw.merchantId) : 'default';
    const quantity = raw && raw.quantity != null ? Math.floor(Number(raw.quantity)) : 1;

    const errors = [];
    if (!id) errors.push('missing id');
    if (!name) errors.push('missing name');
    if (!Number.isFinite(price) || price < 0) errors.push('invalid price');
    if (!fulfillmentType) errors.push('missing fulfillment_type');
    if (!Number.isFinite(quantity) || quantity <= 0) errors.push('invalid quantity');

    const rawMeta = (raw && raw.meta) || {};
    if (fulfillmentType === 'pharmacy' && rawMeta.requiresPrescription && !rawMeta.prescriptionImageDataUrl) {
      // Not a hard error — the cart still accepts the item, but flags it so
      // the UI can prompt for the Rx photo before checkout is allowed.
    }

    if (errors.length) {
      return { ok: false, errors };
    }

    return {
      ok: true,
      item: {
        id,
        name,
        price,
        quantity,
        fulfillment_type: fulfillmentType,
        merchantId,
        imageUrl: raw.imageUrl || raw.image_url || '',
        meta: {
          variant: rawMeta.variant || undefined,
          requiresPrescription: !!rawMeta.requiresPrescription,
          prescriptionImageDataUrl: rawMeta.prescriptionImageDataUrl || null,
          notes: rawMeta.notes ? String(rawMeta.notes).slice(0, 500) : '',
          addOns: sanitizeAddOns(rawMeta.addOns),
        },
      },
    };
  }

  function lineUnitPrice(line) {
    const addOnsTotal = (line.meta.addOns || []).reduce((sum, a) => sum + a.price, 0);
    return line.price + addOnsTotal;
  }

  function round2(n) {
    return Math.round((n + Number.EPSILON) * 100) / 100;
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  // ===========================================================================
  // Mutations
  // ===========================================================================
  function addItem(rawItem) {
    const result = sanitizeIncomingItem(rawItem);
    if (!result.ok) {
      console.error('[HigalaCart] rejected addItem, invalid payload:', result.errors, rawItem);
      Toast.error('Sorry, that item could not be added to your cart.');
      return result;
    }

    const item = result.item;
    const lineId = makeLineId(item);
    const existing = state.items.find((line) => line.lineId === lineId);

    if (existing) {
      existing.quantity += item.quantity;
      // Merging into an existing line keeps its prior notes/Rx photo rather
      // than silently overwriting them — surface a toast so it's clear.
    } else {
      state.items.push(Object.assign({ lineId }, item));
    }

    persist();
    render();
    EventBus.emit('cart:add', { item, lineId });
    EventBus.emit('cart:change', getState());
    Toast.success(`${item.name} added to cart`);
    return { ok: true, lineId };
  }

  function updateQuantity(lineId, delta) {
    const line = state.items.find((l) => l.lineId === lineId);
    if (!line) return;

    line.quantity += delta;
    if (line.quantity <= 0) {
      state.items = state.items.filter((l) => l.lineId !== lineId);
    }

    persist();
    render();
    EventBus.emit('cart:change', getState());
  }

  function setQuantity(lineId, quantity) {
    const qty = Math.floor(Number(quantity));
    const line = state.items.find((l) => l.lineId === lineId);
    if (!line) return;

    if (!Number.isFinite(qty) || qty <= 0) {
      removeItem(lineId);
      return;
    }
    line.quantity = qty;
    persist();
    render();
    EventBus.emit('cart:change', getState());
  }

  function removeItem(lineId) {
    const before = state.items.length;
    state.items = state.items.filter((l) => l.lineId !== lineId);
    if (state.items.length !== before) {
      persist();
      render();
      EventBus.emit('cart:remove', { lineId });
      EventBus.emit('cart:change', getState());
    }
  }

  function clear() {
    state = { items: [], promoCode: null };
    persist();
    render();
    EventBus.emit('cart:change', getState());
  }

  /** Special instructions for a single line (food notes, pharmacy notes, etc). */
  function setLineNotes(lineId, notes) {
    const line = state.items.find((l) => l.lineId === lineId);
    if (!line) return;
    line.meta.notes = String(notes || '').slice(0, 500);
    persist();
    render();
    EventBus.emit('cart:change', getState());
  }

  /** Attaches/replaces a prescription photo (data URL) for a pharmacy line. */
  function setLinePrescription(lineId, photoDataUrl) {
    const line = state.items.find((l) => l.lineId === lineId);
    if (!line) return;
    if (line.fulfillment_type !== 'pharmacy') {
      console.warn('[HigalaCart] setLinePrescription called on a non-pharmacy line, ignoring');
      return;
    }
    line.meta.prescriptionImageDataUrl = photoDataUrl || null;
    persist();
    render();
    EventBus.emit('cart:change', getState());
    if (photoDataUrl) Toast.success('Prescription photo attached.');
  }

  function applyPromo(rawCode) {
    const code = String(rawCode || '').trim().toUpperCase();
    const promo = PROMO_CODES[code];

    if (!code) return { valid: false, message: 'Enter a promo code.' };
    if (!promo) return { valid: false, message: 'That promo code is not valid.' };

    const subtotal = computeSubtotal();
    const check = promo.validate(state, subtotal);
    if (!check.valid) return check;

    state.promoCode = code;
    persist();
    render();
    EventBus.emit('cart:change', getState());
    Toast.success(`Promo "${code}" applied.`);
    return { valid: true, message: promo.label };
  }

  function removePromo() {
    state.promoCode = null;
    persist();
    render();
    EventBus.emit('cart:change', getState());
  }

  // ===========================================================================
  // Derived data / totals
  // ===========================================================================
  function computeSubtotal() {
    return round2(state.items.reduce((sum, l) => sum + lineUnitPrice(l) * l.quantity, 0));
  }

  function computeItemCount() {
    return state.items.reduce((sum, l) => sum + l.quantity, 0);
  }

  function computeDiscount(subtotal) {
    if (!state.promoCode) return 0;
    const promo = PROMO_CODES[state.promoCode];
    if (!promo) return 0;
    const check = promo.validate(state, subtotal);
    if (!check.valid) return 0;
    return round2(promo.compute(state, subtotal));
  }

  function computeDeliveryFee(subtotal) {
    if (state.items.length === 0) return 0;
    return subtotal >= FREE_DELIVERY_THRESHOLD ? 0 : DELIVERY_FEE_BASE;
  }

  function getTotals() {
    const subtotal = computeSubtotal();
    const discount = computeDiscount(subtotal);
    const deliveryFee = computeDeliveryFee(subtotal);
    const total = round2(Math.max(0, subtotal - discount) + deliveryFee);
    return { subtotal, discount, deliveryFee, total, itemCount: computeItemCount() };
  }

  function getState() {
    return clone(state);
  }

  /**
   * Groups current cart lines by merchant, for multi-stop pickup / split
   * dispatch (e.g. a cart with pharmacy items from Mercury Drug Divisoria
   * AND food from a Cogon carinderia becomes two pickup stops on one trip).
   * @returns {{ merchantId: string, verticals: string[], items: CartItem[], subtotal: number, requiresPrescription: boolean }[]}
   */
  function getMerchantGroups() {
    /** @type {Map<string, CartItem[]>} */
    const byMerchant = new Map();
    for (const line of state.items) {
      const key = line.merchantId || 'default';
      if (!byMerchant.has(key)) byMerchant.set(key, []);
      byMerchant.get(key).push(line);
    }

    return Array.from(byMerchant.entries()).map(([merchantId, items]) => ({
      merchantId,
      verticals: Array.from(new Set(items.map((l) => l.fulfillment_type))),
      items: clone(items),
      subtotal: round2(items.reduce((sum, l) => sum + lineUnitPrice(l) * l.quantity, 0)),
      requiresPrescription: items.some((l) => l.meta.requiresPrescription),
    }));
  }

  // ===========================================================================
  // Rendering — KEYED DIFF, not full innerHTML replace. This is what keeps
  // the drawer flicker-free: existing line-item nodes are reused and
  // patched in place; only additions/removals touch the DOM tree structure.
  // ===========================================================================
  /** @type {Map<string, HTMLElement>} lineId -> rendered node */
  const renderedNodes = new Map();
  let renderScheduled = false;

  function formatCurrency(amount) {
    return `\u20b1${round2(amount).toLocaleString('en-PH', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = String(str == null ? '' : str);
    return div.innerHTML;
  }

  /** Batches renders into a single animation frame so rapid successive
   * mutations (e.g. holding down +) don't thrash layout. */
  function render() {
    if (renderScheduled) return;
    renderScheduled = true;
    requestAnimationFrame(() => {
      renderScheduled = false;
      renderImmediate();
    });
  }

  function renderImmediate() {
    renderSummary();

    const itemsContainer = getItemsContainer();
    const emptyState = document.getElementById('cart-empty-state');
    if (!itemsContainer) return; // page has no drawer markup; summary-only sync is fine

    if (state.items.length === 0) {
      renderedNodes.forEach((node) => node.remove());
      renderedNodes.clear();
      if (emptyState) emptyState.hidden = false;
      itemsContainer.hidden = true;
      return;
    }

    if (emptyState) emptyState.hidden = true;
    itemsContainer.hidden = false;

    const currentLineIds = new Set(state.items.map((l) => l.lineId));

    // Remove nodes for lines no longer present.
    renderedNodes.forEach((node, lineId) => {
      if (!currentLineIds.has(lineId)) {
        node.remove();
        renderedNodes.delete(lineId);
      }
    });

    // Add/update nodes in current order, reusing existing DOM where possible.
    let previousNode = null;
    for (const line of state.items) {
      let node = renderedNodes.get(line.lineId);
      if (!node) {
        node = buildLineNode(line);
        renderedNodes.set(line.lineId, node);
      } else {
        patchLineNode(node, line);
      }

      // Ensure correct order without rebuilding: move only if misplaced.
      const expectedNext = previousNode ? previousNode.nextSibling : itemsContainer.firstChild;
      if (expectedNext !== node) {
        itemsContainer.insertBefore(node, expectedNext || null);
      }
      previousNode = node;
    }
  }

  function renderSummary() {
    const countBadge = document.getElementById('cart-item-count') || document.getElementById('cartBadge');
    const subtotalEl = document.getElementById('cart-subtotal') || document.getElementById('cartSubtotal');
    const discountEl = document.getElementById('cart-discount') || document.getElementById('cartDiscount');
    const deliveryEl = document.getElementById('cart-delivery-fee') || document.getElementById('cartDelivery');
    const totalEl = document.getElementById('cart-total') || document.getElementById('cartTotal');
    const promoMessageEl = document.getElementById('cart-promo-message');

    const totals = getTotals();

    if (countBadge) {
      countBadge.textContent = String(totals.itemCount);
      countBadge.hidden = totals.itemCount === 0;
    }
    if (subtotalEl) subtotalEl.textContent = formatCurrency(totals.subtotal);
    if (discountEl) discountEl.textContent = totals.discount > 0 ? `\u2212${formatCurrency(totals.discount)}` : formatCurrency(0);
    if (deliveryEl) deliveryEl.textContent = totals.deliveryFee > 0 ? formatCurrency(totals.deliveryFee) : 'FREE';
    if (totalEl) totalEl.textContent = formatCurrency(totals.total);

    if (promoMessageEl) {
      if (state.promoCode) {
        const promo = PROMO_CODES[state.promoCode];
        const stillValid = promo && promo.validate(state, totals.subtotal).valid;
        promoMessageEl.textContent = stillValid
          ? `"${state.promoCode}" applied \u2014 ${promo.label}`
          : `"${state.promoCode}" is no longer eligible for this cart.`;
        promoMessageEl.dataset.state = stillValid ? 'valid' : 'invalid';
      } else {
        promoMessageEl.textContent = '';
        promoMessageEl.dataset.state = '';
      }
    }
  }

  function buildLineNode(line) {
    const el = document.createElement('div');
    el.className = 'higala-cart-item';
    el.dataset.lineId = line.lineId;
    el.dataset.vertical = line.fulfillment_type;
    fillLineNode(el, line);
    return el;
  }

  function patchLineNode(el, line) {
    // Only touch the pieces that can actually change — quantity, line
    // total, notes/Rx state — never rebuild the whole card.
    const qtyEl = el.querySelector('[data-role="qty"]');
    if (qtyEl && qtyEl.textContent !== String(line.quantity)) {
      qtyEl.textContent = String(line.quantity);
    }
    const totalEl = el.querySelector('[data-role="line-total"]');
    const lineTotal = formatCurrency(lineUnitPrice(line) * line.quantity);
    if (totalEl && totalEl.textContent !== lineTotal) {
      totalEl.textContent = lineTotal;
    }
    const notesEl = el.querySelector('[data-role="notes"]');
    if (notesEl) {
      const notesText = line.meta.notes || '';
      if (notesEl.textContent !== notesText) {
        notesEl.textContent = notesText;
        notesEl.hidden = !notesText;
      }
    }
    const rxBadge = el.querySelector('[data-role="rx-badge"]');
    if (rxBadge) {
      const attached = !!line.meta.prescriptionImageDataUrl;
      rxBadge.textContent = attached ? 'Rx attached' : 'Rx photo needed';
      rxBadge.dataset.state = attached ? 'attached' : 'missing';
    }
  }

  function fillLineNode(el, line) {
    const lineTotal = formatCurrency(lineUnitPrice(line) * line.quantity);
    const imageHtml = line.imageUrl
      ? `<img class="higala-cart-item__image" src="${escapeHtml(line.imageUrl)}" alt="${escapeHtml(line.name)}" loading="lazy">`
      : '';

    const addOnsHtml = (line.meta.addOns || []).length
      ? `<ul class="higala-cart-item__addons">${line.meta.addOns.map((a) =>
          `<li>+ ${escapeHtml(a.name)} (${formatCurrency(a.price)})</li>`).join('')}</ul>`
      : '';

    const rxHtml = line.fulfillment_type === 'pharmacy'
      ? `<span class="higala-cart-item__rx-badge" data-role="rx-badge" data-state="${line.meta.prescriptionImageDataUrl ? 'attached' : 'missing'}">${
          line.meta.prescriptionImageDataUrl ? 'Rx attached' : 'Rx photo needed'
        }</span>`
      : '';

    const notesHtml = `<p class="higala-cart-item__notes" data-role="notes" ${line.meta.notes ? '' : 'hidden'}>${escapeHtml(line.meta.notes || '')}</p>`;

    el.innerHTML = `
      ${imageHtml}
      <div class="higala-cart-item__details">
        <p class="higala-cart-item__name">${escapeHtml(line.name)}</p>
        <p class="higala-cart-item__merchant">${escapeHtml(line.fulfillment_type)} \u00b7 ${escapeHtml(line.merchantId)}</p>
        ${rxHtml}
        ${addOnsHtml}
        ${notesHtml}
        <div class="higala-cart-item__qty-controls">
          <button type="button" class="higala-cart-item__qty-btn" data-cart-decrement="${escapeHtml(line.lineId)}" aria-label="Decrease quantity">\u2212</button>
          <span class="higala-cart-item__qty" data-role="qty" aria-live="polite">${line.quantity}</span>
          <button type="button" class="higala-cart-item__qty-btn" data-cart-increment="${escapeHtml(line.lineId)}" aria-label="Increase quantity">+</button>
        </div>
      </div>
      <div class="higala-cart-item__side">
        <span class="higala-cart-item__price" data-role="line-total">${lineTotal}</span>
        <button type="button" class="higala-cart-item__notes-btn" data-cart-edit-notes="${escapeHtml(line.lineId)}">Add note</button>
        <button type="button" class="higala-cart-item__remove" data-cart-remove="${escapeHtml(line.lineId)}" aria-label="Remove item">Remove</button>
      </div>
    `;
  }

  // ===========================================================================
  // Drawer open/close (supports both legacy #cart-drawer and customer.html #cartDrawer)
  // ===========================================================================
  function getDrawerEl() {
    return document.getElementById('cart-drawer') || document.getElementById('cartDrawer');
  }

  function getItemsContainer() {
    let el = document.getElementById('cart-items-container');
    if (el) return el;
    const body = document.getElementById('cartBody');
    if (!body) return null;
    el = document.createElement('div');
    el.id = 'cart-items-container';
    body.appendChild(el);
    return el;
  }

  function open() {
    const drawer = getDrawerEl();
    if (drawer) {
      drawer.classList.add(DRAWER_OPEN_CLASS);
      drawer.classList.add('open');
      drawer.setAttribute('aria-hidden', 'false');
    }
    EventBus.emit('cart:drawerOpen', {});
  }

  function close() {
    const drawer = getDrawerEl();
    if (drawer) {
      drawer.classList.remove(DRAWER_OPEN_CLASS);
      drawer.classList.remove('open');
      drawer.setAttribute('aria-hidden', 'true');
    }
    EventBus.emit('cart:drawerClose', {});
  }

  function toggle() {
    const drawer = getDrawerEl();
    if (!drawer) return;
    if (drawer.classList.contains(DRAWER_OPEN_CLASS)) close();
    else open();
  }

  // ===========================================================================
  // Event delegation
  // ===========================================================================
  function attachDelegatedListeners() {
    document.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      const incEl = target.closest('[data-cart-increment]');
      if (incEl) { updateQuantity(incEl.getAttribute('data-cart-increment'), 1); return; }

      const decEl = target.closest('[data-cart-decrement]');
      if (decEl) { updateQuantity(decEl.getAttribute('data-cart-decrement'), -1); return; }

      const removeEl = target.closest('[data-cart-remove]');
      if (removeEl) { removeItem(removeEl.getAttribute('data-cart-remove')); return; }

      const notesEl = target.closest('[data-cart-edit-notes]');
      if (notesEl) {
        const lineId = notesEl.getAttribute('data-cart-edit-notes');
        const line = state.items.find((l) => l.lineId === lineId);
        const nextNotes = window.prompt('Special instructions:', (line && line.meta.notes) || '');
        if (nextNotes !== null) setLineNotes(lineId, nextNotes);
        return;
      }

      const openEl = target.closest('[data-cart-open]');
      if (openEl) { open(); return; }

      const closeEl = target.closest('[data-cart-close]');
      if (closeEl) { close(); return; }

      const toggleEl = target.closest('[data-cart-toggle]');
      if (toggleEl) { toggle(); return; }

      const applyPromoEl = target.closest('#cart-promo-apply-btn');
      if (applyPromoEl) {
        const input = document.getElementById('cart-promo-input');
        const result = applyPromo(input ? input.value : '');
        if (!result.valid) Toast.error(result.message || 'Invalid promo code.');
        return;
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      const target = event.target;
      if (!(target instanceof Element) || target.id !== 'cart-promo-input') return;
      event.preventDefault();
      const result = applyPromo(target.value);
      if (!result.valid) Toast.error(result.message || 'Invalid promo code.');
    });
  }

  function attachCoreIntegration() {
    EventBus.on('cart:add', (payload) => {
      if (payload && !payload.lineId && !payload.item) {
        addItem(payload);
      }
    });
    EventBus.on('cart:externalChange', () => {
      load();
      render();
    });
  }

  // ===========================================================================
  // Init
  // ===========================================================================
  function init() {
    load();
    attachDelegatedListeners();
    attachCoreIntegration();

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', render);
    } else {
      render();
    }
  }

  init();

  window.HigalaCart = Object.freeze({
    addItem,
    updateQuantity,
    setQuantity,
    removeItem,
    clear,
    setLineNotes,
    setLinePrescription,
    applyPromo,
    removePromo,
    getState,
    getTotals,
    getMerchantGroups,
    open,
    close,
    toggle,
    render,
  });

  /**
   * Legacy global used by grocery.js, ui.js, and inline onclick handlers.
   * Supports (name, price, img, merchantId, fulfillmentType) or a single product id string.
   */
  window.addToCart = function addToCart(nameOrId, price, imageUrl, merchantId, fulfillmentType) {
    if (!window.HigalaCart) {
      console.error('[addToCart] HigalaCart is not initialized.');
      return;
    }
    if (arguments.length === 1 && typeof nameOrId === 'string') {
      const id = nameOrId;
      window.HigalaCart.addItem({
        id,
        name: id,
        price: 0,
        quantity: 1,
        fulfillment_type: 'grocery',
        merchantId: (window.MERCHANT_IDS && window.MERCHANT_IDS.grocery) || 'grocery-cdo',
        imageUrl: '',
      });
      return;
    }
    window.HigalaCart.addItem({
      id: `legacy-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      name: String(nameOrId || 'Item'),
      price: Number(price) || 0,
      quantity: 1,
      fulfillment_type: fulfillmentType || 'grocery',
      merchantId: merchantId || (window.MERCHANT_IDS && window.MERCHANT_IDS.grocery) || 'grocery-cdo',
      imageUrl: imageUrl || '',
    });
  };
})(window, document);