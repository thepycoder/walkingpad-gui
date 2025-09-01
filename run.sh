#!/bin/bash

# WalkingPad GUI Launcher
# Simple script to run the WalkingPad GUI controller

echo "Starting WalkingPad GUI Controller..."

cd /home/victor/Projects/walkingpad/walkingpad-gui

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Try to run the installed command first
if command -v walkingpad-gui >/dev/null 2>&1; then
    echo "Running installed walkingpad-gui command..."
    walkingpad-gui
elif command -v python3 >/dev/null 2>&1; then
    echo "Running with python3..."
    python3 main.py
elif command -v python >/dev/null 2>&1; then
    echo "Running with python..."
    python main.py
else
    echo "Error: Python not found. Please install Python 3.9 or higher."
    exit 1
fi 