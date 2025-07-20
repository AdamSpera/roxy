"""
Display utilities for consistent terminal output formatting.

This module provides centralized formatting functions for the Roxy CLI,
including color schemes, table formatting, and consistent error messaging.
"""

from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box


# Initialize rich console for colored output
console = Console()


# Color scheme constants
class Colors:
    """Color scheme constants for different message types."""
    SUCCESS = "green"
    ERROR = "red"
    WARNING = "yellow"
    INFO = "blue"
    NEUTRAL = "white"
    ACCENT = "cyan"
    DIM = "dim"


def print_success(message: str) -> None:
    """Print a success message in green color.
    
    Args:
        message: The success message to display
    """
    console.print(f"✓ {message}", style=Colors.SUCCESS)


def print_error(message: str) -> None:
    """Print an error message in red color.
    
    Args:
        message: The error message to display
    """
    console.print(f"✗ {message}", style=Colors.ERROR)


def print_warning(message: str) -> None:
    """Print a warning message in yellow color.
    
    Args:
        message: The warning message to display
    """
    console.print(f"⚠ {message}", style=Colors.WARNING)


def print_info(message: str) -> None:
    """Print an informational message in blue color.
    
    Args:
        message: The informational message to display
    """
    console.print(f"ℹ {message}", style=Colors.INFO)


def print_neutral(message: str) -> None:
    """Print a neutral message without special coloring.
    
    Args:
        message: The message to display
    """
    console.print(message, style=Colors.NEUTRAL)


def print_header(title: str) -> None:
    """Print a formatted header with accent color.
    
    Args:
        title: The header title to display
    """
    console.print(f"\n{title}", style=f"bold {Colors.ACCENT}")
    console.print("─" * len(title), style=Colors.DIM)


def format_error_message(error: str, suggestion: Optional[str] = None) -> None:
    """Format and display a consistent error message with optional suggestion.
    
    Args:
        error: The error message to display
        suggestion: Optional suggestion for resolving the error
    """
    print_error(error)
    if suggestion:
        console.print(f"  Suggestion: {suggestion}", style=Colors.DIM)


def create_status_table(data: Dict[str, Any]) -> Table:
    """Create a formatted table for service status information.
    
    Args:
        data: Dictionary containing status information
        
    Returns:
        Rich Table object ready for display
    """
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("Property", style=Colors.ACCENT, width=15)
    table.add_column("Value", style=Colors.NEUTRAL)
    
    for key, value in data.items():
        # Format boolean values with colors
        if isinstance(value, bool):
            formatted_value = Text("Running" if value else "Stopped")
            formatted_value.style = Colors.SUCCESS if value else Colors.ERROR
        else:
            formatted_value = str(value) if value is not None else "N/A"
        
        table.add_row(key.replace("_", " ").title(), formatted_value)
    
    return table


def create_port_mappings_table(mappings: Dict[str, int]) -> Table:
    """Create a formatted table for port mappings display.
    
    Args:
        mappings: Dictionary with format {"ip|protocol": external_port}
        
    Returns:
        Rich Table object ready for display
    """
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    table.add_column("IP Address", style=Colors.ACCENT, width=15)
    table.add_column("Protocol", style=Colors.INFO, width=10)
    table.add_column("External Port", style=Colors.SUCCESS, width=12)
    table.add_column("Internal Port", style=Colors.NEUTRAL, width=12)
    
    # Protocol to internal port mapping
    protocol_ports = {
        'ssh': 22,
        'telnet': 23,
        'http': 80,
        'https': 443,
    }
    
    for key, external_port in mappings.items():
        if '|' in key:
            ip, protocol = key.split('|', 1)
            internal_port = protocol_ports.get(protocol.lower(), "Unknown")
            
            table.add_row(
                ip,
                protocol.upper(),
                str(external_port),
                str(internal_port)
            )
        else:
            # Handle malformed keys gracefully
            table.add_row(
                "Invalid",
                "Invalid", 
                str(external_port),
                "Unknown"
            )
    
    return table


