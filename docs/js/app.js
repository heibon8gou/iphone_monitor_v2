/**
 * iPhone Monitor App
 * Refactored for Shadow DOM / External Embedding
 */

window.mountIPhoneMonitor = function (container, config) {
    if (!container) {
        console.error('iPhone Monitor: Container element not found.');
        return;
    }

    // --- 1. Config & Base URL ---
    let baseUrl = config.baseUrl || './';
    if (!baseUrl.endsWith('/')) {
        baseUrl += '/';
    }
    const BASE_URL = baseUrl;

    // --- 2. State (Scoped to this instance) ---
    const INITIAL_DISPLAY_COUNT = 5;
    const LOAD_INCREMENT = 5;

    let allData = [];
    let carriers = ['Rakuten', 'ahamo', 'UQ mobile', 'au', 'SoftBank', 'docomo'];
    let selectedModel = 'All';
    let selectedStorage = 'All';
    let priceMode = 'rent'; // 'rent' or 'buyout'
    let sortOrder = 'price_asc'; // 'price_asc', 'price_desc', 'model_newest'
    let displayedCount = INITIAL_DISPLAY_COUNT;

    // --- 3. DOM Elements Reference ---
    // We will query these relative to `container`
    let updatedAtEl, errorMessageEl, errorTextEl, loadingEl, productContainerEl, mobileListEl, noResultsEl, loadMoreBtn, closeListBtn;
    let modeRentBtn, modeBuyoutBtn, sortSelect;
    // `carrierCheckboxes` are queried dynamically

    // --- 4. Initialization ---

    function init() {
        // Inject HTML
        renderAppStructure();
        // Grab References
        grabElements();
        // Fetch & Setup
        fetchData();
        setupEventListeners();
    }

    // --- 5. Core Functions ---

    function renderAppStructure() {
        // Images with Base URL
        const imgRakuten = BASE_URL + 'images/logo_rakuten.png';
        const imgAhamo = BASE_URL + 'images/logo_ahamo.png';
        const imgUQ = BASE_URL + 'images/logo_uq.png';

        container.innerHTML = `

            <!-- Filters Section -->
            <div class="mb-4 md:mb-8 space-y-6 bg-white p-4 md:p-6 rounded-3xl border border-gray-100 shadow-sm">
                <!-- Carriers -->
                <div class="space-y-2">
                    <h3 class="text-xs font-bold text-gray-400 uppercase tracking-wider ml-1">キャリア</h3>
                    <!-- Mobile: Single line (flex-nowrap), Desktop: Wrap -->
                    <div class="flex gap-1.5 md:gap-3 md:flex-wrap" id="carrier-filters">
                        <label class="cursor-pointer select-none group flex-1 min-w-0">
                            <input type="checkbox" class="filter-carrier peer hidden" value="Rakuten" checked>
                            <div class="h-10 md:h-12 w-full rounded-xl border-2 border-slate-900 bg-gray-50 flex items-center justify-center transition-all opacity-50 grayscale hover:opacity-75 peer-checked:opacity-100 peer-checked:grayscale-0 peer-checked:border-pink-500 peer-checked:bg-white peer-checked:shadow-md px-1">
                                <img src="${imgRakuten}" alt="楽天モバイル" class="h-4 md:h-6 w-auto object-contain">
                            </div>
                        </label>
                        <label class="cursor-pointer select-none group flex-1 min-w-0">
                            <input type="checkbox" class="filter-carrier peer hidden" value="ahamo" checked>
                            <div class="h-10 md:h-12 w-full rounded-xl border-2 border-slate-900 bg-gray-50 flex items-center justify-center transition-all opacity-50 grayscale hover:opacity-75 peer-checked:opacity-100 peer-checked:grayscale-0 peer-checked:border-green-500 peer-checked:bg-white peer-checked:shadow-md px-1">
                                <img src="${imgAhamo}" alt="ahamo" class="h-4 md:h-6 w-auto object-contain">
                            </div>
                        </label>
                        <label class="cursor-pointer select-none group flex-1 min-w-0">
                            <input type="checkbox" class="filter-carrier peer hidden" value="UQ mobile" checked>
                            <div class="h-10 md:h-12 w-full rounded-xl border-2 border-slate-900 bg-gray-50 flex items-center justify-center transition-all opacity-50 grayscale hover:opacity-75 peer-checked:opacity-100 peer-checked:grayscale-0 peer-checked:border-blue-500 peer-checked:bg-white peer-checked:shadow-md px-1">
                                <img src="${imgUQ}" alt="UQ mobile" class="h-4 md:h-6 w-auto object-contain">
                            </div>
                        </label>
                        <label class="cursor-pointer select-none group flex-1 min-w-0">
                            <input type="checkbox" class="filter-carrier peer hidden" value="au" checked>
                            <div class="h-10 md:h-12 w-full rounded-xl border-2 border-slate-900 bg-gray-50 flex items-center justify-center transition-all opacity-50 grayscale hover:opacity-75 peer-checked:opacity-100 peer-checked:grayscale-0 peer-checked:border-orange-500 peer-checked:bg-white peer-checked:shadow-md px-1">
                                <img src="${BASE_URL}images/logo_au.svg" alt="au" class="h-4 md:h-6 w-auto object-contain">
                            </div>
                        </label>
                        <label class="cursor-pointer select-none group flex-1 min-w-0">
                            <input type="checkbox" class="filter-carrier peer hidden" value="SoftBank" checked>
                            <div class="h-10 md:h-12 w-full rounded-xl border-2 border-slate-900 bg-gray-50 flex items-center justify-center transition-all opacity-50 grayscale hover:opacity-75 peer-checked:opacity-100 peer-checked:grayscale-0 peer-checked:border-gray-400 peer-checked:bg-white peer-checked:shadow-md px-1">
                                <img src="${BASE_URL}images/logo_softbank.svg" alt="SoftBank" class="h-4 md:h-6 w-auto object-contain">
                            </div>
                        </label>
                        <label class="cursor-pointer select-none group flex-1 min-w-0">
                            <input type="checkbox" class="filter-carrier peer hidden" value="docomo" checked>
                            <div class="h-10 md:h-12 w-full rounded-xl border-2 border-slate-900 bg-gray-50 flex items-center justify-center transition-all opacity-50 grayscale hover:opacity-75 peer-checked:opacity-100 peer-checked:grayscale-0 peer-checked:border-red-600 peer-checked:bg-white peer-checked:shadow-md px-1">
                                <img src="${BASE_URL}images/logo_docomo.svg" alt="docomo" class="h-4 md:h-6 w-auto object-contain">
                            </div>
                        </label>
                    </div>
                </div>

                <!-- Models -->
                <div class="space-y-2">
                    <h3 class="text-xs font-bold text-gray-400 uppercase tracking-wider ml-1">機種</h3>
                    <div class="flex gap-3 overflow-x-auto p-1 no-scrollbar md:flex-wrap" id="filter-model-container"></div>
                </div>

                <!-- Storage -->
                <div class="space-y-2">
                    <h3 class="text-xs font-bold text-gray-400 uppercase tracking-wider ml-1">ストレージ容量</h3>
                    <div class="flex gap-3 overflow-x-auto p-1 no-scrollbar md:flex-wrap" id="filter-storage-container"></div>
                </div>

                <!-- Sort -->
                 <div class="flex justify-end pt-2 border-t border-gray-100">
                    <div class="relative">
                        <select id="sort-select" class="appearance-none bg-white border border-gray-200 text-gray-700 py-2 pl-4 pr-10 rounded-lg shadow-sm text-sm font-bold focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent cursor-pointer">
                            <option value="price_asc">価格が安い順</option>
                            <option value="price_desc">価格が高い順</option>
                            <option value="model_newest">新しい機種順</option>
                        </select>
                        <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-500">
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                            </svg>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Error -->
            <div id="error-message" class="hidden bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg mb-6 text-sm">
                <strong class="font-bold">エラー:</strong> <span id="error-text">データの読み込みに失敗しました。</span>
            </div>

            <!-- Loading -->
            <div id="loading" class="text-center py-20">
                <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-gray-900 mx-auto"></div>
            </div>

            <!-- Product Grid -->
            <div id="product-container" class="hidden">
                <div id="mobile-list" class="grid grid-cols-1 gap-6"></div>
                
                <!-- Load More & Close Buttons -->
                <div class="mt-8 flex flex-col md:flex-row gap-3 justify-center items-center">
                    <button id="load-more-btn" class="hidden w-full md:w-auto md:px-12 py-3 bg-gray-100 text-gray-700 font-bold rounded-xl hover:bg-gray-200 transition-colors shadow-sm active:scale-95">
                        もっと見る (+10件)
                    </button>
                    <button id="close-list-btn" class="hidden w-full md:w-auto md:px-8 py-3 bg-white text-gray-600 font-bold border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors shadow-sm active:scale-95">
                        閉じる
                    </button>
                </div>

                <div id="no-results" class="hidden text-center py-20">
                    <p class="text-gray-500 font-bold mb-2">条件に一致するiPhoneが見つかりませんでした</p>
                    <p class="text-gray-400 text-sm">フィルターを変更して再度お試しください</p>
                </div>
            </div>
        `;
    }

    function grabElements() {
        // Scoped queries
        updatedAtEl = container.querySelector('#updated-at');
        errorMessageEl = container.querySelector('#error-message');
        errorTextEl = container.querySelector('#error-text');
        loadingEl = container.querySelector('#loading');
        productContainerEl = container.querySelector('#product-container');
        mobileListEl = container.querySelector('#mobile-list');
        noResultsEl = container.querySelector('#no-results');
        loadMoreBtn = container.querySelector('#load-more-btn');
        closeListBtn = container.querySelector('#close-list-btn');

        modeRentBtn = container.querySelector('#mode-rent');
        modeBuyoutBtn = container.querySelector('#mode-buyout');
        sortSelect = container.querySelector('#sort-select');
    }

    function setupEventListeners() {
        const carrierCheckboxes = container.querySelectorAll('.filter-carrier');
        carrierCheckboxes.forEach(cb => {
            cb.addEventListener('change', () => {
                carriers = Array.from(carrierCheckboxes)
                    .filter(c => c.checked)
                    .map(c => c.value);
                resetDisplayCount();
                render();
            });
        });

        if (sortSelect) {
            sortSelect.addEventListener('change', (e) => {
                sortOrder = e.target.value;
                resetDisplayCount();
                render();
            });
        }

        if (modeRentBtn) modeRentBtn.onclick = () => setPriceMode('rent');
        if (modeBuyoutBtn) modeBuyoutBtn.onclick = () => setPriceMode('buyout');

        if (loadMoreBtn) {
            loadMoreBtn.onclick = () => {
                displayedCount += LOAD_INCREMENT;
                render();
            };
        }

        if (closeListBtn) {
            closeListBtn.onclick = () => {
                displayedCount = INITIAL_DISPLAY_COUNT;
                render();
                // Scroll back to top
                container.scrollIntoView({ behavior: 'smooth' });
            };
        }
    }

    function resetDisplayCount() {
        displayedCount = INITIAL_DISPLAY_COUNT;
    }

    async function fetchData() {
        try {
            const response = await fetch(BASE_URL + 'data.json');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status} `);
            const data = await response.json();

            if (updatedAtEl) updatedAtEl.textContent = data.updated_at || '不明';

            allData = data.items;

            populateFilterChips(allData);
            markLowestPrices(allData);

            if (loadingEl) loadingEl.classList.add('hidden');
            if (productContainerEl) productContainerEl.classList.remove('hidden');
            render();

        } catch (err) {
            console.error(err);
            if (loadingEl) loadingEl.classList.add('hidden');
            if (errorMessageEl) errorMessageEl.classList.remove('hidden');
            if (errorTextEl) errorTextEl.textContent = err.message;
        }
    }

    function populateFilterChips(items) {
        const modelContainer = container.querySelector('#filter-model-container');
        const storageContainer = container.querySelector('#filter-storage-container');

        if (!modelContainer || !storageContainer) return;

        // --- Models ---
        const models = [...new Set(items.map(i => i.model))];
        models.sort((a, b) => {
            const getNum = (s) => {
                if (s.includes('SE')) return -1;
                const match = s.match(/iPhone\s*(\d+)/);
                return match ? parseInt(match[1]) : 0;
            };
            const numA = getNum(a);
            const numB = getNum(b);
            if (numA !== numB) return numB - numA; // Descending
            return a.localeCompare(b);
        });
        models.unshift('All');

        modelContainer.innerHTML = '';
        models.forEach(m => {
            const btn = document.createElement('button');
            btn.textContent = (m === 'All') ? '全て' : (m.startsWith('iPhone') ? m : 'iPhone ' + m);
            btn.className = getChipClass(m === selectedModel);
            btn.onclick = () => {
                selectedModel = m;
                updateChipStyles(modelContainer, m, '全て');
                resetDisplayCount();
                render();
            };
            modelContainer.appendChild(btn);
        });

        // --- Storage ---
        const storages = [...new Set(items.map(i => i.storage))];
        storages.sort((a, b) => {
            const parse = (s) => (s.includes('TB') ? parseInt(s) * 1024 : parseInt(s) || 9999);
            return parse(a) - parse(b);
        });
        storages.unshift('All');

        storageContainer.innerHTML = '';
        storages.filter(s => s !== 'Unknown' && s !== '最小容量').forEach(s => {
            const btn = document.createElement('button');
            btn.textContent = (s === 'All') ? '全て' : s;
            btn.className = getChipClass(s === selectedStorage);
            btn.onclick = () => {
                selectedStorage = s;
                updateChipStyles(storageContainer, s, '全て');
                resetDisplayCount();
                render();
            };
            storageContainer.appendChild(btn);
        });
    }

    function getChipClass(isSelected) {
        const baseClass = "flex-shrink-0 whitespace-nowrap px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ease-out active:scale-95 outline-none";

        if (isSelected) {
            return `${baseClass} bg-slate-900 text-white shadow-md scale-105`;
        } else {
            return `${baseClass} bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50 scale-100`;
        }
    }

    function updateChipStyles(chipContainer, selectedValue, allLabel) {
        if (!chipContainer) return;
        Array.from(chipContainer.children).forEach(btn => {
            const label = btn.textContent;
            const isSelected = (label === selectedValue.replace('iPhone ', '')) || (label === allLabel && selectedValue === 'All') || (label === selectedValue) || (selectedValue !== 'All' && label === (selectedValue.startsWith('iPhone') ? selectedValue : 'iPhone ' + selectedValue));
            btn.className = getChipClass(isSelected);
        });
    }

    function markLowestPrices(items) {
        const groups = {};
        items.forEach(item => {
            const key = `${item.model} -${item.storage} `;
            if (!groups[key]) groups[key] = [];
            groups[key].push(item);
        });

        Object.values(groups).forEach(group => {
            if (group.length === 0) return;
            const getMonthlyPrice = (i) => i.monthly_payment || (i.price_effective_rent ? Math.floor(i.price_effective_rent / 24) : 0);
            const minPrice = Math.min(...group.map(i => priceMode === 'rent' ? getMonthlyPrice(i) : i.price_gross));
            group.forEach(item => {
                const price = priceMode === 'rent' ? getMonthlyPrice(item) : item.price_gross;
                item.isLowest = (price === minPrice);
            });
        });
    }

    function setPriceMode(mode) {
        priceMode = mode;

        const toggleBg = container.querySelector('#toggle-bg');
        // Note: modeRentBtn and modeBuyoutBtn are already scoped variables

        if (toggleBg && modeRentBtn && modeBuyoutBtn) {
            if (mode === 'rent') {
                toggleBg.classList.remove('translate-x-full');
                modeRentBtn.classList.remove('text-gray-500');
                modeRentBtn.classList.add('text-black');
                modeBuyoutBtn.classList.remove('text-black');
                modeBuyoutBtn.classList.add('text-gray-500');
            } else {
                toggleBg.classList.add('translate-x-full');
                modeRentBtn.classList.remove('text-black');
                modeRentBtn.classList.add('text-gray-500');
                modeBuyoutBtn.classList.remove('text-gray-500');
                modeBuyoutBtn.classList.add('text-black');
            }
        }

        markLowestPrices(allData);
        render();
    }

    function render() {
        let filtered = allData.filter(item => {
            if (!carriers.includes(item.carrier)) return false;
            if (selectedModel !== 'All' && item.model !== selectedModel) return false;
            if (selectedModel !== 'All' && item.model !== selectedModel) return false;
            if (selectedStorage !== 'All') {
                if (item.storage === '最小容量') {
                    // Heuristic: If storage filter is 128GB (standard) or 64GB (SE), show "最小容量" too
                    if (selectedStorage !== '128GB' && selectedStorage !== '64GB' && selectedStorage !== '256GB') return false; 
                    // Basically allow "最小容量" to show up or be generous
                } else if (item.storage !== selectedStorage) {
                    return false;
                }
            }
            return true;
        });

        filtered.sort((a, b) => {
            if (sortOrder === 'model_newest') {
                const getNum = (s) => {
                    if (s.includes('SE')) return -1;
                    const match = s.match(/iPhone\s*(\d+)/);
                    return match ? parseInt(match[1]) : 0;
                };
                const numA = getNum(a.model);
                const numB = getNum(b.model);
                if (numA !== numB) return numB - numA;
                return a.model.localeCompare(b.model);
            } else {
                const getMonthlyPrice = (i) => i.monthly_payment || (i.price_effective_rent ? Math.floor(i.price_effective_rent / 24) : 0);
                const valA = priceMode === 'rent' ? getMonthlyPrice(a) : a.price_gross;
                const valB = priceMode === 'rent' ? getMonthlyPrice(b) : b.price_gross;
                return sortOrder === 'price_asc' ? valA - valB : valB - valA;
            }
        });

        const currentFilteredData = filtered;

        if (mobileListEl) mobileListEl.innerHTML = '';

        if (currentFilteredData.length === 0) {
            if (productContainerEl) productContainerEl.classList.add('hidden');
            if (noResultsEl) noResultsEl.classList.remove('hidden');
            if (loadMoreBtn) loadMoreBtn.classList.add('hidden');
            return;
        } else {
            if (productContainerEl) productContainerEl.classList.remove('hidden');
            if (noResultsEl) noResultsEl.classList.add('hidden');
        }

        const hasMore = currentFilteredData.length > displayedCount;
        const isExpanded = displayedCount > INITIAL_DISPLAY_COUNT;

        if (loadMoreBtn) {
            if (hasMore) {
                loadMoreBtn.classList.remove('hidden');
                loadMoreBtn.textContent = `もっと見る（あと${currentFilteredData.length - displayedCount}件）`;
            } else {
                loadMoreBtn.classList.add('hidden');
            }
        }

        if (closeListBtn) {
            if (isExpanded) {
                closeListBtn.classList.remove('hidden');
            } else {
                closeListBtn.classList.add('hidden');
            }
        }

        const visibleItems = currentFilteredData.slice(0, displayedCount);

        visibleItems.forEach(item => {
            const imgUrl = getProductImage(item.model);
            const carrierName = getCarrierDisplayName(item.carrier);
            const carrierLogo = getCarrierLogoPath(item.carrier);
            const isLowest = item.isLowest;

            let unitBadge = '', phasesHTML = '';
            // Monthly payment only
            const monthlyPayment = item.monthly_payment || (item.price_effective_rent ? Math.floor(item.price_effective_rent / 24) : 0);
            const displayPrice = monthlyPayment;
            if (item.program_exemption > 0) unitBadge = '返却P';
            
            // Monthly payment phases display (all carriers)
            if (item.monthly_payment_phases && item.monthly_payment_phases.length > 1) {
                const phases = item.monthly_payment_phases
                    .filter(p => p.amount > 0)
                    .map(p => `<span class="inline-block">${p.period}: ¥${p.amount.toLocaleString()}</span>`)
                    .join('<span class="mx-1 text-gray-300">→</span>');
                if (phases) {
                    phasesHTML = `<div class="mt-1 text-[10px] text-gray-500 leading-relaxed">${phases}</div>`;
                }
            }

            const fmtPrice = displayPrice.toLocaleString();
            const lowestBadge = isLowest ? `<div class="absolute top-2 left-2 bg-yellow-400 text-yellow-900 text-[10px] font-black px-2 py-0.5 rounded shadow-sm z-10">最安</div>` : '';

            const cardHTML = `
                <div class="flex flex-col gap-3 p-5 border border-gray-100 rounded-2xl bg-white shadow-sm hover:shadow-xl hover:-translate-y-1 hover:border-blue-200 transition-all duration-300 relative overflow-hidden group">
                    ${lowestBadge}
                    <div class="flex gap-4 items-start">
                        <div class="w-20 h-24 flex-shrink-0 bg-gray-50 rounded-xl flex items-center justify-center p-2 group-hover:bg-blue-50/50 transition-colors">
                            <img src="${imgUrl}" onerror="this.onerror=null; this.src='https://placehold.co/200x250/e2e8f0/64748b?text=No+Image'; this.classList.add('opacity-50');" class="w-full h-full object-contain mix-blend-multiply transition-transform duration-500 group-hover:scale-110">
                        </div>
                        <div class="flex-grow min-w-0">
                            <div class="flex flex-col gap-1 items-start mb-2">
                                <div>
                                    <h3 class="text-lg font-bold text-gray-900 leading-tight">${item.model}</h3>
                                    <div class="flex flex-wrap gap-1 mt-1">
                                            <span class="text-[10px] font-medium text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">${item.storage}</span>
                                    </div>
                                </div>
                                <img src="${carrierLogo}" alt="${carrierName}" class="h-5 object-contain object-left mt-1 opacity-80 group-hover:opacity-100 transition-opacity">
                            </div>
                            <div class="mt-3">
                                <div class="flex items-baseline gap-1">
                                    <span class="text-xs text-gray-400 font-bold">月々</span>
                                    <span class="text-3xl font-black text-slate-800 tracking-tighter font-sans">¥${fmtPrice}〜</span>
                                </div>
                                ${phasesHTML}
                                ${unitBadge ? `<div class="mt-1"><span class="text-[10px] text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded font-bold">${unitBadge}</span></div>` : ''}
                            </div>
                        </div>
                    </div>
                    <a href="${item.url}" target="_blank" class="block w-full bg-slate-900 text-white text-center text-sm font-bold py-3 rounded-xl shadow-lg shadow-slate-200 hover:bg-slate-800 hover:shadow-xl transition active:scale-95 flex items-center justify-center gap-2 group/btn">
                        公式サイトで見る
                        <svg class="w-4 h-4 transition-transform group-hover/btn:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
                    </a>
                </div>
            `;
            mobileListEl.insertAdjacentHTML('beforeend', cardHTML);
        });
    }

    function getCarrierLogoPath(carrier) {
        if (carrier === 'Rakuten') return BASE_URL + 'images/logo_rakuten.png';
        if (carrier === 'ahamo') return BASE_URL + 'images/logo_ahamo.png';
        if (carrier === 'UQ mobile') return BASE_URL + 'images/logo_uq.png';
        if (carrier === 'au') return BASE_URL + 'images/logo_au.svg';
        if (carrier === 'SoftBank') return BASE_URL + 'images/logo_softbank.svg';
        if (carrier === 'docomo') return BASE_URL + 'images/logo_docomo.svg';
        return '';
    }

    function getCarrierDisplayName(carrier) {
        if (carrier === 'Rakuten') return '楽天モバイル';
        if (carrier === 'docomo') return 'ドコモ';
        return carrier;
    }

    function getProductImage(model) {
        let clean = model.toLowerCase();
        if (clean.includes('se') && (clean.includes('3') || clean.includes('第3'))) {
            clean = 'iphonese3';
        } else {
            clean = clean.replace(/[^a-z0-9]/g, '');
        }
        return BASE_URL + 'images/' + clean + '.png';
    }

    // Initialize!
    init();
};

/**
 * Legacy Support: Auto-mount on DOMContentLoaded
 * if #monitor-app exists (for existing pages/iframes).
 */
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('monitor-app');
    if (container) {
        // Pass global config if available
        window.mountIPhoneMonitor(container, window.iPhoneMonitorConfig || {});
    }
});
