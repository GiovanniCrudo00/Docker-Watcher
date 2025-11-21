from flask import Flask, render_template, jsonify
import docker
from docker.errors import DockerException
import psutil
from datetime import datetime, timedelta
import threading
import time
import sqlite3
import os

app = Flask(__name__)

# Inizializza il client Docker
try:
    client = docker.from_env()
except DockerException as e:
    print(f"Errore connessione Docker: {e}")
    client = None

# Path del database
DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'data', 'docker_stats.db'))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
# Dizionario per memorizzare gli ultimi valori cumulativi di ogni container
# Formato: {container_id: {'timestamp': datetime, 'net_in': bytes, 'net_out': bytes, 'disk_read': bytes, 'disk_write': bytes}}
last_cumulative_values = {}


# ===== FUNZIONI DATABASE =====

def init_database():
    """Inizializza il database SQLite"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS container_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            container_id TEXT NOT NULL,
            container_name TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            cpu_percent REAL,
            mem_usage_mb REAL,
            mem_limit_mb REAL,
            mem_percent REAL,
            net_input_mb REAL,     -- MB/s rate
            net_output_mb REAL,    -- MB/s rate
            disk_read_mb REAL,     -- MB/s rate
            disk_write_mb REAL,    -- MB/s rate
            UNIQUE(container_id, timestamp)
        )
    ''')
    
    # Indice per query più veloci
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_container_timestamp 
        ON container_stats(container_id, timestamp DESC)
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database inizializzato")


def save_container_stats(container_id, container_name, stats_data):
    """Salva le statistiche nel database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO container_stats 
            (container_id, container_name, timestamp, cpu_percent, mem_usage_mb, 
             mem_limit_mb, mem_percent, net_input_mb, net_output_mb, 
             disk_read_mb, disk_write_mb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            container_id,
            container_name,
            stats_data['timestamp'],
            stats_data['cpu_percent'],
            stats_data['mem_usage_mb'],
            stats_data['mem_limit_mb'],
            stats_data['mem_percent'],
            stats_data['net_input_mb'],
            stats_data['net_output_mb'],
            stats_data['disk_read_mb'],
            stats_data['disk_write_mb']
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Errore salvataggio stats: {e}")


def get_container_stats_history(container_id, days=7):
    """Recupera lo storico delle statistiche per un container"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Calcola la data limite (7 giorni fa)
        limit_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute('''
            SELECT timestamp, cpu_percent, mem_usage_mb, mem_limit_mb, mem_percent,
                   net_input_mb, net_output_mb, disk_read_mb, disk_write_mb
            FROM container_stats
            WHERE container_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        ''', (container_id, limit_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Converti in lista di dict
        history = []
        for row in rows:
            history.append({
                'timestamp': row[0],
                'cpu_percent': row[1],
                'mem_usage_mb': row[2],
                'mem_limit_mb': row[3],
                'mem_percent': row[4],
                'net_input_mb': row[5],
                'net_output_mb': row[6],
                'disk_read_mb': row[7],
                'disk_write_mb': row[8]
            })
        
        return history
    except Exception as e:
        print(f"❌ Errore recupero storico: {e}")
        return []


def cleanup_old_stats():
    """Rimuove le statistiche più vecchie di 7 giorni"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Data limite (7 giorni fa)
        limit_date = (datetime.now() - timedelta(days=7)).isoformat()
        
        cursor.execute('''
            DELETE FROM container_stats
            WHERE timestamp < ?
        ''', (limit_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            print(f"🧹 Puliti {deleted_count} record vecchi dal database")
    except Exception as e:
        print(f"❌ Errore pulizia database: {e}")


# Inizializza il database all'avvio
init_database()


def calculate_rate(container_id, current_cumulative_values, current_timestamp):
    """
    Calcola i rate (MB/s) per Network e Disk I/O confrontando con i valori precedenti.
    
    Args:
        container_id: ID del container
        current_cumulative_values: Dict con valori attuali cumulativi in bytes
                                   {'net_in': bytes, 'net_out': bytes, 'disk_read': bytes, 'disk_write': bytes}
        current_timestamp: Timestamp corrente (datetime)
    
    Returns:
        Dict con i rate in MB/s: {'net_input_mb_s': float, 'net_output_mb_s': float, 
                                   'disk_read_mb_s': float, 'disk_write_mb_s': float}
    """
    global last_cumulative_values
    
    # Se non abbiamo valori precedenti per questo container, salviamo questi e ritorniamo 0
    if container_id not in last_cumulative_values:
        last_cumulative_values[container_id] = {
            'timestamp': current_timestamp,
            'net_in': current_cumulative_values['net_in'],
            'net_out': current_cumulative_values['net_out'],
            'disk_read': current_cumulative_values['disk_read'],
            'disk_write': current_cumulative_values['disk_write']
        }
        return {
            'net_input_mb_s': 0.0,
            'net_output_mb_s': 0.0,
            'disk_read_mb_s': 0.0,
            'disk_write_mb_s': 0.0
        }
    
    # Recupera i valori precedenti
    last_values = last_cumulative_values[container_id]
    
    # Calcola il tempo trascorso in secondi
    time_delta = (current_timestamp - last_values['timestamp']).total_seconds()
    
    # Se il tempo trascorso è troppo piccolo, ritorna 0 per evitare divisioni per numeri molto piccoli
    if time_delta < 0.1:
        return {
            'net_input_mb_s': 0.0,
            'net_output_mb_s': 0.0,
            'disk_read_mb_s': 0.0,
            'disk_write_mb_s': 0.0
        }
    
    # Calcola le differenze in bytes
    net_in_diff = current_cumulative_values['net_in'] - last_values['net_in']
    net_out_diff = current_cumulative_values['net_out'] - last_values['net_out']
    disk_read_diff = current_cumulative_values['disk_read'] - last_values['disk_read']
    disk_write_diff = current_cumulative_values['disk_write'] - last_values['disk_write']
    
    # Gestione del caso in cui i valori cumulativi si azzerano (restart del container)
    # In questo caso, usiamo direttamente i valori attuali come differenza
    if net_in_diff < 0:
        net_in_diff = current_cumulative_values['net_in']
    if net_out_diff < 0:
        net_out_diff = current_cumulative_values['net_out']
    if disk_read_diff < 0:
        disk_read_diff = current_cumulative_values['disk_read']
    if disk_write_diff < 0:
        disk_write_diff = current_cumulative_values['disk_write']
    
    # Calcola i rate in MB/s
    rates = {
        'net_input_mb_s': (net_in_diff / (1024 * 1024)) / time_delta,
        'net_output_mb_s': (net_out_diff / (1024 * 1024)) / time_delta,
        'disk_read_mb_s': (disk_read_diff / (1024 * 1024)) / time_delta,
        'disk_write_mb_s': (disk_write_diff / (1024 * 1024)) / time_delta
    }
    
    # Aggiorna i valori precedenti con quelli attuali
    last_cumulative_values[container_id] = {
        'timestamp': current_timestamp,
        'net_in': current_cumulative_values['net_in'],
        'net_out': current_cumulative_values['net_out'],
        'disk_read': current_cumulative_values['disk_read'],
        'disk_write': current_cumulative_values['disk_write']
    }
    
    return rates


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
            
            # Se non ci sono porte mappate, mostra N/A invece di un messaggio lungo
            ports_str = ', '.join(port_mappings) if port_mappings else 'N/A'
            
            # Ottieni nome dell'immagine
            image_name = container.image.tags[0] if container.image.tags else 'unknown'
            
            # Ottieni data di avvio/riavvio in ORARIO LOCALE
            started_at = container.attrs['State']['StartedAt']
            # Parse la data ISO
            started_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            # Converti in orario locale del sistema
            started_local = started_dt.astimezone()
            started_str = started_local.strftime('%d/%m/%Y %H:%M')
            
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


@app.route('/api/containers/<status>')
def api_containers(status):
    """API endpoint per ottenere container (running/stopped)"""
    running_only = status == 'running'
    containers = get_containers_data(running_only=running_only)
    
    if status == 'stopped':
        containers = [c for c in containers if c['status'] != 'running']
    
    return jsonify(containers)


@app.route('/container/<container_id>')
def container_detail(container_id):
    """Pagina di dettaglio del container"""
    if not client:
        return "Docker non disponibile", 500
    
    try:
        container = client.containers.get(container_id)
        
        # Informazioni base del container
        container_info = {
            'id': container.short_id,
            'name': container.name,
            'image': container.image.tags[0] if container.image.tags else 'unknown',
            'status': container.status,
            'created': container.attrs['Created'][:19].replace('T', ' ')
        }
        
        return render_template('container_detail.html', container=container_info)
    except Exception as e:
        return f"Errore: {e}", 404


@app.route('/api/container/<container_id>/stats')
def api_container_stats(container_id):
    """API per ottenere statistiche in tempo reale del container"""
    if not client:
        return jsonify({'error': 'Docker non disponibile'}), 500
    
    try:
        container = client.containers.get(container_id)
        stats = container.stats(stream=False)
        
        # Calcola CPU percentage con gestione errori
        cpu_percent = 0.0
        try:
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                        stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats'].get('system_cpu_usage', 0) - \
                           stats['precpu_stats'].get('system_cpu_usage', 0)
            cpu_count = stats['cpu_stats'].get('online_cpus', 1)
            
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0
        except (KeyError, TypeError, ZeroDivisionError) as e:
            print(f"⚠️  Calcolo CPU fallito per {container_id}: {e}")
            cpu_percent = 0.0
        
        # Calcola Memory usage con gestione errori
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 1)
        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0
        mem_usage_mb = mem_usage / (1024 * 1024)
        mem_limit_mb = mem_limit / (1024 * 1024)
        
        # Calcola Network I/O - valori cumulativi in bytes
        networks = stats.get('networks', {})
        net_input_cumulative = 0
        net_output_cumulative = 0
        try:
            net_input_cumulative = sum(net.get('rx_bytes', 0) for net in networks.values())
            net_output_cumulative = sum(net.get('tx_bytes', 0) for net in networks.values())
        except (KeyError, TypeError, AttributeError):
            pass
        
        # Calcola Disk I/O - valori cumulativi in bytes
        blkio_stats = stats.get('blkio_stats', {})
        io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
        disk_read_cumulative = 0
        disk_write_cumulative = 0
        try:
            disk_read_cumulative = sum(item['value'] for item in io_service_bytes if item.get('op') == 'Read')
            disk_write_cumulative = sum(item['value'] for item in io_service_bytes if item.get('op') == 'Write')
        except (KeyError, TypeError):
            pass
        
        # Calcola i rate usando i valori cumulativi
        current_time = datetime.now()
        cumulative_values = {
            'net_in': net_input_cumulative,
            'net_out': net_output_cumulative,
            'disk_read': disk_read_cumulative,
            'disk_write': disk_write_cumulative
        }
        rates = calculate_rate(container_id, cumulative_values, current_time)
        
        current_stats = {
            'timestamp': current_time.isoformat(),
            'cpu_percent': round(cpu_percent, 2),
            'mem_usage_mb': round(mem_usage_mb, 2),
            'mem_limit_mb': round(mem_limit_mb, 2),
            'mem_percent': round(mem_percent, 2),
            'net_input_mb': round(rates['net_input_mb_s'], 2),
            'net_output_mb': round(rates['net_output_mb_s'], 2),
            'disk_read_mb': round(rates['disk_read_mb_s'], 2),
            'disk_write_mb': round(rates['disk_write_mb_s'], 2)
        }
        
        # NON salvare nel database qui - lo fa solo il thread in background
        
        return jsonify(current_stats)
    except Exception as e:
        print(f"❌ Errore stats container {container_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/container/<container_id>/stats/history')
def api_container_stats_history(container_id):
    """API per ottenere lo storico delle statistiche (ultimi 7 giorni)"""
    history = get_container_stats_history(container_id, days=7)
    return jsonify(history)


@app.route('/api/container/<container_id>/logs')
def api_container_logs(container_id):
    """API per ottenere gli ultimi log del container"""
    if not client:
        return jsonify({'error': 'Docker non disponibile'}), 500
    
    try:
        container = client.containers.get(container_id)
        # Modifica: ora prendiamo gli ultimi 100 log invece di 10
        logs = container.logs(tail=100, timestamps=True).decode('utf-8')
        
        # Formatta i log in array
        log_lines = []
        for line in logs.strip().split('\n'):
            if line:
                log_lines.append(line)
        
        return jsonify({'logs': log_lines})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def collect_stats_background():
    """Funzione che raccoglie statistiche in background ogni minuto"""
    print("🔄 Thread di raccolta statistiche avviato")
    
    while True:
        if client:
            try:
                containers = client.containers.list()
                print(f"\n📊 Raccolta stats per {len(containers)} container...")
                
                for container in containers:
                    try:
                        stats = container.stats(stream=False)
                        
                        # Calcola CPU con gestione errori
                        cpu_percent = 0.0
                        try:
                            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                                        stats['precpu_stats']['cpu_usage']['total_usage']
                            system_delta = stats['cpu_stats'].get('system_cpu_usage', 0) - \
                                           stats['precpu_stats'].get('system_cpu_usage', 0)
                            cpu_count = stats['cpu_stats'].get('online_cpus', 1)
                            
                            if system_delta > 0 and cpu_delta > 0:
                                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0
                        except (KeyError, TypeError, ZeroDivisionError):
                            cpu_percent = 0.0
                        
                        # Calcola Memory con gestione errori
                        mem_usage = stats['memory_stats'].get('usage', 0)
                        mem_limit = stats['memory_stats'].get('limit', 1)
                        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0
                        mem_usage_mb = mem_usage / (1024 * 1024)
                        mem_limit_mb = mem_limit / (1024 * 1024)
                        
                        # Calcola Network I/O - valori cumulativi in bytes
                        networks = stats.get('networks', {})
                        net_input_cumulative = 0
                        net_output_cumulative = 0
                        try:
                            net_input_cumulative = sum(net.get('rx_bytes', 0) for net in networks.values())
                            net_output_cumulative = sum(net.get('tx_bytes', 0) for net in networks.values())
                        except (KeyError, TypeError, AttributeError):
                            pass
                        
                        # Calcola Disk I/O - valori cumulativi in bytes
                        blkio_stats = stats.get('blkio_stats', {})
                        io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
                        disk_read_cumulative = 0
                        disk_write_cumulative = 0
                        try:
                            disk_read_cumulative = sum(item['value'] for item in io_service_bytes if item.get('op') == 'Read')
                            disk_write_cumulative = sum(item['value'] for item in io_service_bytes if item.get('op') == 'Write')
                        except (KeyError, TypeError):
                            pass
                        
                        # Calcola i rate usando i valori cumulativi
                        current_time = datetime.now()
                        cumulative_values = {
                            'net_in': net_input_cumulative,
                            'net_out': net_output_cumulative,
                            'disk_read': disk_read_cumulative,
                            'disk_write': disk_write_cumulative
                        }
                        rates = calculate_rate(container.id, cumulative_values, current_time)
                        
                        current_stats = {
                            'timestamp': current_time.isoformat(),
                            'cpu_percent': round(cpu_percent, 2),
                            'mem_usage_mb': round(mem_usage_mb, 2),
                            'mem_limit_mb': round(mem_limit_mb, 2),
                            'mem_percent': round(mem_percent, 2),
                            'net_input_mb': round(rates['net_input_mb_s'], 2),
                            'net_output_mb': round(rates['net_output_mb_s'], 2),
                            'disk_read_mb': round(rates['disk_read_mb_s'], 2),
                            'disk_write_mb': round(rates['disk_write_mb_s'], 2)
                        }
                        
                        # Salva nel database
                        save_container_stats(container.short_id, container.name, current_stats)
                        print(f"  ✅ {container.name}: CPU={cpu_percent:.1f}% RAM={mem_percent:.1f}% NET_IN={rates['net_input_mb_s']:.2f}MB/s")
                        
                    except Exception as e:
                        print(f"  ❌ Errore raccolta stats per {container.name}: {e}")
                
                # Pulizia database ogni ciclo
                cleanup_old_stats()
                print("✅ Ciclo di raccolta completato\n")
                
            except Exception as e:
                print(f"❌ Errore generale raccolta stats: {e}")
        
        time.sleep(60)  # Ogni minuto


# Flag per evitare avvii multipli del thread
stats_thread_started = False

# Avvia thread per raccolta statistiche in background SOLO UNA VOLTA
if not stats_thread_started:
    stats_thread = threading.Thread(target=collect_stats_background, daemon=True)
    stats_thread.start()
    stats_thread_started = True
    print("✅ Thread di raccolta statistiche avviato all'inizializzazione")


if __name__ == '__main__':
    
    # Determina host e porta da environment variables
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(
        debug=debug,
        host=host,
        port=port,
        use_reloader=False  # IMPORTANTE: evita doppio thread
    )
