/**
 * Container Detail Page - Real-time monitoring
 */

let cpuChart, memoryChart, networkChart, diskChart;
let lastKnownUpdate = null;

// Configurazione comune per i grafici
const chartConfig = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
        legend: {
            labels: {
                color: '#94a3b8'
            }
        },
        tooltip: {
            enabled: true,
            mode: 'index',
            intersect: false,
            callbacks: {
                title: function(tooltipItems) {
                    // Mostra il timestamp completo nel tooltip
                    return tooltipItems[0].label;
                }
            }
        }
    },
    scales: {
        x: {
            display: false,  // Nasconde completamente l'asse X e i suoi label
            grid: { 
                display: false  // Nasconde anche la griglia verticale
            }
        },
        y: {
            ticks: { color: '#94a3b8' },
            grid: { color: 'rgba(51, 65, 85, 0.3)' }
        }
    }
};

/**
 * Inizializza i grafici
 */
function initCharts() {
    // CPU Chart
    const cpuCtx = document.getElementById('cpuChart').getContext('2d');
    cpuChart = new Chart(cpuCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'CPU %',
                data: [],
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: chartConfig
    });

    // Memory Chart
    const memCtx = document.getElementById('memoryChart').getContext('2d');
    memoryChart = new Chart(memCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'RAM Usage (MB)',
                data: [],
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: chartConfig
    });

    // Network Chart
    const netCtx = document.getElementById('networkChart').getContext('2d');
    networkChart = new Chart(netCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Network IN (MB/s)',
                    data: [],
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    tension: 0.4,
                    fill: true
                },
                {
                    label: 'Network OUT (MB/s)',
                    data: [],
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    tension: 0.4,
                    fill: true
                }
            ]
        },
        options: chartConfig
    });

    // Disk Chart
    const diskCtx = document.getElementById('diskChart').getContext('2d');
    diskChart = new Chart(diskCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Disk READ (MB/s)',
                    data: [],
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    tension: 0.4,
                    fill: true
                },
                {
                    label: 'Disk WRITE (MB/s)',
                    data: [],
                    borderColor: '#ec4899',
                    backgroundColor: 'rgba(236, 72, 153, 0.1)',
                    tension: 0.4,
                    fill: true
                }
            ]
        },
        options: chartConfig
    });
}

/**
 * Carica lo storico delle statistiche
 */
async function loadStatsHistory() {
    try {
        const response = await fetch(`/api/container/${containerId}/stats/history`);
        const history = await response.json();

        if (history.length === 0) {
            console.log('Nessuno storico disponibile ancora');
            return;
        }

        // Prepara i dati per i grafici
        const labels = [];
        const cpuData = [];
        const memData = [];
        const netInData = [];
        const netOutData = [];
        const diskReadData = [];
        const diskWriteData = [];

        // Non facciamo più il campionamento - usiamo TUTTI i dati
        // Rimuoviamo questa riga: const step = Math.ceil(history.length / 100);
        
        for (let i = 0; i < history.length; i++) {
            const stat = history[i];
            const date = new Date(stat.timestamp);
            
            // Formatta timestamp completo per il tooltip
            const fullTimestamp = date.toLocaleString('it-IT', { 
                year: 'numeric',
                month: 'short', 
                day: 'numeric', 
                hour: '2-digit', 
                minute: '2-digit',
                second: '2-digit'
            });
            
            labels.push(fullTimestamp);
            
            cpuData.push(stat.cpu_percent);
            memData.push(stat.mem_usage_mb);
            netInData.push(stat.net_input_mb);
            netOutData.push(stat.net_output_mb);
            diskReadData.push(stat.disk_read_mb);
            diskWriteData.push(stat.disk_write_mb);
        }

        // Aggiorna i grafici
        cpuChart.data.labels = labels;
        cpuChart.data.datasets[0].data = cpuData;
        cpuChart.update();

        memoryChart.data.labels = labels;
        memoryChart.data.datasets[0].data = memData;
        memoryChart.update();

        networkChart.data.labels = labels;
        networkChart.data.datasets[0].data = netInData;
        networkChart.data.datasets[1].data = netOutData;
        networkChart.update();

        diskChart.data.labels = labels;
        diskChart.data.datasets[0].data = diskReadData;
        diskChart.data.datasets[1].data = diskWriteData;
        diskChart.update();

        console.log('✅ Storico caricato:', history.length, 'punti');
    } catch (error) {
        console.error('❌ Errore caricamento storico:', error);
    }
}

