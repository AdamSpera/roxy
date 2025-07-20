"""
Roxy CLI - Command line interface for the Roxy port proxy tool
"""

import sys
import click
from rich.console import Console
from rich.text import Text
from rich.panel import Panel

# Initialize rich console for colored output
console = Console()


def display_error(message: str):
    """Display error message with red coloring"""
    error_text = Text(f"Error: {message}", style="bold red")
    console.print(error_text)


def display_success(message: str):
    """Display success message with green coloring"""
    success_text = Text(message, style="bold green")
    console.print(success_text)


def display_info(message: str):
    """Display informational message with blue coloring"""
    info_text = Text(message, style="bold blue")
    console.print(info_text)


def display_help_header():
    """Display styled help header"""
    header = Text("Roxy - Port Proxy Management Tool", style="bold cyan")
    console.print(Panel(header, style="cyan"))


@click.group(invoke_without_command=True, context_settings={'help_option_names': ['-h', '--help']})
@click.pass_context
def cli(ctx):
    """Roxy - Port proxy management tool
    
    A command-line interface for managing the Roxy port proxy service.
    Use 'roxy COMMAND --help' for more information on a specific command.
    """
    if ctx.invoked_subcommand is None:
        # Display help when no command is provided
        display_help_header()
        console.print()
        console.print("Available commands:", style="bold")
        console.print("  setup   - Run initial setup steps")
        console.print("  start   - Start the Roxy service")
        console.print("  stop    - Stop the Roxy service")
        console.print("  status  - Show service status")
        console.print("  show    - Display current port mappings")
        console.print()
        console.print("Use 'roxy --help' for detailed help information.")
        console.print("Use 'roxy COMMAND --help' for help on a specific command.")


