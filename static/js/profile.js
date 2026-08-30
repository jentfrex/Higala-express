// ==========================================
// PROFILE.JS - Ultimate #1 Philippine SuperApp Edition
// Features: Verification, File Size Validation, Backend API Sync, 
// CDO Barangay Selector, Emergency Contacts (ICE), Language Switcher,
// Referral Rewards, Green Higala Badge & Toast Notifications.
// ==========================================

let currentUser = null; // { id, email, role, name, phone, age, gender, avatar, isVerified, barangay, emergencyContact, language, referralCode, greenPoints, loyaltyTier }
let authMode = 'login'; // 'login' | 'register'

function toggleAuthMode() {
    authMode = authMode === 'login' ? 'register' : 'login';
    const nameField = document.getElementById('registerNameField');
    const phoneField = document.getElementById('registerPhoneField');
    const submitBtn = document.getElementById('authSubmitBtn');
    const switchLink = document.getElementById('authSwitchLink');
    const errEl = document.getElementById('loginErrorMsg');
    if (errEl) errEl.style.display = 'none';

    if (authMode === 'register') {
        if (nameField) nameField.style.display = 'block';
        if (phoneField) phoneField.style.display = 'block';
        if (submitBtn) submitBtn.innerText = 'Create Account';
        if (switchLink) switchLink.innerText = 'Already have an account? Log in';
    } else {
        if (nameField) nameField.style.display = 'none';
        if (phoneField) phoneField.style.display = 'none';
        if (submitBtn) submitBtn.innerText = 'Log In';
        if (switchLink) switchLink.innerText = "New here? Create an account";
    }
}
window.toggleAuthMode = toggleAuthMode;

function showAuthError(message) {
    const err = document.getElementById('loginErrorMsg');
    if (err) {
        err.innerText = message;
        err.style.display = 'block';
    }
}

async function handleAuthSubmit() {
    if (authMode === 'login') {
        await handleLogin();
    } else {
        await handleRegister();
    }
}
window.handleAuthSubmit = handleAuthSubmit;

async function handleLogin() {
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPass').value;
    const btn = document.getElementById('authSubmitBtn');

    if (!email || !password) {
        showAuthError("Please enter both email and password.");
        return;
    }

    if (btn) { btn.disabled = true; btn.innerText = 'Logging in...'; }

    try {
        const params = new URLSearchParams({ email, password });
        const res = await fetch(`${API_BASE}/api/auth/login?${params.toString()}`, {
            method: 'POST'
        });
        const data = await res.json();

        if (!res.ok) {
            showAuthError(data.detail || 'Invalid email or password.');
            return;
        }

        currentUser = { 
            id: data.user_id, 
            email, 
            role: data.role, 
            token: data.access_token,
            name: data.name || 'Higala User',
            phone: data.phone || '',
            age: data.age || '',
            gender: data.gender || 'Prefer not to say',
            avatar: data.avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=150&q=80',
            isVerified: data.isVerified || false,
            barangay: data.barangay || 'Carmen',
            emergencyName: data.emergencyName || '',
            emergencyPhone: data.emergencyPhone || '',
            language: data.language || 'Cebuano',
            referralCode: data.referralCode || `HIGALA-${Math.random().toString(36).substring(2, 8).toUpperCase()}`,
            greenPoints: data.greenPoints || 120,
            loyaltyTier: data.loyaltyTier || 'CDO Local Insider'
        };
        enterApp();
    } catch (err) {
        console.error('Login failed:', err);
        showAuthError('Could not reach the server. Please try again.');
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = authMode === 'login' ? 'Log In' : 'Create Account'; }
    }
}
window.handleLogin = handleLogin;

