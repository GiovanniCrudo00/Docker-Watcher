from flask import Flask, render_template, jsonify
import docker
from docker.errors import DockerException
import psutil
from collections import deque
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)

# Inizializza il client Docker
try:
    client = docker.from_env()
except DockerException as e:
    print(f"Errore connessione Docker: {e}")
    client = None

# Dizionario per memorizzare lo storico delle statistiche (ultimi 7 giorni)
container_stats_history = {}
# Lock per thread-safe access
stats_lock = threading.Lock()


def get_docker_stats():
    """Raccoglie statistiche generali su Docker"""
    if not client:
        return None
    
    try:
        # Ottieni tutte le immagini
        images = client.images.list()
        
        # Ottieni tutti i container
        all_containers = client.containers.list(all=True)
        running_containers = [c for c in all_containers if c.status == 'running']
        stopped_containers = [c for c in all_containers if c.status != 'running']
        
        # Ottieni uso CPU e RAM del sistema
        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_percent = ram.percent
        ram_used_gb = round(ram.used / (1024 ** 3), 2)  # Converti byte in GB
        ram_total_gb = round(ram.total / (1024 ** 3), 2)  # Converti byte in GB
        
        return {
            'images_count': len(images),
            'total_containers': len(all_containers),
            'running_containers': len(running_containers),
            'stopped_containers': len(stopped_containers),
            'cpu_usage': round(cpu_percent, 1),
            'ram_usage': round(ram_percent, 1),
            'ram_used_gb': ram_used_gb,
            'ram_total_gb': ram_total_gb
        }
    except Exception as e:
        print(f"Errore nel recupero statistiche: {e}")
        return None


def get_images_data():
    """Ottieni informazioni sulle immagini Docker"""
    if not client:
        return []
    
    try:
        images = client.images.list()
        images_data = []
        
        # Ottieni container in esecuzione per verificare quali immagini sono in uso
        running_containers = client.containers.list()
        used_images = {c.image.id for c in running_containers}
        
        for img in images:
            # Ottieni tag dell'immagine
            tags = img.tags[0] if img.tags else 'none:none'
            
            # Calcola dimensione in MB
            size_mb = round(img.attrs['Size'] / (1024 * 1024), 1)
            
            # Verifica se l'immagine è in uso
            in_use = img.id in used_images
            
            # Data di creazione dell'immagine
            created_date = img.attrs['Created']
            # Converti in formato leggibile
            from datetime import datetime
            created_dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
            created_str = created_dt.strftime('%d/%m/%Y %H:%M')
            
            images_data.append({
                'name': tags,
                'id': img.short_id.replace('sha256:', ''),
                'size': size_mb,
                'created': created_str,
                'in_use': in_use
            })
        
        return images_data
    except Exception as e:
        print(f"Errore nel recupero immagini: {e}")
        return []


def get_containers_data(running_only=True):
    """Ottieni informazioni sui container Docker"""
    if not client:
        return []
    
    try:
        containers = client.containers.list(all=not running_only)
        containers_data = []
        
        from datetime import datetime
        
        for container in containers:
            # Ottieni informazioni sulle porte
            ports = container.attrs['NetworkSettings']['Ports']
            port_mappings = []
            
            if ports:
                for container_port, host_info in ports.items():
                    if host_info:
                        for mapping in host_info:
                            host_port = mapping.get('HostPort', '')
                            port_mappings.append(f"{host_port}:{container_port}")
            
            ports_str = ', '.join(port_mappings) if port_mappings else 'Nessuna porta mappata'
            
            # Ottieni nome dell'immagine
            image_name = container.image.tags[0] if container.image.tags else 'unknown'
            
            # Ottieni data di avvio/riavvio
            started_at = container.attrs['State']['StartedAt']
            started_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            started_str = started_dt.strftime('%d/%m/%Y %H:%M')
            
            # Ottieni health status
            health_status = 'none'
            health_class = 'none'
            
            if 'Health' in container.attrs['State']:
                health_status = container.attrs['State']['Health']['Status']
                if health_status == 'healthy':
                    health_class = 'healthy'
                elif health_status == 'unhealthy':
                    health_class = 'unhealthy'
                else:
                    health_class = 'starting'
            
            containers_data.append({
                'name': container.name,
                'image': image_name,
                'id': container.short_id,
                'status': container.status,
                'ports': ports_str,
                'started_at': started_str,
                'health_status': health_status,
                'health_class': health_class
            })
        
        return containers_data
    except Exception as e:
        print(f"Errore nel recupero container: {e}")
        return []


