"""
Core proxy server functionality.
"""

import socket
import threading
import json
import os
import sys
import logging
from flask import Flask, request, redirect, render_template

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('roxy.server')

class RoxyServerError(Exception):
    """Base exception class for Roxy server errors."""
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

class PortInUseError(RoxyServerError):
    """Exception raised when a port is already in use."""
    def __init__(self, port):
        super().__init__(
            f"Port {port} is already in use by another process.",
            error_code="PORT_IN_USE",
            suggestion=f"Try using a different port or stop the process using port {port}."
        )

class PermissionError(RoxyServerError):
    """Exception raised when permission is denied for a port."""
    def __init__(self, port):
        super().__init__(
            f"Permission denied when binding to port {port}.",
            error_code="PERMISSION_DENIED",
            suggestion="Try running with sudo or use a port > 1024."
        )

class ConnectionError(RoxyServerError):
    """Exception raised when connection to remote server fails."""
    def __init__(self, ip, port, reason):
        super().__init__(
            f"Failed to connect to {ip}:{port}. {reason}",
            error_code="CONNECTION_FAILED",
            suggestion="Check if the remote server is running and accessible."
        )

class ConfigError(RoxyServerError):
    """Exception raised when there's an issue with configuration."""
    def __init__(self, message, suggestion=None):
        super().__init__(
            message,
            error_code="CONFIG_ERROR",
            suggestion=suggestion or "Check your configuration file for errors."
        )


