#!/bin/bash

# Check if port 5000 is already in use
if lsof -i:5000 -t >/dev/null; then
    echo "Port 5000 is already in use. Exiting."
    exit 1
else
    echo "Port 5000 is available. Starting the service..."
    # Activate the virtual environment
    cd web/current
    source ../../private/aiazure_venv/bin/activate

    # Run gunicorn with the specified parameter
    python3 app.py
fi