@app.route('/')
def home():
    """Homepage con dati Docker"""
    stats = get_docker_stats()
    
    if not stats:
        # Dati di fallback se Docker non è disponibile
        stats = {
            'images_count': 0,
            'total_containers': 0,
            'running_containers': 0,
            'stopped_containers': 0,
            'cpu_usage': 0,
            'ram_usage': 0
        }
    
    images = get_images_data()
    running_containers = get_containers_data(running_only=True)
    stopped_containers = get_containers_data(running_only=False)
    
    # Filtra solo i container fermati
    stopped_containers = [c for c in stopped_containers if c['status'] != 'running']
    
    return render_template('index.html', 
                         stats=stats,
                         images=images,
                         running_containers=running_containers,
                         stopped_containers=stopped_containers)


@app.route('/api/stats')
def api_stats():
    """API endpoint per ottenere statistiche aggiornate"""
    stats = get_docker_stats()
    return jsonify(stats if stats else {'error': 'Docker non disponibile'})


@app.route('/api/images')
def api_images():
    """API endpoint per ottenere lista immagini"""
    images = get_images_data()
    return jsonify(images)


@app.route('/api/container/<container_id>/stats')
def container_stats(container_id):
    try:
        container = client.containers.get(container_id)
        stats = container.stats(stream=False)
        
        # ===== CALCOLO CPU =====
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                    stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                       stats['precpu_stats']['system_cpu_usage']
        cpu_count = stats['cpu_stats']['online_cpus']
        
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0
        
        # ===== CALCOLO MEMORIA (RAM) =====
        # Ottieni usage e limit dalla memoria
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 0)
        
        # Converti in MB
        mem_usage_mb = mem_usage / (1024 * 1024)
        mem_limit_mb = mem_limit / (1024 * 1024)
        
        # Calcola percentuale
        mem_percent = 0.0
        if mem_limit > 0:
            mem_percent = (mem_usage / mem_limit) * 100.0
        
        # ===== CALCOLO NETWORK I/O =====
        networks = stats.get('networks', {})
        net_input = 0
        net_output = 0
        
        for interface, data in networks.items():
            net_input += data.get('rx_bytes', 0)
            net_output += data.get('tx_bytes', 0)
        
        # Converti in MB
        net_input_mb = net_input / (1024 * 1024)
        net_output_mb = net_output / (1024 * 1024)
        
        # ===== CALCOLO DISK I/O =====
        blkio_stats = stats.get('blkio_stats', {})
        io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
        
        disk_read = 0
        disk_write = 0
        
        # Somma tutte le operazioni di lettura e scrittura
        for entry in io_service_bytes:
            op = entry.get('op', '')
            value = entry.get('value', 0)
            
            if op == 'Read':
                disk_read += value
            elif op == 'Write':
                disk_write += value
        
        # Converti in MB
        disk_read_mb = disk_read / (1024 * 1024)
        disk_write_mb = disk_write / (1024 * 1024)
        
        return jsonify({
            "cpu_percent": round(cpu_percent, 2),
            "mem_usage_mb": round(mem_usage_mb, 2),
            "mem_limit_mb": round(mem_limit_mb, 2),
            "mem_percent": round(mem_percent, 2),
            "net_input_mb": round(net_input_mb, 2),
            "net_output_mb": round(net_output_mb, 2),
            "disk_read_mb": round(disk_read_mb, 2),
            "disk_write_mb": round(disk_write_mb, 2),
        })
        
    except Exception as e:
        print(f"Errore stats container {container_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/container/<container_id>')
def container_detail(container_id):
    if not client:
        return "Docker non disponibile", 503

    try:
        container = client.containers.get(container_id)
        info = {
            'id': container.short_id,
            'name': container.name,
            'image': container.image.tags[0] if container.image.tags else 'unknown',
            'status': container.status,
            'created': container.attrs['Created'][:19].replace('T', ' ')
        }
        return render_template('container_detail.html', container=info)
    except Exception as e:
        print(f"Errore caricamento container {container_id}: {e}")
        return f"Errore: impossibile trovare il container {container_id}", 404


@app.route('/api/containers/<status>')
def api_containers(status):
    """API endpoint per ottenere container (running/stopped)"""
    running_only = status == 'running'
    containers = get_containers_data(running_only=running_only)
    
    if status == 'stopped':
        containers = [c for c in containers if c['status'] != 'running']
    
    return jsonify(containers)


@app.route('/api/container/<container_id>/logs')
def container_logs(container_id):
    if not client:
        return jsonify({'error': 'Docker non disponibile'}), 503

    try:
        container = client.containers.get(container_id)
        logs = container.logs(tail=10).decode('utf-8').splitlines()
        return jsonify({'logs': logs})
    except Exception as e:
        print(f"Errore logs container {container_id}: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)