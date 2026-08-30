// ==========================================
// COURIER.JS - Parcel & Document Delivery (CDO Standard)
// ==========================================

// Official CDO Fleet & Fare Matrix (First 2km Base + Succeeding km)
const courierFleet = [
    { 
        type: 'Motorcycle', 
        label: 'Express Motor (Bike)', 
        desc: 'Documents, small parcels, food (Max 20kg)', 
        basePrice: 50.00, 
        perKmRate: 15.00, 
        maxWeight: 20, 
        emoji: '🛵',
        capacityGuide: 'Kaya ang backpack, sobre, o gagmay nga kahon hangtod sa 20kg.'
    },
    { 
        type: 'BaoBao', 
        label: 'Bao-Bao / Tricycle', 
        desc: 'Medium boxes, multiple grocery bags (Max 100kg)', 
        basePrice: 80.00, 
        perKmRate: 20.00, 
        maxWeight: 100, 
        emoji: '🛺',
        capacityGuide: 'Kaya ang sako sa bugas, medium boxes, o daghang grocery bags hangtod 100kg.'
    },
    { 
        type: 'Multicab', 
        label: 'Cargo Cab / Multicab (L300 style)', 
        desc: 'Apparatos, furniture, bulk items (Max 500kg)', 
        basePrice: 150.00, 
        perKmRate: 35.00, 
        maxWeight: 500, 
        emoji: '🚚',
        capacityGuide: 'Kaya ang appliances, gagmay nga muwebles, o dagkong bulk cargo hangtod 500kg.'
    }
];

// CDO Major Barangays List para sa Precision Dropdown
const cdoBarangays = [
    "Carmen", "Divisoria", "C.M. Recto (Poblacion)", "Lapasan", "Cugman", 
    "Bulua", "Lumbia", "Iponan", "Kauswagan", "Balulang", 
    "Nazareth", "Macasandig", "Gusa", "Agusan", "Tablon", 
    "Puerto", "Indahag", "Puntod", "Camaman-an", "Patag"
];

function renderCourierUI() {
    const container = document.getElementById('itemsContainer');
    if (!container) return;

    container.innerHTML = courierFleet.map(svc => `
        <div class="item-row" style="border-left: 4px solid #FF6600; margin-bottom: 12px; background: #fff; padding: 12px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            <div class="item-left" onclick="openCourierModal('${svc.type}')" style="cursor: pointer; display: flex; align-items: center; gap: 12px;">
                <div class="item-emoji" style="font-size: 32px;">${svc.emoji}</div>
                <div class="item-details">
                    <h4 style="margin: 0; font-size: 16px; color: #333;">${svc.label}</h4>
                    <p style="margin: 4px 0; font-size: 13px; color: #666;">${svc.desc}</p>
                    <div class="item-price" style="font-size: 12px; color: #FF6600; font-weight: bold;">
                        ₱${svc.basePrice.toFixed(2)} base (2km) + ₱${svc.perKmRate.toFixed(2)}/km
                    </div>
                    <small style="color: #888; font-size: 11px;">💡 ${svc.capacityGuide}</small>
                </div>
            </div>
            <button class="action-btn" onclick="openCourierModal('${svc.type}')" style="background: #FF6600; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer;">Pilia</button>
        </div>
    `).join('');
}
window.renderCourierUI = renderCourierUI;

function openCourierModal(type) {
    const modal = document.getElementById('courierModal');
    const typeInput = document.getElementById('selectedCourierType');
    if (typeInput) typeInput.value = type;
    
    // Auto-populate Barangay dropdown kunganaa sa HTML
    const brgySelect = document.getElementById('receiverBarangay');
    if (brgySelect && brgySelect.options.length <= 1) {
        brgySelect.innerHTML = '<option value="">Pili og Barangay sa CDO</option>' + 
            cdoBarangays.map(b => `<option value="${b}">${b}</option>`).join('');
    }

    if (modal) modal.classList.add('active');
}
window.openCourierModal = openCourierModal;

