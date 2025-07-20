# Roxy - Port Proxy Management Tool

A command-line tool for managing port proxies with SSL support.

## Installation

Install Roxy using pip:

```bash
pip install roxy
```

Or install from source:

```bash
pip install git+[repository_url]
```

## Usage

After installation, the `roxy` command will be available globally:

```bash
roxy --help
```

## Commands

- `roxy setup` - Run initial setup steps
- `roxy start` - Start the Roxy service
- `roxy stop` - Stop the Roxy service  
- `roxy status` - Show service status
- `roxy show` - Display current port mappings

## Requirements

- Python 3.8+
- Flask
- Gunicorn
- Click
- Rich