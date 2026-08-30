// ==========================================================================
// HIGALA EXPRESS - UI.JS (Synced & Integrated UI Engine with Categorized Grocery)
// ==========================================================================

// 1. Transparent Fare & Order Summary Manager (Synced with map.js & cart)
function updateCartTripInfo(distanceKm, motorFare) {
    const summaryContainer = document.getElementById('trip-summary-container');
    if (!summaryContainer) return;

    const baseFare = 45;
    const perKmRate = 15;
    const distanceFee = Math.max(0, (distanceKm - 2) * perKmRate);
    const platformFee = 10; 
    const totalFare = motorFare + platformFee;

    summaryContainer.innerHTML = `
        <div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 12px; padding: 16px; margin-top: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
            <h4 style="margin: 0 0 10px 0; font-size: 15px; color: #333; display: flex; align-items: center; justify-content: space-between;">
                <span>📊 Transparent Fare Breakdown</span>
                <span style="font-size: 12px; color: #666; background: #e2e8f0; padding: 2px 8px; border-radius: 20px;">${distanceKm.toFixed(2)} km</span>
            </h4>
            <div style="font-size: 13px; color: #555; display: flex; flex-direction: column; gap: 6px;">
                <div style="display: flex; justify-content: space-between;">
                    <span>Base Fare (First 2 km):</span>
                    <span style="font-weight: 600;">₱${baseFare}.00</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>Distance Fee:</span>
                    <span style="font-weight: 600;">₱${distanceFee.toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; border-bottom: 1px dashed #cbd5e1; padding-bottom: 6px;">
                    <span>Platform Transparency Fee:</span>
                    <span style="font-weight: 600;">₱${platformFee}.00</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 15px; color: #FF6600; font-weight: bold; padding-top: 4px;">
                    <span>Total Estimated Fare:</span>
                    <span>₱${totalFare}.00</span>
                </div>
            </div>
        </div>
    `;
}
window.updateCartTripInfo = updateCartTripInfo;

