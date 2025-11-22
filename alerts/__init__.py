"""
Docker Watcher Alert System

This package provides email alerting for Docker container issues:
- Container health status changes (unhealthy)
- High CPU usage (sustained over threshold)
- High RAM usage (sustained over threshold)
"""

__version__ = '1.0.0'

from .config_loader import get_config, reload_config
from .state_tracker import get_state_tracker
from .alert_manager import get_alert_manager, Alert, AlertBatch, AlertType, AlertPriority
from .email_sender import get_email_sender

__all__ = [
    'get_config', 
    'reload_config',
    'get_state_tracker',
    'get_alert_manager',
    'get_email_sender',
    'Alert',
    'AlertBatch',
    'AlertType',
    'AlertPriority'
]