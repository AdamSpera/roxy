"""
Command-line interface for Roxy.
"""

import os
import sys
import json
import logging
import traceback
import click
from tabulate import tabulate
from .server import ProxyServer, RoxyServerError, PortInUseError, PermissionError, ConnectionError, ConfigError
from .service import ServiceManager
from .setup import SetupManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('roxy.cli')

class CliError(Exception):
    """Base exception class for CLI errors."""
    def __init__(self, message, error_code=None, suggestion=None):
        self.message = message
        self.error_code = error_code
        self.suggestion = suggestion
        super().__init__(self.format_message())
        
    def format_message(self):
        """Format the error message with code and suggestion if available."""
        msg = self.message
        if self.error_code:
            msg = f"[Error {self.error_code}] {msg}"
        if self.suggestion:
            msg = f"{msg}\nSuggestion: {self.suggestion}"
        return msg

def handle_error(func):
    """Decorator to handle errors in CLI commands."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RoxyServerError as e:
            # Server errors are already formatted with suggestions
            click.echo(f"Error: {str(e)}", err=True)
            sys.exit(1)
        except CliError as e:
            # CLI errors are already formatted with suggestions
            click.echo(f"Error: {str(e)}", err=True)
            sys.exit(1)
        except json.JSONDecodeError:
            click.echo("Error: Invalid JSON format in configuration file.", err=True)
            click.echo("Suggestion: Check the file format or delete it to start with a clean configuration.", err=True)
            sys.exit(1)
        except PermissionError as e:
            click.echo(f"Error: Permission denied: {str(e)}", err=True)
            click.echo("Suggestion: Check file permissions or run with elevated privileges.", err=True)
            sys.exit(1)
        except FileNotFoundError as e:
            click.echo(f"Error: File not found: {str(e)}", err=True)
            click.echo("Suggestion: Check the file path and try again.", err=True)
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            logger.debug(traceback.format_exc())
            click.echo(f"Error: {str(e)}", err=True)
            click.echo("Suggestion: Check the logs for more details or report this issue.", err=True)
            sys.exit(1)
    return wrapper

@click.group()
def cli():
    """Roxy: Lightweight proxy tool for HTTP/S, SSH, & Telnet."""
    pass

@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind the web interface to.')
@click.option('--web-port', default=5000, type=int, help='Port to bind the web interface to.')
@handle_error
def start(host, web_port):
    """Start the Roxy proxy server."""
    service_manager = ServiceManager()
    
    # Check if this is the first run
    if service_manager.is_first_run():
        click.echo("It looks like this is your first time running Roxy.")
        if click.confirm("Would you like to run the setup process first?", default=True):
            click.echo("Please run 'roxy setup' to set up Roxy.")
            return
        else:
            # Mark first run as complete to avoid prompting again
            try:
                service_manager.mark_first_run_complete()
            except Exception as e:
                raise CliError(
                    f"Failed to mark first run as complete: {str(e)}",
                    error_code="FIRST_RUN_ERROR",
                    suggestion="Check file permissions in your home directory."
                )
    
    # Check if the service is already running
    if service_manager.is_running():
        pid = service_manager.get_pid()
        click.echo(f"Roxy is already running with PID {pid}.")
        return
    
    # Validate port range
    if web_port < 1 or web_port > 65535:
        raise CliError(
            f"Invalid web port: {web_port}",
            error_code="INVALID_PORT",
            suggestion="Port must be between 1 and 65535."
        )
    
    # Start the service
    try:
        pid = service_manager.start_service()
        click.echo(f"Roxy started successfully with PID {pid}.")
        click.echo(f"Web interface available at: http://{host}:{web_port}")
        click.echo("Use 'roxy status' to check the status of the server.")
    except PortInUseError as e:
        # This is already handled by the decorator, but we can add more specific suggestions
        raise CliError(
            f"Port {web_port} is already in use",
            error_code="PORT_IN_USE",
            suggestion=f"Try using a different port with --web-port or stop the process using port {web_port}."
        )
    except PermissionError as e:
        # This is already handled by the decorator, but we can add more specific suggestions
        raise CliError(
            f"Permission denied when binding to port {web_port}",
            error_code="PERMISSION_DENIED",
            suggestion="Try running with sudo or use a port > 1024."
        )

@cli.command()
@handle_error
def stop():
    """Stop the Roxy proxy server."""
    service_manager = ServiceManager()
    
    # Check if the service is running
    if not service_manager.is_running():
        click.echo("Roxy is not running.")
        return
    
    # Get the PID before stopping for the confirmation message
    try:
        pid = service_manager.get_pid()
        
        # Stop the service
        if service_manager.stop_service():
            click.echo(f"Roxy (PID {pid}) stopped successfully.")
            click.echo("All proxy mappings have been terminated.")
        else:
            raise CliError(
                "Failed to stop Roxy service",
                error_code="STOP_FAILED",
                suggestion="Check if the process is still running with 'ps aux | grep roxy' and kill it manually if needed."
            )
    except FileNotFoundError:
        raise CliError(
            "PID file not found",
            error_code="PID_NOT_FOUND",
            suggestion="The service may have been stopped abnormally. Check for running processes with 'ps aux | grep roxy'."
        )

@cli.command()
@handle_error
def status():
    """Check the status of the Roxy proxy server."""
    service_manager = ServiceManager()
    try:
        status = service_manager.get_status()
    except Exception as e:
        raise CliError(
            f"Failed to get Roxy status: {str(e)}",
            error_code="STATUS_ERROR",
            suggestion="Check if the service is running properly."
        )
    
    if status['running']:
        click.echo(f"Roxy is running with PID {status['pid']}.")
        
        # Format uptime in a human-readable way
        if status['uptime'] is not None:
            uptime_seconds = int(status['uptime'])
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            uptime_parts = []
            if days > 0:
                uptime_parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours > 0:
                uptime_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes > 0:
                uptime_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            if seconds > 0 or not uptime_parts:
                uptime_parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                
            uptime_str = ", ".join(uptime_parts)
            click.echo(f"Uptime: {uptime_str}")
        
        # Show active mappings count
        click.echo(f"Active port mappings: {status['mappings_count']}")
        
        # Show log file locations
        click.echo(f"Log file: {service_manager.get_log_path()}")
        click.echo(f"Error log file: {service_manager.get_error_log_path()}")
        
        # Provide hint for more detailed information
        click.echo("\nUse 'roxy show' to see all active port mappings.")
    else:
        click.echo("Roxy is not running.")
        
        # Check if there are mappings configured even though the service is not running
        if status['mappings_count'] > 0:
            click.echo(f"There are {status['mappings_count']} port mappings configured.")
            click.echo("Use 'roxy start' to start the server and activate these mappings.")
        else:
            click.echo("No port mappings are configured.")
            click.echo("Use 'roxy start' to start the server, then access the web interface to create mappings.")

@cli.command()
@handle_error
def show():
    """Display a formatted table of all proxy mappings."""
    service_manager = ServiceManager()
    config_dir = service_manager.config_dir
    mapping_file = os.path.join(config_dir, 'port_mappings.json')
    
    # Check if the mapping file exists
    if not os.path.exists(mapping_file):
        click.echo("No port mappings found.")
        click.echo("Use the web interface to create mappings.")
        return
    
    try:
        # Load the mappings
        with open(mapping_file, 'r') as f:
            raw_mappings = json.load(f)
        
        # Check if there are any mappings
        if not raw_mappings:
            click.echo("No port mappings found.")
            click.echo("Use the web interface to create mappings.")
            return
        
        # Convert the mappings to a list of tuples for tabulate
        table_data = []
        for key, port in raw_mappings.items():
            # Split the key into IP and protocol
            parts = key.split('|')
            if len(parts) == 2:
                ip, protocol = parts
                # Get the default port for the protocol
                server = ProxyServer()
                default_port = server.protocol_ports.get(protocol, 'N/A')
                table_data.append([ip, protocol, default_port, port])
        
        # Sort the table by external port
        table_data.sort(key=lambda x: x[3])
        
        # Display the table
        headers = ["IP Address", "Protocol", "Internal Port", "External Port"]
        click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Show status information
        is_running = service_manager.is_running()
        status_msg = "Roxy is running" if is_running else "Roxy is not running"
        click.echo(f"\n{status_msg}. {len(table_data)} port mapping{'s' if len(table_data) != 1 else ''} configured.")
        
        # Show hints
        if not is_running:
            click.echo("Use 'roxy start' to start the server and activate these mappings.")
        
    except json.JSONDecodeError:
        raise CliError(
            "The port mappings file is corrupted",
            error_code="INVALID_JSON",
            suggestion="You may need to delete it and recreate your mappings using the web interface."
        )
    except PermissionError:
        raise CliError(
            f"Permission denied when reading {mapping_file}",
            error_code="PERMISSION_DENIED",
            suggestion="Check file permissions or run with elevated privileges."
        )

@cli.command()
@click.argument('config_file', type=click.Path(exists=True, readable=True))
@handle_error
def load(config_file):
    """Load proxy mappings from a file."""
    service_manager = ServiceManager()
    config_dir = service_manager.config_dir
    mapping_file = os.path.join(config_dir, 'port_mappings.json')
    
    try:
        # Load mappings from the specified file
        with open(config_file, 'r') as f:
            new_mappings = json.load(f)
        
        # Validate the mappings
        if not isinstance(new_mappings, dict):
            raise CliError(
                f"Invalid format in {config_file}",
                error_code="INVALID_FORMAT",
                suggestion="The file must contain a JSON object with mapping keys and port values."
            )
        
        # Check if the mappings are in the correct format
        valid_mappings = {}
        invalid_count = 0
        server = ProxyServer()
        
        for key, value in new_mappings.items():
            # Check if the key contains the delimiter
            if '|' in key:
                parts = key.split('|')
                if len(parts) == 2:
                    ip, protocol = parts
                    # Validate IP and protocol if needed
                    if not isinstance(value, int):
                        invalid_count += 1
                        continue
                    valid_mappings[key] = value
                else:
                    invalid_count += 1
            else:
                invalid_count += 1
        
        if invalid_count > 0:
            click.echo(f"Warning: {invalid_count} invalid mappings were skipped.")
        
        if not valid_mappings:
            raise CliError(
                "No valid mappings found in the file",
                error_code="NO_VALID_MAPPINGS",
                suggestion="Check that the file contains mappings in the format 'ip|protocol': port."
            )
        
        # Save the valid mappings
        try:
            os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
            with open(mapping_file, 'w') as f:
                json.dump(valid_mappings, f)
        except PermissionError:
            raise CliError(
                f"Permission denied when writing to {mapping_file}",
                error_code="PERMISSION_DENIED",
                suggestion="Check file permissions or run with elevated privileges."
            )
        except Exception as e:
            raise CliError(
                f"Failed to save mappings: {str(e)}",
                error_code="SAVE_ERROR",
                suggestion="Check file system permissions and available disk space."
            )
        
        click.echo(f"Loaded {len(valid_mappings)} port mappings from {config_file}.")
        
        # Check if server is running and offer to restart
        if service_manager.is_running():
            if click.confirm("Roxy is running. Would you like to restart it to apply the changes?", default=True):
                try:
                    pid = service_manager.get_pid()
                    service_manager.stop_service()
                    new_pid = service_manager.start_service()
                    click.echo(f"Roxy restarted successfully (PID {new_pid}).")
                except Exception as e:
                    raise CliError(
                        f"Failed to restart Roxy: {str(e)}",
                        error_code="RESTART_ERROR",
                        suggestion="Try stopping and starting the service manually with 'roxy stop' and 'roxy start'."
                    )
        else:
            click.echo("Roxy is not running. Start it with 'roxy start' to apply the changes.")
    
    except json.JSONDecodeError:
        raise CliError(
            f"{config_file} is not a valid JSON file",
            error_code="INVALID_JSON",
            suggestion="Check that the file contains valid JSON syntax."
        )

@cli.command()
@click.argument('config_file', type=click.Path())
@handle_error
def export(config_file):
    """Export proxy mappings to a file."""
    service_manager = ServiceManager()
    config_dir = service_manager.config_dir
    mapping_file = os.path.join(config_dir, 'port_mappings.json')
    
    # Check if the mapping file exists
    if not os.path.exists(mapping_file):
        click.echo("No port mappings found to export.")
        return
    
    try:
        # Load the current mappings
        with open(mapping_file, 'r') as f:
            mappings = json.load(f)
        
        # Check if there are any mappings
        if not mappings:
            click.echo("No port mappings found to export.")
            return
        
        # Create directory for the export file if it doesn't exist
        export_dir = os.path.dirname(os.path.abspath(config_file))
        if export_dir and not os.path.exists(export_dir):
            try:
                os.makedirs(export_dir, exist_ok=True)
            except PermissionError:
                raise CliError(
                    f"Permission denied when creating directory {export_dir}",
                    error_code="PERMISSION_DENIED",
                    suggestion="Check that you have write permissions for this location or choose a different export path."
                )
            except Exception as e:
                raise CliError(
                    f"Failed to create directory {export_dir}: {str(e)}",
                    error_code="DIRECTORY_ERROR",
                    suggestion="Check file system permissions or choose a different export path."
                )
        
        # Export the mappings
        try:
            with open(config_file, 'w') as f:
                json.dump(mappings, f, indent=2)
        except PermissionError:
            raise CliError(
                f"Permission denied when writing to {config_file}",
                error_code="PERMISSION_DENIED",
                suggestion="Check that you have write permissions for this location or choose a different export path."
            )
        except Exception as e:
            raise CliError(
                f"Failed to write to {config_file}: {str(e)}",
                error_code="WRITE_ERROR",
                suggestion="Check file system permissions and available disk space."
            )
        
        # Count the number of mappings
        mapping_count = len(mappings)
        
        # Provide clear output about exported mappings
        click.echo(f"Successfully exported {mapping_count} port mapping{'s' if mapping_count != 1 else ''} to {config_file}.")
        click.echo(f"You can load these mappings later using 'roxy load {config_file}'.")
        
    except json.JSONDecodeError:
        raise CliError(
            "The port mappings file is corrupted",
            error_code="INVALID_JSON",
            suggestion="You may need to delete it and recreate your mappings using the web interface."
        )

@cli.command()
@handle_error
def setup():
    """Set up Roxy with SSL certificates and dependencies."""
    setup_manager = SetupManager()
    
    try:
        # Run the setup process
        if setup_manager.run_setup():
            click.echo("Roxy setup completed successfully.")
            click.echo("You can now start Roxy with 'roxy start'.")
        else:
            raise CliError(
                "Setup process was not completed successfully",
                error_code="SETUP_INCOMPLETE",
                suggestion="Run 'roxy setup' again to retry or check logs for more details."
            )
    except PermissionError as e:
        raise CliError(
            f"Permission denied during setup: {str(e)}",
            error_code="SETUP_PERMISSION_DENIED",
            suggestion="Try running with elevated privileges or check file permissions."
        )
    except Exception as e:
        raise CliError(
            f"Error during setup: {str(e)}",
            error_code="SETUP_ERROR",
            suggestion="Check system requirements and try running 'roxy setup' again."
        )

@cli.command()
@handle_error
def edit():
    """Interactively edit port mappings."""
    service_manager = ServiceManager()
    config_dir = service_manager.config_dir
    mapping_file = os.path.join(config_dir, 'port_mappings.json')
    
    # Initialize the server to get protocol information
    server = ProxyServer()
    
    # Load existing mappings or create an empty dict
    mappings = {}
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, 'r') as f:
                raw_mappings = json.load(f)
                # Convert keys to tuples
                mappings = {tuple(k.split('|')): v for k, v in raw_mappings.items()}
        except json.JSONDecodeError:
            click.echo("Warning: The port mappings file is corrupted. Starting with an empty mapping.")
    
    # Convert mappings to a list for easier manipulation
    mapping_list = []
    for (ip, protocol), port in mappings.items():
        default_port = server.protocol_ports.get(protocol, 'N/A')
        mapping_list.append({
            'ip': ip,
            'protocol': protocol,
            'internal_port': default_port,
            'external_port': port
        })
    
    # Sort the list by external port
    mapping_list.sort(key=lambda x: x['external_port'])
    
    # Main edit loop
    while True:
        # Display current mappings
        click.clear()
        click.echo("Current Port Mappings:")
        if mapping_list:
            table_data = [[i+1, m['ip'], m['protocol'], m['internal_port'], m['external_port']] 
                         for i, m in enumerate(mapping_list)]
            headers = ["#", "IP Address", "Protocol", "Internal Port", "External Port"]
            click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            click.echo("No mappings configured.")
        
        # Display menu
        click.echo("\nOptions:")
        click.echo("  a - Add a new mapping")
        click.echo("  e - Edit an existing mapping")
        click.echo("  d - Delete a mapping")
        click.echo("  s - Save and exit")
        click.echo("  q - Quit without saving")
        
        choice = click.prompt("Enter your choice", type=str, default="s").lower()
        
        if choice == 'a':
            # Add a new mapping
            click.echo("\nAdd a new port mapping:")
            
            # Get IP address
            ip = click.prompt("Enter IP address", type=str)
            
            # Get protocol
            available_protocols = list(server.protocol_ports.keys())
            click.echo(f"Available protocols: {', '.join(available_protocols)}")
            protocol = click.prompt("Enter protocol", type=str)
            
            # Validate protocol
            if protocol not in server.protocol_ports:
                click.echo(f"Warning: '{protocol}' is not a recognized protocol.")
                if not click.confirm("Continue anyway?", default=False):
                    continue
            
            # Get external port
            if mapping_list:
                suggested_port = max(m['external_port'] for m in mapping_list) + 1
            else:
                suggested_port = server.start_port
            
            external_port = click.prompt(f"Enter external port (default: {suggested_port})", 
                                        type=int, default=suggested_port)
            
            # Check for duplicate external port
            if any(m['external_port'] == external_port for m in mapping_list):
                click.echo(f"Warning: Port {external_port} is already in use.")
                if not click.confirm("Continue anyway? This will overwrite the existing mapping.", default=False):
                    continue
                # Remove the existing mapping with this port
                mapping_list = [m for m in mapping_list if m['external_port'] != external_port]
            
            # Add the new mapping
            internal_port = server.protocol_ports.get(protocol, 0)
            mapping_list.append({
                'ip': ip,
                'protocol': protocol,
                'internal_port': internal_port,
                'external_port': external_port
            })
            
            click.echo(f"Added mapping: {ip} ({protocol}) -> port {external_port}")
            click.pause("Press any key to continue...")
            
        elif choice == 'e':
            # Edit an existing mapping
            if not mapping_list:
                click.echo("No mappings to edit.")
                click.pause("Press any key to continue...")
                continue
            
            # Get the mapping to edit
            index = click.prompt("Enter the number of the mapping to edit", type=int, default=1)
            if index < 1 or index > len(mapping_list):
                click.echo("Invalid selection.")
                click.pause("Press any key to continue...")
                continue
            
            mapping = mapping_list[index-1]
            click.echo(f"\nEditing mapping #{index}:")
            click.echo(f"Current values: {mapping['ip']} ({mapping['protocol']}) -> port {mapping['external_port']}")
            
            # Edit IP address
            new_ip = click.prompt("Enter new IP address", type=str, default=mapping['ip'])
            
            # Edit protocol
            available_protocols = list(server.protocol_ports.keys())
            click.echo(f"Available protocols: {', '.join(available_protocols)}")
            new_protocol = click.prompt("Enter new protocol", type=str, default=mapping['protocol'])
            
            # Validate protocol
            if new_protocol not in server.protocol_ports:
                click.echo(f"Warning: '{new_protocol}' is not a recognized protocol.")
                if not click.confirm("Continue anyway?", default=False):
                    continue
            
            # Edit external port
            new_external_port = click.prompt("Enter new external port", type=int, default=mapping['external_port'])
            
            # Check for duplicate external port
            if (new_external_port != mapping['external_port'] and 
                any(m['external_port'] == new_external_port for m in mapping_list)):
                click.echo(f"Warning: Port {new_external_port} is already in use.")
                if not click.confirm("Continue anyway? This will overwrite the existing mapping.", default=False):
                    continue
                # Remove the existing mapping with this port
                mapping_list = [m for m in mapping_list if m['external_port'] != new_external_port and 
                               m != mapping]
            
            # Update the mapping
            new_internal_port = server.protocol_ports.get(new_protocol, 0)
            mapping_list[index-1] = {
                'ip': new_ip,
                'protocol': new_protocol,
                'internal_port': new_internal_port,
                'external_port': new_external_port
            }
            
            click.echo(f"Updated mapping: {new_ip} ({new_protocol}) -> port {new_external_port}")
            click.pause("Press any key to continue...")
            
        elif choice == 'd':
            # Delete a mapping
            if not mapping_list:
                click.echo("No mappings to delete.")
                click.pause("Press any key to continue...")
                continue
            
            # Get the mapping to delete
            index = click.prompt("Enter the number of the mapping to delete", type=int, default=1)
            if index < 1 or index > len(mapping_list):
                click.echo("Invalid selection.")
                click.pause("Press any key to continue...")
                continue
            
            mapping = mapping_list[index-1]
            if click.confirm(f"Delete mapping {mapping['ip']} ({mapping['protocol']}) -> port {mapping['external_port']}?", default=False):
                del mapping_list[index-1]
                click.echo("Mapping deleted.")
            else:
                click.echo("Deletion cancelled.")
            
            click.pause("Press any key to continue...")
            
        elif choice == 's':
            # Save mappings and exit
            # Convert the list back to the format expected by the server
            new_mappings = {}
            for mapping in mapping_list:
                key = f"{mapping['ip']}|{mapping['protocol']}"
                new_mappings[key] = mapping['external_port']
            
            # Save to file
            try:
                os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
                with open(mapping_file, 'w') as f:
                    json.dump(new_mappings, f)
                
                click.echo(f"Saved {len(new_mappings)} port mappings.")
                
                # Check if server is running and offer to restart
                if service_manager.is_running():
                    if click.confirm("Roxy is running. Would you like to restart it to apply the changes?", default=True):
                        try:
                            pid = service_manager.get_pid()
                            service_manager.stop_service()
                            new_pid = service_manager.start_service()
                            click.echo(f"Roxy restarted successfully (PID {new_pid}).")
                        except Exception as e:
                            logger.error(f"Error restarting Roxy: {str(e)}")
                            raise CliError(
                                f"Failed to restart Roxy: {str(e)}",
                                error_code="RESTART_ERROR",
                                suggestion="Try stopping and starting the service manually with 'roxy stop' and 'roxy start'."
                            )
                else:
                    click.echo("Roxy is not running. Start it with 'roxy start' to apply the changes.")
                
                break
            except PermissionError:
                error_msg = f"Permission denied when writing to {mapping_file}"
                logger.error(error_msg)
                click.echo(f"Error: {error_msg}", err=True)
                click.echo("Suggestion: Check file permissions or run with elevated privileges.", err=True)
                if not click.confirm("Try again?", default=True):
                    break
            except Exception as e:
                error_msg = f"Error saving mappings: {str(e)}"
                logger.error(error_msg)
                click.echo(f"Error: {error_msg}", err=True)
                click.echo("Suggestion: Check file system permissions and available disk space.", err=True)
                if not click.confirm("Try again?", default=True):
                    break
        
        elif choice == 'q':
            # Quit without saving
            if click.confirm("Are you sure you want to quit without saving?", default=False):
                click.echo("Changes discarded.")
                break
        
        else:
            click.echo("Invalid choice.")
            click.pause("Press any key to continue...")