## DOCKER WATCHER
----------------------------------------
#### Description
Docker Watcher is a comprehensive Flask-based web application for monitoring and visualizing Docker containers running on the host.

**Features:**

**Dashboard:**
- Docker images overview
- Running containers with health checks
- Stopped containers
- Host CPU and RAM consumption monitoring
- Real-time statistics with auto-refresh

**Container Details:**
- Real-time CPU, RAM, Network, and Disk I/O metrics
- Historical charts (7-day retention)
- Live container logs with search functionality
- Rate-based I/O metrics (MB/s)

**Networks & Volumes:**
- Docker networks visualization
- Connected containers per network
- IP address assignments
- Docker volumes overview
- Volume usage by containers
- Interactive network topology visualization

**Database:**
- SQLite-based persistent storage
- Automatic cleanup (7-day retention)
- Statistics export capabilities

----------------------------------------
#### Requirements

- Python 3.11+
- Docker Engine
- Access to Docker socket

----------------------------------------
#### Installation

1. Run the permit_docker.sh script to grant Docker socket access permissions
```bash
./permit_docker.sh
```

2. Create a virtual environment
```bash
python -m venv venv
```

3. Activate the virtual environment
```bash
source venv/bin/activate
```

4. Install dependencies from requirements.txt
```bash
pip3 install -r requirements.txt
```

5. Start the web server
```bash
python3 app.py 
```

6. Open your browser and navigate to http://localhost:5000

----------------------------------------
#### Database Utilities

Manage the SQLite database using the db_utils.py script:
```bash
# View database statistics
python db_utils.py stats

# List tracked containers
python db_utils.py list

# Clean up old data (default: 7 days)
python db_utils.py cleanup 7

# Export container data to CSV
python db_utils.py export <container_id>

# Optimize database
python db_utils.py vacuum
```

----------------------------------------
#### Technologies

- **Backend:** Flask, Docker SDK for Python, psutil
- **Database:** SQLite3
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Visualization:** Chart.js, Vis.js Network
- **Monitoring:** Real-time Docker stats API

----------------------------------------
#### License

This project is distributed under the [GNU GPL v3.0](LICENSE) license.

Copyright (C) 2025 Giovambattista Crudo

----------------------------------------
#### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

----------------------------------------
#### Support

For issues, questions, or suggestions, please open an issue on the project repository.