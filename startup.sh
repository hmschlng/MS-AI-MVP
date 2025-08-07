#!/bin/bash

# Azure App Service startup script for Streamlit with uv
echo "Starting AI Test Generator with uv..."

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Create virtual environment and install dependencies
echo "Setting up virtual environment with uv..."
uv venv
source .venv/bin/activate

echo "Installing dependencies..."
uv pip install -e ".[streamlit]"

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start Streamlit
echo "Starting Streamlit application..."
PORT=${WEBSITES_PORT:-${PORT:-8000}}
streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false --server.enableCORS=false --server.enableXsrfProtection=false