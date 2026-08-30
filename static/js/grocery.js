// ==========================================
// GROCERY.JS - Higala Grocery
// ==========================================
const groceryData = [
    // Grains & Rice (Number 1 sa CDO!)
    { id: 'g1', category: 'Rice & Grains', name: 'Premium White Rice (5kg)', desc: 'Sinandomeng local rice sack', price: 260.00, img: 'https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=100&q=80' },
    { id: 'g2', category: 'Rice & Grains', name: 'Jasponica Rice (5kg)', desc: 'Aromatic soft premium quality rice', price: 320.00, img: 'https://images.unsplash.com/photo-1516684732162-798a0862be18?auto=format&fit=crop&w=100&q=80' },

    // Fresh Produce
    { id: 'g3', category: 'Fresh Produce', name: 'Fresh Baguio Vegetables Mix (1kg)', desc: 'Carrots, cabbage, potatoes bundle', price: 150.00, img: 'https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=100&q=80' },
    { id: 'g4', category: 'Fresh Produce', name: 'Mindanao Fresh Bananas (1kg)', desc: 'Sweet saba or latundan bananas', price: 75.00, img: 'https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?auto=format&fit=crop&w=100&q=80' },

    // Dairy & Breakfast
    { id: 'g5', category: 'Dairy & Breakfast', name: 'Fresh Whole Milk (1L)', desc: 'Full cream fresh dairy milk', price: 95.00, img: 'https://images.unsplash.com/photo-1563636619-e9143da7973b?auto=format&fit=crop&w=100&q=80' },
    { id: 'g6', category: 'Dairy & Breakfast', name: 'CDO Farm Fresh Eggs (Tray of 30)', desc: 'Medium sized fresh chicken eggs', price: 220.00, img: 'https://images.unsplash.com/photo-1582722872445-44dc5f7e3c8f?auto=format&fit=crop&w=100&q=80' },

    // Pantry & Canned Goods
    { id: 'g7', category: 'Pantry', name: 'Mega Sardines in Tomato Sauce (155g)', desc: 'Standard red can easy open', price: 23.00, img: 'https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=100&q=80' },
    { id: 'g8', category: 'Pantry', name: 'Argentina Corned Beef (150g)', desc: 'Classic beef chunks style', price: 38.00, img: 'https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?auto=format&fit=crop&w=100&q=80' },

    // Snacks & Beverages
    { id: 'g9', category: 'Snacks & Drinks', name: 'San Miguel Pale Pilsen (6-pack)', desc: 'Bottled beer 330ml each', price: 340.00, img: 'https://images.unsplash.com/photo-1608270104343-24392e205128?auto=format&fit=crop&w=100&q=80' },
    { id: 'g10', category: 'Snacks & Drinks', name: 'Great Taste Granules Coffee (100g)', desc: 'Strong instant coffee refill pack', price: 85.00, img: 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=100&q=80' },

    // Household & Cleaning
    { id: 'g11', category: 'Household', name: 'Surf Cherry Blossom Powder (1kg)', desc: 'Detergent powder with fabcon', price: 98.00, img: 'https://images.unsplash.com/photo-1585421514284-efb74c2b69ba?auto=format&fit=crop&w=100&q=80' },
    { id: 'g12', category: 'Household', name: 'Joy Dishwashing Liquid (250ml)', desc: 'Anti-grease kalamansi scent', price: 65.00, img: 'https://images.unsplash.com/photo-1585670149967-b4f4da88cc9f?auto=format&fit=crop&w=100&q=80' }
];

let currentGroceryCategory = 'All';

function renderGroceryUI() {
    const container = document.getElementById('itemsContainer');
    if (!container) return;
    container.innerHTML = '';

    // I-render ang Category Filter Buttons sa ibabaw sa grocery section
    const categories = ['All', 'Rice & Grains', 'Fresh Produce', 'Dairy & Breakfast', 'Pantry', 'Snacks & Drinks', 'Household'];
    
    const filterWrapper = document.createElement('div');
    filterWrapper.style.cssText = 'display: flex; gap: 6px; overflow-x: auto; padding-bottom: 12px; margin-bottom: 14px; white-space: nowrap;';
    
    categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'action-btn';
        btn.innerText = cat === 'All' ? '🌐 Tanan' : cat;
        if (currentGroceryCategory === cat) {
            btn.style.background = 'var(--primary)';
            btn.style.color = 'white';
        } else {
            btn.style.background = '#f1f5f9';
            btn.style.color = 'var(--text)';
        }
        btn.onclick = () => {
            currentGroceryCategory = cat;
            renderGroceryUI();
        };
        filterWrapper.appendChild(btn);
    });
    container.appendChild(filterWrapper);

    // I-filter ang items base sa gipili nga category
    const filteredItems = currentGroceryCategory === 'All' 
        ? groceryData 
        : groceryData.filter(item => item.category === currentGroceryCategory);

    if (filteredItems.length === 0) {
        const emptyMsg = document.createElement('div');
        emptyMsg.style.cssText = 'text-align: center; color: var(--muted); padding: 30px; font-size: 13px;';
        emptyMsg.innerText = 'Walay produkto nga napaabot niining kategoryaha.';
        container.appendChild(emptyMsg);
        return;
    }

    // I-render ang mga items sa saktong kategorya
    filteredItems.forEach(item => {
        const itemRow = document.createElement('div');
        itemRow.className = 'item-row';
        itemRow.innerHTML = `
            <div class="item-left">
                <img src="${item.img}" class="item-thumb">
                <div class="item-details">
                    <h4>${item.name}</h4>
                    <p>${item.desc}</p>
                    <div class="item-price">₱${item.price.toFixed(2)}</div>
                </div>
            </div>
            <button class="action-btn" onclick="addToCart('${item.name}', ${item.price}, '${item.img}', MERCHANT_IDS.grocery, 'grocery')">Add to Cart</button>
        `;
        container.appendChild(itemRow);
    });
}

window.renderGroceryUI = renderGroceryUI;