// 2. High-Resolution Product / Service Card Renderer (Dako ug klaro nga hulagway)
function renderLargeProductCards(productsArray, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = "";

    productsArray.forEach(prod => {
        const card = document.createElement('div');
        card.style.cssText = `
            background: #ffffff; border-radius: 16px; overflow: hidden;
            box-shadow: 0 6px 20px rgba(0,0,0,0.06); border: 1px solid #f1f5f9;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            display: flex; flex-direction: column; cursor: pointer;
        `;
        
        card.onmouseover = () => { card.style.transform = 'translateY(-4px)'; card.style.boxShadow = '0 12px 25px rgba(0,0,0,0.1)'; };
        card.onmouseout = () => { card.style.transform = 'translateY(0)'; card.style.boxShadow = '0 6px 20px rgba(0,0,0,0.06)'; };

        card.innerHTML = `
            <div style="width: 100%; height: 180px; overflow: hidden; background: #e2e8f0; position: relative;">
                <img src="${prod.image}" alt="${prod.name}" style="width: 100%; height: 100%; object-fit: cover;">
                <div style="position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); color: white; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600;">
                    ⭐ ${prod.rating || '4.9'}
                </div>
            </div>
            <div style="padding: 16px; display: flex; flex-direction: column; flex-grow: 1; justify-content: space-between;">
                <div>
                    <h3 style="margin: 0 0 6px 0; font-size: 16px; color: #1e293b; font-weight: 700;">${prod.name}</h3>
                    <p style="margin: 0 0 12px 0; font-size: 13px; color: #64748b; line-height: 1.4;">${prod.description}</p>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 8px;">
                    <span style="font-size: 18px; font-weight: 800; color: #FF6600;">₱${prod.price.toFixed(2)}</span>
                    <button onclick="handleProductSelect('${prod.id}')" style="background: #FF6600; color: white; border: none; padding: 8px 16px; border-radius: 10px; font-weight: 600; font-size: 13px; cursor: pointer;">
                        Pilia Ni
                    </button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}
window.renderLargeProductCards = renderLargeProductCards;

// 2.5 HIGALA GROCERY - Categorized Item Renderer & Tabs
const groceryItems = [
    { id: 'g1', category: 'rice', name: 'Premium White Rice (5kg)', desc: 'Sinandomeng local rice sack', price: 260.00, image: 'https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=300&q=80' },
    { id: 'g2', category: 'dairy', name: 'Fresh Whole Milk (1L)', desc: 'Full cream fresh dairy milk', price: 95.00, image: 'https://images.unsplash.com/photo-1550583724-b2692b85b150?auto=format&fit=crop&w=300&q=80' },
    { id: 'g3', category: 'rice', name: 'Brown Rice Organic (2kg)', desc: 'Healthy organic local brown rice', price: 140.00, image: 'https://images.unsplash.com/photo-1536304993881-ff6e9eefa2a6?auto=format&fit=crop&w=300&q=80' },
    { id: 'g4', category: 'dairy', name: 'Cheddar Cheese Block (200g)', desc: 'Delicious quick melt cheese', price: 115.00, image: 'https://images.unsplash.com/photo-1452195100486-9cc805987862?auto=format&fit=crop&w=300&q=80' }
];

function renderGrocerySection(selectedCategory = 'all') {
    const container = document.getElementById('grocery-items-container');
    if (!container) return;

    let filterNav = document.getElementById('grocery-category-tabs');
    if (!filterNav) {
        filterNav = document.createElement('div');
        filterNav.id = 'grocery-category-tabs';
        filterNav.style.cssText = 'display: flex; gap: 8px; overflow-x: auto; padding-bottom: 12px; margin-bottom: 16px; white-space: nowrap;';
        filterNav.innerHTML = `
            <button onclick="filterGrocery('all')" style="background: #FF6600; color: white; border: none; padding: 8px 16px; border-radius: 20px; font-weight: bold; cursor: pointer; font-size: 13px;">Tanan</button>
            <button onclick="filterGrocery('rice')" style="background: #f1f5f9; color: #475569; border: none; padding: 8px 16px; border-radius: 20px; font-weight: bold; cursor: pointer; font-size: 13px;">🌾 Bugas & Grains</button>
            <button onclick="filterGrocery('dairy')" style="background: #f1f5f9; color: #475569; border: none; padding: 8px 16px; border-radius: 20px; font-weight: bold; cursor: pointer; font-size: 13px;">🥛 Gatas & Dairy</button>
        `;
        container.parentNode.insertBefore(filterNav, container);
    }

    container.innerHTML = "";
    const filtered = selectedCategory === 'all' ? groceryItems : groceryItems.filter(i => i.category === selectedCategory);

    filtered.forEach(item => {
        const card = document.createElement('div');
        card.style.cssText = `
            background: #ffffff; border-radius: 16px; overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #f1f5f9;
            display: flex; align-items: center; padding: 12px; margin-bottom: 12px; gap: 14px;
        `;
        card.innerHTML = `
            <img src="${item.image}" style="width: 80px; height: 80px; border-radius: 12px; object-fit: cover; background: #e2e8f0;">
            <div style="flex-grow: 1;">
                <h4 style="margin: 0 0 4px 0; font-size: 15px; color: #1e293b; font-weight: 700;">${item.name}</h4>
                <p style="margin: 0 0 8px 0; font-size: 12px; color: #64748b;">${item.desc}</p>
                <div style="font-size: 16px; font-weight: 800; color: #FF6600;">₱${item.price.toFixed(2)}</div>
            </div>
            <button onclick="addToCart('${item.id}')" style="background: #FF6600; color: white; border: none; padding: 10px 16px; border-radius: 12px; font-weight: bold; font-size: 13px; cursor: pointer;">
                Add to Cart
            </button>
        `;
        container.appendChild(card);
    });
}
window.renderGrocerySection = renderGrocerySection;

function filterGrocery(category) {
    renderGrocerySection(category);
}
window.filterGrocery = filterGrocery;

// 3. Synced Driver Matching & Profile Modal (Dako nga hulagway sa drayber, plate number, ug rating)
function showDriverMatchingModal(onDriverFoundCallback) {
    let existingModal = document.getElementById('higala-driver-modal');
    if (existingModal) existingModal.remove();

    const modal = document.createElement('div');
    modal.id = 'higala-driver-modal';
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(5px);
        display: flex; align-items: center; justify-content: center; z-index: 9999;
    `;

    modal.innerHTML = `
        <div style="background: white; width: 90%; max-width: 400px; border-radius: 24px; padding: 24px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.2);">
            <div id="modal-body-content">
                <div style="width: 70px; height: 70px; border: 4px solid #FF6600; border-top: 4px solid transparent; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 16px auto;"></div>
                <h3 style="margin: 0 0 8px 0; font-size: 18px; color: #1e293b; font-weight: 700;">Nangita og Higala Driver...</h3>
                <p style="margin: 0 0 20px 0; font-size: 13px; color: #64748b;">Konekto sa pinakaduol ug kasaligang drayber.</p>
                <button onclick="cancelDriverSearch()" style="background: #f1f5f9; color: #475569; border: none; padding: 10px 20px; border-radius: 12px; font-weight: 600; cursor: pointer;">Kanselahon</button>
            </div>
        </div>
        <style>
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
    `;

    document.body.appendChild(modal);

    setTimeout(() => {
        const contentDiv = document.getElementById('modal-body-content');
        if (!contentDiv) return;

        // Auto-sync sa map.js para ma-lock ang map pag-angkop sa drayber
        if (typeof setRideActive === 'function') setRideActive(true);

        contentDiv.innerHTML = `
            <div style="background: #f0fdf4; border: 2px solid #22c55e; border-radius: 16px; padding: 16px; margin-bottom: 16px;">
                <span style="background: #22c55e; color: white; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; text-transform: uppercase;">Naa Nay Driver!</span>
                <div style="width: 80px; height: 80px; border-radius: 50%; overflow: hidden; margin: 12px auto; border: 3px solid #22c55e; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                    <img src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=200&q=80" style="width: 100%; height: 100%; object-fit: cover;">
                </div>
                <h3 style="margin: 0 0 4px 0; font-size: 18px; color: #1e293b; font-weight: 750;">Kuya Jun Sabanal</h3>
                <p style="margin: 0 0 8px 0; font-size: 13px; color: #15803d; font-weight: 600;">⭐ 4.98 • Honda Click</p>
                <div style="background: white; border-radius: 8px; padding: 8px; font-size: 13px; font-weight: bold; color: #334155; border: 1px dashed #cbd5e1;">
                    Plate No: <span style="color: #FF6600;">KB-98214</span>
                </div>
            </div>
            <div style="display: flex; gap: 10px;">
                <button onclick="alert('Nag-dial sa drayber...')" style="flex: 1; background: #22c55e; color: white; border: none; padding: 12px; border-radius: 12px; font-weight: bold; cursor: pointer;">📞 Tawagan</button>
                <button onclick="closeDriverModal()" style="flex: 1; background: #0f172a; color: white; border: none; padding: 12px; border-radius: 12px; font-weight: bold; cursor: pointer;">Sira / Subaya</button>
            </div>
        `;

        if (typeof onDriverFoundCallback === 'function') onDriverFoundCallback();
    }, 3000);
}
window.showDriverMatchingModal = showDriverMatchingModal;

function cancelDriverSearch() {
    const modal = document.getElementById('higala-driver-modal');
    if (modal) modal.remove();
}
window.cancelDriverSearch = cancelDriverSearch;

function closeDriverModal() {
    const modal = document.getElementById('higala-driver-modal');
    if (modal) modal.remove();
}
window.closeDriverModal = closeDriverModal;

// 4. Advanced Address & Location Modal (Foodpanda-style UX for CDO Delivery)
function showAdvancedAddressModal(currentLat, currentLng) {
    let existingModal = document.getElementById('higala-address-modal');
    if (existingModal) existingModal.remove();

    const modal = document.createElement('div');
    modal.id = 'higala-address-modal';
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(5px);
        display: flex; align-items: center; justify-content: center; z-index: 10000;
    `;

    modal.innerHTML = `
        <div style="background: white; width: 92%; max-width: 480px; border-radius: 24px; padding: 24px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); font-family: inherit;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3 style="margin: 0; font-size: 18px; color: #1e293b; font-weight: 750;">📍 Pilia ang Eksaktong Adres</h3>
                <button onclick="closeAddressModal()" style="background: #f1f5f9; border: none; width: 32px; height: 32px; border-radius: 50%; font-weight: bold; cursor: pointer; color: #64748b;">✕</button>
            </div>

            <div style="margin-bottom: 14px;">
                <label style="display: block; font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 6px; text-transform: uppercase;">Search Adres o Landmark sa CDO</label>
                <input type="text" id="modal-address-search" placeholder="Pananglitan: Limketkai, Divisoria, Bayabas..." style="width: 100%; padding: 12px 14px; border: 1px solid #cbd5e1; border-radius: 12px; font-size: 14px; outline: none; box-sizing: border-box;">
            </div>

            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 14px; margin-bottom: 14px;">
                <div style="font-size: 13px; font-weight: 700; color: #334155; margin-bottom: 4px;">Aktibong Koordinato:</div>
                <div style="font-size: 12px; color: #64748b;">Lat: ${currentLat}, Lng: ${currentLng}</div>
            </div>

            <div style="display: flex; gap: 10px; margin-bottom: 14px;">
                <div style="flex: 1;">
                    <label style="display: block; font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 6px;">Building / Floor / Unit</label>
                    <input type="text" id="modal-floor-input" placeholder="e.g. 2nd Floor" style="width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 10px; font-size: 13px; box-sizing: border-box;">
                </div>
            </div>

            <div style="margin-bottom: 20px;">
                <label style="display: block; font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 6px;">Note to Rider (Landmark)</label>
                <input type="text" id="modal-landmark-input" placeholder="e.g. Atbang sa puti nga gate" style="width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 10px; font-size: 13px; box-sizing: border-box;">
            </div>

            <button onclick="saveAdvancedAddress(${currentLat}, ${currentLng})" style="width: 100%; background: #FF6600; color: white; border: none; padding: 14px; border-radius: 14px; font-weight: 700; font-size: 15px; cursor: pointer; box-shadow: 0 4px 12px rgba(255,102,0,0.3);">
                I-save ang Lokasyon ug Padayon
            </button>
        </div>
    `;

    document.body.appendChild(modal);
}
window.showAdvancedAddressModal = showAdvancedAddressModal;

function closeAddressModal() {
    const modal = document.getElementById('higala-address-modal');
    if (modal) modal.remove();
}
window.closeAddressModal = closeAddressModal;

function saveAdvancedAddress(lat, lng) {
    const floor = document.getElementById('modal-floor-input').value;
    const landmark = document.getElementById('modal-landmark-input').value;
    const addressText = document.getElementById('modal-address-search').value || "Bayabas, Cagayan de Oro City";

    const locationData = { lat, lng, address: addressText, floor, landmark };
    localStorage.setItem('higala_saved_address', JSON.stringify(locationData));

    alert(`Malampuson na-save ang imong lokasyon!\nAdres: ${addressText}\nLandmark: ${landmark || 'Wala'}`);
    closeAddressModal();
}
window.saveAdvancedAddress = saveAdvancedAddress;