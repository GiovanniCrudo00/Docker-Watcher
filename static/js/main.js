let currentSection = 'images';

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
        
        const container = document.querySelector('#images .containers-section');
        
        if (images.length === 0) {
            container.innerHTML = `
                <h2 class="section-title">📦 Immagini Docker</h2>
                <p style="text-align: center; color: #94a3b8; padding: 20px;">
                    Nessuna immagine Docker trovata
                </p>
            `;
            return;
        }
        
        let html = '<h2 class="section-title">📦 Immagini Docker</h2>';
        
        images.forEach(image => {
            const statusClass = image.in_use ? 'running' : 'stopped';
            const statusText = image.in_use ? 'IN USO' : 'NON UTILIZZATA';
            
            html += `
                <div class="container-item">
                    <div class="container-info">
                        <h4>${image.name}</h4>
                        <p>ID: ${image.id} • Dimensione: ${image.size} MB • Creata: ${image.created}</p>
                    </div>
                    <span class="status ${statusClass}">${statusText}</span>
                </div>
            `;
        });
        
        container.innerHTML = html;
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
        
        const container = document.querySelector('#active .containers-section');
        
        if (containers.length === 0) {
            container.innerHTML = `
                <h2 class="section-title">🟢 Container Attivi</h2>
                <p style="text-align: center; color: #94a3b8; padding: 20px;">
                    Nessun container in esecuzione
                </p>
            `;
            return;
        }
        
        let html = '<h2 class="section-title">🟢 Container Attivi</h2>';
        
        containers.forEach(cont => {
            html += `
                <div class="container-item">
                    <div class="container-info">
                        <h4>${cont.name}</h4>
                        <p>Immagine: ${cont.image} • ID: ${cont.id} • Porta: ${cont.ports}</p>
                    </div>
                    <span class="status running">RUNNING</span>
                </div>
            `;
        });
        
        container.innerHTML = html;
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
        
        const container = document.querySelector('#inactive .containers-section');
        
        if (containers.length === 0) {
            container.innerHTML = `
                <h2 class="section-title">🔴 Container Non Attivi</h2>
                <p style="text-align: center; color: #94a3b8; padding: 20px;">
                    Nessun container fermato
                </p>
            `;
            return;
        }
        
        let html = '<h2 class="section-title">🔴 Container Non Attivi</h2>';
        
        containers.forEach(cont => {
            html += `
                <div class="container-item">
                    <div class="container-info">
                        <h4>${cont.name}</h4>
                        <p>Immagine: ${cont.image} • ID: ${cont.id} • Porta: ${cont.ports}</p>
                    </div>
                    <span class="status stopped">STOPPED</span>
                </div>
            `;
        });
        
        container.innerHTML = html;
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

// Inizializzazione quando il DOM è caricato
document.addEventListener('DOMContentLoaded', function() {
    console.log('🐳 Docker Watcher inizializzato');
    
    // Primo aggiornamento immediato
    updateAllData();
    
    // Aggiornamento automatico ogni 20 secondi
    setInterval(updateAllData, 20000);
    
    console.log('✅ Auto-refresh attivo (ogni 20 secondi)');
});