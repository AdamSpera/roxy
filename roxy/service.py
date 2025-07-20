"""
Service management utilities for Roxy
"""

import os
import signal
import subprocess
import psutil
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class ServiceConfig:
    """Configuration for the Roxy service"""
    host: str = "0.0.0.0"
    port: int = 8443
    workers: int = 4
    cert_file: str = "cert.pem"
    key_file: str = "key.pem"
    app_module: str = "roxy.server:app"
    pid_file: str = "roxy.pid"


@dataclass
class ServiceStatus:
    """Status information for the Roxy service"""
    running: bool
    pid: Optional[int] = None
    port: Optional[int] = None
    uptime: Optional[str] = None
    connections: int = 0
    memory_usage: Optional[float] = None
    cpu_percent: Optional[float] = None


class RoxyService:
    """Service management class for Roxy port proxy"""
    
    def __init__(self, config: Optional[ServiceConfig] = None):
        """Initialize the service manager with configuration"""
        self.config = config or ServiceConfig()
        self.pid_file_path = Path(self.config.pid_file)
        
    def start(self) -> bool:
        """Start the Gunicorn server
        
        Returns:
            bool: True if service started successfully, False otherwise
        """
        if self.is_running():
            return False  # Service already running
            
        # Validate SSL certificates exist
        if not self._validate_ssl_certificates():
            return False
            
        try:
            # Build gunicorn command
            cmd = [
                "gunicorn",
                "-w", str(self.config.workers),
                "-b", f"{self.config.host}:{self.config.port}",
                "--certfile", self.config.cert_file,
                "--keyfile", self.config.key_file,
                "--daemon",  # Run as daemon
                "--pid", self.config.pid_file,
                self.config.app_module
            ]
            
            # Start the process
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Give the process a moment to start
                import time
                time.sleep(1)
                return self.is_running()
            else:
                return False
                
        except Exception:
            return False
    
    def stop(self) -> bool:
        """Stop the Gunicorn server
        
        Returns:
            bool: True if service stopped successfully, False otherwise
        """
        if not self.is_running():
            return False  # Service not running
            
        try:
            pid = self._get_pid_from_file()
            if pid:
                # Try graceful shutdown first
                os.kill(pid, signal.SIGTERM)
                
                # Wait for process to terminate
                import time
                for _ in range(10):  # Wait up to 10 seconds
                    if not self._is_process_running(pid):
                        break
                    time.sleep(1)
                
                # If still running, force kill
                if self._is_process_running(pid):
                    os.kill(pid, signal.SIGKILL)
                    time.sleep(1)
                
                # Clean up PID file
                self._cleanup_pid_file()
                return not self.is_running()
                
        except (ProcessLookupError, PermissionError):
            # Process already dead or no permission
            self._cleanup_pid_file()
            return True
        except Exception:
            return False
            
        return False
    
    def status(self) -> ServiceStatus:
        """Get current service status
        
        Returns:
            ServiceStatus: Current status information
        """
        if not self.is_running():
            return ServiceStatus(running=False)
            
        pid = self._get_pid_from_file()
        if not pid:
            return ServiceStatus(running=False)
            
        try:
            process = psutil.Process(pid)
            
            # Get process information
            create_time = process.create_time()
            uptime = self._format_uptime(create_time)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024  # Convert to MB
            cpu_percent = process.cpu_percent()
            
            # Count connections (approximate)
            connections = len(process.connections())
            
            return ServiceStatus(
                running=True,
                pid=pid,
                port=self.config.port,
                uptime=uptime,
                connections=connections,
                memory_usage=memory_mb,
                cpu_percent=cpu_percent
            )
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process doesn't exist or no access
            self._cleanup_pid_file()
            return ServiceStatus(running=False)
    
    def is_running(self) -> bool:
        """Check if the Gunicorn service is currently running
        
        Returns:
            bool: True if service is running, False otherwise
        """
        pid = self._get_pid_from_file()
        if not pid:
            return False
            
        return self._is_process_running(pid)
    
    def _get_pid_from_file(self) -> Optional[int]:
        """Read PID from the PID file
        
        Returns:
            Optional[int]: PID if found and valid, None otherwise
        """
        try:
            if self.pid_file_path.exists():
                with open(self.pid_file_path, 'r') as f:
                    pid_str = f.read().strip()
                    if pid_str.isdigit():
                        return int(pid_str)
        except (IOError, ValueError):
            pass
        return None
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running
        
        Args:
            pid: Process ID to check
            
        Returns:
            bool: True if process is running, False otherwise
        """
        try:
            # Check if process exists and is a gunicorn process
            process = psutil.Process(pid)
            cmdline = ' '.join(process.cmdline())
            return 'gunicorn' in cmdline.lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def _cleanup_pid_file(self):
        """Remove the PID file if it exists"""
        try:
            if self.pid_file_path.exists():
                self.pid_file_path.unlink()
        except OSError:
            pass
    
    def _validate_ssl_certificates(self) -> bool:
        """Validate that SSL certificates exist and are readable
        
        Returns:
            bool: True if certificates are valid, False otherwise
        """
        cert_path = Path(self.config.cert_file)
        key_path = Path(self.config.key_file)
        
        return (cert_path.exists() and cert_path.is_file() and
                key_path.exists() and key_path.is_file())
    
    def _format_uptime(self, create_time: float) -> str:
        """Format process uptime in human-readable format
        
        Args:
            create_time: Process creation timestamp
            
        Returns:
            str: Formatted uptime string
        """
        import time
        uptime_seconds = int(time.time() - create_time)
        
        if uptime_seconds < 60:
            return f"{uptime_seconds}s"
        elif uptime_seconds < 3600:
            minutes = uptime_seconds // 60
            seconds = uptime_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def get_port_mappings(self) -> Dict[str, Any]:
        """Read and return current port mappings
        
        Returns:
            Dict: Port mappings data or empty dict if file doesn't exist
        """
        mappings_file = Path("port_mappings.json")
        try:
            if mappings_file.exists():
                with open(mappings_file, 'r') as f:
                    return json.load(f)
        except (IOError, json.JSONDecodeError):
            pass
        return {}