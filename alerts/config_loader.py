"""
Configuration loader and validator for Docker Watcher Alert System
"""

import yaml
import os
import re
from typing import Dict, Any, List, Optional


class ConfigLoader:
    """Loads and validates alert configuration from YAML file"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize config loader
        
        Args:
            config_path: Path to alerts.yml file. If None, uses default location.
        """
        if config_path is None:
            # Default location
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'config', 
                'alerts.yml'
            )
        
        self.config_path = config_path
        self.config = None
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file
        
        Returns:
            Dict containing configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
            ValueError: If configuration validation fails
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please copy config/alerts.yml.template to config/alerts.yml "
                f"and configure it with your settings."
            )
        
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Expand environment variables
        self.config = self._expand_env_vars(self.config)
        
        # Validate configuration
        self._validate()
        
        return self.config
    
    def _expand_env_vars(self, config: Any) -> Any:
        """
        Recursively expand environment variables in config
        Supports ${VAR_NAME} syntax
        
        Args:
            config: Configuration dict or value
            
        Returns:
            Config with expanded environment variables
        """
        if isinstance(config, dict):
            return {key: self._expand_env_vars(value) for key, value in config.items()}
        elif isinstance(config, list):
            return [self._expand_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Replace ${VAR_NAME} with environment variable
            pattern = r'\$\{([^}]+)\}'
            
            def replace_env(match):
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))
            
            return re.sub(pattern, replace_env, config)
        else:
            return config
    
    def _validate(self):
        """
        Validate configuration structure and values
        
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.config:
            raise ValueError("Configuration is empty")
        
        # Required top-level keys
        required_keys = ['app', 'thresholds', 'alerts', 'email']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required configuration section: {key}")
        
        # Validate app section
        if 'base_url' not in self.config['app']:
            raise ValueError("Missing required field: app.base_url")
        
        # Validate thresholds
        thresholds = self.config['thresholds']
        if thresholds['cpu_percent'] < 0 or thresholds['cpu_percent'] > 100:
            raise ValueError("cpu_percent must be between 0 and 100")
        if thresholds['ram_percent'] < 0 or thresholds['ram_percent'] > 100:
            raise ValueError("ram_percent must be between 0 and 100")
        if thresholds['duration_minutes'] < 1:
            raise ValueError("duration_minutes must be at least 1")
        
        # Validate alerts section
        alerts = self.config['alerts']
        if alerts['cooldown_minutes'] < 1:
            raise ValueError("cooldown_minutes must be at least 1")
        if 'recovery_cooldown_minutes' in alerts and alerts['recovery_cooldown_minutes'] < 1:
            raise ValueError("recovery_cooldown_minutes must be at least 1")
        
        # Validate email section
        email = self.config['email']
        if email.get('enabled', True):
            required_email_fields = ['smtp_server', 'smtp_port', 'sender_email', 
                                    'sender_password', 'recipient_emails']
            for field in required_email_fields:
                if field not in email:
                    raise ValueError(f"Missing required email field: {field}")
            
            if not email['recipient_emails']:
                raise ValueError("At least one recipient email is required")
            
            # Validate email format (basic check)
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            if not re.match(email_pattern, email['sender_email']):
                raise ValueError(f"Invalid sender email format: {email['sender_email']}")
            
            for recipient in email['recipient_emails']:
                if not re.match(email_pattern, recipient):
                    raise ValueError(f"Invalid recipient email format: {recipient}")
            
            # Validate SMTP port
            if not isinstance(email['smtp_port'], int) or email['smtp_port'] < 1 or email['smtp_port'] > 65535:
                raise ValueError("smtp_port must be between 1 and 65535")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key path
        
        Args:
            key_path: Dot-separated path (e.g., 'email.smtp_server')
            default: Default value if key not found
            
        Returns:
            Configuration value
            
        Example:
            config.get('thresholds.cpu_percent')  # Returns 90
            config.get('email.smtp_server')        # Returns 'smtp.gmail.com'
        """
        if not self.config:
            return default
        
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def is_enabled(self) -> bool:
        """Check if alert system is enabled"""
        return self.get('alerts.enabled', True) and self.get('email.enabled', True)
    
    def get_container_rule(self, container_name: str) -> Optional[Dict[str, Any]]:
        """
        Get specific rules for a container if defined
        
        Args:
            container_name: Name of the container
            
        Returns:
            Container-specific rules or None
        """
        rules = self.get('container_rules', [])
        for rule in rules:
            if rule.get('name') == container_name:
                return rule
        return None
    
    def get_cpu_threshold(self, container_name: str) -> float:
        """Get CPU threshold for specific container or global default"""
        rule = self.get_container_rule(container_name)
        if rule and 'cpu_threshold' in rule:
            return rule['cpu_threshold']
        return self.get('thresholds.cpu_percent')
    
    def get_ram_threshold(self, container_name: str) -> float:
        """Get RAM threshold for specific container or global default"""
        rule = self.get_container_rule(container_name)
        if rule and 'ram_threshold' in rule:
            return rule['ram_threshold']
        return self.get('thresholds.ram_percent')
    
    def is_container_alerts_disabled(self, container_name: str) -> bool:
        """Check if alerts are disabled for specific container"""
        rule = self.get_container_rule(container_name)
        if rule:
            return rule.get('alerts_disabled', False)
        return False


# Singleton instance
_config_instance = None

def get_config() -> ConfigLoader:
    """
    Get singleton config instance
    
    Returns:
        ConfigLoader instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader()
        _config_instance.load()
    return _config_instance


def reload_config():
    """Reload configuration from file"""
    global _config_instance
    _config_instance = None
    return get_config()


# Example usage
if __name__ == '__main__':
    try:
        config = ConfigLoader()
        config.load()
        
        print("✅ Configuration loaded successfully!")
        print(f"📧 SMTP Server: {config.get('email.smtp_server')}")
        print(f"🎯 CPU Threshold: {config.get('thresholds.cpu_percent')}%")
        print(f"💾 RAM Threshold: {config.get('thresholds.ram_percent')}%")
        print(f"⏱️  Duration: {config.get('thresholds.duration_minutes')} minutes")
        print(f"🔗 Base URL: {config.get('app.base_url')}")
        print(f"📬 Recipients: {', '.join(config.get('email.recipient_emails'))}")
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
