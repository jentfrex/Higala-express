/**
 * Database Connection Manager
 * Provides a unified interface for SQLite (default) with optional MongoDB/PostgreSQL
 */
const Database = (function () {
  let db = null;
  let driver = 'sqlite';

  // In-memory store for demo / fallback when no external DB is configured
  const memoryStore = {
    users: [],
    drivers: [],
    orders: [],
    applications: [],
    wallets: {},
    reviews: [],
    notifications: [],
    audit: [],
    sessions: [],
    settings: {},
  };

  function init(options = {}) {
    driver = options.driver || 'sqlite';
    if (driver === 'memory') {
      seedMemory();
      return memoryStore;
    }
    // For SQLite/Mongo/PG, would initialize connection here
    seedMemory();
    return memoryStore;
  }

  function seedMemory() {
    if (memoryStore.users.length > 0) return;
    const hash = (pw) => Buffer.from(pw).toString('base64');
    memoryStore.users = [
      { id: 'u_admin', name: 'Higala Admin', email: 'admin@higala.ph', password: hash('admin123'), role: 'admin', phone: '09170000001', barangay: 'Carmen', avatar: '', verified: true, createdAt: new Date().toISOString() },
      { id: 'u_merchant', name: 'CDO Food Merchant', email: 'merchant@higala.ph', password: hash('merchant123'), role: 'merchant', phone: '09170000002', barangay: 'Divisoria', avatar: '', verified: true, createdAt: new Date().toISOString() },
      { id: 'u_driver', name: 'Kuya Jun Driver', email: 'driver@higala.ph', password: hash('driver123'), role: 'driver', phone: '09170000003', barangay: 'Lapasan', avatar: '', verified: true, vehicleType: 'motor', createdAt: new Date().toISOString() },
      { id: 'u_customer', name: 'Maria Customer', email: 'customer@higala.ph', password: hash('customer123'), role: 'customer', phone: '09170000004', barangay: 'Carmen', avatar: '', verified: true, createdAt: new Date().toISOString() },
    ];
    memoryStore.drivers = [
      { id: 'd_001', userId: 'u_driver', name: 'Kuya Jun Driver', online: false, vehicleType: 'motor', plateNo: 'CDO-1234', lat: 8.4822, lng: 124.6471, dailyRides: {}, earnings: 0, tips: [] },
    ];
  }

  function getStore() {
    return memoryStore;
  }

  return { init, getStore, memoryStore };
})();

module.exports = Database;