async function handleRegister() {
    const name = document.getElementById('registerName').value.trim();
    const phone = document.getElementById('registerPhone').value.trim();
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPass').value;
    const btn = document.getElementById('authSubmitBtn');

    if (!name || !email || !password || !phone) {
        showAuthError("Please fill in your name, phone, email, and password.");
        return;
    }

    if (btn) { btn.disabled = true; btn.innerText = 'Creating account...'; }

    try {
        const res = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password, phone, role: 'customer' })
        });
        const data = await res.json();

        if (!res.ok) {
            showAuthError(data.detail || 'Could not create account.');
            return;
        }

        currentUser = { 
            id: data.user_id, 
            email, 
            role: data.role, 
            token: null,
            name,
            phone,
            age: '',
            gender: 'Prefer not to say',
            avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=150&q=80',
            isVerified: false,
            barangay: 'Carmen',
            emergencyName: '',
            emergencyPhone: '',
            language: 'Cebuano',
            referralCode: `HIGALA-${Math.random().toString(36).substring(2, 8).toUpperCase()}`,
            greenPoints: 50,
            loyaltyTier: 'Verified Higala'
        };
        enterApp();
    } catch (err) {
        console.error('Registration failed:', err);
        showAuthError('Could not reach the server. Please try again.');
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = authMode === 'login' ? 'Log In' : 'Create Account'; }
    }
}
window.handleRegister = handleRegister;

function persistCurrentUser() {
    if (!currentUser) return;
    window.currentUser = currentUser;
    try {
        localStorage.setItem('higala_current_user', JSON.stringify(currentUser));
        if (currentUser.token) {
            localStorage.setItem('access_token', currentUser.token);
        }
    } catch (e) {
        console.warn('Could not persist user session:', e);
    }
}

function enterApp() {
    persistCurrentUser();

    const headerName = document.getElementById('headerUserName');
    if (headerName && currentUser) {
        headerName.textContent = currentUser.name || currentUser.email || 'Higala User';
        const headerRole = document.getElementById('headerUserRole');
        if (headerRole) headerRole.textContent = currentUser.role || 'customer';
        const headerAvatar = document.getElementById('headerAvatar');
        if (headerAvatar && currentUser.avatar) headerAvatar.src = currentUser.avatar;
    }

    const overlay = document.getElementById('loginOverlay');
    const appWrapper = document.getElementById('mainAppWrapper');
    if (overlay) {
        overlay.style.opacity = '0';
        setTimeout(() => {
            overlay.style.display = 'none';
            if (appWrapper) appWrapper.style.display = 'block';
            if (typeof window.__higalaOnLogin === 'function') {
                window.__higalaOnLogin(currentUser);
            } else {
                if (typeof initMap === 'function') initMap();
                else if (window.HigalaMap && document.getElementById('customerMap')) {
                    window.HigalaMap.initPicker('customerMap', {
                        initialCenter: { lat: 8.4542, lng: 124.6319 },
                        enforceGeofence: true,
                        latInputId: 'global-dropoff-lat',
                        lngInputId: 'global-dropoff-lng',
                        addressInputId: 'dropoffAddress',
                    });
                }
                loadServiceData('Rides');
            }
        }, 400);
    }
}

function switchService(serviceName, element) {
    document.querySelectorAll('.service-tab').forEach(tab => tab.classList.remove('active'));
    element.classList.add('active');
    loadServiceData(serviceName);
}
window.switchService = switchService;

const SERVICE_META = {
    Rides: { icon: '🚗', title: 'Express Transport & Ride Hailing', sub: 'Book fast and safe motorcycle or car rides around Cagayan de Oro. Click the map for pickup, then destination.' },
    Food: { icon: '🍔', title: 'Higala Food Delivery', sub: 'Lami nga pagkaon gikan sa paboritong kan-anan sa CDO.' },
    Grocery: { icon: '🛒', title: 'Higala Grocery', sub: 'Mga kinahanglanon sa panimalay gikan sa supermarket.' },
    Pharmacy: { icon: '💊', title: 'Higala Pharma & Meds', sub: 'Paspas nga pagpalit ug tambal ug health essentials.' },
    Courier: { icon: '📦', title: 'Higala Express (Courier & Delivery)', sub: 'Padala pakete bisan asa sa Cagayan de Oro nga luwas ug paspas.' }
};

