# Roxy

Lightweight proxy tool for HTTP/S, SSH, & Telnet, with one-command CLI control and web-based management. 

## Description

Roxy is a Python-based HTTP/HTTPS/SSH/Telnet proxy tool that provides a web interface for creating dynamic proxy mappings and a CLI for management.
Features

* Create HTTP/HTTPS/SSH/Telnet proxy mappings through a web interface
* Manage proxy mappings through a CLI
* Automatically assign ephemeral ports for proxy connections
* Import and export proxy configurations
* Support for HTTP, HTTPS, SSH, and Telnet protocols
* Clean, intuitive web interface

## Installation

Follow these steps to install and run the project:

```
pip install git+https://github.com/adamspera/roxy.git
    or
pip3 install git+https://github.com/adamspera/roxy.git
```

For platforms that require virtual environments, you may need to install with:
```
pip3 install git+https://github.com/adamspera/roxy.git --break-package-system
```

## Usage

### Starting the Service

```
roxy start
```

This will start the proxy server and web interface on the default port (8080).

Options:

* `--host`: Host address to bind to (default: 127.0.0.1)
* `--web-port`: Port for web interface (default: 8080)
* `--no-web`: Disable web interface

Example output:
```
Roxy server started successfully.
Web interface available at http://127.0.0.1:8080
```

### Stopping the Service

```
roxy stop
```

Example output:
```
Roxy server stopped successfully.
```

### Checking Service Status

```
roxy status
```

Example output:
```
Roxy server is running (PID: 12345).
Active mappings: 3
```

### Displaying Proxy Mappings

```
roxy show
```

Example output:
```
+---------------+----------+---------------+---------------+
| IP Address    | Protocol | External Port | Internal Port |
+---------------+----------+---------------+---------------+
| 192.168.1.100 | ssh      | 10000         | 22            |
| 192.168.1.101 | http     | 10001         | 80            |
| 192.168.1.102 | https    | 10002         | 443           |
+---------------+----------+---------------+---------------+
```

### Editing Configuration

```
roxy edit
```

This will open the configuration file in your default editor.

### Loading Configuration from File

```
roxy load config.json
```

Example output:
```
Loaded 5 mappings from config.json.
Sent reload signal to the server.
```

### Exporting Configuration to File

```
roxy export config.json
```

Example output:
```
Exported 3 mappings to config.json.
```

### Web Interface

The web interface is available at http://127.0.0.1:8080 by default.

## Development

To install the package in development mode:

```
git clone https://github.com/adamspera/roxy.git
cd roxy
pip install -e .
```

This allows you to make changes to the code and have them immediately reflected when running the `roxy` command.