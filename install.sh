#!/bin/bash

# WalkingPad GUI Installation Script
# Installs the WalkingPad GUI using pip

set -e  # Exit on any error

echo "WalkingPad GUI Controller - Installation Script"
echo "==============================================="

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.9"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "✓ Python $python_version detected (>= $required_version required)"
else
    echo "✗ Python $required_version or higher is required. Found: $python_version"
    exit 1
fi

# Check for pip
if ! command -v pip3 >/dev/null 2>&1; then
    echo "✗ pip3 not found. Please install pip3:"
    echo "  sudo apt install python3-pip  # Ubuntu/Debian"
    echo "  sudo pacman -S python-pip     # Arch"
    echo "  sudo dnf install python3-pip  # Fedora"
    exit 1
fi

echo "✓ pip3 found"

# Create and activate virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo "Activating virtual environment..."
source .venv/bin/activate

# Install the package
echo ""
echo "Installing WalkingPad GUI and dependencies..."

# Install in development mode if we're in the source directory
if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
    echo "Installing in development mode from source..."
    pip install -e .
else
    echo "Installing from requirements.txt..."
    pip install -r requirements.txt
fi

echo ""
echo "✓ Installation complete!"
echo ""
echo "Usage:"
echo "  source .venv/bin/activate && walkingpad-gui   # Run the installed command"
echo "  source .venv/bin/activate && python main.py   # Run from source directory"
echo "  ./run.sh                                       # Use the launcher script (auto-activates venv)"
echo ""
echo "Desktop integration:"
echo "  cp walkingpad-gui.desktop ~/.local/share/applications/"
echo "  update-desktop-database ~/.local/share/applications/"
echo ""
echo "Documentation:"
echo "  README.md             # Complete setup guide"
echo "  QUICKSTART.md         # 5-minute quick start" 