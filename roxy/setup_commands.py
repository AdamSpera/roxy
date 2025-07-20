"""Setup command implementation for Roxy CLI."""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel


class SetupManager:
    """Manages the setup process for Roxy application."""
    
    def __init__(self):
        self.console = Console()
        self.base_dir = Path.cwd()
        self.cert_file = self.base_dir / "cert.pem"
        self.key_file = self.base_dir / "key.pem"
    
    def run_setup(self) -> bool:
        """Execute all setup steps with progress feedback."""
        self.console.print(Panel.fit(
            "[bold blue]Roxy Setup Process[/bold blue]",
            subtitle="Initializing port proxy environment"
        ))
        
        setup_steps = [
            ("Checking system dependencies", self._check_system_dependencies),
            ("Generating SSL certificates", self._generate_ssl_certificates),
            ("Verifying Python environment", self._verify_python_environment),
            ("Validating configuration", self._validate_configuration),
        ]
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                
                for description, step_func in setup_steps:
                    task = progress.add_task(description, total=None)
                    
                    try:
                        success, message = step_func()
                        if not success:
                            progress.stop()
                            self.console.print(f"[red]✗ {description} failed: {message}[/red]")
                            return False
                        
                        progress.update(task, completed=True)
                        self.console.print(f"[green]✓ {description} completed[/green]")
                        
                    except Exception as e:
                        progress.stop()
                        self.console.print(f"[red]✗ {description} failed: {str(e)}[/red]")
                        return False
            
            self.console.print("\n[bold green]Setup completed successfully![/bold green]")
            self.console.print("[yellow]Run 'roxy start' to begin using the service.[/yellow]")
            return True
            
        except KeyboardInterrupt:
            self.console.print("\n[red]Setup interrupted by user[/red]")
            return False
    
    def _check_system_dependencies(self) -> Tuple[bool, str]:
        """Check if required system dependencies are available."""
        required_commands = ["openssl"]
        
        for cmd in required_commands:
            if not self._command_exists(cmd):
                return False, f"Required command '{cmd}' not found. Please install OpenSSL."
        
        return True, "System dependencies verified"
    
    def _generate_ssl_certificates(self) -> Tuple[bool, str]:
        """Generate SSL certificates if they don't exist."""
        if self.cert_file.exists() and self.key_file.exists():
            # Verify existing certificates are valid
            if self._validate_ssl_certificates():
                return True, "SSL certificates already exist and are valid"
            else:
                # Remove invalid certificates
                self.cert_file.unlink(missing_ok=True)
                self.key_file.unlink(missing_ok=True)
        
        try:
            # Generate new SSL certificate
            cmd = [
                "openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes",
                "-out", str(self.cert_file),
                "-keyout", str(self.key_file),
                "-days", "365",
                "-subj", "/CN=localhost"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            if not (self.cert_file.exists() and self.key_file.exists()):
                return False, "Certificate files were not created"
            
            return True, "SSL certificates generated successfully"
            
        except subprocess.CalledProcessError as e:
            return False, f"OpenSSL command failed: {e.stderr}"
        except Exception as e:
            return False, f"Certificate generation failed: {str(e)}"
    
    def _verify_python_environment(self) -> Tuple[bool, str]:
        """Verify Python environment and dependencies."""
        try:
            # Check Python version
            if sys.version_info < (3, 8):
                return False, "Python 3.8 or higher is required"
            
            # Check if required packages are available
            required_packages = ["flask", "gunicorn", "click", "rich"]
            missing_packages = []
            
            for package in required_packages:
                try:
                    __import__(package)
                except ImportError:
                    missing_packages.append(package)
            
            if missing_packages:
                return False, f"Missing required packages: {', '.join(missing_packages)}. Install with: pip install {' '.join(missing_packages)}"
            
            return True, "Python environment verified"
            
        except Exception as e:
            return False, f"Python environment check failed: {str(e)}"
    
    def _validate_configuration(self) -> Tuple[bool, str]:
        """Validate the overall configuration."""
        try:
            # Check if port_mappings.json exists, create if not
            mappings_file = self.base_dir / "port_mappings.json"
            if not mappings_file.exists():
                mappings_file.write_text("[]")
            elif mappings_file.stat().st_size == 0:
                # File exists but is empty, initialize it
                mappings_file.write_text("[]")
            
            # Verify SSL certificates one more time
            if not self._validate_ssl_certificates():
                return False, "SSL certificates are invalid"
            
            # Check if we can write to the current directory
            test_file = self.base_dir / ".roxy_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except Exception:
                return False, "Cannot write to current directory"
            
            return True, "Configuration validated"
            
        except Exception as e:
            return False, f"Configuration validation failed: {str(e)}"
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in the system PATH."""
        try:
            subprocess.run(
                ["which", command],
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def _validate_ssl_certificates(self) -> bool:
        """Validate that SSL certificates are properly formatted."""
        if not (self.cert_file.exists() and self.key_file.exists()):
            return False
        
        try:
            # Check certificate validity
            result = subprocess.run(
                ["openssl", "x509", "-in", str(self.cert_file), "-noout", "-text"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Check private key validity
            result = subprocess.run(
                ["openssl", "rsa", "-in", str(self.key_file), "-noout", "-check"],
                capture_output=True,
                text=True,
                check=True
            )
            
            return True
            
        except subprocess.CalledProcessError:
            return False
        except Exception:
            return False