/**
 * Networks & Volumes Page - JavaScript
 */

// Variabile per tracciare tab corrente
let currentTab = 'networks';

/**
 * Mostra tab specifica
 */
function showTab(tabName) {
    currentTab = tabName;
    
    // Nascondi tutte le tab
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Rimuovi active da tutti i bottoni
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Mostra tab selezionata
    document.getElementById(tabName).classList.add('active');
    
    // Aggiungi active al bottone cliccato
    event.target.classList.add('active');
    
    console.log(`📑 Switched to ${tabName} tab`);
}

/**
 * Setup ricerca networks
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
        
        console.log(`🔍 Networks search: "${searchTerm}" - ${visibleCount} risultati`);
    });
}

/**
 * Setup ricerca volumes
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
        
        console.log(`🔍 Volumes search: "${searchTerm}" - ${visibleCount} risultati`);
    });
}

/**
 * Aggiorna dati networks
 */
async function updateNetworks() {
    try {
        const response = await fetch('/api/networks');
        const networks = await response.json();
        
        console.log(`✅ Networks aggiornate: ${networks.length} networks`);
        
        // TODO: Aggiornare dinamicamente la UI se necessario
        // Per ora facciamo un refresh completo
        
    } catch (error) {
        console.error('❌ Errore aggiornamento networks:', error);
    }
}

/**
 * Aggiorna dati volumes
 */
async function updateVolumes() {
    try {
        const response = await fetch('/api/volumes');
        const volumes = await response.json();
        
        console.log(`✅ Volumes aggiornati: ${volumes.length} volumes`);
        
        // TODO: Aggiornare dinamicamente la UI se necessario
        
    } catch (error) {
        console.error('❌ Errore aggiornamento volumes:', error);
    }
}

/**
 * Inizializzazione
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('🌐 Networks & Volumes page inizializzata');
    
    // Setup ricerca
    setupNetworksSearch();
    setupVolumesSearch();
    
    // Aggiornamento automatico ogni 30 secondi
    setInterval(() => {
        if (currentTab === 'networks') {
            updateNetworks();
        } else if (currentTab === 'volumes') {
            updateVolumes();
        }
    }, 30000);
    
    console.log('✅ Auto-refresh attivo (ogni 30 secondi)');
});