class ProxyServer:
    """
    Core proxy server class that handles TCP proxying and web interface.
    """
    def __init__(self):
        # Fixed configuration to ensure compatibility with nginx and gunicorn
        self.host = '127.0.0.1'
        self.port = 5000
        self.app = Flask(__name__, static_folder='static', template_folder='templates')
        self.active_proxies = {}
        self.mapping_file = os.path.expanduser('~/.roxy/port_mappings.json')
        self.start_port = 10000
        self.delimiter = '|'
        
        # Mapping of protocols to their default ports
        self.protocol_ports = {
            'ssh': 22,
            'telnet': 23,
            'http': 80,
            'https': 443,
            'rdp': 3389,
            # Add more protocols as needed
        }
        
        # Ensure config directory exists
        os.makedirs(os.path.dirname(self.mapping_file), exist_ok=True)
        
        self.setup_routes()
    
    def setup_routes(self):
        """
        Set up Flask routes for the web interface.
        """
        @self.app.route('/', methods=['GET', 'POST'])
        def index():
            """
            Handle incoming HTTP GET and POST requests.
            Parse parameters, manage port mappings, start proxies, and redirect the client.
            """
            protocol = None
            ip = None

            if request.method == 'POST':
                protocol = request.form.get('protocol')
                ip = request.form.get('ip')
            elif request.method == 'GET':
                protocol = request.args.get('protocol')
                ip = request.args.get('ip')

            if protocol and ip:
                if protocol not in self.protocol_ports:
                    return render_template('index.html', error=f"Unsupported protocol '{protocol}'.", 
                                          protocols=self.protocol_ports.keys())

                internal_port = self.protocol_ports[protocol]
                mappings = self.load_mappings()
                mapping_key = (ip, protocol)

                if mapping_key in mappings:
                    port = mappings[mapping_key]
                else:
                    if mappings:
                        max_port = max(mappings.values())
                        port = max_port + 1
                    else:
                        port = self.start_port
                    mappings[mapping_key] = port
                    self.save_mappings(mappings)

                threading.Thread(
                    target=self.start_tcp_proxy,
                    args=(port, ip, internal_port),
                    daemon=True
                ).start()

                host_ip = request.host.split(':')[0]
                new_url = f"{protocol}://{host_ip}:{port}"
                print(f"Redirecting to {new_url}")
                return redirect(new_url)
            else:
                error_message = None
                if request.method == 'POST':
                    error_message = "Please specify both protocol and IP."
                return render_template('index.html', error=error_message, protocols=self.protocol_ports.keys())
    
    def start(self):
        """
        Start the proxy server.
        
        Returns:
            None
            
        Raises:
            RoxyServerError: If there's an error starting the server
        """
        try:
            self.restart_proxies()
            logger.info(f"Starting server on {self.host}:{self.port}...")
            self.app.run(host=self.host, port=self.port)
        except socket.error as e:
            if e.errno == 98:  # Address already in use
                error = PortInUseError(self.port)
                logger.error(str(error))
                raise error
            elif e.errno == 13:  # Permission denied
                error = PermissionError(self.port)
                logger.error(str(error))
                raise error
            else:
                error = RoxyServerError(
                    f"Failed to start server on {self.host}:{self.port}: {e}",
                    error_code="SERVER_START_ERROR",
                    suggestion="Check network configuration and try again."
                )
                logger.error(str(error))
                raise error
        except Exception as e:
            error = RoxyServerError(
                f"Failed to start server on {self.host}:{self.port}: {e}",
                error_code="SERVER_START_ERROR",
                suggestion="Check system resources and try again."
            )
            logger.error(str(error))
            raise error
    
    def stop(self):
        """
        Stop the proxy server.
        
        Returns:
            None
            
        Raises:
            RoxyServerError: If there's an error stopping the server
        """
        try:
            for port in list(self.active_proxies.keys()):
                self.stop_proxy(port)
            logger.info("All proxy servers stopped successfully")
        except Exception as e:
            error = RoxyServerError(
                f"Failed to stop proxy server: {e}",
                error_code="SERVER_STOP_ERROR",
                suggestion="Check if the server is still running and try again."
            )
            logger.error(str(error))
            raise error
    
    def restart(self):
        """
        Restart the proxy server.
        """
        self.stop()
        self.start()
    
    def load_mappings(self):
        """
        Load existing mappings from the JSON file.
        Returns a dictionary with keys as (ip, protocol) tuples and values as external ports.
        Handles empty or invalid JSON files gracefully.
        
        Returns:
            dict: A dictionary of mappings
            
        Raises:
            ConfigError: If the mapping file exists but contains invalid JSON
        """
        if os.path.exists(self.mapping_file):
            try:
                with open(self.mapping_file, 'r') as f:
                    mappings = json.load(f)
                    # Convert keys back to tuples by splitting on the delimiter
                    return {tuple(k.split(self.delimiter)): v for k, v in mappings.items()}
            except json.JSONDecodeError:
                logger.warning("port_mappings.json contains invalid JSON. Starting with an empty mapping.")
                # Don't raise an exception here, just return an empty dict to allow the server to start
                return {}
            except PermissionError:
                error_msg = f"Permission denied when reading mapping file: {self.mapping_file}"
                logger.error(error_msg)
                raise ConfigError(error_msg, "Check file permissions or run with elevated privileges.")
            except Exception as e:
                error_msg = f"Failed to load mappings: {str(e)}"
                logger.error(error_msg)
                raise ConfigError(error_msg)
        else:
            logger.info(f"Mapping file {self.mapping_file} does not exist. Starting with an empty mapping.")
            return {}
    
    def save_mappings(self, mappings):
        """
        Save the mappings to the JSON file.
        
        Args:
            mappings (dict): Dictionary of mappings to save
            
        Raises:
            ConfigError: If there's an error saving the mappings
        """
        # Ensure directory exists
        try:
            os.makedirs(os.path.dirname(self.mapping_file), exist_ok=True)
            
            with open(self.mapping_file, 'w') as f:
                # Convert tuple keys to strings for JSON serialization using the delimiter
                mappings_serializable = {f"{k[0]}{self.delimiter}{k[1]}": v for k, v in mappings.items()}
                json.dump(mappings_serializable, f)
            
            logger.info(f"Successfully saved {len(mappings)} mappings to {self.mapping_file}")
        except PermissionError:
            error_msg = f"Permission denied when writing to mapping file: {self.mapping_file}"
            logger.error(error_msg)
            raise ConfigError(error_msg, "Check file permissions or run with elevated privileges.")
        except Exception as e:
            error_msg = f"Failed to save mappings: {str(e)}"
            logger.error(error_msg)
            raise ConfigError(error_msg)
    
    def stop_proxy(self, port):
        """
        Stop the proxy running on the specified port.
        """
        if port in self.active_proxies:
            proxy_thread = self.active_proxies.pop(port)
            proxy_thread.join()  # Wait for the thread to exit
            print(f"Stopped proxy on port {port}")
    
    def start_tcp_proxy(self, local_port, remote_ip, remote_port):
        """
        Start a TCP proxy that listens on local_port and forwards traffic to remote_ip:remote_port.
        
        Args:
            local_port (int): The local port to listen on
            remote_ip (str): The remote IP to forward traffic to
            remote_port (int): The remote port to forward traffic to
            
        Returns:
            None
            
        Raises:
            PortInUseError: If the port is already in use
            PermissionError: If permission is denied for the port
            RoxyServerError: For other server-related errors
        """
        def proxy_worker():
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                # Set socket option to reuse address to avoid "Address already in use" errors
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # Bind the server socket to all interfaces on the specified local port
                server_socket.bind(('0.0.0.0', local_port))
                server_socket.listen(5)
                logger.info(f"Started proxy on port {local_port} to {remote_ip}:{remote_port}")
                
                while True:
                    try:
                        # Accept incoming client connections
                        client_socket, client_address = server_socket.accept()
                        logger.info(f"Accepted connection from {client_address}")
                        # Start a new thread to handle the client connection
                        threading.Thread(
                            target=self.handle_client_connection,
                            args=(client_socket, remote_ip, remote_port),
                            daemon=True
                        ).start()
                    except socket.error as e:
                        logger.error(f"Socket error while accepting connection: {e}")
                    except Exception as e:
                        logger.error(f"Unexpected error while accepting connection: {e}")
            except socket.error as e:
                if e.errno == 13:  # Permission denied
                    error = PermissionError(local_port)
                    logger.error(str(error))
                    raise error
                elif e.errno == 98:  # Address already in use
                    error = PortInUseError(local_port)
                    logger.error(str(error))
                    raise error
                else:
                    error = RoxyServerError(
                        f"Socket error when starting proxy on port {local_port}: {e}",
                        error_code="SOCKET_ERROR",
                        suggestion="Check network configuration and try again."
                    )
                    logger.error(str(error))
                    raise error
            except Exception as e:
                error = RoxyServerError(
                    f"Failed to start proxy on port {local_port}: {e}",
                    error_code="PROXY_START_ERROR",
                    suggestion="Check system resources and try again."
                )
                logger.error(str(error))
                raise error
            finally:
                server_socket.close()
                logger.info(f"Proxy on port {local_port} has been stopped.")

        # Check if a proxy is already running on this port, if so, stop it
        if local_port in self.active_proxies:
            self.stop_proxy(local_port)

        try:
            # Start the proxy in a new thread
            proxy_thread = threading.Thread(target=proxy_worker, daemon=True)
            proxy_thread.start()
            self.active_proxies[local_port] = proxy_thread
            logger.info(f"Proxy thread started for port {local_port}")
        except Exception as e:
            logger.error(f"Failed to start proxy thread for port {local_port}: {e}")
            # If we can't start the thread, make sure the port is not in active_proxies
            if local_port in self.active_proxies:
                del self.active_proxies[local_port]
            raise RoxyServerError(
                f"Failed to start proxy thread for port {local_port}: {e}",
                error_code="THREAD_ERROR",
                suggestion="Check system resources and try again."
            )
    
    def handle_client_connection(self, client_socket, remote_ip, remote_port):
        """
        Handle an individual client connection.
        Connect to the remote server and set up forwarding between the client and the server.
        
        Args:
            client_socket (socket.socket): The client socket connection
            remote_ip (str): The remote IP to connect to
            remote_port (int): The remote port to connect to
            
        Returns:
            None
            
        Raises:
            ConnectionError: If connection to the remote server fails
        """
        client_address = client_socket.getpeername() if hasattr(client_socket, 'getpeername') else 'unknown'
        
        try:
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Set a timeout for the connection attempt
            remote_socket.settimeout(10)
            remote_socket.connect((remote_ip, remote_port))
            # Reset to blocking mode after connection
            remote_socket.settimeout(None)
            logger.info(f"Connected to remote server {remote_ip}:{remote_port} for client {client_address}")
        except socket.timeout:
            error_msg = f"Connection to {remote_ip}:{remote_port} timed out for client {client_address}"
            logger.error(error_msg)
            client_socket.close()
            raise ConnectionError(remote_ip, remote_port, "Connection timed out")
        except ConnectionRefusedError:
            error_msg = f"Connection to {remote_ip}:{remote_port} refused for client {client_address}. Service may be down."
            logger.error(error_msg)
            client_socket.close()
            raise ConnectionError(remote_ip, remote_port, "Connection refused. Service may be down.")
        except socket.gaierror:
            error_msg = f"Address resolution error for {remote_ip}. Check if the IP is valid."
            logger.error(error_msg)
            client_socket.close()
            raise ConnectionError(remote_ip, remote_port, "Address resolution error. Check if the IP is valid.")
        except Exception as e:
            error_msg = f"Failed to connect to {remote_ip}:{remote_port} for client {client_address}: {e}"
            logger.error(error_msg)
            client_socket.close()
            raise ConnectionError(remote_ip, remote_port, str(e))

        # Start threads to forward data between client and remote server
        try:
            threading.Thread(
                target=self.forward_data,
                args=(client_socket, remote_socket, f"client-{client_address}", f"remote-{remote_ip}:{remote_port}"),
                daemon=True
            ).start()
            threading.Thread(
                target=self.forward_data,
                args=(remote_socket, client_socket, f"remote-{remote_ip}:{remote_port}", f"client-{client_address}"),
                daemon=True
            ).start()
        except Exception as e:
            error_msg = f"Failed to start forwarding threads for {remote_ip}:{remote_port}: {e}"
            logger.error(error_msg)
            client_socket.close()
            remote_socket.close()
            raise RoxyServerError(
                error_msg,
                error_code="THREAD_ERROR",
                suggestion="Check system resources and try again."
            )
    
    def forward_data(self, source_socket, destination_socket, source_name='source', dest_name='destination'):
        """
        Forward data from source_socket to destination_socket.
        
        Args:
            source_socket (socket.socket): The socket to read data from
            destination_socket (socket.socket): The socket to write data to
            source_name (str): A name for the source socket for logging purposes
            dest_name (str): A name for the destination socket for logging purposes
            
        Returns:
            None
            
        Raises:
            RoxyServerError: If there's an error forwarding data
        """
        buffer_size = 8192  # Increased buffer size for better performance
        total_bytes = 0
        
        try:
            while True:
                try:
                    # Receive data from source
                    data = source_socket.recv(buffer_size)
                    if not data:
                        logger.info(f"Connection closed by {source_name}")
                        break
                    
                    # Send data to destination
                    destination_socket.sendall(data)
                    total_bytes += len(data)
                    
                except socket.timeout:
                    # Handle socket timeout - continue and try again
                    continue
                except ConnectionResetError:
                    logger.warning(f"Connection reset by {source_name} or {dest_name}")
                    break
                except BrokenPipeError:
                    logger.warning(f"Broken pipe when forwarding from {source_name} to {dest_name}")
                    break
                except socket.error as e:
                    logger.error(f"Socket error when forwarding from {source_name} to {dest_name}: {e}")
                    break
        except Exception as e:
            logger.error(f"Error forwarding data from {source_name} to {dest_name}: {e}")
            # We don't raise here because this is running in a separate thread
            # and we want to gracefully handle errors without crashing the thread
        finally:
            # Clean up resources
            try:
                source_socket.close()
            except Exception as e:
                logger.debug(f"Error closing source socket: {e}")
                
            try:
                destination_socket.close()
            except Exception as e:
                logger.debug(f"Error closing destination socket: {e}")
                
            logger.info(f"Connection closed: {source_name} -> {dest_name}, {total_bytes} bytes transferred")
    
    def restart_proxies(self):
        """
        Restart all proxies based on the existing mappings in port_mappings.json.
        
        Returns:
            None
            
        Raises:
            RoxyServerError: If there's an error restarting proxies
        """
        try:
            mappings = self.load_mappings()
            logger.info(f"Restarting {len(mappings)} proxy mappings")
            
            for mapping_key, port in mappings.items():
                ip, protocol = mapping_key
                if protocol in self.protocol_ports:
                    internal_port = self.protocol_ports[protocol]
                    try:
                        threading.Thread(
                            target=self.start_tcp_proxy,
                            args=(port, ip, internal_port),
                            daemon=True
                        ).start()
                        logger.info(f"Restarted proxy on port {port} to {ip}:{internal_port}")
                    except Exception as e:
                        logger.error(f"Failed to restart proxy on port {port} to {ip}:{internal_port}: {e}")
                        # Continue with other proxies even if one fails
                else:
                    logger.warning(f"Protocol '{protocol}' not recognized. Skipping mapping for {ip}:{port}")
        except ConfigError:
            # ConfigError is already logged and formatted in load_mappings
            raise
        except Exception as e:
            error = RoxyServerError(
                f"Failed to restart proxies: {e}",
                error_code="PROXY_RESTART_ERROR",
                suggestion="Check your configuration and try again."
            )
            logger.error(str(error))
            raise error