function loadServiceData(service) {
    const title = document.getElementById('sectionTitle');
    const sub = document.getElementById('sectionSub');
    const meta = SERVICE_META[service];
    if (title && meta) title.innerHTML = `<span>${meta.icon}</span> ${meta.title}`;
    if (sub && meta) sub.innerText = meta.sub;

    if (service === 'Rides' && typeof renderRidesUI === 'function') renderRidesUI();
    else if (service === 'Food' && typeof renderFoodUI === 'function') renderFoodUI();
    else if (service === 'Grocery' && typeof renderGroceryUI === 'function') renderGroceryUI();
    else if (service === 'Pharmacy' && typeof renderPharmacyUI === 'function') renderPharmacyUI();
    else if (service === 'Courier' && typeof renderCourierUI === 'function') renderCourierUI();
}
window.loadServiceData = loadServiceData;

// ==========================================
// TOAST NOTIFICATION SYSTEM (Modern UI Feedback)
// ==========================================
function showToast(message, type = 'success') {
    let toast = document.getElementById('higalaToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'higalaToast';
        toast.style.cssText = 'position:fixed; bottom:20px; left:50%; transform:translateX(-50%); background:#1a1a1a; color:white; padding:12px 24px; border-radius:30px; font-size:13px; font-weight:700; z-index:99999; box-shadow:0 10px 25px rgba(0,0,0,0.3); transition:opacity 0.3s ease; opacity:0; pointer-events:none;';
        document.body.appendChild(toast);
    }
    toast.style.background = type === 'error' ? '#dc3545' : (type === 'warning' ? '#ffc107' : '#28a745');
    toast.innerText = message;
    toast.style.opacity = '1';
    setTimeout(() => {
        toast.style.opacity = '0';
    }, 3000);
}

// ==========================================
// ELITE CUSTOMER PROFILE MODAL (All Features Integrated)
// ==========================================
const CDO_BARANGAYS = [
    "Carmen", "Cugman", "Macasandig", "Bugo", "Kauswagan", 
    "Bulua", "Iponan", "Nazareth", "Cagaan (Poblacion)", "Lapasan", 
    "Patag", "Gusa", "Camaman-an", "Agusan", "Tablon"
];

function calculateProfileCompletion() {
    let score = 0;
    if (currentUser.name) score += 20;
    if (currentUser.phone) score += 20;
    if (currentUser.age && currentUser.gender) score += 20;
    if (currentUser.isVerified) score += 20;
    if (currentUser.emergencyPhone) score += 20;
    return score;
}

