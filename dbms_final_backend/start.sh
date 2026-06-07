#!/bin/bash
# Initialize the database and rules
python seed.py

# Start the FastAPI server
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
