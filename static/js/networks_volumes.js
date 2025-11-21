/**
 * Networks & Volumes Page - JavaScript
 */

// Variable to track current tab
let currentTab = 'networks';

/**
 * Show specific tab
 */
function showTab(tabName) {
    currentTab = tabName;
    
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active from all buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabName).classList.add('active');
    
    // Add active to clicked button
    event.target.classList.add('active');
    
    console.log(`📑 Switched to ${tabName} tab`);
}

/**
 * Setup networks search
 */
function setupNetworksSearch() {
    const searchInput = document.getElementById('search-networks');
    if (!searchInput) return;
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        const networkCards = document.querySelectorAll('#networks-list .network-card');
        
        let visibleCount = 0;
        
        networkCards.forEach(card => {
            const networkName = card.getAttribute('data-name');
            
            if (!searchTerm || networkName.includes(searchTerm)) {
                card.classList.remove('hidden');
                visibleCount++;
            } else {
                card.classList.add('hidden');
            }
        });
        
        console.log(`🔍 Networks search: "${searchTerm}" - ${visibleCount} results`);
    });
}

/**
 * Setup volumes search
 */
function setupVolumesSearch() {
    const searchInput = document.getElementById('search-volumes');
    if (!searchInput) return;
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        const volumeCards = document.querySelectorAll('#volumes-list .volume-card');
        
        let visibleCount = 0;
        
        volumeCards.forEach(card => {
            const volumeName = card.getAttribute('data-name');
            
            if (!searchTerm || volumeName.includes(searchTerm)) {
                card.classList.remove('hidden');
                visibleCount++;
            } else {
                card.classList.add('hidden');
            }
        });
        
        console.log(`🔍 Volumes search: "${searchTerm}" - ${visibleCount} results`);
    });
}

/**
 * Update networks data
 */
async function updateNetworks() {
    try {
        const response = await fetch('/api/networks');
        const networks = await response.json();
        
        console.log(`✅ Networks updated: ${networks.length} networks`);
        
        // TODO: Update UI dynamically if needed
        // For now we do a full refresh
        
    } catch (error) {
        console.error('❌ Error updating networks:', error);
    }
}

/**
 * Update volumes data
 */
async function updateVolumes() {
    try {
        const response = await fetch('/api/volumes');
        const volumes = await response.json();
        
        console.log(`✅ Volumes updated: ${volumes.length} volumes`);
        
        // TODO: Update UI dynamically if needed
        
    } catch (error) {
        console.error('❌ Error updating volumes:', error);
    }
}

/**
 * Initialization
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('🌐 Networks & Volumes page initialized');
    
    // Setup search
    setupNetworksSearch();
    setupVolumesSearch();
    
    // Auto-refresh every 30 seconds
    setInterval(() => {
        if (currentTab === 'networks') {
            updateNetworks();
        } else if (currentTab === 'volumes') {
            updateVolumes();
        }
    }, 30000);
    
    console.log('✅ Auto-refresh active (every 30 seconds)');
});