function closeCourierModal() {
    const modal = document.getElementById('courierModal');
    if (modal) modal.classList.remove('active');
    
    // Clear inputs
    ['receiverName', 'receiverPhone', 'receiverAddress', 'receiverZone', 'receiverBarangay', 'packageWeight', 'itemPrice', 'deliveryNotes'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const codEl = document.getElementById('isCodCheckbox');
    if (codEl) codEl.checked = false;
}
window.closeCourierModal = closeCourierModal;

// Tukma ug hapsay nga computation sa Fare Matrix batok sa Vehicle Type, Distance, ug Weight
function calculateCourierTotalFee(vehicleType, distanceKm, weightKg) {
    const fleet = courierFleet.find(f => f.type === vehicleType) || courierFleet[0];
    let dist = distanceKm > 0 ? distanceKm : 2.0;
    
    let basePrice = fleet.basePrice;
    let distanceFee = 0;
    
    // Kung milapas sa 2km base distance
    if (dist > 2) {
        distanceFee = Math.round((dist - 2) * fleet.perKmRate);
    }

    // Weight check/fee kung kinahanglan
    let weightFee = 0;
    if (weightKg > 5 && vehicleType === 'Motorcycle') {
        weightFee = Math.round((weightKg - 5) * 5); // Gamay nga extra para sa bug-at nga motor load
    }

    return {
        totalPrice: basePrice + distanceFee + weightFee,
        distance: dist,
        basePrice: basePrice,
        extraKmFee: distanceFee
    };
}
window.calculateCourierTotalFee = calculateCourierTotalFee;

// Multi-Stop Array para sa mga Negosyante (Batch Delivery)
let multiStopList = [];

function addDropoffStop() {
    const name = document.getElementById('receiverName')?.value.trim();
    const phone = document.getElementById('receiverPhone')?.value.trim();
    const barangay = document.getElementById('receiverBarangay')?.value;
    
    if (!name || !phone || !barangay) {
        if (typeof showHigalaAlert === 'function') {
            showHigalaAlert("Palihug butangi una ang pangalan, phone, ug barangay sa kasamtangang dropoff usa magdugang og laing stop!", "kulang ang Detalye");
        }
        return;
    }

    multiStopList.push({
        name, phone, barangay,
        zone: document.getElementById('receiverZone')?.value.trim() || '',
        address: document.getElementById('receiverAddress')?.value.trim() || ''
    });

    // Clear fields para sa sunod nga stop
    ['receiverName', 'receiverPhone', 'receiverAddress', 'receiverZone'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    
    if (typeof showHigalaAlert === 'function') {
        showHigalaAlert(`Na-save ang Stop #${multiStopList.length}! Pwede na nimo i-input ang sunod nga destinasyon.`, "Multi-Stop Added");
    }
}
window.addDropoffStop = addDropoffStop;

function submitCourierToCart() {
    const nameEl = document.getElementById('receiverName');
    const phoneEl = document.getElementById('receiverPhone');
    const brgyEl = document.getElementById('receiverBarangay');
    const zoneEl = document.getElementById('receiverZone');
    const addressEl = document.getElementById('receiverAddress');
    const typeEl = document.getElementById('selectedCourierType');
    const weightEl = document.getElementById('packageWeight');
    const isCodEl = document.getElementById('isCodCheckbox');
    const itemPriceEl = document.getElementById('itemPrice');

    const name = nameEl ? nameEl.value.trim() : '';
    const phone = phoneEl ? phoneEl.value.trim() : '';
    const barangay = brgyEl ? brgyEl.value : '';
    const zone = zoneEl ? zoneEl.value.trim() : '';
    const address = addressEl ? addressEl.value.trim() : '';
    const vehicleType = typeEl ? typeEl.value : 'Motorcycle';
    const weightKg = weightEl ? parseFloat(weightEl.value) || 1.0 : 1.0;
    
    const isCod = isCodEl ? isCodEl.checked : false;
    const itemPrice = itemPriceEl ? parseFloat(itemPriceEl.value) || 0 : 0;

    if (!name || !phone || !barangay) {
        if (typeof showHigalaAlert === 'function') {
            showHigalaAlert("Palihug isulat ang Kumpletong Ngalan, Phone Number, ug Barangay sa makadawat sa CDO, Kol!", "Missing Info");
        }
        return;
    }

    const fleet = courierFleet.find(f => f.type === vehicleType) || courierFleet[0];

    // Vehicle Capacity Validation
    if (weightKg > fleet.maxWeight) {
        if (typeof showHigalaAlert === 'function') {
            showHigalaAlert(`Pasayloa, Kol! Ang ${fleet.label} kutob ra sa ${fleet.maxWeight}kg ang kapasidad. Palihug pagpili og mas dako nga sakyanan (Bao-Bao o Multicab).`, "Capacity Limit Exceeded");
        }
        return;
    }

    const currentDist = (typeof currentDistanceKm !== 'undefined' && currentDistanceKm > 0) ? currentDistanceKm : (window.currentDistanceKm || 3.0);
    const calc = calculateCourierTotalFee(vehicleType, currentDist, weightKg);

    // Generate Secure 4-Digit PIN para sa Anti-Wrong Dropoff Verification
    const securePin = Math.floor(1000 + Math.random() * 9000);

    // I-push sa global cart object
    if (typeof cart !== 'undefined') {
        cart.push({
            name: `Courier (${vehicleType}): ${name} [Brgy. ${barangay}, Zone ${zone || 'N/A'}]`,
            basePrice: calc.basePrice,
            deliveryFee: calc.totalPrice - calc.basePrice,
            price: calc.totalPrice,
            qty: 1,
            image: vehicleType === 'Multicab' ? 'https://images.unsplash.com/photo-1519003722824-194d4455a60c?w=100' : 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=100',
            isRide: false,
            category: 'courier',
            vehicleType: vehicleType,
            weightKg: weightKg,
            zipCode: '9000', // CDO Standard Zip Code
            receiverDetails: { 
                name, 
                phone, 
                barangay, 
                zone, 
                address, 
                zipCode: '9000',
                isCod,
                itemPrice,
                securePin,
                multiStops: [...multiStopList]
            },
            distance: calc.distance
        });
    }

    // Reset multi-stop list human masubmit
    multiStopList = [];

    if (typeof updateCartUI === 'function') updateCartUI();
    closeCourierModal();
    if (typeof toggleCartDrawer === 'function') toggleCartDrawer();
    
    if (typeof showHigalaAlert === 'function') {
        showHigalaAlert(`Na-add na sa Cart ang imong Express Courier! Secure PIN para kang ${name}: <b>${securePin}</b>`, "Success");
    }
}
window.submitCourierToCart = submitCourierToCart;

// Auto-Save Draft sa Local Storage aron dili mawala kung ma-refresh ang browser
document.addEventListener('input', (e) => {
    if (['receiverName', 'receiverPhone', 'receiverAddress', 'receiverZone', 'itemPrice'].includes(e.target.id)) {
        localStorage.setItem(`cdo_courier_draft_${e.target.id}`, e.target.value);
    }
});

window.addEventListener('DOMContentLoaded', () => {
    ['receiverName', 'receiverPhone', 'receiverAddress', 'receiverZone', 'itemPrice'].forEach(id => {
        const saved = localStorage.getItem(`cdo_courier_draft_${id}`);
        const el = document.getElementById(id);
        if (saved && el) el.value = saved;
    });
});

// Cinematic Delivery Journey uban sa Leaflet Map ug Receiver Notification Simulation
async function startCourierDeliveryJourney(packageName, receiverDetails = null) {
    if (!destMarker) {
        if (userMarker) {
            destMarker = userMarker;
        } else {
            return; 
        }
    }

    const userLatLng = userMarker ? userMarker.getLatLng() : destMarker.getLatLng();
    const destLatLng = destMarker.getLatLng();
    const driverName = "Kuya Michael 'Mike' Tan";

    let receiverInfoHtml = "";
    if (receiverDetails) {
        receiverInfoHtml = `<br><small>👤 Rec: <b>${receiverDetails.name}</b><br>📍 Brgy. ${receiverDetails.barangay}, Zone ${receiverDetails.zone || 'N/A'}<br>📞 ${receiverDetails.phone}<br>🔐 PIN: <b>${receiverDetails.securePin || '4821'}</b></small>`;
    }

    if (typeof activeDummyDrivers !== 'undefined') {
        activeDummyDrivers.forEach(d => { if (d.marker) map.removeLayer(d.marker); });
    }

    const motorIcon = L.divIcon({
        className: 'cinematic-motor-marker',
        html: `<div style="width: 44px; height: 44px; border-radius: 50%; border: 3px solid #FF6600; display: flex; align-items: center; justify-content: center; background: white; box-shadow: 0 8px 20px rgba(0,0,0,0.35); font-size: 20px;">🛵</div>`,
        iconSize: [44, 44],
        iconAnchor: [22, 22]
    });

    const startSpawnLat = userLatLng.lat + 0.004;
    const startSpawnLng = userLatLng.lng - 0.004;

    const roadToUser = await fetchRoadRouteWithDetails([startSpawnLng, startSpawnLat], [userLatLng.lng, userLatLng.lat]);
    const roadToDest = await fetchRoadRouteWithDetails([userLatLng.lng, userLatLng.lat], [destLatLng.lng, destLatLng.lat]);

    if (typeof driverMarker !== 'undefined' && driverMarker) map.removeLayer(driverMarker);
    driverMarker = L.marker([startSpawnLat, startSpawnLng], { icon: motorIcon }).addTo(map);
    driverMarker.bindPopup(`<b>🛵 Padulong kuhaon ang pakete ni ${driverName}</b>${receiverInfoHtml}`).openPopup();

    if (typeof routeLine !== 'undefined' && routeLine) {
        routeLine.setLatLngs(roadToUser.coordinates);
    } else {
        routeLine = L.polyline(roadToUser.coordinates, {color: '#FF6600', weight: 5, opacity: 0.85, dashArray: '8, 8'}).addTo(map);
    }

    animateMarkerStepWithETA(driverMarker, roadToUser.coordinates, 0, 25, `🛵 Kuhaon ang Pakete sa Sender`, receiverInfoHtml, () => {
        driverMarker.bindPopup(`<b>✅ Nakuha na ang pakete (${packageName})! Padulong na sa CDO Destination.</b>${receiverInfoHtml}`).openPopup();

        setTimeout(() => {
            if (routeLine) routeLine.setLatLngs(roadToDest.coordinates);

            animateMarkerStepWithETA(driverMarker, roadToDest.coordinates, 0, 25, `📦 Hatud sa Receiver (Zip: 9000)`, receiverInfoHtml, () => {
                driverMarker.bindPopup(`<b>🏁 Nahatud na ang Pakete! Kinahanglan i-input ang 4-digit PIN aron ma-complete.</b>${receiverInfoHtml}`).openPopup();

                if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
                if (destMarker && destMarker !== userMarker) { map.removeLayer(destMarker); }
                destMarker = null;
                if (driverMarker) { map.removeLayer(driverMarker); driverMarker = null; }
                if (typeof spawnCDOWideMovingDrivers === 'function') spawnCDOWideMovingDrivers();
            });
        }, 1500);
    });
}
window.startCourierDeliveryJourney = startCourierDeliveryJourney;