# Roxy

Easily HTTP/HTTPS, SSH, Telnet, or RDP into any lab issued internal IP address over VPN! No jumphost needed.

## Description

Roxy allows you to forward traffic from a local port to a remote IP and port based on the protocol specified. The server also provides a simple web interface for managing port mappings.

## Installation

Follow these steps to install and run the project:

1. Open a terminal.

2. Install the required Python packages:
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install flask
    pip install gunicorn
    ```

3. Install the required apt packages:
    ```bash
    apt install nginx
    ```

## Usage

1. Run the server.py script:
    ```bash
    python server.py
        OR
    gunicorn --bind 127.0.0.1:5000 server:app
    ```

The server will start on `http://127.0.0.1:5000` but will be forwarded to teh hosts external IP via Gunicorn. You can access the web interface by opening this URL in a web browser.

When searching for an IP for the first time, a custom port is allocated to that specific IP and protocol. This binding is persistant, so you and others can bookmark the same URL.
