// App state
const state = {
    analyzing: false,
    currentResults: null
};

// DOM Elements
const reportInput = document.getElementById('report-input');
const analyzeBtn = document.getElementById('analyze-btn');
const clearBtn = document.getElementById('clear-btn');
const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const errorMessageEl = document.getElementById('error-message');
const errorCloseBtn = document.getElementById('error-close');
const resultsEl = document.getElementById('results');
const statusIndicator = document.getElementById('status-indicator');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    setupEventListeners();
});

// Event Listeners
function setupEventListeners() {
    analyzeBtn.addEventListener('click', handleAnalyze);
    clearBtn.addEventListener('click', handleClear);
    errorCloseBtn.addEventListener('click', hideError);
}

// Check backend health
async function checkHealth() {
    try {
        const response = await fetch('/health');
        const data = await response.json();
        
        if (data.status === 'healthy') {
            updateStatusIndicator('healthy', 'Sistem hazır');
        } else {
            updateStatusIndicator('error', 'Sistem hatası');
        }
    } catch (error) {
        updateStatusIndicator('error', 'Bağlantı hatası');
    }
}

function updateStatusIndicator(status, message) {
    const indicator = statusIndicator.querySelector('div');
    const text = statusIndicator.querySelector('span');
    
    indicator.className = 'w-3 h-3 rounded-full';
    
    if (status === 'healthy') {
        indicator.classList.add('bg-green-500');
        text.className = 'text-sm text-green-600';
    } else if (status === 'error') {
        indicator.classList.add('bg-red-500');
        text.className = 'text-sm text-red-600';
    } else {
        indicator.classList.add('bg-yellow-500');
        text.className = 'text-sm text-yellow-600';
    }
    
    text.textContent = message;
}

// Handle analyze button
async function handleAnalyze() {
    const reportText = reportInput.value.trim();
    
    if (!reportText) {
        showError('Lütfen rapor metnini girin');
        return;
    }
    
    if (state.analyzing) {
        return;
    }
    
    state.analyzing = true;
    showLoading();
    hideError();
    hideResults();
    
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ report_text: reportText })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'Analiz başarısız oldu');
        }
        
        state.currentResults = data;
        displayResults(data);
        
    } catch (error) {
        console.error('Analysis error:', error);
        showError(error.message || 'Bir hata oluştu. Lütfen tekrar deneyin.');
    } finally {
        state.analyzing = false;
        hideLoading();
    }
}

// Handle clear button
function handleClear() {
    reportInput.value = '';
    hideError();
    hideResults();
    reportInput.focus();
}

// Show/hide UI elements
function showLoading() {
    loadingEl.classList.remove('hidden');
    analyzeBtn.disabled = true;
    analyzeBtn.classList.add('opacity-50', 'cursor-not-allowed');
}

function hideLoading() {
    loadingEl.classList.add('hidden');
    analyzeBtn.disabled = false;
    analyzeBtn.classList.remove('opacity-50', 'cursor-not-allowed');
}

function showError(message) {
    errorMessageEl.textContent = message;
    errorEl.classList.remove('hidden');
}

function hideError() {
    errorEl.classList.add('hidden');
}

function hideResults() {
    resultsEl.classList.add('hidden');
}

function showResults() {
    resultsEl.classList.remove('hidden');
}

// Display results
function displayResults(data) {
    displayDrugResults(data.results);
    displayPerformance(data.performance);
    showResults();
}

