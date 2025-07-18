"""
Setup functionality for Roxy.
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path
import click

class SetupManager:
    """
    Manages the setup process for Roxy, including SSL certificate generation and dependency checking.
    """
    def __init__(self, config_dir=None):
        """
        Initialize the SetupManager.
        
        Args:
            config_dir (str, optional): Path to the configuration directory. Defaults to ~/.roxy.
        """
        self.config_dir = config_dir or os.path.expanduser('~/.roxy')
        self.ssl_cert = os.path.join(self.config_dir, 'cert.pem')
        self.ssl_key = os.path.join(self.config_dir, 'key.pem')
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
    
    def run_setup(self):
        """
        Run the complete setup process.
        
        Returns:
            bool: True if setup was successful, False otherwise.
        """
        click.echo("Starting Roxy setup...")
        
        # Check dependencies
        if not self.check_dependencies():
            click.echo("Failed to verify all dependencies.")
            if not click.confirm("Continue anyway?", default=False):
                return False
        
        # Generate SSL certificates
        if not self.generate_ssl_certificates():
            click.echo("Failed to generate SSL certificates.")
            if not click.confirm("Continue anyway?", default=False):
                return False
        
        # Mark setup as complete
        from .service import ServiceManager
        service_manager = ServiceManager(config_dir=self.config_dir)
        service_manager.mark_first_run_complete()
        
        click.echo("Setup completed successfully!")
        click.echo(f"Configuration directory: {self.config_dir}")
        click.echo(f"SSL certificate: {self.ssl_cert}")
        click.echo(f"SSL key: {self.ssl_key}")
        click.echo("\nYou can now start Roxy with 'roxy start'")
        
        return True
    
    def check_dependencies(self):
        """
        Check if all required dependencies are installed.
        
        Returns:
            bool: True if all dependencies are installed, False otherwise.
        """
        click.echo("Checking dependencies...")
        
        dependencies = {
            'openssl': self._check_openssl,
            'python_packages': self._check_python_packages
        }
        
        all_dependencies_met = True
        
        for name, check_func in dependencies.items():
            click.echo(f"Checking {name}...")
            if check_func():
                click.echo(f"✓ {name} is available")
            else:
                click.echo(f"✗ {name} is missing or not properly configured")
                all_dependencies_met = False
        
        return all_dependencies_met
    
    def _check_openssl(self):
        """
        Check if OpenSSL is installed and available.
        
        Returns:
            bool: True if OpenSSL is available, False otherwise.
        """
        try:
            result = subprocess.run(
                ['openssl', 'version'], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                click.echo(f"  Found OpenSSL: {result.stdout.strip()}")
                return True
            else:
                click.echo(f"  OpenSSL check failed: {result.stderr.strip()}")
                return False
        except FileNotFoundError:
            click.echo("  OpenSSL not found. Please install OpenSSL.")
            self._suggest_openssl_installation()
            return False
        except Exception as e:
            click.echo(f"  Error checking OpenSSL: {str(e)}")
            return False
    
    def _suggest_openssl_installation(self):
        """
        Suggest how to install OpenSSL based on the platform.
        """
        system = platform.system().lower()
        
        if system == 'darwin':
            click.echo("  Suggestion: Install OpenSSL using Homebrew:")
            click.echo("    brew install openssl")
        elif system == 'linux':
            click.echo("  Suggestion: Install OpenSSL using your package manager:")
            click.echo("    Ubuntu/Debian: sudo apt-get install openssl")
            click.echo("    CentOS/RHEL: sudo yum install openssl")
            click.echo("    Fedora: sudo dnf install openssl")
        elif system == 'windows':
            click.echo("  Suggestion: Install OpenSSL from https://slproweb.com/products/Win32OpenSSL.html")
        else:
            click.echo("  Please install OpenSSL for your platform.")
    
    def _check_python_packages(self):
        """
        Check if all required Python packages are installed.
        
        Returns:
            bool: True if all required packages are installed, False otherwise.
        """
        required_packages = ['flask', 'click', 'tabulate', 'psutil']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            click.echo(f"  Missing Python packages: {', '.join(missing_packages)}")
            click.echo("  Install missing packages with:")
            click.echo(f"    pip install {' '.join(missing_packages)}")
            return False
        
        return True
    
    def generate_ssl_certificates(self):
        """
        Generate self-signed SSL certificates for HTTPS support.
        
        Returns:
            bool: True if certificates were generated successfully, False otherwise.
        """
        click.echo("Generating SSL certificates...")
        
        # Check if certificates already exist
        if os.path.exists(self.ssl_cert) and os.path.exists(self.ssl_key):
            if click.confirm("SSL certificates already exist. Regenerate?", default=False):
                # Backup existing certificates
                backup_dir = os.path.join(self.config_dir, 'backup')
                os.makedirs(backup_dir, exist_ok=True)
                
                try:
                    shutil.copy2(self.ssl_cert, os.path.join(backup_dir, 'cert.pem.bak'))
                    shutil.copy2(self.ssl_key, os.path.join(backup_dir, 'key.pem.bak'))
                    click.echo("Existing certificates backed up.")
                except Exception as e:
                    click.echo(f"Warning: Failed to backup existing certificates: {str(e)}")
            else:
                click.echo("Using existing SSL certificates.")
                return True
        
        try:
            # Generate a new private key
            key_cmd = [
                'openssl', 'genrsa',
                '-out', self.ssl_key,
                '2048'
            ]
            
            result = subprocess.run(
                key_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                click.echo(f"Failed to generate private key: {result.stderr}")
                return False
            
            # Generate a self-signed certificate
            cert_cmd = [
                'openssl', 'req',
                '-new',
                '-key', self.ssl_key,
                '-out', os.path.join(self.config_dir, 'cert.csr'),
                '-subj', '/CN=localhost'
            ]
            
            result = subprocess.run(
                cert_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                click.echo(f"Failed to generate certificate request: {result.stderr}")
                return False
            
            # Sign the certificate
            sign_cmd = [
                'openssl', 'x509',
                '-req',
                '-days', '365',
                '-in', os.path.join(self.config_dir, 'cert.csr'),
                '-signkey', self.ssl_key,
                '-out', self.ssl_cert
            ]
            
            result = subprocess.run(
                sign_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                click.echo(f"Failed to sign certificate: {result.stderr}")
                return False
            
            # Clean up the CSR file
            csr_file = os.path.join(self.config_dir, 'cert.csr')
            if os.path.exists(csr_file):
                os.remove(csr_file)
            
            click.echo("SSL certificates generated successfully.")
            return True
            
        except Exception as e:
            click.echo(f"Error generating SSL certificates: {str(e)}")
            return False