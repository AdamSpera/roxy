"""
Service management for Roxy.
"""

import os
import sys
import signal
import time
import psutil
import json
from pathlib import Path

class ServiceManager:
    """
    Manages the Roxy service lifecycle including starting, stopping, and status checking.
    """
    def __init__(self, pid_file=None, config_dir=None):
        """
        Initialize the ServiceManager.
        
        Args:
            pid_file (str, optional): Path to the PID file. Defaults to ~/.roxy/roxy.pid.
            config_dir (str, optional): Path to the configuration directory. Defaults to ~/.roxy.
        """
        self.config_dir = config_dir or os.path.expanduser('~/.roxy')
        self.pid_file = pid_file or os.path.join(self.config_dir, 'roxy.pid')
        self.first_run_flag = os.path.join(self.config_dir, '.first_run')
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
    
    def start_service(self, server_instance=None):
        """
        Start the Roxy service.
        
        Args:
            server_instance: An instance of ProxyServer to use. If None, a new instance will be created.
            
        Returns:
            int: The PID of the started process.
            
        Raises:
            RuntimeError: If the service is already running.
        """
        # Check if service is already running
        if self.is_running():
            pid = self.get_pid()
            raise RuntimeError(f"Roxy service is already running with PID {pid}")
        
        # If no server instance is provided, we'll need to import and create one
        if server_instance is None:
            from .server import ProxyServer
            server_instance = ProxyServer()
        
        # Fork a child process
        pid = os.fork()
        
        if pid == 0:
            # This is the child process
            try:
                # Detach from parent process
                os.setsid()
                
                # Close file descriptors
                os.close(0)
                os.close(1)
                os.close(2)
                
                # Redirect standard file descriptors
                sys.stdin = open(os.devnull, 'r')
                sys.stdout = open(os.path.join(self.config_dir, 'roxy.log'), 'a+')
                sys.stderr = open(os.path.join(self.config_dir, 'roxy.err'), 'a+')
                
                # Write PID file
                with open(self.pid_file, 'w') as f:
                    f.write(str(os.getpid()))
                
                # Start the server
                server_instance.start()
            except Exception as e:
                # Log any exceptions
                with open(os.path.join(self.config_dir, 'roxy.err'), 'a+') as f:
                    f.write(f"Error starting Roxy service: {str(e)}\n")
                os._exit(1)
        else:
            # This is the parent process
            # Wait a moment to ensure the child process has started
            time.sleep(1)
            
            # Check if the process is actually running
            if not self.is_running():
                raise RuntimeError("Failed to start Roxy service")
            
            return pid
    
    def stop_service(self):
        """
        Stop the Roxy service.
        
        Returns:
            bool: True if the service was stopped, False if it wasn't running.
            
        Raises:
            RuntimeError: If the service couldn't be stopped.
        """
        if not os.path.exists(self.pid_file):
            return False
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if the process exists
            if not psutil.pid_exists(pid):
                # Process doesn't exist, clean up the PID file
                os.remove(self.pid_file)
                return False
            
            # Send SIGTERM to the process
            os.kill(pid, signal.SIGTERM)
            
            # Wait for the process to terminate
            for _ in range(10):  # Wait up to 10 seconds
                if not psutil.pid_exists(pid):
                    break
                time.sleep(1)
            
            # If the process is still running, send SIGKILL
            if psutil.pid_exists(pid):
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            
            # Check if the process is still running
            if psutil.pid_exists(pid):
                raise RuntimeError(f"Failed to stop process with PID {pid}")
            
            # Remove the PID file
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            
            return True
        
        except (IOError, ValueError) as e:
            # Invalid PID file, clean it up
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            return False
        except ProcessLookupError:
            # Process doesn't exist, clean up the PID file
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            return False
    
    def get_pid(self):
        """
        Get the PID of the running service.
        
        Returns:
            int: The PID of the running service, or None if not running.
        """
        if not os.path.exists(self.pid_file):
            return None
        
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except (IOError, ValueError):
            return None
    
    def is_running(self):
        """
        Check if the service is running.
        
        Returns:
            bool: True if the service is running, False otherwise.
        """
        pid = self.get_pid()
        if pid is None:
            return False
        
        # Check if the process exists
        try:
            # Check if the process exists and is running
            process = psutil.Process(pid)
            
            # Check if the process is a Python process (additional validation)
            if 'python' not in process.name().lower():
                return False
            
            return True
        except psutil.NoSuchProcess:
            # Process doesn't exist, clean up the PID file
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            return False
            
    def get_status(self):
        """
        Get the status of the Roxy service.
        
        Returns:
            dict: A dictionary containing status information:
                - running (bool): Whether the service is running
                - pid (int): The PID of the running service, or None if not running
                - uptime (float): The uptime of the service in seconds, or None if not running
                - mappings_count (int): The number of active port mappings
        """
        status = {
            'running': False,
            'pid': None,
            'uptime': None,
            'mappings_count': 0
        }
        
        # Check if the service is running
        pid = self.get_pid()
        if pid is not None and self.is_running():
            status['running'] = True
            status['pid'] = pid
            
            # Get process information
            try:
                process = psutil.Process(pid)
                status['uptime'] = time.time() - process.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Get the number of active port mappings
        mapping_file = os.path.join(self.config_dir, 'port_mappings.json')
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r') as f:
                    mappings = json.load(f)
                    status['mappings_count'] = len(mappings)
            except (json.JSONDecodeError, IOError):
                pass
        
        return status
        
    def is_first_run(self):
        """
        Check if this is the first time running the service.
        
        Returns:
            bool: True if this is the first run, False otherwise.
        """
        # Check if the first run flag file exists
        if os.path.exists(self.first_run_flag):
            return False
        
        # Check if the port mappings file exists
        mapping_file = os.path.join(self.config_dir, 'port_mappings.json')
        if os.path.exists(mapping_file):
            # If mappings exist, it's not the first run
            return False
        
        # Check if any SSL certificates exist
        ssl_cert = os.path.join(self.config_dir, 'cert.pem')
        ssl_key = os.path.join(self.config_dir, 'key.pem')
        if os.path.exists(ssl_cert) and os.path.exists(ssl_key):
            # If SSL certificates exist, it's not the first run
            return False
        
        # This is the first run
        return True
    
    def mark_first_run_complete(self):
        """
        Mark the first run as complete by creating the first run flag file.
        """
        # Create the first run flag file
        Path(self.first_run_flag).touch()
        
    def reset_first_run(self):
        """
        Reset the first run flag, useful for testing or resetting the application.
        """
        # Remove the first run flag file if it exists
        if os.path.exists(self.first_run_flag):
            os.remove(self.first_run_flag)
            
    def get_log_path(self):
        """
        Get the path to the log file.
        
        Returns:
            str: The path to the log file.
        """
        return os.path.join(self.config_dir, 'roxy.log')
    
    def get_error_log_path(self):
        """
        Get the path to the error log file.
        
        Returns:
            str: The path to the error log file.
        """
        return os.path.join(self.config_dir, 'roxy.err')
    
    def clear_logs(self):
        """
        Clear the log files.
        """
        # Clear the log file
        log_path = self.get_log_path()
        if os.path.exists(log_path):
            with open(log_path, 'w') as f:
                f.write('')
        
        # Clear the error log file
        error_log_path = self.get_error_log_path()
        if os.path.exists(error_log_path):
            with open(error_log_path, 'w') as f:
                f.write('')