function displayDrugResults(results) {
    const container = document.getElementById('drug-results');
    const summaryContainer = document.getElementById('summary');
    
    // Calculate summary
    const eligible = results.filter(r => r.status === 'ELIGIBLE').length;
    const conditional = results.filter(r => r.status === 'CONDITIONAL').length;
    const notEligible = results.filter(r => r.status === 'NOT_ELIGIBLE').length;
    
    summaryContainer.innerHTML = `
        <div class="flex items-center space-x-2">
            <div class="w-3 h-3 bg-green-500 rounded-full"></div>
            <span class="text-gray-700">Uygun: <strong>${eligible}</strong></span>
        </div>
        <div class="flex items-center space-x-2">
            <div class="w-3 h-3 bg-yellow-500 rounded-full"></div>
            <span class="text-gray-700">Koşullu: <strong>${conditional}</strong></span>
        </div>
        <div class="flex items-center space-x-2">
            <div class="w-3 h-3 bg-red-500 rounded-full"></div>
            <span class="text-gray-700">Uygun Değil: <strong>${notEligible}</strong></span>
        </div>
    `;
    
    // Display each drug
    container.innerHTML = results.map((result, index) => {
        const statusConfig = getStatusConfig(result.status);
        
        return `
            <div class="border-l-4 ${statusConfig.borderColor} bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
                <div class="flex items-start justify-between mb-4">
                    <div class="flex-1">
                        <div class="flex items-center space-x-3 mb-2">
                            <span class="text-2xl font-bold text-gray-400">${index + 1}</span>
                            <h3 class="text-xl font-bold text-gray-800">${result.drug_name}</h3>
                        </div>
                        <div class="flex items-center space-x-2">
                            <span class="text-2xl">${statusConfig.emoji}</span>
                            <span class="px-3 py-1 ${statusConfig.bgColor} ${statusConfig.textColor} rounded-full text-sm font-semibold">
                                ${statusConfig.text}
                            </span>
                            <span class="text-sm text-gray-500">
                                (${(result.confidence * 100).toFixed(0)}% güven)
                            </span>
                        </div>
                    </div>
                </div>
                
                <div class="mb-4">
                    <div class="flex items-start space-x-2 text-sm text-gray-600">
                        <i class="fas fa-book text-indigo-600 mt-1"></i>
                        <div>
                            <span class="font-semibold">SUT Referans:</span> ${result.sut_reference}
                        </div>
                    </div>
                </div>
                
                ${result.conditions.length > 0 ? `
                    <div class="mb-4">
                        <h4 class="font-semibold text-gray-700 mb-2 flex items-center">
                            <i class="fas fa-list-check text-indigo-600 mr-2"></i>
                            Koşullar
                        </h4>
                        <div class="space-y-2">
                            ${result.conditions.map(condition => `
                                <div class="flex items-start space-x-2 text-sm">
                                    <span class="text-lg">${getConditionIcon(condition.is_met)}</span>
                                    <div class="flex-1">
                                        <p class="text-gray-700">${condition.description}</p>
                                        ${condition.required_info ? `
                                            <p class="text-gray-500 text-xs mt-1 ml-4">→ ${condition.required_info}</p>
                                        ` : ''}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${result.explanation ? `
                    <div class="mb-4 p-4 bg-blue-50 rounded-lg">
                        <h4 class="font-semibold text-gray-700 mb-2 flex items-center">
                            <i class="fas fa-info-circle text-blue-600 mr-2"></i>
                            Açıklama
                        </h4>
                        <p class="text-sm text-gray-700 whitespace-pre-line">${result.explanation}</p>
                    </div>
                ` : ''}
                
                ${result.warnings.length > 0 ? `
                    <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                        <h4 class="font-semibold text-yellow-800 mb-2 flex items-center">
                            <i class="fas fa-exclamation-triangle mr-2"></i>
                            Uyarılar
                        </h4>
                        <ul class="list-disc list-inside space-y-1">
                            ${result.warnings.map(warning => `
                                <li class="text-sm text-yellow-700">${warning}</li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

function displayPerformance(performance) {
    const container = document.getElementById('performance');
    
    const metrics = [
        { label: 'Rapor Analizi', value: performance.parsing, unit: 'ms' },
        { label: 'RAG Retrieval', value: performance.retrieval, unit: 'ms' },
        { label: 'Uygunluk Kontrolü', value: performance.eligibility_check, unit: 'ms' },
        { label: 'Toplam Süre', value: performance.total, unit: 'ms', highlight: true },
    ];
    
    container.innerHTML = metrics.map(metric => {
        const seconds = metric.value / 1000;
        const displayValue = metric.value < 1000 ? 
            `${metric.value.toFixed(1)} ${metric.unit}` : 
            `${seconds.toFixed(2)} s`;
        
        return `
            <div class="p-4 ${metric.highlight ? 'bg-indigo-50 border border-indigo-200' : 'bg-gray-50'} rounded-lg">
                <p class="text-xs text-gray-500 font-medium mb-1">${metric.label}</p>
                <p class="text-2xl font-bold ${metric.highlight ? 'text-indigo-600' : 'text-gray-800'}">${displayValue}</p>
            </div>
        `;
    }).join('');
}

// Helper functions
function getStatusConfig(status) {
    const configs = {
        'ELIGIBLE': {
            emoji: '✅',
            text: 'SGK KAPSAMINDA KARŞILANIR',
            bgColor: 'bg-green-100',
            textColor: 'text-green-800',
            borderColor: 'border-green-500'
        },
        'NOT_ELIGIBLE': {
            emoji: '❌',
            text: 'SGK KAPSAMINDA DEĞİL',
            bgColor: 'bg-red-100',
            textColor: 'text-red-800',
            borderColor: 'border-red-500'
        },
        'CONDITIONAL': {
            emoji: '⚠️',
            text: 'KOŞULLU - EK BİLGİ GEREKİYOR',
            bgColor: 'bg-yellow-100',
            textColor: 'text-yellow-800',
            borderColor: 'border-yellow-500'
        }
    };
    
    return configs[status] || configs['CONDITIONAL'];
}

function getConditionIcon(isMet) {
    if (isMet === true) return '✅';
    if (isMet === false) return '❌';
    return '❓';
}