def display_table(table: Table) -> None:
    """Display a table using the rich console.
    
    Args:
        table: Rich Table object to display
    """
    console.print(table)


def print_progress(step: str, current: int, total: int) -> None:
    """Print a progress message for setup steps.
    
    Args:
        step: Description of the current step
        current: Current step number
        total: Total number of steps
    """
    progress_text = f"[{current}/{total}]"
    console.print(f"{progress_text} {step}...", style=Colors.INFO)


def print_completion_message(message: str, next_step: Optional[str] = None) -> None:
    """Print a completion message with optional next step suggestion.
    
    Args:
        message: The completion message
        next_step: Optional suggestion for the next step
    """
    print_success(message)
    if next_step:
        console.print(f"  Next: {next_step}", style=Colors.DIM)


def display_service_status(status_data: Dict[str, Any]) -> None:
    """Display service status information in a formatted table.
    
    Args:
        status_data: Dictionary containing service status information
    """
    print_header("Service Status")
    table = create_status_table(status_data)
    display_table(table)


def display_port_mappings(mappings: Dict[str, int]) -> None:
    """Display port mappings in a formatted table.
    
    Args:
        mappings: Dictionary with format {"ip|protocol": external_port}
    """
    if not mappings:
        print_info("No port mappings configured")
        return
    
    print_header("Port Mappings")
    table = create_port_mappings_table(mappings)
    display_table(table)
    
    # Display summary
    mapping_count = len(mappings)
    if mapping_count == 1:
        print_success(f"✓ {mapping_count} port mapping configured")
    else:
        print_success(f"✓ {mapping_count} port mappings configured")


def display_no_mappings_message() -> None:
    """Display a message when no port mappings are found."""
    print_info("No port mappings are currently configured")
    console.print("  Use the web interface to add port mappings", style=Colors.DIM)


def display_file_error(filename: str, error: str) -> None:
    """Display a file-related error message.
    
    Args:
        filename: Name of the file that caused the error
        error: Description of the error
    """
    format_error_message(
        f"Cannot read {filename}: {error}",
        f"Ensure {filename} exists and is readable"
    )


def confirm_action(message: str) -> bool:
    """Display a confirmation prompt and return user's choice.
    
    Args:
        message: The confirmation message to display
        
    Returns:
        True if user confirms, False otherwise
    """
    try:
        response = console.input(f"[yellow]?[/yellow] {message} [y/N]: ")
        return response.lower().strip() in ('y', 'yes')
    except (KeyboardInterrupt, EOFError):
        console.print("\nOperation cancelled", style=Colors.WARNING)
        return False


def load_and_display_port_mappings() -> None:
    """Load port mappings from file and display them in a formatted table."""
    import json
    from pathlib import Path
    
    # Try both possible locations for the port mappings file
    possible_paths = [
        Path("port_mappings.json"),  # Root directory
        Path("roxy/port_mappings.json")  # Roxy package directory
    ]
    
    mappings_data = {}
    mappings_file = None
    
    for path in possible_paths:
        if path.exists():
            mappings_file = path
            try:
                with open(path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        if isinstance(data, dict) and data:
                            mappings_data = data
                            break
                        elif isinstance(data, list) and data:
                            # Convert list format to dict format if needed
                            for item in data:
                                if isinstance(item, dict):
                                    key = f"{item.get('ip', 'unknown')}|{item.get('protocol', 'unknown')}"
                                    mappings_data[key] = item.get('external_port', 0)
                            break
            except (json.JSONDecodeError, IOError) as e:
                display_file_error(str(path), str(e))
                continue
    
    if not mappings_file:
        print_info("No port mappings file found")
        console.print("  Port mappings will be created when you first use the proxy service", style=Colors.DIM)
        return
    
    if not mappings_data:
        display_no_mappings_message()
        return
    
    display_port_mappings(mappings_data)
    print_info("These mappings are active when the Roxy service is running")
    console.print("  Use 'roxy status' to check if the service is currently running", style=Colors.DIM)