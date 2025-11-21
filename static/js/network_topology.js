/**
 * Network Topology Visualization
 * Uses Vis.js Network library
 */

let network = null;
let nodes = null;
let edges = null;
let physicsEnabled = true;

/**
 * Inizializza il grafico della rete
 */
async function initNetwork() {
    try {
        console.log(`🌐 Loading topology for network: ${networkId}`);
        
        // Fetch dati dalla API
        const response = await fetch(`/api/network/${networkId}/topology`);
        const data = await response.json();
        
        if (data.error) {
            console.error('❌ Error:', data.error);
            return;
        }
        
        console.log(`✅ Loaded ${data.nodes.length} nodes and ${data.edges.length} edges`);
        
        // Crea DataSets
        nodes = new vis.DataSet(data.nodes);
        edges = new vis.DataSet(data.edges);
        
        // Container
        const container = document.getElementById('network-graph');
        
        // Dati
        const graphData = {
            nodes: nodes,
            edges: edges
        };
        
        // Opzioni
        const options = {
            nodes: {
                borderWidth: 2,
                borderWidthSelected: 4,
                chosen: true,
                shadow: {
                    enabled: true,
                    color: 'rgba(0,0,0,0.3)',
                    size: 10,
                    x: 3,
                    y: 3
                }
            },
            edges: {
                width: 2,
                selectionWidth: 4,
                shadow: {
                    enabled: true,
                    color: 'rgba(0,0,0,0.2)',
                    size: 5,
                    x: 2,
                    y: 2
                }
            },
            physics: {
                enabled: true,
                stabilization: {
                    enabled: true,
                    iterations: 200,
                    updateInterval: 25
                },
                barnesHut: {
                    gravitationalConstant: -8000,
                    centralGravity: 0.3,
                    springLength: 200,
                    springConstant: 0.04,
                    damping: 0.09,
                    avoidOverlap: 0.5
                }
            },
            interaction: {
                hover: true,
                tooltipDelay: 200,
                zoomView: true,
                dragView: true,
                dragNodes: true,
                navigationButtons: false,
                keyboard: {
                    enabled: true
                }
            },
            layout: {
                improvedLayout: true,
                hierarchical: false
            }
        };
        
        // Crea network
        network = new vis.Network(container, graphData, options);
        
        // Event listeners
        network.on('click', function(params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                showNodeInfo(nodeId);
            } else {
                closeInfoPanel();
            }
        });
        
        network.on('doubleClick', function(params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = nodes.get(nodeId);
                
                // Se è un container, apri la pagina di dettaglio
                if (node.type === 'container') {
                    window.location.href = `/container/${node.info.id}`;
                }
            }
        });
        
        network.on('hoverNode', function(params) {
            document.body.style.cursor = 'pointer';
        });
        
        network.on('blurNode', function(params) {
            document.body.style.cursor = 'default';
        });
        
        network.on('stabilizationIterationsDone', function() {
            console.log('✅ Network stabilization complete');
        });
        
        // Fit dopo stabilizzazione
        setTimeout(() => {
            network.fit({
                animation: {
                    duration: 1000,
                    easingFunction: 'easeInOutQuad'
                }
            });
        }, 500);
        
    } catch (error) {
        console.error('❌ Error loading network topology:', error);
    }
}

/**
 * Mostra informazioni di un nodo
 */
function showNodeInfo(nodeId) {
    const node = nodes.get(nodeId);
    const infoPanel = document.getElementById('info-panel');
    const infoTitle = document.getElementById('info-title');
    const infoContent = document.getElementById('info-content');
    const infoActions = document.getElementById('info-actions');
    
    if (!node) return;
    
    // Titolo
    infoTitle.textContent = node.label;
    
    // Contenuto
    let html = '';
    
    if (node.type === 'network') {
        html = `
            <div class="info-row">
                <span class="info-row-label">🔧 Driver:</span>
                <span class="info-row-value">${node.info.driver}</span>
            </div>
            <div class="info-row">
                <span class="info-row-label">🌍 Scope:</span>
                <span class="info-row-value">${node.info.scope}</span>
            </div>
            <div class="info-row">
                <span class="info-row-label">🌍 Subnet:</span>
                <span class="info-row-value">${node.info.subnet}</span>
            </div>
            <div class="info-row">
                <span class="info-row-label">🚪 Gateway:</span>
                <span class="info-row-value">${node.info.gateway}</span>
            </div>
        `;
        infoActions.innerHTML = '';
    } else if (node.type === 'container') {
        const statusClass = node.info.status === 'running' ? 'running' : 
                           node.info.status === 'exited' ? 'exited' : 'other';
        
        html = `
            <div class="info-row">
                <span class="info-row-label">🆔 ID:</span>
                <span class="info-row-value">${node.info.id}</span>
            </div>
            <div class="info-row">
                <span class="info-row-label">📊 Status:</span>
                <span class="info-row-value">
                    <span class="status-badge ${statusClass}">${node.info.status}</span>
                </span>
            </div>
            <div class="info-row">
                <span class="info-row-label">🐳 Image:</span>
                <span class="info-row-value">${node.info.image}</span>
            </div>
            <div class="info-row">
                <span class="info-row-label">🔗 IPv4:</span>
                <span class="info-row-value">${node.info.ipv4}</span>
            </div>
            ${node.info.mac !== 'N/A' ? `
            <div class="info-row">
                <span class="info-row-label">📡 MAC:</span>
                <span class="info-row-value">${node.info.mac}</span>
            </div>
            ` : ''}
            <div class="info-row">
                <span class="info-row-label">🔌 Ports:</span>
                <span class="info-row-value">${node.info.ports}</span>
            </div>
        `;
        
        infoActions.innerHTML = `
            <a href="/container/${node.info.id}" class="action-btn">
                📊 View Details
            </a>
        `;
    }
    
    infoContent.innerHTML = html;
    infoPanel.classList.remove('hidden');
}

/**
 * Chiudi info panel
 */
function closeInfoPanel() {
    document.getElementById('info-panel').classList.add('hidden');
}

/**
 * Fit network alla view
 */
function fitNetwork() {
    if (network) {
        network.fit({
            animation: {
                duration: 1000,
                easingFunction: 'easeInOutQuad'
            }
        });
    }
}

/**
 * Reset zoom
 */
function resetZoom() {
    if (network) {
        network.moveTo({
            scale: 1.0,
            animation: {
                duration: 1000,
                easingFunction: 'easeInOutQuad'
            }
        });
    }
}

/**
 * Toggle physics
 */
function togglePhysics() {
    if (network) {
        physicsEnabled = !physicsEnabled;
        network.setOptions({
            physics: {
                enabled: physicsEnabled
            }
        });
        
        const icon = document.getElementById('physics-icon');
        icon.textContent = physicsEnabled ? '⚡' : '⚡';
        icon.style.opacity = physicsEnabled ? '1' : '0.5';
        
        console.log(`Physics ${physicsEnabled ? 'enabled' : 'disabled'}`);
    }
}

/**
 * Inizializzazione
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('🌐 Network Topology page initialized');
    initNetwork();
});