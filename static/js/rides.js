// ==========================================
// RIDES.JS - Higala Express Ride Hailing (Updated CDO Fare)
// ==========================================

let isJourneyActive = false;
let driverMarker = null;
let routeLine = null;

function renderRidesUI() {
    const container = document.getElementById('itemsContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="item-row">
            <div class="item-left">
                <div class="item-emoji">🏍️</div>
                <div class="item-details">
                    <h4>Higala Motor (Habal-Habal)</h4>
                    <p>Dali ra maka-agi sa traffic sa CDO</p>
                    <div class="item-price" id="motor-fare">₱50.00 est. fare</div>
                </div>
            </div>
            <button class="action-btn" onclick="bookRideToCart('Higala Motor', getEstimatedFare('motor'))">Book Ride</button>
        </div>
        <div class="item-row">
            <div class="item-left">
                <div class="item-emoji">🚗</div>
                <div class="item-details">
                    <h4>Higala Car (Sedan/SUV)</h4>
                    <p>Airconditioned comfort para sa pamilya</p>
                    <div class="item-price" id="car-fare">₱100.00 est. fare</div>
                </div>
            </div>
            <button class="action-btn" onclick="bookRideToCart('Higala Car', getEstimatedFare('car'))">Book Car</button>
        </div>
        <p style="font-size:11px; color:#999; text-align:center; margin-top:10px;">📍 Click the map to set your pickup, then your destination, to get an accurate fare.</p>
    `;
}
window.renderRidesUI = renderRidesUI;

// Updated CDO Realistic Fare Calculation Logic based on Distance (km)
function calculateRideFare(distanceKm, rideType) {
    let baseFare = 0;
    let perKmRate = 0;

    if (rideType === 'car') {
        baseFare = 100.00; // Base fare para sa Car (apil na unang 2km)
        perKmRate = 25.00; // P25 kada sunod nga kilometro
    } else {
        baseFare = 50.00;  // Base fare para sa Motor (apil na unang 2km)
        perKmRate = 15.00; // P15 kada sunod nga kilometro
    }

    let computedFare = baseFare;
    if (distanceKm > 2) {
        computedFare = baseFare + ((distanceKm - 2) * perKmRate);
    }

    return Math.round(computedFare);
}
window.calculateRideFare = calculateRideFare;

// Reads whatever fare map.js's drawRouteBetweenMarkers() last calculated
// or computes it dynamically using the realistic CDO rate.
function getEstimatedFare(type) {
    const elId = type === 'car' ? 'car-fare' : 'motor-fare';
    const el = document.getElementById(elId);
    if (el) {
        const match = el.innerText.match(/₱([\d.]+)/);
        if (match) return parseFloat(match[1]);
    }
    return type === 'car' ? 100.00 : 50.00;
}
window.getEstimatedFare = getEstimatedFare;

function bookRideToCart(serviceName, fare) {
    if (!window.HigalaCart || typeof window.HigalaCart.addItem !== 'function') {
        console.error('[rides.js] HigalaCart is not available.');
        return;
    }
    const isCar = /car/i.test(serviceName);
    const type = isCar ? 'car' : 'motor';
    window.HigalaCart.addItem({
        id: `ride-${type}`,
        name: serviceName,
        price: Number(fare) || getEstimatedFare(type),
        quantity: 1,
        fulfillment_type: 'ride',
        merchantId: 'higala-rides',
        imageUrl: isCar
            ? 'https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?auto=format&fit=crop&w=700&q=85'
            : 'https://images.unsplash.com/photo-1558981806-ec527fa84c39?auto=format&fit=crop&w=700&q=85',
        meta: { notes: 'CDO pickup and destination pinned on map.' },
    });
    if (typeof window.HigalaCart.open === 'function') {
        window.HigalaCart.open();
    }
}
window.bookRideToCart = bookRideToCart;

// Pure visual animation — called AFTER the backend has already
// confirmed and paid for the order via /checkout/split. This does not
// create any order itself.
async function bookAndRunCareemJourney(serviceType = "Higala Motor") {
    if (isJourneyActive) return;

    if (typeof userMarker === 'undefined' || !userMarker || typeof destMarker === 'undefined' || !destMarker) {
        return; // No route was drawn; skip the animation silently.
    }

    isJourneyActive = true;

    const userLatLng = userMarker.getLatLng();
    const destLatLng = destMarker.getLatLng();
    const driverName = "Ramil 'Bong' Cagaitan";

    if (typeof activeDummyDrivers !== 'undefined' && Array.isArray(activeDummyDrivers)) {
        activeDummyDrivers.forEach(d => {
            if (d && d.marker && typeof map !== 'undefined') map.removeLayer(d.marker);
        });
    }

    const driverIcon = L.divIcon({
        className: 'cinematic-driver-marker',
        html: `<div style="width: 46px; height: 46px; border-radius: 50%; border: 3px solid #FF6600; overflow: hidden; background: white; box-shadow: 0 8px 20px rgba(0,0,0,0.35);"><img src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=120&q=80" style="width: 100%; height: 100%; object-fit: cover;"></div>`,
        iconSize: [46, 46],
        iconAnchor: [23, 23]
    });

    const startSpawnLat = userLatLng.lat + 0.004;
    const startSpawnLng = userLatLng.lng - 0.004;

    let roadToUser = null;
    let roadToDest = null;

    try {
        if (typeof fetchRoadRouteWithDetails === 'function') {
            roadToUser = await fetchRoadRouteWithDetails([startSpawnLng, startSpawnLat], [userLatLng.lng, userLatLng.lat]);
            roadToDest = await fetchRoadRouteWithDetails([userLatLng.lng, userLatLng.lat], [destLatLng.lng, destLatLng.lat]);
        }
    } catch (err) {
        console.warn("Routing API failed or unavailable:", err);
    }

    const userCoords = roadToUser?.coordinates || [[startSpawnLat, startSpawnLng], [userLatLng.lat, userLatLng.lng]];
    const destCoords = roadToDest?.coordinates || [[userLatLng.lat, userLatLng.lng], [destLatLng.lat, destLatLng.lat]];

    if (driverMarker && typeof map !== 'undefined') map.removeLayer(driverMarker);
    driverMarker = L.marker([startSpawnLat, startSpawnLng], { icon: driverIcon }).addTo(map);
    driverMarker.bindPopup(`<b>🚗 Padulong sa imong lokasyon si ${driverName} (${serviceType})</b>`).openPopup();

    if (routeLine && typeof map !== 'undefined') {
        routeLine.setLatLngs(userCoords);
    } else if (typeof map !== 'undefined') {
        routeLine = L.polyline(userCoords, { color: '#FF6600', weight: 5, opacity: 0.85, dashArray: '8, 8' }).addTo(map);
    }

    const runAnimation = (marker, coords, speed, startText, endText, onComplete) => {
        if (typeof animateMarkerStepWithETA === 'function') {
            animateMarkerStepWithETA(marker, coords, 0, speed, startText, endText, onComplete);
        } else {
            let step = 0;
            const interval = setInterval(() => {
                if (step < coords.length) {
                    marker.setLatLng(coords[step]);
                    step++;
                } else {
                    clearInterval(interval);
                    if (onComplete) onComplete();
                }
            }, 100);
        }
    };

    runAnimation(driverMarker, userCoords, 25, `🚗 Padulong si ${driverName}`, "", () => {
        driverMarker.bindPopup(`<b>✅ Naabot na ang Driver! Sakay na, Kol.</b>`).openPopup();

        if (typeof userMarker !== 'undefined' && userMarker && typeof map !== 'undefined') {
            map.removeLayer(userMarker);
            userMarker = null;
        }

        setTimeout(() => {
            if (routeLine) routeLine.setLatLngs(destCoords);

            runAnimation(driverMarker, destCoords, 25, `🏁 Paingon sa Destinasyon`, "", () => {
                driverMarker.bindPopup(`<b>🏁 Naabot na sa Destinasyon! Daghang Salamat sa Pag-book!</b>`).openPopup();

                const finalLatLng = destMarker ? destMarker.getLatLng() : destLatLng;
                const userAvatarIcon = L.divIcon({
                    className: 'custom-user-avatar',
                    html: `<div style="width: 44px; height: 44px; border-radius: 50%; border: 3px solid #FF6600; overflow: hidden; background: white;"><img src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=100&q=80" style="width: 100%; height: 100%; object-fit: cover;"></div>`,
                    iconSize: [44, 44],
                    iconAnchor: [22, 22]
                });

                if (typeof map !== 'undefined') {
                    userMarker = L.marker(finalLatLng, { icon: userAvatarIcon, draggable: true }).addTo(map);
                    map.setView(finalLatLng, 15);

                    if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
                    if (destMarker) { map.removeLayer(destMarker); destMarker = null; }
                    if (driverMarker) { map.removeLayer(driverMarker); driverMarker = null; }
                }

                if (typeof spawnCDOWideMovingDrivers === 'function') {
                    spawnCDOWideMovingDrivers();
                }

                isJourneyActive = false;
            });
        }, 1500);
    });
}
window.bookAndRunCareemJourney = bookAndRunCareemJourney;