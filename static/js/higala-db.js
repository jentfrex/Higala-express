/**
 * Higala Express — Unified localStorage Database & Commission Engine
 * Shared across customer, merchant, driver, and admin dashboards.
 */
(function (window) {
  'use strict';

  const KEYS = {
    users: 'higala_users',
    orders: 'higala_orders',
    merchants: 'higala_merchants',
    drivers: 'higala_drivers',
    wallet: 'higala_wallet',
    session: 'higala_session',
    audit: 'higala_audit_log',
    settings: 'higala_settings',
    inventory: 'higala_inventory',
    reviews: 'higala_reviews',
    disputes: 'higala_disputes',
    notifications: 'higala_notifications',
    promos: 'higala_promos',
  };

  const COMMISSION = Object.freeze({
    DELIVERY: 0.14,
    RIDER_QUOTA: 0.07,
    RIDER_QUOTA_THRESHOLD: 10,
    TAXI: 0.08,
    MERCHANT: 0.16,
  });

  const CDO_CENTER = Object.freeze({ lat: 8.4822, lng: 124.6471 });
  const BARANGAYS = Object.freeze([
    'Carmen', 'Divisoria', 'Kauswagan', 'Bulua', 'Nazareth', 'Lapasan', 'Cugman', 'Macasandig',
  ]);

  const ROUTES = Object.freeze({
    customer: '/customer.html',
    merchant: '/merchant.html',
    driver: '/driver.html',
    admin: '/admin.html',
  });

  function read(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (e) {
      return fallback;
    }
  }

  function write(key, data) {
    localStorage.setItem(key, JSON.stringify(data));
  }

  function uid(prefix) {
    return `${prefix || 'id'}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function todayKey() {
    return new Date().toISOString().slice(0, 10);
  }

  function money(n) {
    return `₱${Number(n || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  function haversineKm(a, b) {
    const R = 6371;
    const rad = (x) => (x * Math.PI) / 180;
    const dLat = rad(b.lat - a.lat);
    const dLng = rad(b.lng - a.lng);
    const h =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
  }

  function distanceFare(km) {
    const d = Math.max(0, Number(km) || 0);
    if (d <= 0) return 0;
    const extraKm = Math.max(0, d - 2);
    return Math.round((50 + extraKm * 15) * 100) / 100;
  }

  function courierFare(km, weightKg) {
    const base = distanceFare(km);
    const extraKg = Math.max(0, (Number(weightKg) || 1) - 1);
    return Math.round((base + extraKg * 20) * 100) / 100;
  }

  function hashPassword(pw) {
    return btoa(unescape(encodeURIComponent(String(pw || ''))));
  }

  function audit(action, meta) {
    const logs = read(KEYS.audit, []);
    logs.unshift({
      id: uid('audit'),
      action,
      meta: meta || {},
      at: new Date().toISOString(),
    });
    write(KEYS.audit, logs.slice(0, 500));
  }

  function seed() {
    const users = read(KEYS.users, []);
    if (users.length) return;

    const defaults = [
      { id: 'u_admin', name: 'Higala Admin', email: 'admin@higala.ph', password: hashPassword('admin123'), role: 'admin', phone: '09170000001', barangay: 'Carmen', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=160&q=80', verified: true },
      { id: 'u_merchant', name: 'CDO Food Hub', email: 'merchant@higala.ph', password: hashPassword('merchant123'), role: 'merchant', phone: '09170000002', barangay: 'Divisoria', avatar: 'https://images.unsplash.com/photo-1560250097-0b93528c311a?w=160&q=80', storeName: 'Higala Food CDO', verified: true },
      { id: 'u_driver', name: 'Kuya Jun', email: 'driver@higala.ph', password: hashPassword('driver123'), role: 'driver', phone: '09170000003', barangay: 'Lapasan', avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=160&q=80', vehicleType: 'motor', plateNo: 'KB-98214', verified: true },
      { id: 'u_customer', name: 'Maria Higala', email: 'customer@higala.ph', password: hashPassword('customer123'), role: 'customer', phone: '09170000004', barangay: 'Carmen', avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=160&q=80', age: 28, gender: 'Female', verified: true },
    ];
    write(KEYS.users, defaults);

    write(KEYS.merchants, [{
      id: 'm_cdo_food', userId: 'u_merchant', name: 'Higala Food CDO', category: 'Food',
      open: true, rating: 4.9, barangay: 'Divisoria', commissionRate: COMMISSION.MERCHANT,
    }]);

    write(KEYS.drivers, [{
      id: 'd_jun', userId: 'u_driver', name: 'Kuya Jun', online: false,
      vehicleType: 'motor', plateNo: 'KB-98214', lat: CDO_CENTER.lat, lng: CDO_CENTER.lng,
      dailyRides: {}, earnings: 0, tips: 0,
    }]);

    write(KEYS.wallet, {
      u_customer: { balance: 500, history: [{ type: 'topup', amount: 500, at: new Date().toISOString(), method: 'GCash' }] },
      u_merchant: { balance: 1200, history: [] },
      u_driver: { balance: 850, history: [] },
    });

    write(KEYS.inventory, {
      m_cdo_food: [
        { id: 'f1', name: 'Chicken Inasal Meal', price: 149, stock: 50, category: 'Meals', img: 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=200&q=80' },
        { id: 'f2', name: 'Beef Kare-Kare Bowl', price: 189, stock: 30, category: 'Meals', img: 'https://images.unsplash.com/photo-1603133872878-684f208fb84b?w=200&q=80' },
        { id: 'f3', name: 'Pancit Canton', price: 139, stock: 40, category: 'Noodles', img: 'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=200&q=80' },
        { id: 'g1', name: 'Premium Rice 5kg', price: 260, stock: 25, category: 'Grocery', img: 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=200&q=80' },
        { id: 'p1', name: 'Paracetamol 500mg', price: 55, stock: 100, category: 'Pharmacy', img: 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=200&q=80' },
        { id: 'c1', name: 'Document Pouch Dispatch', price: 80, stock: 200, category: 'Courier/Others', img: 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=200&q=80' },
      ],
    });

    write(KEYS.promos, [
      { code: 'HIGALA50', type: 'flat', value: 50, minSubtotal: 200, active: true },
      { code: 'HIGALA', type: 'percent', value: 10, minSubtotal: 300, active: true },
    ]);

    write(KEYS.settings, { surgeMultiplier: 1.0, broadcast: '', maintenance: false });
    write(KEYS.orders, []);
    write(KEYS.reviews, []);
    write(KEYS.disputes, []);
    write(KEYS.notifications, []);
    audit('system.seed', { message: 'Higala Express database initialized' });
  }

  function getUsers() { return read(KEYS.users, []); }
  function saveUsers(users) { write(KEYS.users, users); }

  function register(payload) {
    const users = getUsers();
    const email = String(payload.email || '').trim().toLowerCase();
    if (!email || !payload.password) return { ok: false, error: 'Email and password required.' };
    if (users.some((u) => u.email === email)) return { ok: false, error: 'Email already registered.' };
    const user = {
      id: uid('u'),
      name: payload.name || 'Higala User',
      email,
      password: hashPassword(payload.password),
      role: payload.role || 'customer',
      phone: payload.phone || '',
      barangay: payload.barangay || 'Carmen',
      avatar: payload.avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=160&q=80',
      age: payload.age || '',
      gender: payload.gender || 'Prefer not to say',
      verified: false,
      createdAt: new Date().toISOString(),
    };
    users.push(user);
    saveUsers(users);
    const wallets = read(KEYS.wallet, {});
    wallets[user.id] = { balance: 100, history: [{ type: 'bonus', amount: 100, at: new Date().toISOString(), method: 'Welcome' }] };
    write(KEYS.wallet, wallets);
    if (user.role === 'merchant') {
      const merchants = read(KEYS.merchants, []);
      merchants.push({ id: uid('m'), userId: user.id, name: user.name + ' Store', category: 'Food', open: true, rating: 5, barangay: user.barangay, commissionRate: COMMISSION.MERCHANT });
      write(KEYS.merchants, merchants);
    }
    if (user.role === 'driver') {
      const drivers = read(KEYS.drivers, []);
      drivers.push({ id: uid('d'), userId: user.id, name: user.name, online: false, vehicleType: payload.vehicleType || 'motor', plateNo: payload.plateNo || 'CDO-0000', lat: CDO_CENTER.lat, lng: CDO_CENTER.lng, dailyRides: {}, earnings: 0, tips: 0 });
      write(KEYS.drivers, drivers);
    }
    audit('user.register', { userId: user.id, role: user.role });
    return { ok: true, user: sanitizeUser(user) };
  }

  function login(email, password) {
    const users = getUsers();
    const user = users.find((u) => u.email === String(email).trim().toLowerCase() && u.password === hashPassword(password));
    if (!user) return { ok: false, error: 'Invalid email or password.' };
    const session = { userId: user.id, role: user.role, at: new Date().toISOString() };
    write(KEYS.session, session);
    audit('user.login', { userId: user.id, role: user.role });
    return { ok: true, user: sanitizeUser(user), route: ROUTES[user.role] || ROUTES.customer };
  }

  function logout() {
    write(KEYS.session, null);
  }

  function getSession() {
    const s = read(KEYS.session, null);
    if (!s) return null;
    const user = getUsers().find((u) => u.id === s.userId);
    if (!user) return null;
    return { ...s, user: sanitizeUser(user) };
  }

  function requireRole(role) {
    const s = getSession();
    if (!s || s.role !== role) return null;
    return s;
  }

  function sanitizeUser(user) {
    if (!user) return null;
    const { password, ...safe } = user;
    return safe;
  }

  function updateUser(userId, patch) {
    const users = getUsers();
    const idx = users.findIndex((u) => u.id === userId);
    if (idx < 0) return { ok: false };
    users[idx] = { ...users[idx], ...patch };
    if (patch.password) users[idx].password = hashPassword(patch.password);
    saveUsers(users);
    audit('user.update', { userId });
    return { ok: true, user: sanitizeUser(users[idx]) };
  }

  function getOrders() { return read(KEYS.orders, []); }
  function saveOrders(orders) { write(KEYS.orders, orders); }

    function countTodayRides(driverId) {
      const day = todayKey();
      const orders = getOrders().filter((o) => {
        if (o.status !== 'completed' || o.service !== 'rides') return false;
        const d = (o.updatedAt || o.createdAt || '').slice(0, 10);
        return d === day && (o.driverId === driverId);
      });
      if (orders.length) return orders.length;
      const driver = read(KEYS.drivers, []).find((d) => d.id === driverId || d.userId === driverId);
      return driver ? ((driver.dailyRides || {})[day] || 0) : 0;
    }

  function riderCommissionRate(driverId, vehicleType) {
    if (vehicleType === 'car' || vehicleType === 'taxi') return COMMISSION.TAXI;
    const rides = countTodayRides(driverId);
    return rides >= COMMISSION.RIDER_QUOTA_THRESHOLD ? COMMISSION.RIDER_QUOTA : COMMISSION.DELIVERY;
  }

  function calcCommissionBreakdown(order) {
    const subtotal = Number(order.subtotal || 0);
    const deliveryFee = Number(order.deliveryFee || 0);
    const vehicleType = order.vehicleType || 'motor';
    const driverId = order.driverId || '';
    const riderRate = riderCommissionRate(driverId, vehicleType);
    const merchantCut = Math.round(subtotal * COMMISSION.MERCHANT * 100) / 100;
    const riderCut = Math.round((deliveryFee || subtotal) * riderRate * 100) / 100;
    const platformTotal = merchantCut + riderCut;
    return {
      merchantRate: COMMISSION.MERCHANT,
      merchantCut,
      riderRate,
      riderCut,
      platformTotal,
      merchantNet: Math.round((subtotal - merchantCut) * 100) / 100,
      riderNet: Math.round((deliveryFee - riderCut) * 100) / 100,
    };
  }

  function createOrder(payload) {
    const orders = getOrders();
    const km = Number(payload.distanceKm || 0);
    const deliveryFee = payload.deliveryFee != null ? payload.deliveryFee : distanceFare(km);
    const order = {
      id: uid('ord'),
      status: 'pending',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      customerId: payload.customerId,
      customerName: payload.customerName || 'Customer',
      merchantId: payload.merchantId || null,
      driverId: payload.driverId || null,
      service: payload.service || 'food',
      items: payload.items || [],
      subtotal: Number(payload.subtotal || 0),
      deliveryFee,
      discount: Number(payload.discount || 0),
      total: Number(payload.total || 0),
      paymentMethod: payload.paymentMethod || 'COD',
      pickup: payload.pickup || { ...CDO_CENTER, address: 'CDO Hub' },
      dropoff: payload.dropoff || null,
      distanceKm: km,
      vehicleType: payload.vehicleType || 'motor',
      notes: payload.notes || '',
      scheduledAt: payload.scheduledAt || null,
      stops: payload.stops || [],
      commission: null,
      tracking: [],
    };
    order.total = order.total || Math.max(0, order.subtotal - order.discount + order.deliveryFee);
    order.commission = calcCommissionBreakdown(order);
    orders.unshift(order);
    saveOrders(orders);
    pushNotification({ type: 'order', orderId: order.id, message: `New ${order.service} order ${order.id}` });
    audit('order.create', { orderId: order.id, total: order.total });
    return order;
  }

  function updateOrder(orderId, patch) {
    const orders = getOrders();
    const idx = orders.findIndex((o) => o.id === orderId);
    if (idx < 0) return null;
    orders[idx] = { ...orders[idx], ...patch, updatedAt: new Date().toISOString() };
    if (patch.status === 'completed' && orders[idx].driverId) {
      const drivers = read(KEYS.drivers, []);
      const dIdx = drivers.findIndex((d) => d.id === orders[idx].driverId || d.userId === orders[idx].driverId);
      if (dIdx >= 0) {
        const day = todayKey();
        drivers[dIdx].dailyRides = drivers[dIdx].dailyRides || {};
        drivers[dIdx].dailyRides[day] = (drivers[dIdx].dailyRides[day] || 0) + 1;
        drivers[dIdx].earnings = (drivers[dIdx].earnings || 0) + (orders[idx].commission?.riderNet || 0);
        write(KEYS.drivers, drivers);
      }
    }
    saveOrders(orders);
    audit('order.update', { orderId, status: patch.status });
    return orders[idx];
  }

  function getWallet(userId) {
    const wallets = read(KEYS.wallet, {});
    return wallets[userId] || { balance: 0, history: [] };
  }

  function walletTopUp(userId, amount, method) {
    const wallets = read(KEYS.wallet, {});
    const w = wallets[userId] || { balance: 0, history: [] };
    w.balance = Math.round((w.balance + Number(amount)) * 100) / 100;
    w.history.unshift({ type: 'topup', amount: Number(amount), method: method || 'GCash', at: new Date().toISOString() });
    wallets[userId] = w;
    write(KEYS.wallet, wallets);
    audit('wallet.topup', { userId, amount });
    return w;
  }

  function walletDeduct(userId, amount, note) {
    const wallets = read(KEYS.wallet, {});
    const w = wallets[userId] || { balance: 0, history: [] };
    if (w.balance < amount) return { ok: false, error: 'Insufficient balance' };
    w.balance = Math.round((w.balance - Number(amount)) * 100) / 100;
    w.history.unshift({ type: 'payment', amount: -Number(amount), note: note || '', at: new Date().toISOString() });
    wallets[userId] = w;
    write(KEYS.wallet, wallets);
    return { ok: true, wallet: w };
  }

  function applyPromo(code, subtotal) {
    const promos = read(KEYS.promos, []);
    const promo = promos.find((p) => p.code === String(code).trim().toUpperCase() && p.active);
    if (!promo) return { ok: false, discount: 0, message: 'Invalid promo code.' };
    if (subtotal < (promo.minSubtotal || 0)) return { ok: false, discount: 0, message: `Minimum spend ${money(promo.minSubtotal)} required.` };
    let discount = promo.type === 'percent' ? subtotal * (promo.value / 100) : promo.value;
    return { ok: true, discount: Math.round(discount * 100) / 100, message: `${promo.code} applied!` };
  }

  function pushNotification(n) {
    const list = read(KEYS.notifications, []);
    list.unshift({ id: uid('ntf'), ...n, at: new Date().toISOString(), read: false });
    write(KEYS.notifications, list.slice(0, 200));
  }

  function getNotifications() { return read(KEYS.notifications, []); }

  function isInGeofence(lat, lng) {
    const bounds = { minLat: 8.35, maxLat: 8.58, minLng: 124.52, maxLng: 124.78 };
    return lat >= bounds.minLat && lat <= bounds.maxLat && lng >= bounds.minLng && lng <= bounds.maxLng;
  }

  function gmv() {
    const orders = getOrders().filter((o) => o.status === 'completed');
    return orders.reduce((s, o) => s + (o.total || 0), 0);
  }

  function platformRevenue() {
    return getOrders()
      .filter((o) => o.status === 'completed')
      .reduce((s, o) => s + (o.commission?.platformTotal || 0), 0);
  }

  seed();

  window.HigalaDB = Object.freeze({
    KEYS,
    COMMISSION,
    CDO_CENTER,
    BARANGAYS,
    ROUTES,
    money,
    haversineKm,
    distanceFare,
    courierFare,
    register,
    login,
    logout,
    getSession,
    requireRole,
    getUsers,
    updateUser,
    getOrders,
    createOrder,
    updateOrder,
    calcCommissionBreakdown,
    riderCommissionRate,
    countTodayRides,
    getWallet,
    walletTopUp,
    walletDeduct,
    applyPromo,
    pushNotification,
    getNotifications,
    isInGeofence,
    gmv,
    platformRevenue,
    audit,
    read,
    write,
    uid,
    todayKey,
    seed,
  });
})(window);