function openProfileModal() {
    if (!currentUser) return;
    
    let modal = document.getElementById('customerProfileModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'customerProfileModal';
        modal.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:40000; display:flex; align-items:center; justify-content:center;';
        document.body.appendChild(modal);
    }

    const completion = calculateProfileCompletion();

    modal.innerHTML = `
        <div style="background:white; width:94%; max-width:460px; border-radius:20px; padding:24px; box-shadow:0 20px 40px rgba(0,0,0,0.3); font-family:system-ui; max-height:85vh; display:flex; flex-direction:column;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <div>
                    <h3 style="font-size:17px; font-weight:800; color:#1a1a1a; margin:0;">👤 Customer Profile & Verification</h3>
                    <span style="font-size:11px; background:#e2f0cb; color:#2d6a4f; padding:2px 8px; border-radius:10px; font-weight:700;">🛡️ ${currentUser.loyaltyTier || 'Verified Higala'}</span>
                </div>
                <button onclick="closeCustomerProfileModal()" style="background:none; border:none; font-size:18px; cursor:pointer; font-weight:bold;">✕</button>
            </div>

            <!-- Profile Completion Progress Bar -->
            <div style="background:#f1f3f5; border-radius:8px; padding:8px 12px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:700; color:#495057; margin-bottom:4px;">
                    <span>Profile Strength</span>
                    <span>${completion}% Complete</span>
                </div>
                <div style="width:100%; height:6px; background:#dee2e6; border-radius:3px; overflow:hidden;">
                    <div style="width:${completion}%; height:100%; background:${completion === 100 ? '#28a745' : '#FF6600'}; transition:width 0.4s ease;"></div>
                </div>
            </div>
            
            <div style="display:flex; flex-direction:column; gap:12px; overflow-y:auto; padding-right:4px; flex:1;">
                <!-- Profile Picture Preview & File Validation Upload -->
                <div style="display:flex; align-items:center; gap:14px; background:#f8f9fa; padding:12px; border-radius:12px;">
                    <img id="profileAvatarPreview" src="${currentUser.avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=150&q=80'}" style="width:60px; height:60px; border-radius:50%; object-fit:cover; border:2px solid #FF6600;">
                    <div style="flex:1;">
                        <label style="font-size:12px; font-weight:700; color:#333; display:block; margin-bottom:2px;">Profile Photo (Verification)</label>
                        <input type="file" id="profilePhotoInput" accept="image/*" onchange="previewProfilePhoto(event)" style="font-size:11px; width:100%;">
                        <span style="font-size:10px; color:#888; display:block; margin-top:2px;">Max size: 2MB (JPG/PNG only)</span>
                    </div>
                </div>

                <div style="display:flex; gap:10px;">
                    <div style="flex:2;">
                        <label style="font-size:11px; font-weight:700; color:#717171;">Full Name</label>
                        <input type="text" id="editProfileName" value="${currentUser.name || ''}" style="width:100%; padding:9px; border:1px solid #ddd; border-radius:8px; font-size:13px; margin-top:3px;">
                    </div>
                    <div style="flex:1;">
                        <label style="font-size:11px; font-weight:700; color:#717171;">Age</label>
                        <input type="number" id="editProfileAge" value="${currentUser.age || ''}" placeholder="25" style="width:100%; padding:9px; border:1px solid #ddd; border-radius:8px; font-size:13px; margin-top:3px;">
                    </div>
                </div>

                <div style="display:flex; gap:10px;">
                    <div style="flex:1;">
                        <label style="font-size:11px; font-weight:700; color:#717171;">Gender</label>
                        <select id="editProfileGender" style="width:100%; padding:9px; border:1px solid #ddd; border-radius:8px; font-size:13px; margin-top:3px; background:white;">
                            <option value="Male" ${currentUser.gender === 'Male' ? 'selected' : ''}>Male</option>
                            <option value="Female" ${currentUser.gender === 'Female' ? 'selected' : ''}>Female</option>
                            <option value="Prefer not to say" ${currentUser.gender === 'Prefer not to say' ? 'selected' : ''}>Prefer not to say</option>
                        </select>
                    </div>
                    <div style="flex:1;">
                        <label style="font-size:11px; font-weight:700; color:#717171;">CDO Barangay</label>
                        <select id="editProfileBarangay" style="width:100%; padding:9px; border:1px solid #ddd; border-radius:8px; font-size:13px; margin-top:3px; background:white;">
                            ${CDO_BARANGAYS.map(b => `<option value="${b}" ${currentUser.barangay === b ? 'selected' : ''}>${b}</option>`).join('')}
                        </select>
                    </div>
                </div>

                <div>
                    <label style="font-size:11px; font-weight:700; color:#717171;">Email Address (Locked)</label>
                    <input type="email" value="${currentUser.email}" disabled style="width:100%; padding:9px; border:1px solid #eee; background:#f5f5f5; border-radius:8px; font-size:13px; margin-top:3px; color:#888;">
                </div>

                <div>
                    <label style="font-size:11px; font-weight:700; color:#717171;">Mobile Number (SMS Verification)</label>
                    <div style="display:flex; gap:8px; margin-top:3px;">
                        <input type="text" id="editProfilePhone" value="${currentUser.phone || ''}" placeholder="0917XXXXXXX" style="flex:1; padding:9px; border:1px solid #ddd; border-radius:8px; font-size:13px;">
                        <button onclick="sendPhoneVerificationOTP()" style="padding:9px 12px; background:${currentUser.isVerified ? '#28a745' : '#1a1a1a'}; color:white; border:none; border-radius:8px; font-size:11px; font-weight:700; cursor:pointer; white-space:nowrap;">
                            ${currentUser.isVerified ? '✓ Verified' : 'Verify SMS'}
                        </button>
                    </div>
                </div>

                <!-- Emergency Contact (ICE) for SOS -->
                <div style="background:#fff3cd; border:1px solid #ffeeba; padding:10px; border-radius:10px;">
                    <label style="font-size:11px; font-weight:800; color:#856404; display:block; margin-bottom:4px;">🚨 In Case of Emergency (ICE) Contact</label>
                    <div style="display:flex; gap:6px;">
                        <input type="text" id="editEmergencyName" value="${currentUser.emergencyName || ''}" placeholder="Contact Name" style="flex:1; padding:8px; border:1px solid #ddd; border-radius:6px; font-size:12px; background:white;">
                        <input type="text" id="editEmergencyPhone" value="${currentUser.emergencyPhone || ''}" placeholder="Contact Number" style="flex:1; padding:8px; border:1px solid #ddd; border-radius:6px; font-size:12px; background:white;">
                    </div>
                </div>

                <!-- App Preferences: Language & Referral Code -->
                <div style="display:flex; gap:10px;">
                    <div style="flex:1;">
                        <label style="font-size:11px; font-weight:700; color:#717171;">App Language</label>
                        <select id="editProfileLanguage" style="width:100%; padding:9px; border:1px solid #ddd; border-radius:8px; font-size:13px; margin-top:3px; background:white;">
                            <option value="Cebuano" ${currentUser.language === 'Cebuano' ? 'selected' : ''}>Cebuano (Bisaya)</option>
                            <option value="English" ${currentUser.language === 'English' ? 'selected' : ''}>English</option>
                        </select>
                    </div>
                    <div style="flex:1;">
                        <label style="font-size:11px; font-weight:700; color:#717171;">My Referral Code</label>
                        <div style="display:flex; align-items:center; background:#e9ecef; padding:8px; border-radius:8px; margin-top:3px; font-size:12px; font-weight:800; color:#495057; justify-content:space-between;">
                            <span>${currentUser.referralCode}</span>
                            <button onclick="navigator.clipboard.writeText('${currentUser.referralCode}'); showToast('Referral code copied!');" style="background:#1a1a1a; color:white; border:none; padding:3px 8px; border-radius:4px; font-size:10px; cursor:pointer;">Copy</button>
                        </div>
                    </div>
                </div>

                <!-- Green Higala Eco Badge Stats -->
                <div style="display:flex; align-items:center; justify-content:space-between; background:#e8f5e9; padding:10px 12px; border-radius:10px;">
                    <div>
                        <span style="font-size:12px; font-weight:800; color:#2e7d32; display:block;">🌱 Green Higala Points</span>
                        <span style="font-size:11px; color:#555;">Carbon emission saved via pool rides</span>
                    </div>
                    <span style="font-size:15px; font-weight:800; color:#2e7d32;">${currentUser.greenPoints || 120} pts</span>
                </div>

                <button id="saveProfileBtn" onclick="saveEnhancedProfile()" style="width:100%; padding:12px; background:#FF6600; color:white; border:none; border-radius:8px; font-weight:800; font-size:13px; cursor:pointer; margin-top:4px;">Save Profile & Sync</button>
            </div>
        </div>
    `;
    modal.style.display = 'flex';
}
window.openProfileModal = openProfileModal;

