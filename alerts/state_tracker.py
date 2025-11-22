"""
State Tracker - Monitors container states and detects alert conditions
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque


class ContainerState:
    """Represents the state of a single container"""
    
    def __init__(self, container_id: str, container_name: str, buffer_size: int = 3):
        """
        Initialize container state
        
        Args:
            container_id: Container ID
            container_name: Container name
            buffer_size: Number of stats readings to keep in history
        """
        self.container_id = container_id
        self.container_name = container_name
        
        # Circular buffers for stats history
        self.cpu_history = deque(maxlen=buffer_size)
        self.ram_history = deque(maxlen=buffer_size)
        
        # Health status tracking
        self.current_health = "unknown"
        self.previous_health = "unknown"
        
        # Alert state tracking
        self.cpu_alert_active = False
        self.ram_alert_active = False
        self.health_alert_active = False
        
        # Cooldown tracking
        self.last_cpu_alert = None
        self.last_ram_alert = None
        self.last_health_alert = None
        self.last_recovery_alert = None
        
        # Timestamps
        self.last_update = None
        self.unhealthy_since = None
    
    def update_stats(self, cpu_percent: float, ram_percent: float):
        """
        Update container stats
        
        Args:
            cpu_percent: Current CPU usage percentage
            ram_percent: Current RAM usage percentage
        """
        self.cpu_history.append(cpu_percent)
        self.ram_history.append(ram_percent)
        self.last_update = datetime.now()
    
    def update_health(self, health_status: str):
        """
        Update container health status
        
        Args:
            health_status: Current health status (healthy, unhealthy, starting, none)
        """
        self.previous_health = self.current_health
        self.current_health = health_status
        
        # Track when container became unhealthy
        if health_status == "unhealthy" and self.previous_health != "unhealthy":
            self.unhealthy_since = datetime.now()
        elif health_status == "healthy":
            self.unhealthy_since = None
    
    def has_health_changed(self) -> bool:
        """Check if health status changed"""
        return (self.current_health != self.previous_health and 
                self.previous_health != "unknown")
    
    def is_unhealthy_transition(self) -> bool:
        """Check if container transitioned to unhealthy"""
        return (self.current_health == "unhealthy" and 
                self.previous_health in ["healthy", "starting"])
    
    def is_recovery_transition(self) -> bool:
        """Check if container recovered (unhealthy -> healthy)"""
        return (self.current_health == "healthy" and 
                self.previous_health == "unhealthy")
    
    def get_downtime_duration(self) -> Optional[timedelta]:
        """Get duration of unhealthy state (if recovering)"""
        if self.is_recovery_transition() and self.unhealthy_since:
            return datetime.now() - self.unhealthy_since
        return None
    
    def check_sustained_high_cpu(self, threshold: float) -> bool:
        """
        Check if CPU has been consistently high
        
        Args:
            threshold: CPU percentage threshold
            
        Returns:
            True if all readings in buffer are above threshold
        """
        if len(self.cpu_history) < self.cpu_history.maxlen:
            return False  # Not enough data yet
        
        return all(cpu >= threshold for cpu in self.cpu_history)
    
    def check_sustained_high_ram(self, threshold: float) -> bool:
        """
        Check if RAM has been consistently high
        
        Args:
            threshold: RAM percentage threshold
            
        Returns:
            True if all readings in buffer are above threshold
        """
        if len(self.ram_history) < self.ram_history.maxlen:
            return False  # Not enough data yet
        
        return all(ram >= threshold for ram in self.ram_history)
    
    def get_cpu_history_list(self) -> List[float]:
        """Get CPU history as list"""
        return list(self.cpu_history)
    
    def get_ram_history_list(self) -> List[float]:
        """Get RAM history as list"""
        return list(self.ram_history)
    
    def get_current_cpu(self) -> Optional[float]:
        """Get most recent CPU reading"""
        return self.cpu_history[-1] if self.cpu_history else None
    
    def get_current_ram(self) -> Optional[float]:
        """Get most recent RAM reading"""
        return self.ram_history[-1] if self.ram_history else None
    
    def is_in_cooldown(self, alert_type: str, cooldown_minutes: int) -> bool:
        """
        Check if alert type is in cooldown period
        
        Args:
            alert_type: Type of alert ('cpu', 'ram', 'health', 'recovery')
            cooldown_minutes: Cooldown duration in minutes
            
        Returns:
            True if in cooldown period
        """
        last_alert_time = None
        
        if alert_type == 'cpu':
            last_alert_time = self.last_cpu_alert
        elif alert_type == 'ram':
            last_alert_time = self.last_ram_alert
        elif alert_type == 'health':
            last_alert_time = self.last_health_alert
        elif alert_type == 'recovery':
            last_alert_time = self.last_recovery_alert
        
        if last_alert_time is None:
            return False
        
        time_since_alert = datetime.now() - last_alert_time
        return time_since_alert < timedelta(minutes=cooldown_minutes)
    
    def set_alert_sent(self, alert_type: str):
        """
        Mark that an alert was sent for this type
        
        Args:
            alert_type: Type of alert ('cpu', 'ram', 'health', 'recovery')
        """
        now = datetime.now()
        
        if alert_type == 'cpu':
            self.last_cpu_alert = now
            self.cpu_alert_active = True
        elif alert_type == 'ram':
            self.last_ram_alert = now
            self.ram_alert_active = True
        elif alert_type == 'health':
            self.last_health_alert = now
            self.health_alert_active = True
        elif alert_type == 'recovery':
            self.last_recovery_alert = now
    
    def clear_alert(self, alert_type: str):
        """
        Clear active alert flag
        
        Args:
            alert_type: Type of alert ('cpu', 'ram', 'health')
        """
        if alert_type == 'cpu':
            self.cpu_alert_active = False
        elif alert_type == 'ram':
            self.ram_alert_active = False
        elif alert_type == 'health':
            self.health_alert_active = False


class StateTracker:
    """Tracks state of all containers and detects alert conditions"""
    
    def __init__(self, buffer_size: int = 3):
        """
        Initialize state tracker
        
        Args:
            buffer_size: Number of stats readings to keep per container
        """
        self.buffer_size = buffer_size
        self.containers: Dict[str, ContainerState] = {}
    
    def get_or_create_state(self, container_id: str, container_name: str) -> ContainerState:
        """
        Get existing container state or create new one
        
        Args:
            container_id: Container ID
            container_name: Container name
            
        Returns:
            ContainerState instance
        """
        if container_id not in self.containers:
            self.containers[container_id] = ContainerState(
                container_id, 
                container_name, 
                self.buffer_size
            )
        return self.containers[container_id]
    
    def update_container(self, container_id: str, container_name: str, 
                        cpu_percent: float, ram_percent: float, 
                        health_status: str = "none"):
        """
        Update container state with new stats
        
        Args:
            container_id: Container ID
            container_name: Container name
            cpu_percent: CPU usage percentage
            ram_percent: RAM usage percentage
            health_status: Health status (healthy, unhealthy, starting, none)
        """
        state = self.get_or_create_state(container_id, container_name)
        state.update_stats(cpu_percent, ram_percent)
        state.update_health(health_status)
    
    def get_state(self, container_id: str) -> Optional[ContainerState]:
        """
        Get container state
        
        Args:
            container_id: Container ID
            
        Returns:
            ContainerState or None if not found
        """
        return self.containers.get(container_id)
    
    def get_all_states(self) -> Dict[str, ContainerState]:
        """Get all container states"""
        return self.containers
    
    def cleanup_stale_containers(self, active_container_ids: List[str]):
        """
        Remove containers that are no longer active
        
        Args:
            active_container_ids: List of currently active container IDs
        """
        # Find containers to remove (not in active list)
        to_remove = [
            cid for cid in self.containers.keys() 
            if cid not in active_container_ids
        ]
        
        for cid in to_remove:
            del self.containers[cid]
    
    def clear_cpu_alert_if_normal(self, container_id: str, threshold: float):
        """
        Clear CPU alert flag if CPU is back to normal
        
        Args:
            container_id: Container ID
            threshold: CPU threshold percentage
        """
        state = self.get_state(container_id)
        if state and state.cpu_alert_active:
            current_cpu = state.get_current_cpu()
            if current_cpu is not None and current_cpu < threshold:
                state.clear_alert('cpu')
    
    def clear_ram_alert_if_normal(self, container_id: str, threshold: float):
        """
        Clear RAM alert flag if RAM is back to normal
        
        Args:
            container_id: Container ID
            threshold: RAM threshold percentage
        """
        state = self.get_state(container_id)
        if state and state.ram_alert_active:
            current_ram = state.get_current_ram()
            if current_ram is not None and current_ram < threshold:
                state.clear_alert('ram')


# Global singleton instance
_state_tracker = None

def get_state_tracker() -> StateTracker:
    """
    Get global state tracker instance
    
    Returns:
        StateTracker instance
    """
    global _state_tracker
    if _state_tracker is None:
        _state_tracker = StateTracker()
    return _state_tracker