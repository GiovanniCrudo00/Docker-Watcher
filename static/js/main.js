/**
 * Docker Watcher - Main JavaScript
 * Gestisce la navigazione tra le sezioni e l'aggiornamento automatico dei dati
 */

// Variabile globale per tenere traccia della sezione attiva
let currentSection = 'images';
// Traccia gli stati di salute precedenti
let previousHealthStates = {};

function showSection(sectionId) {
    // Aggiorna la sezione corrente
    currentSection = sectionId;
    
    // Nascondi tutte le sezioni
    const sections = document.querySelectorAll('.section-content');
    sections.forEach(section => {
        section.classList.remove('active');
    });

    // Rimuovi classe active da tutti i bottoni
    const buttons = document.querySelectorAll('.nav-btn');
    buttons.forEach(btn => {
        btn.classList.remove('active');
    });

    // Mostra la sezione selezionata
    document.getElementById(sectionId).classList.add('active');

    // Aggiungi classe active al bottone cliccato
    event.target.classList.add('active');
}

/**
 * Funzione di ricerca generica
 */
function setupSearch(searchInputId, listId) {
    const searchInput = document.getElementById(searchInputId);
    const list = document.getElementById(listId);
    
    if (!searchInput || !list) return;
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        const items = list.querySelectorAll('.container-item');
        
        items.forEach(item => {
            const name = item.getAttribute('data-name');
            if (name && name.includes(searchTerm)) {
                item.classList.remove('hidden');
            } else {
                item.classList.add('hidden');
            }
        });
    });
}

/**
 * Aggiorna le statistiche in tempo reale
 */
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        if (stats.error) {
            console.error('Errore dal server:', stats.error);
            return;
        }
        
        // Aggiorna i valori nelle card
        document.querySelectorAll('.stat-card').forEach((card, index) => {
            const valueElement = card.querySelector('.stat-value');
            const detailElement = card.querySelector('.stat-detail');
            let newValue;
            
            switch(index) {
                case 0: newValue = stats.images_count; break;
                case 1: newValue = stats.total_containers; break;
                case 2: newValue = stats.running_containers; break;
                case 3: newValue = stats.stopped_containers; break;
                case 4: newValue = stats.cpu_usage + '%'; break;
                case 5: 
                    newValue = stats.ram_usage + '%';
                    // Aggiorna anche il dettaglio GB per la RAM
                    if (detailElement && stats.ram_used_gb && stats.ram_total_gb) {
                        detailElement.textContent = `${stats.ram_used_gb} GB / ${stats.ram_total_gb} GB`;
                    }
                    break;
            }
            
            // Animazione del cambio valore
            if (valueElement.textContent != newValue) {
                valueElement.style.color = '#22c55e';
                valueElement.textContent = newValue;
                setTimeout(() => {
                    valueElement.style.color = '#3b82f6';
                }, 500);
            }
        });
        
        console.log('✅ Statistiche aggiornate');
    } catch (error) {
        console.error('❌ Errore aggiornamento statistiche:', error);
    }
}

/**
 * Aggiorna la lista delle immagini Docker
 */
async function updateImages() {
    try {
        const response = await fetch('/api/images');
        const images = await response.json();
        
        const list = document.getElementById('images-list');
        
        if (images.length === 0) {
            list.innerHTML = `
                <p style="text-align: center; color: #94a3b8; padding: 20px;">
                    Nessuna immagine Docker trovata
                </p>
            `;
            return;
        }
        
        let html = '';
        
        images.forEach(image => {
            const statusClass = image.in_use ? 'running' : 'stopped';
            const statusText = image.in_use ? 'IN USO' : 'NON UTILIZZATA';
            
            html += `
                <div class="container-item" data-name="${image.name.toLowerCase()}">
                    <div class="container-info">
                        <h4>${image.name}</h4>
                        <p>ID: ${image.id} • Dimensione: ${image.size} MB • Scaricata: ${image.created}</p>
                    </div>
                    <span class="status ${statusClass}">${statusText}</span>
                </div>
            `;
        });
        
        list.innerHTML = html;
        console.log('✅ Immagini aggiornate');
    } catch (error) {
        console.error('❌ Errore aggiornamento immagini:', error);
    }
}

/**
 * Aggiorna la lista dei container attivi
 */
async function updateRunningContainers() {
    try {
        const response = await fetch('/api/containers/running');
        const containers = await response.json();
        
        const list = document.getElementById('active-list');
        
        if (containers.length === 0) {
            list.innerHTML = `
                <p style="text-align: center; color: #94a3b8; padding: 20px;">
                    Nessun container in esecuzione
                </p>
            `;
            return;
        }
        
        let html = '';
        
        containers.forEach(cont => {
            let healthBadge = '';
            if (cont.health_status !== 'none') {
                let emoji = '🟡';
                let text = 'Starting';
                let healthClass = 'starting';
                
                if (cont.health_status === 'healthy') {
                    emoji = '💚';
                    text = 'Healthy';
                    healthClass = 'healthy';
                } else if (cont.health_status === 'unhealthy') {
                    emoji = '❤️';
                    text = 'Unhealthy';
                    healthClass = 'unhealthy';
                    
                    // Notifica se unhealthy
                    showNotification(`⚠️ Container ${cont.name} è diventato UNHEALTHY!`);
                }
                
                healthBadge = `<span class="health-badge ${healthClass}">${emoji} ${text}</span>`;
            }
            
            html += `
                <div class="container-item clickable" onclick="window.location.href='/container/${cont.id}'" data-name="${cont.name.toLowerCase()}">
                    <div class="container-info">
                        <h4>${cont.name}</h4>
                        <p>Immagine: ${cont.image} • ID: ${cont.id} • Porta: ${cont.ports}</p>
                        <p style="font-size: 0.85em; color: #64748b; margin-top: 4px;">
                            ⏰ Avviato: ${cont.started_at}
                        </p>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        ${healthBadge}
                        <span class="status running">RUNNING</span>
                    </div>
                </div>
            `;
        });
        
        list.innerHTML = html;
        console.log('✅ Container attivi aggiornati');
    } catch (error) {
        console.error('❌ Errore aggiornamento container attivi:', error);
    }
}

/**
 * Aggiorna la lista dei container fermati
 */
async function updateStoppedContainers() {
    try {
        const response = await fetch('/api/containers/stopped');
        const containers = await response.json();
        
        const list = document.getElementById('inactive-list');
        
        if (containers.length === 0) {
            list.innerHTML = `
                <p style="text-align: center; color: #94a3b8; padding: 20px;">
                    Nessun container fermato
                </p>
            `;
            return;
        }
        
        let html = '';
        
        containers.forEach(cont => {
            html += `
                <div class="container-item" data-name="${cont.name.toLowerCase()}">
                    <div class="container-info">
                        <h4>${cont.name}</h4>
                        <p>Immagine: ${cont.image} • ID: ${cont.id} • Porta: ${cont.ports}</p>
                        <p style="font-size: 0.85em; color: #64748b; margin-top: 4px;">
                            ⏰ Ultimo avvio: ${cont.started_at}
                        </p>
                    </div>
                    <span class="status stopped">STOPPED</span>
                </div>
            `;
        });
        
        list.innerHTML = html;
        console.log('✅ Container fermati aggiornati');
    } catch (error) {
        console.error('❌ Errore aggiornamento container fermati:', error);
    }
}

/**
 * Aggiorna tutti i dati
 */
async function updateAllData() {
    console.log('🔄 Aggiornamento dati in corso...');
    
    await updateStats();
    await updateImages();
    await updateRunningContainers();
    await updateStoppedContainers();
    
    // Aggiorna il timestamp dell'ultimo aggiornamento
    updateLastRefreshTime();
}

/**
 * Mostra l'orario dell'ultimo aggiornamento
 */
function updateLastRefreshTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('it-IT');
    
    // Cerca se esiste già l'elemento del timestamp
    let timeElement = document.querySelector('.last-refresh-time');
    
    if (!timeElement) {
        // Crea l'elemento se non esiste
        timeElement = document.createElement('div');
        timeElement.className = 'last-refresh-time';
        timeElement.style.cssText = `
            position: fixed;
            bottom: 90px;
            right: 30px;
            color: #94a3b8;
            font-size: 0.85em;
            background: rgba(30, 41, 59, 0.8);
            padding: 8px 16px;
            border-radius: 20px;
            border: 1px solid #334155;
        `;
        document.body.appendChild(timeElement);
    }
    
    timeElement.textContent = `⏱️ Aggiornato: ${timeString}`;
}

/**
 * Mostra una notifica toast
 */
function showNotification(message) {
    // Verifica se la notifica è già stata mostrata recentemente
    const notifKey = `notif_${message}`;
    const lastShown = sessionStorage.getItem(notifKey);
    const now = Date.now();
    
    // Non mostrare la stessa notifica più di una volta ogni 5 minuti
    if (lastShown && (now - parseInt(lastShown)) < 300000) {
        return;
    }
    
    sessionStorage.setItem(notifKey, now.toString());
    
    // Crea l'elemento notifica
    const notification = document.createElement('div');
    notification.className = 'notification-toast';
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: rgba(239, 68, 68, 0.95);
        color: white;
        padding: 16px 24px;
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        z-index: 9999;
        font-weight: 600;
        animation: slideIn 0.3s ease-out;
        border: 2px solid #ef4444;
    `;
    
    // Aggiungi al body
    document.body.appendChild(notification);
    
    // Rimuovi dopo 5 secondi
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 5000);
    
    console.warn('🚨 NOTIFICA:', message);
}

// Aggiungi gli stili per le animazioni
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);


// Inizializzazione quando il DOM è caricato
document.addEventListener('DOMContentLoaded', function() {
    console.log('🐳 Docker Watcher inizializzato');
    
    // Setup ricerca per ogni sezione
    setupSearch('search-images', 'images-list');
    setupSearch('search-active', 'active-list');
    setupSearch('search-inactive', 'inactive-list');
    
    // Primo aggiornamento immediato
    updateAllData();
    
    // Aggiornamento automatico ogni 20 secondi
    setInterval(updateAllData, 20000);
    
    console.log('✅ Auto-refresh attivo (ogni 20 secondi)');
});