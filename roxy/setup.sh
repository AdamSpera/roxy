#!/bin/bash

# Install dependencies
apt-get install -y openssl
pip install pipenv

# Generate SSL certificate
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj "/CN=localhost"

# Install Python dependencies
pipenv install
pipenv install gunicorn

# Set Flask app environment variable
export FLASK_APP=server.py

# Run the application
pipenv run gunicorn -w 4 -b :443 --certfile cert.pem --keyfile key.pem server:app