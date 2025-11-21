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

# Initialize Docker client
try:
    client = docker.from_env()
except DockerException as e:
    print(f"Docker connection error: {e}")
    client = None

# Database path
DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'data', 'docker_stats.db'))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Dictionary to store last cumulative values for each container
# Format: {container_id: {'timestamp': datetime, 'net_in': bytes, 'net_out': bytes, 'disk_read': bytes, 'disk_write': bytes}}
last_cumulative_values = {}


# ===== DATABASE FUNCTIONS =====

def init_database():
    """Initialize SQLite database"""
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
    
    # Index for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_container_timestamp 
        ON container_stats(container_id, timestamp DESC)
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")


def save_container_stats(container_id, container_name, stats_data):
    """Save statistics to database"""
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
        print(f"❌ Error saving stats: {e}")


def get_container_stats_history(container_id, days=7):
    """Retrieve statistics history for a container"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Calculate limit date (7 days ago)
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
        
        # Convert to list of dicts
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
        print(f"❌ Error retrieving history: {e}")
        return []


def cleanup_old_stats():
    """Remove statistics older than 7 days"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Limit date (7 days ago)
        limit_date = (datetime.now() - timedelta(days=7)).isoformat()
        
        cursor.execute('''
            DELETE FROM container_stats
            WHERE timestamp < ?
        ''', (limit_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            print(f"🧹 Cleaned {deleted_count} old records from database")
    except Exception as e:
        print(f"❌ Error cleaning database: {e}")


# Initialize database on startup
init_database()


def calculate_rate(container_id, current_cumulative_values, current_timestamp):
    """
    Calculate rates (MB/s) for Network and Disk I/O by comparing with previous values.
    
    Args:
        container_id: Container ID
        current_cumulative_values: Dict with current cumulative values in bytes
                                   {'net_in': bytes, 'net_out': bytes, 'disk_read': bytes, 'disk_write': bytes}
        current_timestamp: Current timestamp (datetime)
    
    Returns:
        Dict with rates in MB/s: {'net_input_mb_s': float, 'net_output_mb_s': float, 
                                   'disk_read_mb_s': float, 'disk_write_mb_s': float}
    """
    global last_cumulative_values
    
    # If we don't have previous values for this container, save these and return 0
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
    
    # Retrieve previous values
    last_values = last_cumulative_values[container_id]
    
    # Calculate elapsed time in seconds
    time_delta = (current_timestamp - last_values['timestamp']).total_seconds()
    
    # If elapsed time is too small, return 0 to avoid divisions by very small numbers
    if time_delta < 0.1:
        return {
            'net_input_mb_s': 0.0,
            'net_output_mb_s': 0.0,
            'disk_read_mb_s': 0.0,
            'disk_write_mb_s': 0.0
        }
    
    # Calculate differences in bytes
    net_in_diff = current_cumulative_values['net_in'] - last_values['net_in']
    net_out_diff = current_cumulative_values['net_out'] - last_values['net_out']
    disk_read_diff = current_cumulative_values['disk_read'] - last_values['disk_read']
    disk_write_diff = current_cumulative_values['disk_write'] - last_values['disk_write']
    
    # Handle case where cumulative values reset (container restart)
    # In this case, use current values directly as difference
    if net_in_diff < 0:
        net_in_diff = current_cumulative_values['net_in']
    if net_out_diff < 0:
        net_out_diff = current_cumulative_values['net_out']
    if disk_read_diff < 0:
        disk_read_diff = current_cumulative_values['disk_read']
    if disk_write_diff < 0:
        disk_write_diff = current_cumulative_values['disk_write']
    
    # Calculate rates in MB/s
    rates = {
        'net_input_mb_s': (net_in_diff / (1024 * 1024)) / time_delta,
        'net_output_mb_s': (net_out_diff / (1024 * 1024)) / time_delta,
        'disk_read_mb_s': (disk_read_diff / (1024 * 1024)) / time_delta,
        'disk_write_mb_s': (disk_write_diff / (1024 * 1024)) / time_delta
    }
    
    # Update previous values with current ones
    last_cumulative_values[container_id] = {
        'timestamp': current_timestamp,
        'net_in': current_cumulative_values['net_in'],
        'net_out': current_cumulative_values['net_out'],
        'disk_read': current_cumulative_values['disk_read'],
        'disk_write': current_cumulative_values['disk_write']
    }
    
    return rates


def get_docker_stats():
    """Collect general Docker statistics"""
    if not client:
        return None
    
    try:
        # Get all images
        images = client.images.list()
        
        # Get all containers
        all_containers = client.containers.list(all=True)
        running_containers = [c for c in all_containers if c.status == 'running']
        stopped_containers = [c for c in all_containers if c.status != 'running']
        
        # Get system CPU and RAM usage
        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_percent = ram.percent
        ram_used_gb = round(ram.used / (1024 ** 3), 2)  # Convert bytes to GB
        ram_total_gb = round(ram.total / (1024 ** 3), 2)  # Convert bytes to GB
        
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
        print(f"Error retrieving statistics: {e}")
        return None


def get_images_data():
    """Get Docker images information"""
    if not client:
        return []
    
    try:
        images = client.images.list()
        images_data = []
        
        # Get running containers to check which images are in use
        running_containers = client.containers.list()
        used_images = {c.image.id for c in running_containers}
        
        for img in images:
            # Get image tags
            tags = img.tags[0] if img.tags else 'none:none'
            
            # Calculate size in MB
            size_mb = round(img.attrs['Size'] / (1024 * 1024), 1)
            
            # Check if image is in use
            in_use = img.id in used_images
            
            # Image creation date
            created_date = img.attrs['Created']
            # Convert to readable format
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
        print(f"Error retrieving images: {e}")
        return []


def get_containers_data(running_only=True):
    """Get Docker containers information"""
    if not client:
        return []
    
    try:
        containers = client.containers.list(all=not running_only)
        containers_data = []
        
        for container in containers:
            # Get port information
            ports = container.attrs['NetworkSettings']['Ports']
            port_mappings = []
            
            if ports:
                for container_port, host_info in ports.items():
                    if host_info:
                        for mapping in host_info:
                            host_port = mapping.get('HostPort', '')
                            port_mappings.append(f"{host_port}:{container_port}")
            
            # If no ports are mapped, show N/A instead of a long message
            ports_str = ', '.join(port_mappings) if port_mappings else 'N/A'
            
            # Get image name
            image_name = container.image.tags[0] if container.image.tags else 'unknown'
            
            # Get start/restart date in LOCAL TIME
            started_at = container.attrs['State']['StartedAt']
            # Parse ISO date
            started_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            # Convert to system local time
            started_local = started_dt.astimezone()
            started_str = started_local.strftime('%d/%m/%Y %H:%M')
            
            # Get health status
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
        print(f"Error retrieving containers: {e}")
        return []


def get_networks_data():
    """Get Docker networks information"""
    if not client:
        return []
    
    try:
        networks = client.networks.list()
        networks_data = []
        
        for network in networks:
            # IMPORTANT: Reload network to get updated data
            try:
                network.reload()
            except:
                pass
            
            # Get connected containers
            connected_containers = []
            
            # Debug: print network info
            print(f"🌐 Processing network: {network.name}")
            
            containers_in_network = network.attrs.get('Containers', {})
            print(f"   Found {len(containers_in_network)} containers in network")
            
            # If no containers found, try alternative method
            if not containers_in_network:
                print(f"   ⚠️  No containers in attrs, trying alternative method...")
                
                # Alternative method: search all containers and see which are connected
                all_containers = client.containers.list(all=True)
                for container in all_containers:
                    network_settings = container.attrs.get('NetworkSettings', {})
                    networks_dict = network_settings.get('Networks', {})
                    
                    if network.name in networks_dict:
                        net_info = networks_dict[network.name]
                        
                        # Get IPv4
                        ipv4 = net_info.get('IPAddress', 'N/A')
                        ipv6 = net_info.get('GlobalIPv6Address', 'N/A')
                        
                        connected_containers.append({
                            'id': container.short_id,
                            'name': container.name,
                            'ipv4': ipv4,
                            'ipv6': ipv6,
                            'status': container.status
                        })
                        
                        print(f"   ✅ Found via alternative: {container.name} ({ipv4})")
            else:
                # Standard method
                for container_id, container_info in containers_in_network.items():
                    try:
                        container = client.containers.get(container_id)
                        
                        # Get IPv4 (remove /subnet if present)
                        ipv4_raw = container_info.get('IPv4Address', '')
                        ipv4 = ipv4_raw.split('/')[0] if ipv4_raw else 'N/A'
                        
                        # Get IPv6 (remove /subnet if present)
                        ipv6_raw = container_info.get('IPv6Address', '')
                        ipv6 = ipv6_raw.split('/')[0] if ipv6_raw else 'N/A'
                        
                        connected_containers.append({
                            'id': container.short_id,
                            'name': container.name,
                            'ipv4': ipv4,
                            'ipv6': ipv6,
                            'status': container.status
                        })
                        
                        print(f"   ✅ Added container: {container.name} ({ipv4})")
                        
                    except Exception as e:
                        print(f"   ❌ Error getting container {container_id[:12]}: {e}")
                        continue
            
            # Get IPAM configuration
            ipam_config = network.attrs.get('IPAM', {}).get('Config', [])
            subnet = ipam_config[0].get('Subnet', 'N/A') if ipam_config else 'N/A'
            gateway = ipam_config[0].get('Gateway', 'N/A') if ipam_config else 'N/A'
            
            networks_data.append({
                'id': network.short_id,
                'name': network.name,
                'driver': network.attrs.get('Driver', 'unknown'),
                'scope': network.attrs.get('Scope', 'unknown'),
                'internal': network.attrs.get('Internal', False),
                'subnet': subnet,
                'gateway': gateway,
                'containers': connected_containers,
                'container_count': len(connected_containers)
            })
            
            print(f"   📊 Network {network.name}: {len(connected_containers)} containers added")
        
        # Sort by container count (descending)
        networks_data.sort(key=lambda x: x['container_count'], reverse=True)
        
        print(f"✅ Total networks processed: {len(networks_data)}")
        return networks_data
        
    except Exception as e:
        print(f"❌ Error retrieving networks: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_volumes_data():
    """Get Docker volumes information"""
    if not client:
        return []
    
    try:
        volumes = client.volumes.list()
        volumes_data = []
        
        # Get all containers to check which volumes are in use
        all_containers = client.containers.list(all=True)
        
        for volume in volumes:
            # Find containers using this volume
            using_containers = []
            for container in all_containers:
                mounts = container.attrs.get('Mounts', [])
                for mount in mounts:
                    if mount.get('Type') == 'volume' and mount.get('Name') == volume.name:
                        using_containers.append({
                            'id': container.short_id,
                            'name': container.name,
                            'status': container.status,
                            'destination': mount.get('Destination', 'N/A'),
                            'mode': mount.get('Mode', 'rw')
                        })
            
            volumes_data.append({
                'name': volume.name,
                'driver': volume.attrs.get('Driver', 'local'),
                'mountpoint': volume.attrs.get('Mountpoint', 'N/A'),
                'scope': volume.attrs.get('Scope', 'local'),
                'created': volume.attrs.get('CreatedAt', 'N/A')[:19].replace('T', ' ') if volume.attrs.get('CreatedAt') else 'N/A',
                'containers': using_containers,
                'container_count': len(using_containers),
                'in_use': len(using_containers) > 0
            })
        
        # Sort: first those in use, then by container count
        volumes_data.sort(key=lambda x: (not x['in_use'], -x['container_count']))
        
        return volumes_data
    except Exception as e:
        print(f"Error retrieving volumes: {e}")
        return []


@app.route('/')
def home():
    """Homepage with Docker data"""
    stats = get_docker_stats()
    
    if not stats:
        # Fallback data if Docker is not available
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
    
    # Filter only stopped containers
    stopped_containers = [c for c in stopped_containers if c['status'] != 'running']
    
    return render_template('index.html', 
                         stats=stats,
                         images=images,
                         running_containers=running_containers,
                         stopped_containers=stopped_containers)


@app.route('/api/stats')
def api_stats():
    """API endpoint to get updated statistics"""
    stats = get_docker_stats()
    return jsonify(stats if stats else {'error': 'Docker not available'})


@app.route('/api/images')
def api_images():
    """API endpoint to get images list"""
    images = get_images_data()
    return jsonify(images)


@app.route('/api/containers/<status>')
def api_containers(status):
    """API endpoint to get containers (running/stopped)"""
    running_only = status == 'running'
    containers = get_containers_data(running_only=running_only)
    
    if status == 'stopped':
        containers = [c for c in containers if c['status'] != 'running']
    
    return jsonify(containers)


@app.route('/container/<container_id>')
def container_detail(container_id):
    """Container detail page"""
    if not client:
        return "Docker not available", 500
    
    try:
        container = client.containers.get(container_id)
        
        # Container basic information
        container_info = {
            'id': container.short_id,
            'name': container.name,
            'image': container.image.tags[0] if container.image.tags else 'unknown',
            'status': container.status,
            'created': container.attrs['Created'][:19].replace('T', ' ')
        }
        
        return render_template('container_detail.html', container=container_info)
    except Exception as e:
        return f"Error: {e}", 404


@app.route('/api/container/<container_id>/stats')
def api_container_stats(container_id):
    """API to get container real-time statistics"""
    if not client:
        return jsonify({'error': 'Docker not available'}), 500
    
    try:
        container = client.containers.get(container_id)
        stats = container.stats(stream=False)
        
        # Calculate CPU percentage with error handling
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
            print(f"⚠️  CPU calculation failed for {container_id}: {e}")
            cpu_percent = 0.0
        
        # Calculate Memory usage with error handling
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 1)
        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0
        mem_usage_mb = mem_usage / (1024 * 1024)
        mem_limit_mb = mem_limit / (1024 * 1024)
        
        # Calculate Network I/O - cumulative values in bytes
        networks = stats.get('networks', {})
        net_input_cumulative = 0
        net_output_cumulative = 0
        try:
            net_input_cumulative = sum(net.get('rx_bytes', 0) for net in networks.values())
            net_output_cumulative = sum(net.get('tx_bytes', 0) for net in networks.values())
        except (KeyError, TypeError, AttributeError):
            pass
        
        # Calculate Disk I/O - cumulative values in bytes
        blkio_stats = stats.get('blkio_stats', {})
        io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
        disk_read_cumulative = 0
        disk_write_cumulative = 0
        try:
            disk_read_cumulative = sum(item['value'] for item in io_service_bytes if item.get('op') == 'Read')
            disk_write_cumulative = sum(item['value'] for item in io_service_bytes if item.get('op') == 'Write')
        except (KeyError, TypeError):
            pass
        
        # Calculate rates using cumulative values
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
        
        # DO NOT save to database here - only background thread does it
        
        return jsonify(current_stats)
    except Exception as e:
        print(f"❌ Error stats container {container_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/container/<container_id>/stats/history')
def api_container_stats_history(container_id):
    """API to get statistics history (last 7 days)"""
    history = get_container_stats_history(container_id, days=7)
    return jsonify(history)


@app.route('/api/container/<container_id>/logs')
def api_container_logs(container_id):
    """API to get latest container logs"""
    if not client:
        return jsonify({'error': 'Docker not available'}), 500
    
    try:
        container = client.containers.get(container_id)
        # Modified: now we get the last 100 logs instead of 10
        logs = container.logs(tail=100, timestamps=True).decode('utf-8')
        
        # Format logs into array
        log_lines = []
        for line in logs.strip().split('\n'):
            if line:
                log_lines.append(line)
        
        return jsonify({'logs': log_lines})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/networks-volumes')
def networks_volumes():
    """Networks and volumes page"""
    networks = get_networks_data()
    volumes = get_volumes_data()
    
    return render_template('networks_volumes.html', networks=networks, volumes=volumes)


@app.route('/network/<network_id>/topology')
def network_topology(network_id):
    """Network topology page for a specific network"""
    if not client:
        return "Docker not available", 500
    
    try:
        # Get specific network
        network = client.networks.get(network_id)
        
        # Reload for updated data
        try:
            network.reload()
        except:
            pass
        
        # Network basic info
        network_info = {
            'id': network.short_id,
            'name': network.name,
            'driver': network.attrs.get('Driver', 'unknown'),
            'scope': network.attrs.get('Scope', 'unknown'),
            'internal': network.attrs.get('Internal', False),
        }
        
        # IPAM
        ipam_config = network.attrs.get('IPAM', {}).get('Config', [])
        network_info['subnet'] = ipam_config[0].get('Subnet', 'N/A') if ipam_config else 'N/A'
        network_info['gateway'] = ipam_config[0].get('Gateway', 'N/A') if ipam_config else 'N/A'
        
        return render_template('network_topology.html', network=network_info)
        
    except Exception as e:
        return f"Error: {e}", 404


@app.route('/api/network/<network_id>/topology')
def api_network_topology(network_id):
    """API to get network topology data in Vis.js format"""
    if not client:
        return jsonify({'error': 'Docker not available'}), 500
    
    try:
        network = client.networks.get(network_id)
        
        # Reload
        try:
            network.reload()
        except:
            pass
        
        nodes = []
        edges = []
        
        # Add network central node
        network_node_id = f"network_{network.id}"
        nodes.append({
            'id': network_node_id,
            'label': network.name,
            'shape': 'diamond',
            'size': 40,
            'color': {
                'background': '#3b82f6',
                'border': '#2563eb',
                'highlight': {
                    'background': '#60a5fa',
                    'border': '#3b82f6'
                }
            },
            'font': {
                'color': '#ffffff',
                'size': 16,
                'face': 'arial',
                'bold': True
            },
            'type': 'network',
            'info': {
                'driver': network.attrs.get('Driver', 'unknown'),
                'scope': network.attrs.get('Scope', 'unknown'),
                'subnet': '',
                'gateway': ''
            }
        })
        
        # IPAM info
        ipam_config = network.attrs.get('IPAM', {}).get('Config', [])
        if ipam_config:
            nodes[0]['info']['subnet'] = ipam_config[0].get('Subnet', 'N/A')
            nodes[0]['info']['gateway'] = ipam_config[0].get('Gateway', 'N/A')
        
        # Find connected containers (alternative method)
        connected_containers = []
        containers_in_network = network.attrs.get('Containers', {})
        
        if not containers_in_network:
            # Alternative method
            all_containers = client.containers.list(all=True)
            for container in all_containers:
                network_settings = container.attrs.get('NetworkSettings', {})
                networks_dict = network_settings.get('Networks', {})
                
                if network.name in networks_dict:
                    net_info = networks_dict[network.name]
                    connected_containers.append({
                        'container': container,
                        'ipv4': net_info.get('IPAddress', 'N/A'),
                        'ipv6': net_info.get('GlobalIPv6Address', 'N/A'),
                        'mac': net_info.get('MacAddress', 'N/A')
                    })
        else:
            # Standard method
            for container_id, container_info in containers_in_network.items():
                try:
                    container = client.containers.get(container_id)
                    ipv4_raw = container_info.get('IPv4Address', '')
                    ipv4 = ipv4_raw.split('/')[0] if ipv4_raw else 'N/A'
                    
                    connected_containers.append({
                        'container': container,
                        'ipv4': ipv4,
                        'ipv6': container_info.get('IPv6Address', 'N/A'),
                        'mac': container_info.get('MacAddress', 'N/A')
                    })
                except:
                    continue
        
        # Add container nodes
        for item in connected_containers:
            container = item['container']
            
            # Color based on status - darker and more contrasted colors
            if container.status == 'running':
                color_bg = '#065f46'      # Dark green
                color_border = '#10b981'   # Bright green border
                color_highlight_bg = '#059669'
            elif container.status == 'exited':
                color_bg = '#1e293b'       # Dark gray
                color_border = '#64748b'   # Medium gray border
                color_highlight_bg = '#334155'
            else:
                color_bg = '#78350f'       # Dark orange
                color_border = '#f59e0b'   # Bright orange border
                color_highlight_bg = '#92400e'
            
            # Get ports
            ports = container.attrs['NetworkSettings']['Ports']
            port_list = []
            if ports:
                for container_port, host_info in ports.items():
                    if host_info:
                        for mapping in host_info:
                            host_port = mapping.get('HostPort', '')
                            port_list.append(f"{host_port}:{container_port}")
            
            nodes.append({
                'id': container.id,
                'label': container.name,
                'shape': 'box',
                'size': 25,
                'color': {
                    'background': color_bg,
                    'border': color_border,
                    'highlight': {
                        'background': color_highlight_bg,
                        'border': color_border
                    }
                },
                'font': {
                    'color': '#ffffff',
                    'size': 14,
                    'face': 'arial'
                },
                'type': 'container',
                'info': {
                    'id': container.short_id,
                    'name': container.name,
                    'status': container.status,
                    'image': container.image.tags[0] if container.image.tags else 'unknown',
                    'ipv4': item['ipv4'],
                    'ipv6': item['ipv6'],
                    'mac': item['mac'],
                    'ports': ', '.join(port_list) if port_list else 'N/A'
                }
            })
            
            # Add edge between network and container
            edges.append({
                'from': network_node_id,
                'to': container.id,
                'color': {
                    'color': '#94a3b8',
                    'highlight': '#3b82f6'
                },
                'width': 2,
                'smooth': {
                    'type': 'cubicBezier',
                    'roundness': 0.5
                }
            })
        
        return jsonify({
            'nodes': nodes,
            'edges': edges
        })
        
    except Exception as e:
        print(f"❌ Topology error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/networks')
def api_networks():
    """API endpoint to get networks list"""
    networks = get_networks_data()
    return jsonify(networks)


@app.route('/api/volumes')
def api_volumes():
    """API endpoint to get volumes list"""
    volumes = get_volumes_data()
    return jsonify(volumes)


def collect_stats_background():
    """Function that collects statistics in background every minute"""
    print("🔄 Statistics collection thread started")
    
    while True:
        if client:
            try:
                containers = client.containers.list()
                print(f"\n📊 Collecting stats for {len(containers)} containers...")
                
                for container in containers:
                    try:
                        stats = container.stats(stream=False)
                        
                        # Calculate CPU with error handling
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
                        
                        # Calculate Memory with error handling
                        mem_usage = stats['memory_stats'].get('usage', 0)
                        mem_limit = stats['memory_stats'].get('limit', 1)
                        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0
                        mem_usage_mb = mem_usage / (1024 * 1024)
                        mem_limit_mb = mem_limit / (1024 * 1024)
                        
                        # Calculate Network I/O - cumulative values in bytes
                        networks = stats.get('networks', {})
                        net_input_cumulative = 0
                        net_output_cumulative = 0
                        try:
                            net_input_cumulative = sum(net.get('rx_bytes', 0) for net in networks.values())
                            net_output_cumulative = sum(net.get('tx_bytes', 0) for net in networks.values())
                        except (KeyError, TypeError, AttributeError):
                            pass
                        
                        # Calculate Disk I/O - cumulative values in bytes
                        blkio_stats = stats.get('blkio_stats', {})
                        io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
                        disk_read_cumulative = 0
                        disk_write_cumulative = 0
                        try:
                            disk_read_cumulative = sum(item['value'] for item in io_service_bytes if item.get('op') == 'Read')
                            disk_write_cumulative = sum(item['value'] for item in io_service_bytes if item.get('op') == 'Write')
                        except (KeyError, TypeError):
                            pass
                        
                        # Calculate rates using cumulative values
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
                        
                        # Save to database
                        save_container_stats(container.short_id, container.name, current_stats)
                        print(f"  ✅ {container.name}: CPU={cpu_percent:.1f}% RAM={mem_percent:.1f}% NET_IN={rates['net_input_mb_s']:.2f}MB/s")
                        
                    except Exception as e:
                        print(f"  ❌ Error collecting stats for {container.name}: {e}")
                
                # Database cleanup every cycle
                cleanup_old_stats()
                print("✅ Collection cycle completed\n")
                
            except Exception as e:
                print(f"❌ General error collecting stats: {e}")
        
        time.sleep(60)  # Every minute


# Flag to avoid multiple thread starts
stats_thread_started = False

# Start thread for background statistics collection ONLY ONCE
if not stats_thread_started:
    stats_thread = threading.Thread(target=collect_stats_background, daemon=True)
    stats_thread.start()
    stats_thread_started = True
    print("✅ Statistics collection thread started at initialization")


if __name__ == '__main__':
    
    # Determine host and port from environment variables
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(
        debug=debug,
        host=host,
        port=port,
        use_reloader=False  # IMPORTANT: avoid double thread
    )