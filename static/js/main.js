/**
 * Docker Watcher - Main JavaScript
 * Handles navigation between sections and automatic data updates
 */

// Global variable to track active section
let currentSection = 'images';
// Track previous health states
let previousHealthStates = {};

function showSection(sectionId) {
    // Update current section
    currentSection = sectionId;
    
    // Hide all sections
    const sections = document.querySelectorAll('.section-content');
    sections.forEach(section => {
        section.classList.remove('active');
    });

    // Remove active class from all buttons
    const buttons = document.querySelectorAll('.nav-btn');
    buttons.forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected section
    document.getElementById(sectionId).classList.add('active');

    // Add active class to clicked button
    event.target.classList.add('active');
}

/**
 * Generic search function
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
 * Update real-time statistics
 */
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        if (stats.error) {
            console.error('Error from server:', stats.error);
            return;
        }
        
        // Update values in cards
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
                    // Also update GB detail for RAM
                    if (detailElement && stats.ram_used_gb && stats.ram_total_gb) {
                        detailElement.textContent = `${stats.ram_used_gb} GB / ${stats.ram_total_gb} GB`;
                    }
                    break;
            }
            
            // Value change animation
            if (valueElement.textContent != newValue) {
                valueElement.style.color = '#22c55e';
                valueElement.textContent = newValue;
                setTimeout(() => {
                    valueElement.style.color = '#3b82f6';
                }, 500);
            }
        });
        
        console.log('✅ Statistics updated');
    } catch (error) {
        console.error('❌ Error updating statistics:', error);
    }
}

/**
 * Update Docker images list
 */
async function updateImages() {
    try {
        const response = await fetch('/api/images');
        const images = await response.json();
        
        const list = document.getElementById('images-list');
        
        if (images.length === 0) {
            list.innerHTML = `
                <p style="text-align: center; color: #94a3b8; padding: 20px;">
                    No Docker images found
                </p>
            `;
            return;
        }
        
        let html = '';
        
        images.forEach(image => {
            const statusClass = image.in_use ? 'running' : 'stopped';
            const statusText = image.in_use ? 'IN USE' : 'NOT USED';
            
            html += `
                <div class="container-item" data-name="${image.name.toLowerCase()}">
                    <div class="container-info">
                        <h4>${image.name}</h4>
                        <p>ID: ${image.id} • Size: ${image.size} MB • Downloaded: ${image.created}</p>
                    </div>
                    <span class="status ${statusClass}">${statusText}</span>
                </div>
            `;
        });
        
        list.innerHTML = html;
        console.log('✅ Images updated');
    } catch (error) {
        console.error('❌ Error updating images:', error);
    }
}

/**
 * Update running containers list
 */
async function updateRunningContainers() {
    try {
        const response = await fetch('/api/containers/running');
        const containers = await response.json();
        
        const list = document.getElementById('active-list');
        
        if (containers.length === 0) {
            list.innerHTML = `
                <p style="text-align: center; color: #94a3b8; padding: 20px;">
                    No running containers
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
                    
                    // Notify if unhealthy
                    showNotification(`⚠️ Container ${cont.name} became UNHEALTHY!`);
                }
                
                healthBadge = `<span class="health-badge ${healthClass}">${emoji} ${text}</span>`;
            }
            
            html += `
                <div class="container-item clickable" onclick="window.location.href='/container/${cont.id}'" data-name="${cont.name.toLowerCase()}">
                    <div class="container-info">
                        <h4>${cont.name}</h4>
                        <p>Image: ${cont.image} • ID: ${cont.id} • Port: ${cont.ports}</p>
                        <p style="font-size: 0.85em; color: #64748b; margin-top: 4px;">
                            ⏰ Started: ${cont.started_at}
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
        console.log('✅ Running containers updated');
    } catch (error) {
        console.error('❌ Error updating running containers:', error);
    }
}

/**
 * Update stopped containers list
 */
async function updateStoppedContainers() {
    try {
        const response = await fetch('/api/containers/stopped');
        const containers = await response.json();
        
        const list = document.getElementById('inactive-list');
        
        if (containers.length === 0) {
            list.innerHTML = `
                <p style="text-align: center; color: #94a3b8; padding: 20px;">
                    No stopped containers
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
                        <p>Image: ${cont.image} • ID: ${cont.id} • Port: ${cont.ports}</p>
                        <p style="font-size: 0.85em; color: #64748b; margin-top: 4px;">
                            ⏰ Last start: ${cont.started_at}
                        </p>
                    </div>
                    <span class="status stopped">STOPPED</span>
                </div>
            `;
        });
        
        list.innerHTML = html;
        console.log('✅ Stopped containers updated');
    } catch (error) {
        console.error('❌ Error updating stopped containers:', error);
    }
}

/**
 * Update all data
 */
async function updateAllData() {
    console.log('🔄 Data update in progress...');
    
    await updateStats();
    await updateImages();
    await updateRunningContainers();
    await updateStoppedContainers();
    
    // Update last refresh timestamp
    updateLastRefreshTime();
}

/**
 * Show last update time
 */
function updateLastRefreshTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US');
    
    // Check if timestamp element already exists
    let timeElement = document.querySelector('.last-refresh-time');
    
    if (!timeElement) {
        // Create element if it doesn't exist
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
    
    timeElement.textContent = `⏱️ Updated: ${timeString}`;
}

/**
 * Show toast notification
 */
function showNotification(message) {
    // Check if notification was recently shown
    const notifKey = `notif_${message}`;
    const lastShown = sessionStorage.getItem(notifKey);
    const now = Date.now();
    
    // Don't show same notification more than once every 5 minutes
    if (lastShown && (now - parseInt(lastShown)) < 300000) {
        return;
    }
    
    sessionStorage.setItem(notifKey, now.toString());
    
    // Create notification element
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
    
    // Add to body
    document.body.appendChild(notification);
    
    // Remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 5000);
    
    console.warn('🚨 NOTIFICATION:', message);
}

// Add styles for animations
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


// Initialization when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🐳 Docker Watcher initialized');
    
    // Setup search for each section
    setupSearch('search-images', 'images-list');
    setupSearch('search-active', 'active-list');
    setupSearch('search-inactive', 'inactive-list');
    
    // First immediate update
    updateAllData();
    
    // Automatic update every 20 seconds
    setInterval(updateAllData, 20000);
    
    console.log('✅ Auto-refresh active (every 20 seconds)');
});