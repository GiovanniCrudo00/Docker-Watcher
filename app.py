# Copyright (C) 2025  Il Tuo Nome
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


from flask import Flask, render_template, jsonify
import docker
from docker.errors import DockerException
import psutil

app = Flask(__name__)

# Inizializza il client Docker
try:
    client = docker.from_env()
except DockerException as e:
    print(f"Errore connessione Docker: {e}")
    client = None


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
            
            images_data.append({
                'name': tags,
                'id': img.short_id.replace('sha256:', ''),
                'size': size_mb,
                'created': img.attrs['Created'][:10],  # Solo la data
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
            
            containers_data.append({
                'name': container.name,
                'image': image_name,
                'id': container.short_id,
                'status': container.status,
                'ports': ports_str
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


@app.route('/api/containers/<status>')
def api_containers(status):
    """API endpoint per ottenere container (running/stopped)"""
    running_only = status == 'running'
    containers = get_containers_data(running_only=running_only)
    
    if status == 'stopped':
        containers = [c for c in containers if c['status'] != 'running']
    
    return jsonify(containers)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)