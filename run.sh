#!/bin/bash
source .venv/bin/activate
streamlit run main.py --server.port 8501 --server.address 0.0.0.0 --theme.base "dark"
