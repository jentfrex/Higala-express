// ==========================================
// MERCHANT.JS - Food, Grocery & Pharmacy Deliveries
// ==========================================
// Pure visual animation — called AFTER checkout has already succeeded
// and the order is paid for via /checkout/split.
async function startMerchantDeliveryJourney(itemName) {
    if (!destMarker) {
        return; // No destination set on the map; skip animation.
    }

    const merchantLatLng = L.latLng(8.4850, 124.6570); // Limketkai Center default store coordinate
    const destLatLng = destMarker.getLatLng();
    const driverName = "Ramil 'Bong' Cagaitan";

    if (typeof activeDummyDrivers !== 'undefined') {
        activeDummyDrivers.forEach(d => { if (d.marker) map.removeLayer(d.marker); });
    }

    const motorIcon = L.divIcon({
        className: 'cinematic-motor-marker',
        html: `<div style="width: 44px; height: 44px; border-radius: 50%; border: 3px solid #FF6600; display: flex; align-items: center; justify-content: center; background: white; box-shadow: 0 8px 20px rgba(0,0,0,0.35); font-size: 20px;">🛵</div>`,
        iconSize: [44, 44],
        iconAnchor: [22, 22]
    });

    const roadFromMerchantToDest = await fetchRoadRouteWithDetails([merchantLatLng.lng, merchantLatLng.lat], [destLatLng.lng, destLatLng.lat]);

    if (typeof driverMarker !== 'undefined' && driverMarker) map.removeLayer(driverMarker);
    driverMarker = L.marker(merchantLatLng, { icon: motorIcon }).addTo(map);
    driverMarker.bindPopup(`<b>📦 Gikuha na ang order (${itemName}) ni ${driverName} gikan sa Store!</b>`).openPopup();

    if (typeof routeLine !== 'undefined' && routeLine) {
        routeLine.setLatLngs(roadFromMerchantToDest.coordinates);
    } else {
        routeLine = L.polyline(roadFromMerchantToDest.coordinates, {color: '#FF6600', weight: 5, opacity: 0.85, dashArray: '8, 8'}).addTo(map);
    }

    const simpleAnimate = (marker, coords, idx) => {
        if (idx >= coords.length) {
            marker.bindPopup(`<b>🏁 Nahatud na ang order (${itemName}) sa imong destinasyon!</b>`).openPopup();
            setTimeout(() => {
                if (routeLine) { map.removeLayer(routeLine); routeLine = null; }
                if (destMarker) { map.removeLayer(destMarker); destMarker = null; }
                if (typeof userMarker !== 'undefined' && userMarker) { map.removeLayer(userMarker); userMarker = null; }
                if (driverMarker) { map.removeLayer(driverMarker); driverMarker = null; }
                if (typeof spawnCDOWideMovingDrivers === 'function') spawnCDOWideMovingDrivers();
            }, 3000);
            return;
        }
        marker.setLatLng(coords[idx]);
        setTimeout(() => simpleAnimate(marker, coords, idx + 1), 50);
    };

    simpleAnimate(driverMarker, roadFromMerchantToDest.coordinates, 0);
}
window.startMerchantDeliveryJourney = startMerchantDeliveryJourney;