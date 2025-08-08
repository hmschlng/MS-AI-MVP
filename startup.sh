pip install -r requirements.txt

export GIT_PYTHON_REFRESH=quiet
export STREAMLIT_SERVER_PORT=${PORT:-8000}
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
echo "Using PORT: $STREAMLIT_SERVER_PORT"
apt update && apt install -y git
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port $STREAMLIT_SERVER_PORT