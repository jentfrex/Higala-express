// ==========================================
// HIGALA EXPRESS - MAIN.JS (SuperApp Bootstrap)
// ==========================================
// Map + service data are initialized from profile.js's enterApp()
// right after a successful login/register, not here — the map
// container is hidden behind the login overlay until then.

document.addEventListener("DOMContentLoaded", () => {
    if (typeof setPaymentMethod === 'function') {
        setPaymentMethod('COD');
    }
});

// Safely override switchService using a closure to prevent undefined reference errors
window.switchService = (function(oldSwitch) {
    return function(serviceName, element) {
        // Tawgon ang daan nga switch service kon anaa pa
        if (typeof oldSwitch === 'function') {
            oldSwitch(serviceName, element);
        } else {
            // Fallback tab switching kung wala ang original function
            document.querySelectorAll('.service-tab').forEach(tab => tab.classList.remove('active'));
            if (element) element.classList.add('active');
        }

        // Kung Pharmacy ang gipili, tawgon ang CDO Pharmacy Masterplan UI
        if (serviceName === 'Pharmacy') {
            if (window.cdoPharmacy && typeof window.cdoPharmacy.renderPharmacyUI === 'function') {
                window.cdoPharmacy.renderPharmacyUI();
            } else {
                console.warn("[MAIN.JS] cdoPharmacy is not yet initialized.");
            }
        }
    };
})(window.switchService);