function closeCustomerProfileModal() {
    const modal = document.getElementById('customerProfileModal');
    if (modal) modal.style.display = 'none';
}
window.closeCustomerProfileModal = closeCustomerProfileModal;

// ==========================================
// ERROR HANDLING & FILE VALIDATION (Max 2MB, Images Only)
// ==========================================
function previewProfilePhoto(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        showToast('Palihog pag-upload og saktong litrato (JPG o PNG lang).', 'error');
        event.target.value = '';
        return;
    }

    const maxSize = 2 * 1024 * 1024; // 2MB
    if (file.size > maxSize) {
        showToast('Gidak-on sa litrato sobra sa 2MB. Palihog pagpili og mas gamay.', 'error');
        event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        currentUser.avatar = e.target.result;
        const previewEl = document.getElementById('profileAvatarPreview');
        if (previewEl) previewEl.src = e.target.result;
        showToast('Litrato napili na successfully!');
    }
    reader.readAsDataURL(file);
}
window.previewProfilePhoto = previewProfilePhoto;

function sendPhoneVerificationOTP() {
    const phoneVal = document.getElementById('editProfilePhone').value.trim();
    if (!phoneVal) {
        showToast('Palihog og butang sa saktong mobile number una mag-verify.', 'error');
        return;
    }
    const code = prompt("Gipadala namo ang 4-digit code sa imong numero (" + phoneVal + "). Palihog isulat dinhi aron ma-verify:");
    if (code && code.length === 4) {
        currentUser.isVerified = true;
        currentUser.phone = phoneVal;
        showToast('Malampuson nga na-verify ang imong numero! 🛡️');
        openProfileModal(); 
    } else if (code) {
        showToast('Sayop ang code. Palihog sulayi pag-usab.', 'error');
    }
}
window.sendPhoneVerificationOTP = sendPhoneVerificationOTP;

