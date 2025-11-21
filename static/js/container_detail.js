/**
 * Container Detail Page - Real-time monitoring
 */

let cpuChart, memoryChart, networkChart, diskChart;
let lastKnownUpdate = null;

// Common configuration for charts
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
                    // Show full timestamp in tooltip
                    return tooltipItems[0].label;
                }
            }
        }
    },
    scales: {
        x: {
            display: false,  // Completely hide X axis and its labels
            grid: { 
                display: false  // Also hide vertical grid
            }
        },
        y: {
            ticks: { color: '#94a3b8' },
            grid: { color: 'rgba(51, 65, 85, 0.3)' }
        }
    }
};

/**
 * Initialize charts
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
 * Load statistics history
 */
async function loadStatsHistory() {
    try {
        const response = await fetch(`/api/container/${containerId}/stats/history`);
        const history = await response.json();

        if (history.length === 0) {
            console.log('No history available yet');
            return;
        }

        // Prepare data for charts
        const labels = [];
        const cpuData = [];
        const memData = [];
        const netInData = [];
        const netOutData = [];
        const diskReadData = [];
        const diskWriteData = [];

        // No longer sampling - use ALL data
        // Removed this line: const step = Math.ceil(history.length / 100);
        
        for (let i = 0; i < history.length; i++) {
            const stat = history[i];
            const date = new Date(stat.timestamp);
            
            // Format full timestamp for tooltip
            const fullTimestamp = date.toLocaleString('en-US', { 
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

        // Update charts
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

        console.log('✅ History loaded:', history.length, 'points');
    } catch (error) {
        console.error('❌ Error loading history:', error);
    }
}

/**
 * Update real-time statistics
 */
async function updateRealtimeStats() {
    const syncIndicator = document.getElementById('sync-indicator');
    const lastUpdateSpan = document.getElementById('last-update');
    
    try {
        // Show synchronization status
        syncIndicator.classList.add('syncing');
        
        const response = await fetch(`/api/container/${containerId}/stats`);
        const stats = await response.json();

        if (stats.error) {
            console.error('Error:', stats.error);
            lastUpdateSpan.textContent = 'Update error';
            syncIndicator.classList.remove('syncing');
            return;
        }

        // Update real-time values
        document.getElementById('cpu-value').textContent = stats.cpu_percent + '%';
        document.getElementById('cpu-progress').style.width = Math.min(stats.cpu_percent, 100) + '%';
        
        document.getElementById('ram-value').textContent = stats.mem_usage_mb.toFixed(2) + ' MB';
        document.getElementById('ram-percent').textContent = stats.mem_percent.toFixed(2) + '% of ' + stats.mem_limit_mb.toFixed(2) + ' MB';
        document.getElementById('ram-progress').style.width = Math.min(stats.mem_percent, 100) + '%';
        
        document.getElementById('net-in-value').textContent = stats.net_input_mb.toFixed(2) + ' MB/s';
        document.getElementById('net-out-value').textContent = stats.net_output_mb.toFixed(2) + ' MB/s';
        document.getElementById('disk-read-value').textContent = stats.disk_read_mb.toFixed(2) + ' MB/s';
        document.getElementById('disk-write-value').textContent = stats.disk_write_mb.toFixed(2) + ' MB/s';

        // Change progress bar color if CPU > 80%
        const cpuProgress = document.getElementById('cpu-progress');
        if (stats.cpu_percent > 80) {
            cpuProgress.style.background = 'linear-gradient(90deg, #ef4444, #dc2626)';
        } else {
            cpuProgress.style.background = 'linear-gradient(90deg, #3b82f6, #2563eb)';
        }

        // Change progress bar color if RAM > 80%
        const ramProgress = document.getElementById('ram-progress');
        if (stats.mem_percent > 80) {
            ramProgress.style.background = 'linear-gradient(90deg, #ef4444, #dc2626)';
        } else {
            ramProgress.style.background = 'linear-gradient(90deg, #3b82f6, #2563eb)';
        }

        // Update timestamp
        const now = new Date();
        lastUpdateSpan.textContent = `Updated: ${now.toLocaleTimeString('en-US')}`;
        syncIndicator.classList.remove('syncing');

    } catch (error) {
        console.error('❌ Error updating stats:', error);
        lastUpdateSpan.textContent = 'Connection error';
        syncIndicator.classList.remove('syncing');
    }
}

/**
 * Highlight search text in log
 */
function highlightSearchText(text, searchTerm) {
    if (!searchTerm) return text;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    return text.replace(regex, '<span class="search-highlight">$1</span>');
}

/**
 * Log search function
 */
function setupLogSearch() {
    const searchInput = document.getElementById('log-search');
    const clearButton = document.getElementById('clear-search');
    const logsContainer = document.getElementById('logs-container');
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        const logLines = logsContainer.querySelectorAll('.log-line');
        let visibleCount = 0;
        
        // Show/hide clear button
        if (searchTerm) {
            clearButton.style.display = 'inline-block';
        } else {
            clearButton.style.display = 'none';
        }
        
        logLines.forEach(line => {
            const logText = line.getAttribute('data-original-text') || line.textContent;
            
            if (!searchTerm) {
                // If no search, show everything without highlight
                line.classList.remove('hidden', 'highlight');
                line.innerHTML = logText;
                visibleCount++;
            } else {
                // Search in text
                if (logText.toLowerCase().includes(searchTerm)) {
                    line.classList.remove('hidden');
                    line.classList.add('highlight');
                    
                    // Save original text if doesn't exist
                    if (!line.getAttribute('data-original-text')) {
                        line.setAttribute('data-original-text', logText);
                    }
                    
                    // Highlight search term
                    line.innerHTML = highlightSearchText(logText, searchTerm);
                    visibleCount++;
                } else {
                    line.classList.add('hidden');
                    line.classList.remove('highlight');
                }
            }
        });
        
        // Update visible log counter
        document.getElementById('log-visible-count').textContent = `${visibleCount} visible`;
        
        // Auto-scroll to first result if there's a search
        if (searchTerm && visibleCount > 0) {
            const firstVisible = logsContainer.querySelector('.log-line:not(.hidden)');
            if (firstVisible) {
                firstVisible.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    });
    
    // Button to clear search
    clearButton.addEventListener('click', function() {
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input'));
        searchInput.focus();
    });
}

/**
 * Update container logs
 */
async function updateLogs() {
    try {
        const response = await fetch(`/api/container/${containerId}/logs`);
        const data = await response.json();

        if (data.error) {
            document.getElementById('logs-container').innerHTML = 
                `<p style="color: #ef4444;">Error: ${data.error}</p>`;
            return;
        }

        const logsContainer = document.getElementById('logs-container');
        
        // Save current search term
        const searchInput = document.getElementById('log-search');
        const currentSearch = searchInput ? searchInput.value : '';
        
        logsContainer.innerHTML = '';

        if (data.logs.length === 0) {
            logsContainer.innerHTML = '<p style="color: #94a3b8;">No logs available</p>';
            document.getElementById('log-count').textContent = '0 logs loaded';
            document.getElementById('log-visible-count').textContent = '0 visible';
            return;
        }

        // Update log counter
        document.getElementById('log-count').textContent = `${data.logs.length} logs loaded`;
        
        // Update last update timestamp
        const now = new Date();
        document.getElementById('log-last-update').textContent = `Updated: ${now.toLocaleTimeString('en-US')}`;

        data.logs.forEach(log => {
            const logLine = document.createElement('div');
            logLine.className = 'log-line';
            
            // Format log with highlighted timestamp
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
            
            // Save original text for search
            logLine.setAttribute('data-original-text', logText);
            
            logsContainer.appendChild(logLine);
        });

        // Re-apply search if it was active
        if (currentSearch) {
            searchInput.value = currentSearch;
            searchInput.dispatchEvent(new Event('input'));
        } else {
            document.getElementById('log-visible-count').textContent = `${data.logs.length} visible`;
        }

        // Auto-scroll to bottom only if no active search
        if (!currentSearch) {
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }

        console.log(`✅ ${data.logs.length} logs updated`);

    } catch (error) {
        console.error('❌ Error updating logs:', error);
    }
}

/**
 * Initialization
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('🐳 Container Detail initialized for:', containerId);
    
    // Initialize charts
    initCharts();
    
    // Load history
    loadStatsHistory();
    
    // First read stats and logs
    updateRealtimeStats();
    updateLogs();
    
    // Setup log search
    setupLogSearch();
    
    // Automatic update
    setInterval(updateRealtimeStats, 10000);   // Stats every 10 seconds (frequent for real-time)
    setInterval(updateLogs, 60000);             // Logs every 60 seconds (1 minute)
    setInterval(loadStatsHistory, 60000);       // History every 60 seconds (when there's new data from backend)
    
    console.log('✅ Auto-refresh active:');
    console.log('   📊 Real-time stats: every 10 seconds');
    console.log('   📄 Logs: every 60 seconds (1 minute)');
    console.log('   📈 Historical charts: every 60 seconds');

    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible') {
            console.log('🔌 Page visible again, updating data...');
            updateRealtimeStats();
            updateLogs();
            loadStatsHistory();
        }
    });
});