/**
 * Aggiorna le statistiche in tempo reale
 */
async function updateRealtimeStats() {
    const syncIndicator = document.getElementById('sync-indicator');
    const lastUpdateSpan = document.getElementById('last-update');
    
    try {
        // Mostra stato di sincronizzazione
        syncIndicator.classList.add('syncing');
        
        const response = await fetch(`/api/container/${containerId}/stats`);
        const stats = await response.json();

        if (stats.error) {
            console.error('Errore:', stats.error);
            lastUpdateSpan.textContent = 'Errore aggiornamento';
            syncIndicator.classList.remove('syncing');
            return;
        }

        // Aggiorna valori in tempo reale
        document.getElementById('cpu-value').textContent = stats.cpu_percent + '%';
        document.getElementById('cpu-progress').style.width = Math.min(stats.cpu_percent, 100) + '%';
        
        document.getElementById('ram-value').textContent = stats.mem_usage_mb.toFixed(2) + ' MB';
        document.getElementById('ram-percent').textContent = stats.mem_percent.toFixed(2) + '% di ' + stats.mem_limit_mb.toFixed(2) + ' MB';
        document.getElementById('ram-progress').style.width = Math.min(stats.mem_percent, 100) + '%';
        
        document.getElementById('net-in-value').textContent = stats.net_input_mb.toFixed(2) + ' MB/s';
        document.getElementById('net-out-value').textContent = stats.net_output_mb.toFixed(2) + ' MB/s';
        document.getElementById('disk-read-value').textContent = stats.disk_read_mb.toFixed(2) + ' MB/s';
        document.getElementById('disk-write-value').textContent = stats.disk_write_mb.toFixed(2) + ' MB/s';

        // Cambia colore della progress bar se CPU > 80%
        const cpuProgress = document.getElementById('cpu-progress');
        if (stats.cpu_percent > 80) {
            cpuProgress.style.background = 'linear-gradient(90deg, #ef4444, #dc2626)';
        } else {
            cpuProgress.style.background = 'linear-gradient(90deg, #3b82f6, #2563eb)';
        }

        // Cambia colore della progress bar se RAM > 80%
        const ramProgress = document.getElementById('ram-progress');
        if (stats.mem_percent > 80) {
            ramProgress.style.background = 'linear-gradient(90deg, #ef4444, #dc2626)';
        } else {
            ramProgress.style.background = 'linear-gradient(90deg, #3b82f6, #2563eb)';
        }

        // Aggiorna timestamp
        const now = new Date();
        lastUpdateSpan.textContent = `Aggiornato: ${now.toLocaleTimeString('it-IT')}`;
        syncIndicator.classList.remove('syncing');

    } catch (error) {
        console.error('❌ Errore aggiornamento stats:', error);
        lastUpdateSpan.textContent = 'Errore connessione';
        syncIndicator.classList.remove('syncing');
    }
}

/**
 * Evidenzia il testo di ricerca nel log
 */
function highlightSearchText(text, searchTerm) {
    if (!searchTerm) return text;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    return text.replace(regex, '<span class="search-highlight">$1</span>');
}

/**
 * Funzione di ricerca nei log
 */
function setupLogSearch() {
    const searchInput = document.getElementById('log-search');
    const clearButton = document.getElementById('clear-search');
    const logsContainer = document.getElementById('logs-container');
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        const logLines = logsContainer.querySelectorAll('.log-line');
        let visibleCount = 0;
        
        // Mostra/nascondi bottone cancella
        if (searchTerm) {
            clearButton.style.display = 'inline-block';
        } else {
            clearButton.style.display = 'none';
        }
        
        logLines.forEach(line => {
            const logText = line.getAttribute('data-original-text') || line.textContent;
            
            if (!searchTerm) {
                // Se non c'è ricerca, mostra tutto senza highlight
                line.classList.remove('hidden', 'highlight');
                line.innerHTML = logText;
                visibleCount++;
            } else {
                // Cerca nel testo
                if (logText.toLowerCase().includes(searchTerm)) {
                    line.classList.remove('hidden');
                    line.classList.add('highlight');
                    
                    // Salva il testo originale se non esiste
                    if (!line.getAttribute('data-original-text')) {
                        line.setAttribute('data-original-text', logText);
                    }
                    
                    // Evidenzia il termine cercato
                    line.innerHTML = highlightSearchText(logText, searchTerm);
                    visibleCount++;
                } else {
                    line.classList.add('hidden');
                    line.classList.remove('highlight');
                }
            }
        });
        
        // Aggiorna contatore log visibili
        document.getElementById('log-visible-count').textContent = `${visibleCount} visibili`;
        
        // Scroll automatico al primo risultato se c'è una ricerca
        if (searchTerm && visibleCount > 0) {
            const firstVisible = logsContainer.querySelector('.log-line:not(.hidden)');
            if (firstVisible) {
                firstVisible.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    });
    
    // Bottone per cancellare la ricerca
    clearButton.addEventListener('click', function() {
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input'));
        searchInput.focus();
    });
}

