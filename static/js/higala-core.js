/**
 * higala-core.js
 * ---------------------------------------------------------------------------
 * Higala Express — Global Engine
 *
 * Provides, on window.HigalaCore:
 *   - Config             shared constants (API base, storage keys)
 *   - EventBus           pub/sub for same-tab cross-component sync
 *   - Api                fetch wrapper with auto Bearer token injection
 *   - Session            auth/session state backed by localStorage
 *   - Toast               toast notification UI
 *
 * Load this file first, before cart.js or any vertical module (pharmacy.js,
 * food.js, grocery.js, water.js, gifts.js, party.js, etc).
 *
 *   <script src="/static/js/higala-core.js"></script>
 *   <script src="/static/js/cart.js"></script>
 *   <script src="/static/js/pharmacy.js"></script>
 * ---------------------------------------------------------------------------
 */
(function (window, document) {
  'use strict';

  if (window.HigalaCore) {
    // Already initialized (e.g. script included twice) — don't clobber state.
    return;
  }

  // ===========================================================================
  // Config
  // ===========================================================================
  const Config = Object.freeze({
    API_BASE_URL: window.HIGALA_API_BASE_URL || '/api/v1',
    TOKEN_KEY: 'higala_auth_token',
    REFRESH_TOKEN_KEY: 'higala_refresh_token',
    USER_KEY: 'higala_user',
    CART_KEY: 'higala_cart',
    REQUEST_TIMEOUT_MS: 20000,
    TOAST_DEFAULT_DURATION_MS: 3200,
  });

  // ===========================================================================
  // EventBus — same-tab pub/sub so customer.html, pharmacy.html, food.html
  // etc. can stay in sync without a bundler or framework.
  // ===========================================================================
  const EventBus = (function () {
    /** @type {Map<string, Set<Function>>} */
    const listeners = new Map();

    function on(eventName, handler) {
      if (typeof handler !== 'function') {
        throw new TypeError('HigalaCore.EventBus.on: handler must be a function');
      }
      if (!listeners.has(eventName)) {
        listeners.set(eventName, new Set());
      }
      listeners.get(eventName).add(handler);
      return function unsubscribe() {
        off(eventName, handler);
      };
    }

    function once(eventName, handler) {
      const off_ = on(eventName, function wrapped(payload) {
        off_();
        handler(payload);
      });
      return off_;
    }

    function off(eventName, handler) {
      const set = listeners.get(eventName);
      if (!set) return;
      set.delete(handler);
      if (set.size === 0) listeners.delete(eventName);
    }

    function emit(eventName, payload) {
      const set = listeners.get(eventName);
      if (set) {
        // Iterate over a copy — a handler may unsubscribe itself mid-emit.
        Array.from(set).forEach((handler) => {
          try {
            handler(payload);
          } catch (err) {
            console.error(`[HigalaCore.EventBus] listener for "${eventName}" threw:`, err);
          }
        });
      }
      // Also broadcast as a native CustomEvent on document, so plain
      // addEventListener('higala:cart:add', ...) works too, and so devtools
      // / other libraries can observe Higala events.
      document.dispatchEvent(
        new CustomEvent(`higala:${eventName}`, { detail: payload })
      );
    }

    return { on, once, off, emit };
  })();

  // ===========================================================================
  // Session — auth/session state
  // ===========================================================================
  const Session = (function () {
    function getToken() {
      try {
        return localStorage.getItem(Config.TOKEN_KEY);
      } catch (err) {
        console.error('[HigalaCore.Session] localStorage unavailable:', err);
        return null;
      }
    }

    function setToken(token, refreshToken) {
      try {
        if (token) {
          localStorage.setItem(Config.TOKEN_KEY, token);
        } else {
          localStorage.removeItem(Config.TOKEN_KEY);
        }
        if (typeof refreshToken !== 'undefined') {
          if (refreshToken) {
            localStorage.setItem(Config.REFRESH_TOKEN_KEY, refreshToken);
          } else {
            localStorage.removeItem(Config.REFRESH_TOKEN_KEY);
          }
        }
      } catch (err) {
        console.error('[HigalaCore.Session] failed to persist token:', err);
      }
      EventBus.emit('session:change', { authenticated: isAuthenticated() });
    }

    function getRefreshToken() {
      try {
        return localStorage.getItem(Config.REFRESH_TOKEN_KEY);
      } catch (err) {
        return null;
      }
    }

    function getUser() {
      try {
        const raw = localStorage.getItem(Config.USER_KEY);
        return raw ? JSON.parse(raw) : null;
      } catch (err) {
        console.error('[HigalaCore.Session] corrupt user record, clearing:', err);
        try { localStorage.removeItem(Config.USER_KEY); } catch (_e) { /* noop */ }
        return null;
      }
    }

    function setUser(user) {
      try {
        if (user) {
          localStorage.setItem(Config.USER_KEY, JSON.stringify(user));
        } else {
          localStorage.removeItem(Config.USER_KEY);
        }
      } catch (err) {
        console.error('[HigalaCore.Session] failed to persist user:', err);
      }
      EventBus.emit('session:userChange', { user: user || null });
    }

    function isAuthenticated() {
      return Boolean(getToken());
    }

    /** Clears all session data and notifies the app (e.g. to redirect to login). */
    function logout(reason) {
      setToken(null, null);
      setUser(null);
      EventBus.emit('session:logout', { reason: reason || 'manual' });
    }

    return {
      getToken,
      setToken,
      getRefreshToken,
      getUser,
      setUser,
      isAuthenticated,
      logout,
    };
  })();

  // ===========================================================================
  // Toast — lightweight notification UI, zero external CSS dependency
  // ===========================================================================
  const Toast = (function () {
    let container = null;
    let styleInjected = false;

    function injectStyles() {
      if (styleInjected) return;
      styleInjected = true;
      const style = document.createElement('style');
      style.setAttribute('data-higala', 'toast-styles');
      style.textContent = `
        #higala-toast-container {
          position: fixed;
          top: 16px;
          right: 16px;
          z-index: 2147483000;
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-width: 360px;
          pointer-events: none;
        }
        .higala-toast {
          pointer-events: auto;
          display: flex;
          align-items: flex-start;
          gap: 10px;
          padding: 12px 14px;
          border-radius: 10px;
          background: #1f2430;
          color: #fff;
          box-shadow: 0 6px 18px rgba(0,0,0,0.25);
          font: 500 14px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
          opacity: 0;
          transform: translateY(-8px);
          transition: opacity 180ms ease, transform 180ms ease;
        }
        .higala-toast.higala-toast--visible {
          opacity: 1;
          transform: translateY(0);
        }
        .higala-toast--success { background: #1e7e34; }
        .higala-toast--error   { background: #c0392b; }
        .higala-toast--warning { background: #b7791f; color: #1a1a1a; }
        .higala-toast--info    { background: #1f2430; }
        .higala-toast__close {
          margin-left: auto;
          cursor: pointer;
          background: none;
          border: none;
          color: inherit;
          opacity: 0.7;
          font-size: 16px;
          line-height: 1;
          padding: 0;
        }
        .higala-toast__close:hover { opacity: 1; }
      `;
      document.head.appendChild(style);
    }

    function ensureContainer() {
      if (container && document.body.contains(container)) return container;
      container = document.getElementById('higala-toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'higala-toast-container';
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'true');
        document.body.appendChild(container);
      }
      return container;
    }

    /**
     * @param {string} message
     * @param {{type?: 'info'|'success'|'error'|'warning', duration?: number}} [opts]
     */
    function show(message, opts) {
      const options = opts || {};
      const type = options.type || 'info';
      const duration = typeof options.duration === 'number'
        ? options.duration
        : Config.TOAST_DEFAULT_DURATION_MS;

      injectStyles();
      const host = ensureContainer();

      const toastEl = document.createElement('div');
      toastEl.className = `higala-toast higala-toast--${type}`;
      toastEl.setAttribute('role', type === 'error' ? 'alert' : 'status');

      const text = document.createElement('span');
      text.textContent = String(message == null ? '' : message);
      toastEl.appendChild(text);

      const closeBtn = document.createElement('button');
      closeBtn.className = 'higala-toast__close';
      closeBtn.setAttribute('aria-label', 'Dismiss notification');
      closeBtn.textContent = '\u00D7';
      toastEl.appendChild(closeBtn);

      host.appendChild(toastEl);
      // Force layout so the transition fires.
      requestAnimationFrame(() => toastEl.classList.add('higala-toast--visible'));

      let dismissed = false;
      function dismiss() {
        if (dismissed) return;
        dismissed = true;
        toastEl.classList.remove('higala-toast--visible');
        setTimeout(() => toastEl.remove(), 200);
      }

      closeBtn.addEventListener('click', dismiss);
      if (duration > 0) {
        setTimeout(dismiss, duration);
      }

      return { dismiss };
    }

    const success = (msg, opts) => show(msg, Object.assign({}, opts, { type: 'success' }));
    const error = (msg, opts) => show(msg, Object.assign({}, opts, { type: 'error' }));
    const warning = (msg, opts) => show(msg, Object.assign({}, opts, { type: 'warning' }));
    const info = (msg, opts) => show(msg, Object.assign({}, opts, { type: 'info' }));

    return { show, success, error, warning, info };
  })();

  // ===========================================================================
  // Api — fetch wrapper with automatic Bearer token injection
  // ===========================================================================
  const Api = (function () {
    class ApiError extends Error {
      constructor(message, { status, data, endpoint } = {}) {
        super(message);
        this.name = 'ApiError';
        this.status = status || 0;
        this.data = data || null;
        this.endpoint = endpoint || null;
      }
    }

    function buildUrl(endpoint) {
      if (/^https?:\/\//i.test(endpoint)) return endpoint;
      const base = Config.API_BASE_URL.replace(/\/+$/, '');
      const path = String(endpoint).replace(/^\/+/, '');
      return `${base}/${path}`;
    }

    /**
     * @param {string} endpoint          e.g. '/orders' or a full URL
     * @param {object} [options]
     * @param {'GET'|'POST'|'PUT'|'PATCH'|'DELETE'} [options.method]
     * @param {object|FormData} [options.body]
     * @param {object} [options.headers]
     * @param {boolean} [options.auth]    default true — attach Bearer token if present
     * @param {number} [options.timeout]  ms, default Config.REQUEST_TIMEOUT_MS
     * @param {boolean} [options.silent]  suppress automatic error toast
     */
    async function request(endpoint, options) {
      const opts = options || {};
      const method = (opts.method || 'GET').toUpperCase();
      const useAuth = opts.auth !== false;
      const timeout = typeof opts.timeout === 'number' ? opts.timeout : Config.REQUEST_TIMEOUT_MS;
      const isFormData = typeof FormData !== 'undefined' && opts.body instanceof FormData;

      const headers = Object.assign(
        {},
        isFormData ? {} : { 'Content-Type': 'application/json', Accept: 'application/json' },
        opts.headers || {}
      );

      if (useAuth) {
        const token = Session.getToken();
        if (token) headers.Authorization = `Bearer ${token}`;
      }

      const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
      const timer = controller ? setTimeout(() => controller.abort(), timeout) : null;

      let response;
      try {
        response = await fetch(buildUrl(endpoint), {
          method,
          headers,
          credentials: 'same-origin',
          signal: controller ? controller.signal : undefined,
          body: opts.body == null
            ? undefined
            : (isFormData ? opts.body : JSON.stringify(opts.body)),
        });
      } catch (networkErr) {
        if (timer) clearTimeout(timer);
        const isAbort = networkErr && networkErr.name === 'AbortError';
        const message = isAbort
          ? 'Request timed out. Please check your connection and try again.'
          : 'Network error. Please check your connection and try again.';
        if (!opts.silent) Toast.error(message);
        EventBus.emit('api:error', { endpoint, method, message, networkErr });
        throw new ApiError(message, { status: 0, endpoint });
      }
      if (timer) clearTimeout(timer);

      // Parse response body (JSON if possible, else raw text).
      let data = null;
      const contentType = response.headers.get('content-type') || '';
      try {
        if (contentType.includes('application/json')) {
          data = await response.json();
        } else {
          const text = await response.text();
          data = text || null;
        }
      } catch (parseErr) {
        data = null;
      }

      if (response.status === 401 && useAuth) {
        // Session expired or invalid — clear it and let the app react
        // (e.g. redirect to login) via the session:logout event.
        Session.logout('unauthorized');
        if (!opts.silent) Toast.error('Your session has expired. Please log in again.');
      }

      if (!response.ok) {
        const message =
          (data && (data.message || data.error)) ||
          `Request failed with status ${response.status}`;
        if (!opts.silent && response.status !== 401) Toast.error(message);
        EventBus.emit('api:error', { endpoint, method, status: response.status, message, data });
        throw new ApiError(message, { status: response.status, data, endpoint });
      }

      return data;
    }

    const get = (endpoint, options) => request(endpoint, Object.assign({}, options, { method: 'GET' }));
    const post = (endpoint, body, options) => request(endpoint, Object.assign({}, options, { method: 'POST', body }));
    const put = (endpoint, body, options) => request(endpoint, Object.assign({}, options, { method: 'PUT', body }));
    const patch = (endpoint, body, options) => request(endpoint, Object.assign({}, options, { method: 'PATCH', body }));
    const del = (endpoint, options) => request(endpoint, Object.assign({}, options, { method: 'DELETE' }));

    return { request, get, post, put, patch, delete: del, ApiError };
  })();

  // ===========================================================================
  // Global error handling — catch anything that slips past local try/catch
  // ===========================================================================
  window.addEventListener('error', (event) => {
    console.error('[HigalaCore] uncaught error:', event.error || event.message);
    EventBus.emit('app:error', { source: 'window.error', error: event.error || event.message });
  });

  window.addEventListener('unhandledrejection', (event) => {
    console.error('[HigalaCore] unhandled promise rejection:', event.reason);
    EventBus.emit('app:error', { source: 'unhandledrejection', error: event.reason });
  });

  // Cross-tab sync: if the token or cart changes in another tab, notify this one.
  window.addEventListener('storage', (event) => {
    if (!event.key) return;
    if (event.key === Config.TOKEN_KEY) {
      EventBus.emit('session:change', { authenticated: Session.isAuthenticated() });
    }
    if (event.key === Config.CART_KEY) {
      EventBus.emit('cart:externalChange', { raw: event.newValue });
    }
  });

  // ===========================================================================
  // Public export
  // ===========================================================================
  window.HigalaCore = Object.freeze({
    Config,
    EventBus,
    Session,
    Toast,
    Api,
  });

  EventBus.emit('core:ready', { timestamp: Date.now() });
})(window, document);