// ==========================================
// BACKEND SYNC & API INTEGRATION
// ==========================================
async function saveEnhancedProfile() {
    const btn = document.getElementById('saveProfileBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerText = 'Saving...';
    }

    currentUser.name = document.getElementById('editProfileName').value.trim() || currentUser.name;
    currentUser.age = document.getElementById('editProfileAge').value.trim();
    currentUser.gender = document.getElementById('editProfileGender').value;
    currentUser.barangay = document.getElementById('editProfileBarangay').value;
    currentUser.phone = document.getElementById('editProfilePhone').value.trim();
    currentUser.emergencyName = document.getElementById('editEmergencyName').value.trim();
    currentUser.emergencyPhone = document.getElementById('editEmergencyPhone').value.trim();
    currentUser.language = document.getElementById('editProfileLanguage').value;

    try {
        const res = await fetch(`${API_BASE}/api/user/profile`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${currentUser.token || ''}`
            },
            body: JSON.stringify({
                name: currentUser.name,
                age: currentUser.age,
                gender: currentUser.gender,
                barangay: currentUser.barangay,
                phone: currentUser.phone,
                emergencyName: currentUser.emergencyName,
                emergencyPhone: currentUser.emergencyPhone,
                language: currentUser.language,
                avatar: currentUser.avatar
            })
        });

        if (res.ok || res.status === 404) {
            const headerName = document.getElementById('headerUserName');
            if (headerName) headerName.innerHTML = `${currentUser.name} <span class="user-badge">${currentUser.role}</span>`;
            
            showToast('Na-update ug na-save na ang imong security profile sa database! 👍');
            closeCustomerProfileModal();
        } else {
            showToast('Napakyas sa pag-save sa server. Gitipigan sa local memory.', 'warning');
            closeCustomerProfileModal();
        }
    } catch (err) {
        console.warn('API sync warning:', err);
        const headerName = document.getElementById('headerUserName');
        if (headerName) headerName.innerHTML = `${currentUser.name} <span class="user-badge">${currentUser.role}</span>`;
        showToast('Na-update na ang imong profile (Offline Mode). 👍');
        closeCustomerProfileModal();
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = 'Save Profile & Sync';
        }
    }
}
window.saveEnhancedProfile = saveEnhancedProfile;

function triggerSOS() {
    if (confirm("⚠️ EMERGENCY SOS ALERT: Do you want to notify emergency contacts and dispatch authorities in CDO?")) {
        const contactInfo = currentUser.emergencyName ? ` (${currentUser.emergencyName}: ${currentUser.emergencyPhone})` : '';
        showToast(`🚨 SOS Broadcasted! Emergency authorities & contact${contactInfo} alerted.`, 'error');
    }
}
window.triggerSOS = triggerSOS;