/**
 * Aggiorna i log del container
 */
async function updateLogs() {
    try {
        const response = await fetch(`/api/container/${containerId}/logs`);
        const data = await response.json();

        if (data.error) {
            document.getElementById('logs-container').innerHTML = 
                `<p style="color: #ef4444;">Errore: ${data.error}</p>`;
            return;
        }

        const logsContainer = document.getElementById('logs-container');
        
        // Salva il termine di ricerca corrente
        const searchInput = document.getElementById('log-search');
        const currentSearch = searchInput ? searchInput.value : '';
        
        logsContainer.innerHTML = '';

        if (data.logs.length === 0) {
            logsContainer.innerHTML = '<p style="color: #94a3b8;">Nessun log disponibile</p>';
            document.getElementById('log-count').textContent = '0 log caricati';
            document.getElementById('log-visible-count').textContent = '0 visibili';
            return;
        }

        // Aggiorna il contatore dei log
        document.getElementById('log-count').textContent = `${data.logs.length} log caricati`;
        
        // Aggiorna il timestamp dell'ultimo aggiornamento
        const now = new Date();
        document.getElementById('log-last-update').textContent = `Aggiornato: ${now.toLocaleTimeString('it-IT')}`;

        data.logs.forEach(log => {
            const logLine = document.createElement('div');
            logLine.className = 'log-line';
            
            // Formatta il log con timestamp in evidenza
            const parts = log.split(' ');
            let logText;
            if (parts.length > 0) {
                const timestamp = parts[0];
                const message = parts.slice(1).join(' ');
                logText = `${timestamp} ${message}`;
                logLine.innerHTML = `<span class="log-timestamp">${timestamp}</span> ${message}`;
            } else {
                logText = log;
                logLine.textContent = log;
            }
            
            // Salva il testo originale per la ricerca
            logLine.setAttribute('data-original-text', logText);
            
            logsContainer.appendChild(logLine);
        });

        // Riapplica la ricerca se era attiva
        if (currentSearch) {
            searchInput.value = currentSearch;
            searchInput.dispatchEvent(new Event('input'));
        } else {
            document.getElementById('log-visible-count').textContent = `${data.logs.length} visibili`;
        }

        // Auto-scroll in fondo solo se non c'è ricerca attiva
        if (!currentSearch) {
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }

        console.log(`✅ ${data.logs.length} log aggiornati`);

    } catch (error) {
        console.error('❌ Errore aggiornamento log:', error);
    }
}

/**
 * Inizializzazione
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('🐳 Container Detail inizializzato per:', containerId);
    
    // Inizializza grafici
    initCharts();
    
    // Carica storico
    loadStatsHistory();
    
    // Prima lettura stats e log
    updateRealtimeStats();
    updateLogs();
    
    // Setup ricerca log
    setupLogSearch();
    
    // Aggiornamento automatico
    setInterval(updateRealtimeStats, 10000);   // Stats ogni 10 secondi (frequente per real-time)
    setInterval(updateLogs, 60000);             // Log ogni 60 secondi (1 minuto)
    setInterval(loadStatsHistory, 60000);       // Storico ogni 60 secondi (quando ci sono nuovi dati dal backend)
    
    console.log('✅ Auto-refresh attivo:');
    console.log('   📊 Stats real-time: ogni 10 secondi');
    console.log('   📄 Log: ogni 60 secondi (1 minuto)');
    console.log('   📈 Grafici storici: ogni 60 secondi');

    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible') {
            console.log('🔌 Pagina visibile di nuovo, aggiornamento dati...');
            updateRealtimeStats();
            updateLogs();
            loadStatsHistory();
        }
    });
});