@cli.command()
def setup():
    """Run initial setup steps
    
    Executes all necessary setup steps to prepare Roxy for use,
    including SSL certificate generation and dependency checks.
    """
    from .setup_commands import SetupManager
    
    try:
        setup_manager = SetupManager()
        success = setup_manager.run_setup()
        
        if not success:
            display_error("Setup process failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        display_error("Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        display_error(f"Setup failed with unexpected error: {str(e)}")
        sys.exit(1)


@cli.command()
def start():
    """Start the Roxy service
    
    Starts the Gunicorn server with SSL configuration.
    The service will run in the background.
    """
    from .service import RoxyService
    
    try:
        service = RoxyService()
        
        # Check if service is already running
        if service.is_running():
            display_info("Roxy service is already running")
            status_info = service.status()
            if status_info.pid:
                display_info(f"Process ID: {status_info.pid}")
                display_info(f"Port: {status_info.port}")
            return
        
        display_info("Starting Roxy service...")
        
        # Attempt to start the service
        if service.start():
            display_success("✓ Roxy service started successfully!")
            status_info = service.status()
            if status_info.pid:
                display_success(f"Process ID: {status_info.pid}")
                display_success(f"Listening on port: {status_info.port}")
                display_info("Service is running in the background")
        else:
            display_error("Failed to start Roxy service")
            
            # Provide troubleshooting information
            display_info("\nTroubleshooting:")
            
            # Check SSL certificates
            from pathlib import Path
            cert_path = Path("roxy/cert.pem")
            key_path = Path("roxy/key.pem")
            
            if not cert_path.exists():
                display_error("• SSL certificate (cert.pem) not found")
                display_info("  Run 'roxy setup' to generate SSL certificates")
            elif not key_path.exists():
                display_error("• SSL private key (key.pem) not found")
                display_info("  Run 'roxy setup' to generate SSL certificates")
            else:
                display_info("• SSL certificates appear to be present")
            
            # Check if gunicorn is installed
            import shutil
            if not shutil.which("gunicorn"):
                display_error("• Gunicorn is not installed or not in PATH")
                display_info("  Install with: pip install gunicorn")
            else:
                display_info("• Gunicorn appears to be installed")
            
            # Check port availability
            import socket
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', 443))
            except OSError:
                display_error("• Port 443 may already be in use")
                display_info("  Check for other services using: sudo lsof -i :443")
            else:
                display_info("• Port 443 appears to be available")
            
            sys.exit(1)
            
    except KeyboardInterrupt:
        display_error("Start command interrupted by user")
        sys.exit(1)
    except Exception as e:
        display_error(f"Failed to start service: {str(e)}")
        display_info("Run 'roxy setup' if you haven't already")
        sys.exit(1)


@cli.command()
def stop():
    """Stop the Roxy service
    
    Gracefully stops the running Roxy service.
    """
    from .service import RoxyService
    
    try:
        service = RoxyService()
        
        # Check if service is running
        if not service.is_running():
            display_info("Roxy service is not currently running")
            return
        
        display_info("Stopping Roxy service...")
        
        # Get current status before stopping
        status_info = service.status()
        current_pid = status_info.pid
        
        # Attempt to stop the service
        if service.stop():
            display_success("✓ Roxy service stopped successfully!")
            if current_pid:
                display_success(f"Process {current_pid} terminated gracefully")
            display_info("Service is no longer running")
        else:
            display_error("Failed to stop Roxy service")
            
            # Provide troubleshooting information
            display_info("\nTroubleshooting:")
            display_info("• Check if you have permission to terminate the process")
            display_info("• The process may have already stopped")
            display_info("• Try running 'roxy status' to check current state")
            
            # Check if PID file still exists
            from pathlib import Path
            pid_file = Path("roxy.pid")
            if pid_file.exists():
                display_info("• PID file still exists, you may need to remove it manually")
                display_info(f"  Remove with: rm {pid_file}")
            
            sys.exit(1)
            
    except KeyboardInterrupt:
        display_error("Stop command interrupted by user")
        sys.exit(1)
    except Exception as e:
        display_error(f"Failed to stop service: {str(e)}")
        display_info("Try running 'roxy status' to check the current state")
        sys.exit(1)


@cli.command()
def status():
    """Show service status
    
    Displays the current status of the Roxy service,
    including process information and connection details.
    """
    from .service import RoxyService
    
    try:
        service = RoxyService()
        status_info = service.status()
        
        # Display header
        console.print()
        console.print("Roxy Service Status", style="bold cyan")
        console.print("=" * 20, style="cyan")
        
        if status_info.running:
            # Service is running - display with green/success colors
            display_success("✓ Service is RUNNING")
            console.print()
            
            # Process information
            if status_info.pid:
                console.print(f"Process ID: {status_info.pid}", style="bold")
            
            if status_info.port:
                console.print(f"Port: {status_info.port}", style="bold")
                console.print(f"Listening on: https://0.0.0.0:{status_info.port}", style="bold blue")
            
            if status_info.uptime:
                console.print(f"Uptime: {status_info.uptime}", style="bold")
            
            # Resource usage information
            if status_info.memory_usage is not None:
                console.print(f"Memory Usage: {status_info.memory_usage:.1f} MB", style="bold")
            
            if status_info.cpu_percent is not None:
                console.print(f"CPU Usage: {status_info.cpu_percent:.1f}%", style="bold")
            
            # Connection information
            console.print(f"Active Connections: {status_info.connections}", style="bold")
            
            # Additional connection info
            console.print()
            display_info("Connection Information:")
            console.print("• HTTPS endpoint: https://localhost:443", style="blue")
            console.print("• SSL certificates: cert.pem, key.pem", style="blue")
            
        else:
            # Service is not running - display with red/error colors
            display_error("✗ Service is STOPPED")
            console.print()
            display_info("The Roxy service is not currently running.")
            display_info("Use 'roxy start' to start the service.")
            
            # Check for common issues
            from pathlib import Path
            cert_path = Path("roxy/cert.pem")
            key_path = Path("roxy/key.pem")
            
            if not cert_path.exists() or not key_path.exists():
                console.print()
                display_info("Note: SSL certificates not found.")
                display_info("Run 'roxy setup' to generate certificates before starting.")
        
        console.print()
        
    except KeyboardInterrupt:
        display_error("Status check interrupted by user")
        sys.exit(1)
    except Exception as e:
        display_error(f"Failed to check service status: {str(e)}")
        display_info("There may be an issue with the service configuration.")
        sys.exit(1)


@cli.command()
def show():
    """Display current port mappings
    
    Shows all configured port mappings in a formatted table.
    """
    from .display import load_and_display_port_mappings
    
    try:
        load_and_display_port_mappings()
        
    except KeyboardInterrupt:
        display_error("Show command interrupted by user")
        sys.exit(1)
    except Exception as e:
        display_error(f"Failed to display port mappings: {str(e)}")
        display_info("There may be an issue reading the port mappings file.")
        sys.exit(1)


# Error handling for CLI
def handle_cli_error(exception):
    """Handle CLI errors with colored output"""
    if isinstance(exception, click.ClickException):
        display_error(str(exception))
        sys.exit(1)
    else:
        display_error(f"Unexpected error: {str(exception)}")
        sys.exit(1)


# Override click's exception handling
click.ClickException.show = lambda self, file=None: display_error(self.format_message())


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        handle_cli_error(e)