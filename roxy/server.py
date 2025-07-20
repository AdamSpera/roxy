import socket
import threading
import json
import os
from flask import Flask, request, redirect, render_template

# Initialize the Flask application
app = Flask(__name__, static_folder='static', template_folder='templates')

# Configuration variables
MAPPING_FILE = 'port_mappings.json'  # File to store IP and protocol to port mappings
START_PORT = 10000                   # Starting port number for external ports
DELIMITER = '|'                      # Delimiter for serializing keys

# Mapping of protocols to their default ports
PROTOCOL_PORTS = {
    'ssh': 22,
    'telnet': 23,
    'http': 80,
    'https': 443,
}

# Keep track of running proxies
active_proxies = {}

def load_mappings():
    """
    Load existing mappings from the JSON file.
    Returns a dictionary with keys as (ip, protocol) tuples and values as external ports.
    Handles empty or invalid JSON files gracefully.
    """
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, 'r') as f:
                mappings = json.load(f)
                # Convert keys back to tuples by splitting on the delimiter
                return {tuple(k.split(DELIMITER)): v for k, v in mappings.items()}
        except json.JSONDecodeError:
            print("Warning: port_mappings.json is empty or contains invalid JSON. Starting with an empty mapping.")
            return {}
    else:
        return {}

def save_mappings(mappings):
    """
    Save the mappings to the JSON file.
    """
    with open(MAPPING_FILE, 'w') as f:
        # Convert tuple keys to strings for JSON serialization using the delimiter
        mappings_serializable = {f"{k[0]}{DELIMITER}{k[1]}": v for k, v in mappings.items()}
        json.dump(mappings_serializable, f)

def stop_proxy(port):
    """
    Stop the proxy running on the specified port.
    """
    if port in active_proxies:
        proxy_thread = active_proxies.pop(port)
        proxy_thread.join()  # Wait for the thread to exit
        print(f"Stopped proxy on port {port}")

def start_tcp_proxy(local_port, remote_ip, remote_port):
    """
    Start a TCP proxy that listens on local_port and forwards traffic to remote_ip:remote_port.
    """
    def proxy_worker():
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Bind the server socket to all interfaces on the specified local port
            server_socket.bind(('0.0.0.0', local_port))
            server_socket.listen(5)
            print(f"Started proxy on port {local_port} to {remote_ip}:{remote_port}")
            while True:
                # Accept incoming client connections
                client_socket, client_address = server_socket.accept()
                print(f"Accepted connection from {client_address}")
                # Start a new thread to handle the client connection
                threading.Thread(
                    target=handle_client_connection,
                    args=(client_socket, remote_ip, remote_port),
                    daemon=True
                ).start()
        except Exception as e:
            print(f"Failed to start proxy on port {local_port}: {e}")
        finally:
            server_socket.close()
            print(f"Proxy on port {local_port} has been stopped.")

    # Check if a proxy is already running on this port, if so, stop it
    if local_port in active_proxies:
        stop_proxy(local_port)

    # Start the proxy in a new thread
    proxy_thread = threading.Thread(target=proxy_worker, daemon=True)
    proxy_thread.start()
    active_proxies[local_port] = proxy_thread

def handle_client_connection(client_socket, remote_ip, remote_port):
    """
    Handle an individual client connection.
    Connect to the remote server and set up forwarding between the client and the server.
    """
    try:
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.connect((remote_ip, remote_port))
    except Exception as e:
        print(f"Failed to connect to {remote_ip}:{remote_port}: {e}")
        client_socket.close()
        return

    # Start threads to forward data between client and remote server
    threading.Thread(
        target=forward_data,
        args=(client_socket, remote_socket),
        daemon=True
    ).start()
    threading.Thread(
        target=forward_data,
        args=(remote_socket, client_socket),
        daemon=True
    ).start()

def forward_data(source_socket, destination_socket):
    """
    Forward data from source_socket to destination_socket.
    """
    try:
        while True:
            data = source_socket.recv(4096)
            if not data:
                break
            destination_socket.sendall(data)
    except Exception as e:
        print(f"Data forwarding error: {e}")
    finally:
        source_socket.close()
        destination_socket.close()

@app.route('/', methods=['GET', 'POST'])
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
        if protocol not in PROTOCOL_PORTS:
            return render_template('index.html', error=f"Unsupported protocol '{protocol}'.", protocols=PROTOCOL_PORTS.keys())

        internal_port = PROTOCOL_PORTS[protocol]
        mappings = load_mappings()
        mapping_key = (ip, protocol)

        if mapping_key in mappings:
            port = mappings[mapping_key]
        else:
            if mappings:
                max_port = max(mappings.values())
                port = max_port + 1
            else:
                port = START_PORT
            mappings[mapping_key] = port
            save_mappings(mappings)

        threading.Thread(
            target=start_tcp_proxy,
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
        return render_template('index.html', error=error_message, protocols=PROTOCOL_PORTS.keys())

def restart_proxies():
    """
    Restart all proxies based on the existing mappings in port_mappings.json.
    """
    mappings = load_mappings()
    for mapping_key, port in mappings.items():
        ip, protocol = mapping_key
        if protocol in PROTOCOL_PORTS:
            internal_port = PROTOCOL_PORTS[protocol]
            threading.Thread(
                target=start_tcp_proxy,
                args=(port, ip, internal_port),
                daemon=True
            ).start()
            print(f"Restarted proxy on port {port} to {ip}:{internal_port}")
        else:
            print(f"Warning: Protocol '{protocol}' not recognized. Skipping mapping for {ip}:{port}")

if __name__ == '__main__':
    restart_proxies()  # Restart existing proxies on program start
    print("Starting server...")
    app.run(host='127.0.0.1', port=5000)
