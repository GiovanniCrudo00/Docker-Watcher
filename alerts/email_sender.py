"""
Email Sender - Sends alert emails via SMTP
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Optional
import os

from .config_loader import get_config
from .alert_manager import AlertBatch, Alert, AlertType, AlertPriority


class EmailSender:
    """Handles sending alert emails"""
    
    def __init__(self):
        """Initialize email sender"""
        self.config = get_config()
    
    def _load_template(self, template_name: str) -> str:
        """
        Load email template from file
        
        Args:
            template_name: Name of template file
            
        Returns:
            Template content as string
        """
        template_path = os.path.join(
            os.path.dirname(__file__),
            'templates',
            template_name
        )
        
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _render_alert_section(self, alerts: List[Alert], priority_label: str, 
                             priority_color: str, priority_emoji: str) -> str:
        """
        Render section of alerts with same priority
        
        Args:
            alerts: List of alerts
            priority_label: Label (e.g., "CRITICAL ALERTS")
            priority_color: Color code
            priority_emoji: Emoji for priority
            
        Returns:
            HTML string for section
        """
        if not alerts:
            return ""
        
        base_url = self.config.get('app.base_url', 'http://localhost:5001')
        
        html = f"""
        <div style="margin-bottom: 30px;">
            <div style="background: {priority_color}22; border-left: 4px solid {priority_color}; 
                        padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <h2 style="margin: 0; color: {priority_color}; font-size: 18px;">
                    {priority_emoji} {priority_label} ({len(alerts)})
                </h2>
            </div>
        """
        
        for alert in alerts:
            # Container header
            html += f"""
            <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; 
                        padding: 20px; margin-bottom: 15px; border-left: 4px solid {priority_color};">
                <h3 style="margin: 0 0 10px 0; color: #e2e8f0; font-size: 16px;">
                    {alert.container_name} <span style="color: #64748b; font-size: 14px;">(ID: {alert.container_id[:12]})</span>
                </h3>
            """
            
            # Alert details based on type
            if alert.alert_type == AlertType.UNHEALTHY:
                html += f"""
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Status:</strong> <span style="color: {priority_color};">UNHEALTHY</span>
                </p>
                <p style="margin: 8px 0; color: #94a3b8; font-size: 14px;">
                    ⏰ Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
                </p>
                """
            
            elif alert.alert_type == AlertType.HIGH_CPU:
                threshold = self.config.get_cpu_threshold(alert.container_name)
                html += f"""
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Issue:</strong> High CPU Usage
                </p>
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Current:</strong> <span style="color: {priority_color}; font-size: 18px; font-weight: bold;">{alert.value:.1f}%</span>
                    <span style="color: #64748b;"> (threshold: {threshold}%)</span>
                </p>
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Duration:</strong> {self.config.get('thresholds.duration_minutes', 3)} minutes
                </p>
                """
                
                if alert.history:
                    history_str = " → ".join([f"{h:.1f}%" for h in alert.history])
                    html += f"""
                    <p style="margin: 8px 0; color: #94a3b8; font-size: 13px;">
                        📊 History: {history_str}
                    </p>
                    """
            
            elif alert.alert_type == AlertType.HIGH_RAM:
                threshold = self.config.get_ram_threshold(alert.container_name)
                html += f"""
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Issue:</strong> High RAM Usage
                </p>
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Current:</strong> <span style="color: {priority_color}; font-size: 18px; font-weight: bold;">{alert.value:.1f}%</span>
                    <span style="color: #64748b;"> (threshold: {threshold}%)</span>
                </p>
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Duration:</strong> {self.config.get('thresholds.duration_minutes', 3)} minutes
                </p>
                """
                
                if alert.history:
                    history_str = " → ".join([f"{h:.1f}%" for h in alert.history])
                    html += f"""
                    <p style="margin: 8px 0; color: #94a3b8; font-size: 13px;">
                        📊 History: {history_str}
                    </p>
                    """
            
            # Link to container
            container_url = f"{base_url}/container/{alert.container_id}"
            html += f"""
                <div style="margin-top: 15px;">
                    <a href="{container_url}" 
                       style="display: inline-block; background: #3b82f6; color: white; 
                              padding: 8px 16px; text-decoration: none; border-radius: 6px; 
                              font-size: 14px;">
                        → View Container Details
                    </a>
                </div>
            </div>
            """
        
        html += "</div>"
        return html
    
    def _create_alert_email_html(self, alert_batch: AlertBatch) -> str:
        """
        Create HTML content for aggregate alert email
        
        Args:
            alert_batch: Batch of alerts
            
        Returns:
            HTML string
        """
        # Determine subject based on priorities
        if alert_batch.critical_alerts:
            subject_prefix = "🚨 CRITICAL"
        else:
            subject_prefix = "⚠️ WARNING"
        
        critical_count = len(alert_batch.critical_alerts)
        warning_count = len(alert_batch.warning_alerts)
        
        # Build title
        title_parts = []
        if critical_count > 0:
            title_parts.append(f"{critical_count} Critical Issue{'s' if critical_count != 1 else ''}")
        if warning_count > 0:
            title_parts.append(f"{warning_count} Warning{'s' if warning_count != 1 else ''}")
        
        title = " + ".join(title_parts)
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Docker Watcher Alert</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
             background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #e2e8f0;">
    <div style="max-width: 800px; margin: 0 auto; padding: 40px 20px;">
        
        <!-- Header -->
        <div style="text-align: center; margin-bottom: 40px;">
            <h1 style="color: #3b82f6; font-size: 32px; margin: 0 0 10px 0;">
                Docker Watcher
            </h1>
            <p style="color: #94a3b8; font-size: 16px; margin: 0;">
                Container Monitoring Alert System
            </p>
        </div>
        
        <!-- Alert Title -->
        <div style="background: rgba(239, 68, 68, 0.15); border: 2px solid #ef4444; 
                    border-radius: 12px; padding: 20px; margin-bottom: 30px; text-align: center;">
            <h2 style="margin: 0; color: #ef4444; font-size: 24px;">
                {subject_prefix}: {title}
            </h2>
            <p style="margin: 10px 0 0 0; color: #94a3b8; font-size: 14px;">
                {alert_batch.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>
        
        <!-- Alerts Content -->
        <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid #334155; 
                    border-radius: 12px; padding: 30px;">
        """
        
        # Critical alerts section
        if alert_batch.critical_alerts:
            html += self._render_alert_section(
                alert_batch.critical_alerts,
                "CRITICAL ALERTS",
                "#ef4444",
                "🚨"
            )
        
        # Warning alerts section
        if alert_batch.warning_alerts:
            html += self._render_alert_section(
                alert_batch.warning_alerts,
                "WARNING ALERTS",
                "#f59e0b",
                "⚠️"
            )
        
        # Footer
        base_url = self.config.get('app.base_url', 'http://localhost:5001')
        html += f"""
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; margin-top: 30px; padding-top: 20px; 
                    border-top: 1px solid #334155;">
            <p style="color: #64748b; font-size: 14px; margin: 0 0 10px 0;">
                Docker Watcher Alert System
            </p>
            <a href="{base_url}" 
               style="color: #3b82f6; text-decoration: none; font-size: 14px;">
                → View Full Dashboard
            </a>
        </div>
        
    </div>
</body>
</html>
        """
        
        return html
    
    def _create_recovery_email_html(self, alert: Alert) -> str:
        """
        Create HTML content for recovery email
        
        Args:
            alert: Recovery alert
            
        Returns:
            HTML string
        """
        base_url = self.config.get('app.base_url', 'http://localhost:5001')
        container_url = f"{base_url}/container/{alert.container_id}"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Docker Watcher - Container Recovered</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
             background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #e2e8f0;">
    <div style="max-width: 800px; margin: 0 auto; padding: 40px 20px;">
        
        <!-- Header -->
        <div style="text-align: center; margin-bottom: 40px;">
            <h1 style="color: #3b82f6; font-size: 32px; margin: 0 0 10px 0;">
                Docker Watcher
            </h1>
            <p style="color: #94a3b8; font-size: 16px; margin: 0;">
                Container Monitoring Alert System
            </p>
        </div>
        
        <!-- Recovery Title -->
        <div style="background: rgba(34, 197, 94, 0.15); border: 2px solid #22c55e; 
                    border-radius: 12px; padding: 20px; margin-bottom: 30px; text-align: center;">
            <h2 style="margin: 0; color: #22c55e; font-size: 24px;">
                ✅ RESOLVED: Container Recovered
            </h2>
            <p style="margin: 10px 0 0 0; color: #94a3b8; font-size: 14px;">
                {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            </p>
        </div>
        
        <!-- Recovery Details -->
        <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid #334155; 
                    border-radius: 12px; padding: 30px;">
            
            <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; 
                        padding: 20px; border-left: 4px solid #22c55e;">
                <h3 style="margin: 0 0 15px 0; color: #e2e8f0; font-size: 18px;">
                    {alert.container_name}
                </h3>
                
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Container ID:</strong> <span style="color: #64748b;">{alert.container_id[:12]}</span>
                </p>
                
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Previous Status:</strong> <span style="color: #ef4444;">UNHEALTHY</span>
                </p>
                
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Current Status:</strong> <span style="color: #22c55e;">HEALTHY</span>
                </p>
        """
        
        if alert.downtime:
            html += f"""
                <p style="margin: 8px 0; color: #e2e8f0;">
                    <strong>Downtime:</strong> <span style="color: #f59e0b;">{alert.downtime}</span>
                </p>
            """
        
        html += f"""
                <p style="margin: 8px 0; color: #94a3b8; font-size: 14px;">
                    ⏰ Recovered At: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
                </p>
                
                <div style="margin-top: 20px;">
                    <a href="{container_url}" 
                       style="display: inline-block; background: #22c55e; color: white; 
                              padding: 10px 20px; text-decoration: none; border-radius: 6px; 
                              font-size: 14px; font-weight: 600;">
                        → View Container Details
                    </a>
                </div>
            </div>
            
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; margin-top: 30px; padding-top: 20px; 
                    border-top: 1px solid #334155;">
            <p style="color: #64748b; font-size: 14px; margin: 0 0 10px 0;">
                Docker Watcher Alert System
            </p>
            <a href="{base_url}" 
               style="color: #3b82f6; text-decoration: none; font-size: 14px;">
                → View Full Dashboard
            </a>
        </div>
        
    </div>
</body>
</html>
        """
        
        return html
    
    def _create_plain_text(self, alert_batch: AlertBatch = None, recovery_alert: Alert = None) -> str:
        """
        Create plain text version of email (fallback)
        
        Args:
            alert_batch: Alert batch (for aggregate email)
            recovery_alert: Recovery alert (for recovery email)
            
        Returns:
            Plain text string
        """
        base_url = self.config.get('app.base_url', 'http://localhost:5001')
        
        if recovery_alert:
            text = f"""
Docker Watcher - Container Recovered
=====================================

Container: {recovery_alert.container_name}
ID: {recovery_alert.container_id[:12]}

Previous Status: UNHEALTHY
Current Status: HEALTHY
"""
            if recovery_alert.downtime:
                text += f"Downtime: {recovery_alert.downtime}\n"
            
            text += f"""
Recovered At: {recovery_alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

View Details: {base_url}/container/{recovery_alert.container_id}

---
Docker Watcher Alert System
            """
            return text
        
        if alert_batch:
            # Determine title
            critical_count = len(alert_batch.critical_alerts)
            warning_count = len(alert_batch.warning_alerts)
            
            text = f"""
Docker Watcher - Container Alerts
===================================

Timestamp: {alert_batch.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

"""
            
            if alert_batch.critical_alerts:
                text += f"\nCRITICAL ALERTS ({critical_count})\n"
                text += "=" * 50 + "\n\n"
                
                for alert in alert_batch.critical_alerts:
                    text += f"Container: {alert.container_name} (ID: {alert.container_id[:12]})\n"
                    
                    if alert.alert_type == AlertType.UNHEALTHY:
                        text += f"Status: UNHEALTHY\n"
                    
                    text += f"Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    text += f"Details: {base_url}/container/{alert.container_id}\n\n"
            
            if alert_batch.warning_alerts:
                text += f"\nWARNING ALERTS ({warning_count})\n"
                text += "=" * 50 + "\n\n"
                
                for alert in alert_batch.warning_alerts:
                    text += f"Container: {alert.container_name} (ID: {alert.container_id[:12]})\n"
                    
                    if alert.alert_type == AlertType.HIGH_CPU:
                        text += f"Issue: High CPU Usage\n"
                        text += f"Current: {alert.value:.1f}%\n"
                        if alert.history:
                            history_str = " -> ".join([f"{h:.1f}%" for h in alert.history])
                            text += f"History: {history_str}\n"
                    
                    elif alert.alert_type == AlertType.HIGH_RAM:
                        text += f"Issue: High RAM Usage\n"
                        text += f"Current: {alert.value:.1f}%\n"
                        if alert.history:
                            history_str = " -> ".join([f"{h:.1f}%" for h in alert.history])
                            text += f"History: {history_str}\n"
                    
                    text += f"Details: {base_url}/container/{alert.container_id}\n\n"
            
            text += "\n---\nDocker Watcher Alert System\n"
            text += f"Dashboard: {base_url}\n"
            
            return text
        
        return "Docker Watcher Alert"
    
    def send_alert_email(self, alert_batch: AlertBatch) -> bool:
        """
        Send aggregate alert email
        
        Args:
            alert_batch: Batch of alerts to send
            
        Returns:
            True if email sent successfully
        """
        if not self.config.is_enabled():
            print("⚠️  Alert system disabled in config")
            return False
        
        if not alert_batch.has_alerts():
            return False
        
        try:
            # Get email config
            smtp_server = self.config.get('email.smtp_server')
            smtp_port = self.config.get('email.smtp_port')
            sender_email = self.config.get('email.sender_email')
            sender_password = self.config.get('email.sender_password')
            recipients = self.config.get('email.recipient_emails', [])
            use_tls = self.config.get('email.use_tls', True)
            
            # Determine subject
            if alert_batch.critical_alerts:
                subject_prefix = "🚨 CRITICAL"
                critical_count = len(alert_batch.critical_alerts)
                warning_count = len(alert_batch.warning_alerts)
                
                if warning_count > 0:
                    subject = f"{subject_prefix}: {critical_count} Container Issue{'s' if critical_count != 1 else ''} (+ {warning_count} Warning{'s' if warning_count != 1 else ''})"
                else:
                    subject = f"{subject_prefix}: {critical_count} Container Issue{'s' if critical_count != 1 else ''}"
            else:
                warning_count = len(alert_batch.warning_alerts)
                subject = f"⚠️ WARNING: {warning_count} Resource Alert{'s' if warning_count != 1 else ''}"
            
            # Create email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = sender_email
            msg['To'] = ', '.join(recipients)
            
            # Plain text version
            text_content = self._create_plain_text(alert_batch=alert_batch)
            part1 = MIMEText(text_content, 'plain')
            
            # HTML version
            html_content = self._create_alert_email_html(alert_batch)
            part2 = MIMEText(html_content, 'html')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            
            print(f"✅ Alert email sent successfully to {len(recipients)} recipient(s)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send alert email: {e}")
            return False
    
    def send_recovery_email(self, recovery_alert: Alert) -> bool:
        """
        Send recovery notification email
        
        Args:
            recovery_alert: Recovery alert
            
        Returns:
            True if email sent successfully
        """
        if not self.config.is_enabled():
            return False
        
        if not self.config.get('recovery.send_email', True):
            return False
        
        try:
            # Get email config
            smtp_server = self.config.get('email.smtp_server')
            smtp_port = self.config.get('email.smtp_port')
            sender_email = self.config.get('email.sender_email')
            sender_password = self.config.get('email.sender_password')
            recipients = self.config.get('email.recipient_emails', [])
            use_tls = self.config.get('email.use_tls', True)
            
            subject = f"✅ RESOLVED: {recovery_alert.container_name} Container Recovered"
            
            # Create email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = sender_email
            msg['To'] = ', '.join(recipients)
            
            # Plain text version
            text_content = self._create_plain_text(recovery_alert=recovery_alert)
            part1 = MIMEText(text_content, 'plain')
            
            # HTML version
            html_content = self._create_recovery_email_html(recovery_alert)
            part2 = MIMEText(html_content, 'html')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            
            print(f"✅ Recovery email sent successfully to {len(recipients)} recipient(s)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send recovery email: {e}")
            return False


# Global singleton
_email_sender = None

def get_email_sender() -> EmailSender:
    """
    Get global email sender instance
    
    Returns:
        EmailSender instance
    """
    global _email_sender
    if _email_sender is None:
        _email_sender = EmailSender()
    return _email_sender