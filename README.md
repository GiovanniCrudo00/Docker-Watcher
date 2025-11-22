## DOCKER WATCHER
----------------------------------------
#### Description
Docker Watcher is a comprehensive Flask-based web application for monitoring and visualizing Docker containers running on the host, with intelligent email alerting capabilities.

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

**Email Alerting System:**
- Automatic email notifications for container issues
- **Critical Alerts:** Container becomes unhealthy
- **Warning Alerts:** High CPU/RAM usage (≥90% for 3 minutes)
- **Recovery Notifications:** Container returns to healthy state
- Configurable thresholds and cooldown periods
- Aggregate alerts (multiple issues in one email)
- HTML email templates with direct links to containers
- Per-container rule customization

**Database:**
- SQLite-based persistent storage
- Automatic cleanup (7-day retention for stats, 30-day for alerts)
- Statistics and alert history export capabilities

----------------------------------------
#### Requirements

- Python 3.11+
- Docker Engine
- Access to Docker socket
- SMTP email account (Gmail, Outlook, etc.) for alerts

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

5. **Configure Email Alerts** (see Alert Configuration section below)

6. Start the web server
```bash
python3 app.py 
```

7. Open your browser and navigate to http://localhost:5001

----------------------------------------
#### Alert Configuration

**Step 1: Create Configuration File**

Copy the template and customize it:
```bash
cp config/alerts.yml.template config/alerts.yml
nano config/alerts.yml
```

**Step 2: Configure Email Settings**

For **Gmail**:
```yaml
email:
  enabled: true
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  use_tls: true
  sender_email: "your-email@gmail.com"
  sender_password: "your-app-password"  # See Gmail setup below
  recipient_emails:
    - "admin@example.com"
    - "alerts@example.com"
```

For **Outlook/Hotmail**:
```yaml
email:
  smtp_server: "smtp-mail.outlook.com"
  smtp_port: 587
  sender_email: "your-email@outlook.com"
  sender_password: "your-password"
```

**Step 3: Customize Alert Thresholds** (optional)
```yaml
thresholds:
  cpu_percent: 90          # CPU threshold (%)
  ram_percent: 90          # RAM threshold (%)
  duration_minutes: 3      # Consecutive minutes above threshold

alerts:
  cooldown_minutes: 15              # Wait time between same alerts
  recovery_cooldown_minutes: 5      # Wait time for recovery notifications
```

**Step 4: Set Application URL**
```yaml
app:
  base_url: "http://your-server:5001"  # Used for links in emails
```

----------------------------------------
#### Gmail App Password Setup

Gmail requires an **App Password** for third-party applications:

1. **Enable 2-Factor Authentication:**
   - Go to: https://myaccount.google.com/security
   - Enable "2-Step Verification"

2. **Generate App Password:**
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and your device
   - Click "Generate"
   - Copy the 16-character password (e.g., `abcdefghijklmnop`)

3. **Add to Configuration:**
```yaml
   sender_password: "abcdefghijklmnop"  # No spaces
```

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

**Query alert history:**
```bash
sqlite3 data/docker_stats.db "SELECT datetime(timestamp) as time, container_name, alert_type, priority, email_sent FROM alert_history ORDER BY timestamp DESC LIMIT 20;"
```

----------------------------------------
#### Alert System Behavior

**Critical Alerts (🚨):**
- Container health status changes to `unhealthy`
- Immediate notification
- 15-minute cooldown

**Warning Alerts (⚠️):**
- CPU usage ≥90% for 3 consecutive minutes
- RAM usage ≥90% for 3 consecutive minutes
- 15-minute cooldown per alert type

**Recovery Notifications (✅):**
- Container returns to `healthy` state
- Includes downtime duration
- 5-minute cooldown (flapping protection)

**Aggregation:**
- Multiple alerts combined into single email
- Separate recovery emails for clarity
- Reduces email spam

**Per-Container Rules (Optional):**
```yaml
container_rules:
  - name: "critical-database"
    cpu_threshold: 80
    ram_threshold: 85
  - name: "dev-container"
    alerts_disabled: true
```

----------------------------------------
#### Configuration Reference

**Full configuration options in `config/alerts.yml`:**
```yaml
# Application settings
app:
  base_url: "http://localhost:5001"

# Alert thresholds
thresholds:
  cpu_percent: 90
  ram_percent: 90
  duration_minutes: 3

# Alert behavior
alerts:
  enabled: true
  cooldown_minutes: 15
  recovery_cooldown_minutes: 5

# Email configuration
email:
  enabled: true
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  use_tls: true
  sender_email: "your-email@gmail.com"
  sender_password: "your-app-password"
  recipient_emails:
    - "admin@example.com"

# Recovery notifications
recovery:
  send_email: true
  include_downtime: true

# Logging
logging:
  log_alerts_to_console: true
  log_alerts_to_database: true
```

**Environment Variables:**
You can use environment variables in the configuration:
```yaml
sender_email: "${SMTP_EMAIL}"
sender_password: "${SMTP_PASSWORD}"
```

Then export them before running:
```bash
export SMTP_EMAIL="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
python app.py
```

----------------------------------------
#### Troubleshooting

**Alert system not working:**
```bash
# Check if alerts are enabled in config
grep "enabled: true" config/alerts.yml

# Verify configuration is valid
python -c "from alerts import get_config; get_config().load()"

# Check console output for alert system initialization
python app.py | grep -i alert
```

**Emails not received:**
1. Check spam/junk folder
2. Verify SMTP credentials with test script: `python test_alerts.py`
3. Check alert history in database:
```bash
   sqlite3 data/docker_stats.db "SELECT * FROM alert_history ORDER BY timestamp DESC LIMIT 5;"
```
4. Review console logs for email sending confirmation

**Gmail authentication failed:**
- Ensure 2FA is enabled
- Use App Password, not regular password
- Remove spaces from App Password in config
- Try: https://myaccount.google.com/apppasswords

**No alerts triggering:**
- Verify containers have health checks: `docker inspect <container> | grep -A5 Health`
- Check threshold settings in `config/alerts.yml`
- Monitor container stats: `docker stats`
- Review StateTracker buffer (requires 3 consecutive readings)

----------------------------------------
#### Technologies

- **Backend:** Flask, Docker SDK for Python, psutil
- **Database:** SQLite3
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Visualization:** Chart.js, Vis.js Network
- **Monitoring:** Real-time Docker stats API
- **Alerting:** SMTP/TLS email notifications, YAML configuration
- **Email Templates:** HTML multipart emails with inline CSS

----------------------------------------
#### Support

For issues, questions, or suggestions, please open an issue on the project repository.

**Common Issues:**
- Email configuration: See Troubleshooting section
- Gmail authentication: Use App Passwords
- Database queries: Use SQLite commands in documentation

**Useful Links:**
- Gmail App Passwords: https://myaccount.google.com/apppasswords
- Docker Health Checks: https://docs.docker.com/engine/reference/builder/#healthcheck
- SMTP Settings: https://support.google.com/mail/answer/7126229
----------------------------------------
#### License

This project is distributed under the [GNU GPL v3.0](LICENSE) license.

Copyright (C) 2025 Giovambattista Crudo

