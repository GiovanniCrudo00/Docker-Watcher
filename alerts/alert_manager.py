"""
Alert Manager - Detects alert conditions and manages alert lifecycle
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .state_tracker import get_state_tracker, ContainerState
from .config_loader import get_config


class AlertType(Enum):
    """Types of alerts"""
    UNHEALTHY = "unhealthy"
    HIGH_CPU = "high_cpu"
    HIGH_RAM = "high_ram"
    RECOVERY = "recovery"


class AlertPriority(Enum):
    """Alert priority levels"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Alert:
    """Represents a single alert"""
    container_id: str
    container_name: str
    alert_type: AlertType
    priority: AlertPriority
    value: Optional[float]  # CPU% or RAM%, None for health alerts
    timestamp: datetime
    history: Optional[List[float]] = None  # Historical values for context
    downtime: Optional[str] = None  # For recovery alerts
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'container_id': self.container_id,
            'container_name': self.container_name,
            'alert_type': self.alert_type.value,
            'priority': self.priority.value,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'history': self.history,
            'downtime': self.downtime
        }


@dataclass
class AlertBatch:
    """Batch of alerts to send together"""
    critical_alerts: List[Alert]
    warning_alerts: List[Alert]
    recovery_alerts: List[Alert]
    timestamp: datetime
    
    def has_alerts(self) -> bool:
        """Check if batch has any alerts"""
        return bool(self.critical_alerts or self.warning_alerts)
    
    def has_recovery(self) -> bool:
        """Check if batch has recovery alerts"""
        return bool(self.recovery_alerts)
    
    def total_count(self) -> int:
        """Total number of alerts"""
        return len(self.critical_alerts) + len(self.warning_alerts)


class AlertManager:
    """Manages alert detection and lifecycle"""
    
    def __init__(self):
        """Initialize alert manager"""
        self.config = get_config()
        self.state_tracker = get_state_tracker()
    
    def check_container_alerts(self, container_id: str, container_name: str,
                               cpu_percent: float, ram_percent: float,
                               health_status: str = "none") -> List[Alert]:
        """
        Check single container for alert conditions
        
        Args:
            container_id: Container ID
            container_name: Container name
            cpu_percent: Current CPU percentage
            ram_percent: Current RAM percentage
            health_status: Health status
            
        Returns:
            List of alerts for this container
        """
        # Check if alerts disabled for this container
        if self.config.is_container_alerts_disabled(container_name):
            return []
        
        alerts = []
        
        # Update state tracker
        self.state_tracker.update_container(
            container_id, container_name, 
            cpu_percent, ram_percent, health_status
        )
        
        state = self.state_tracker.get_state(container_id)
        if not state:
            return []
        
        # Get thresholds for this container
        cpu_threshold = self.config.get_cpu_threshold(container_name)
        ram_threshold = self.config.get_ram_threshold(container_name)
        cooldown_minutes = self.config.get('alerts.cooldown_minutes', 15)
        recovery_cooldown = self.config.get('alerts.recovery_cooldown_minutes', 5)
        
        # Check for RECOVERY (unhealthy -> healthy)
        if state.is_recovery_transition():
            if not state.is_in_cooldown('recovery', recovery_cooldown):
                downtime = state.get_downtime_duration()
                downtime_str = None
                if downtime:
                    minutes = int(downtime.total_seconds() / 60)
                    downtime_str = f"{minutes} minutes"
                
                alerts.append(Alert(
                    container_id=container_id,
                    container_name=container_name,
                    alert_type=AlertType.RECOVERY,
                    priority=AlertPriority.INFO,
                    value=None,
                    timestamp=datetime.now(),
                    downtime=downtime_str
                ))
                state.set_alert_sent('recovery')
                state.clear_alert('health')
        
        # Check for UNHEALTHY
        elif state.is_unhealthy_transition():
            if not state.is_in_cooldown('health', cooldown_minutes):
                alerts.append(Alert(
                    container_id=container_id,
                    container_name=container_name,
                    alert_type=AlertType.UNHEALTHY,
                    priority=AlertPriority.CRITICAL,
                    value=None,
                    timestamp=datetime.now()
                ))
                state.set_alert_sent('health')
        
        # Check for HIGH CPU (sustained)
        if state.check_sustained_high_cpu(cpu_threshold):
            if not state.cpu_alert_active and not state.is_in_cooldown('cpu', cooldown_minutes):
                alerts.append(Alert(
                    container_id=container_id,
                    container_name=container_name,
                    alert_type=AlertType.HIGH_CPU,
                    priority=AlertPriority.WARNING,
                    value=state.get_current_cpu(),
                    timestamp=datetime.now(),
                    history=state.get_cpu_history_list()
                ))
                state.set_alert_sent('cpu')
        else:
            # Clear alert if CPU back to normal
            self.state_tracker.clear_cpu_alert_if_normal(container_id, cpu_threshold)
        
        # Check for HIGH RAM (sustained)
        if state.check_sustained_high_ram(ram_threshold):
            if not state.ram_alert_active and not state.is_in_cooldown('ram', cooldown_minutes):
                alerts.append(Alert(
                    container_id=container_id,
                    container_name=container_name,
                    alert_type=AlertType.HIGH_RAM,
                    priority=AlertPriority.WARNING,
                    value=state.get_current_ram(),
                    timestamp=datetime.now(),
                    history=state.get_ram_history_list()
                ))
                state.set_alert_sent('ram')
        else:
            # Clear alert if RAM back to normal
            self.state_tracker.clear_ram_alert_if_normal(container_id, ram_threshold)
        
        return alerts
    
    def check_all_containers(self, containers_data: List[Dict]) -> AlertBatch:
        """
        Check all containers and aggregate alerts
        
        Args:
            containers_data: List of container stats dicts with keys:
                - container_id
                - container_name
                - cpu_percent
                - ram_percent
                - health_status (optional)
        
        Returns:
            AlertBatch with all alerts found
        """
        all_alerts = []
        
        # Check each container
        for data in containers_data:
            container_alerts = self.check_container_alerts(
                container_id=data['container_id'],
                container_name=data['container_name'],
                cpu_percent=data['cpu_percent'],
                ram_percent=data['ram_percent'],
                health_status=data.get('health_status', 'none')
            )
            all_alerts.extend(container_alerts)
        
        # Cleanup stale containers
        active_ids = [data['container_id'] for data in containers_data]
        self.state_tracker.cleanup_stale_containers(active_ids)
        
        # Separate alerts by priority
        critical = [a for a in all_alerts if a.priority == AlertPriority.CRITICAL]
        warning = [a for a in all_alerts if a.priority == AlertPriority.WARNING]
        recovery = [a for a in all_alerts if a.alert_type == AlertType.RECOVERY]
        
        return AlertBatch(
            critical_alerts=critical,
            warning_alerts=warning,
            recovery_alerts=recovery,
            timestamp=datetime.now()
        )
    
    def should_send_email(self, alert_batch: AlertBatch) -> bool:
        """
        Determine if email should be sent
        
        Args:
            alert_batch: Batch of alerts
            
        Returns:
            True if email should be sent
        """
        if not self.config.is_enabled():
            return False
        
        # Send if there are any alerts
        return alert_batch.has_alerts() or alert_batch.has_recovery()


# Global singleton
_alert_manager = None

def get_alert_manager() -> AlertManager:
    """
    Get global alert manager instance
    
    Returns:
        AlertManager instance
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager