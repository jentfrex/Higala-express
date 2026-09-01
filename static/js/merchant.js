// ==========================================
// MERCHANT.JS - Full Featured Merchant Superapp Engine
// ==========================================

document.addEventListener('alpine:init', () => {
    Alpine.data('merchantApp', () => ({
        merchant: null,
        user: null,
        activeTab: 'orders',
        orders: [],
        inventory: [],
        profileForm: { storeName: '', phone: '', address: '', password: '' },
        productForm: { name: '', price: '', category: 'food', stock: 0 },

        init() {
            const session = DB.getSession();
            if (!session || session.role !== 'merchant') {
                window.location.href = '/merchant-login.html';
                return;
            }
            this.user = session.user || {};
            this.loadMerchant();
            this.loadOrders();
            this.loadInventory();
        },

        loadMerchant() {
            const merchants = DB.read(DB.KEYS.merchants, []);
            this.merchant = merchants.find(m => m.userId === this.user.id) || merchants[0] || { name: 'Admin Merchant', address: 'CDO' };
            this.profileForm.storeName = this.merchant.name || '';
            this.profileForm.phone = this.merchant.phone || '';
            this.profileForm.address = this.merchant.address || '';
        },

        loadOrders() {
            const allOrders = DB.read(DB.KEYS.orders, []);
            // Filter orders intended for this specific merchant store
            this.orders = allOrders.filter(o => !this.merchant || o.storeId === this.merchant.id || o.merchantId === this.user.id);
        },

        updateOrderStatus(orderId, newStatus) {
            let allOrders = DB.read(DB.KEYS.orders, []);
            allOrders = allOrders.map(order => {
                if (order.id === orderId) {
                    order.status = newStatus;
                    order.updatedAt = new Date().toISOString();
                }
                return order;
            });
            DB.write(DB.KEYS.orders, allOrders);
            this.loadOrders();
            alert(`Na-update na ang order ${orderId} ngadto sa status: ${newStatus}`);
        },

        loadInventory() {
            const allProducts = DB.read(DB.KEYS.products, []);
            this.inventory = allProducts.filter(p => !this.merchant || p.merchantId === this.user.id);
        },

        addProduct() {
            if (!this.productForm.name || !this.productForm.price) {
                alert('Palihug isulat ang pangalan ug presyo sa produkto.');
                return;
            }
            const allProducts = DB.read(DB.KEYS.products, []);
            const newProduct = {
                id: 'PROD-' + Date.now(),
                merchantId: this.user.id,
                name: this.productForm.name,
                price: parseFloat(this.productForm.price),
                category: this.productForm.category,
                stock: parseInt(this.productForm.stock) || 0
            };
            allProducts.push(newProduct);
            DB.write(DB.KEYS.products, allProducts);
            this.loadInventory();
            this.productForm = { name: '', price: '', category: 'food', stock: 0 };
            alert('Malampusong na-dugang ang produkto!');
        },

        deleteProduct(productId) {
            let allProducts = DB.read(DB.KEYS.products, []);
            allProducts = allProducts.filter(p => p.id !== productId);
            DB.write(DB.KEYS.products, allProducts);
            this.loadInventory();
        },

        saveProfile() {
            const merchants = DB.read(DB.KEYS.merchants, []);
            const idx = merchants.findIndex(m => m.id === this.merchant?.id || m.userId === this.user.id);
            if (idx >= 0) {
                merchants[idx].name = this.profileForm.storeName;
                merchants[idx].phone = this.profileForm.phone;
                merchants[idx].address = this.profileForm.address;
                DB.write(DB.KEYS.merchants, merchants);
                this.merchant = merchants[idx];
            }
            alert('Na-save na ang profile sa store!');
        },

        logout() {
            DB.logout();
            window.location.href = '/merchant-login.html';
        }
    }));
});