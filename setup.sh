#!/bin/bash
# Capsolver setup script

set -e

echo "================================"
echo "Capsolver Setup"
echo "================================"
echo

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "[*] Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "[*] Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "[*] Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Install Playwright browsers
echo "[*] Installing Playwright Chromium..."
playwright install chromium

# Install ffmpeg if not present
if ! command -v ffmpeg &> /dev/null; then
    echo "[*] Installing ffmpeg..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install ffmpeg
        else
            echo "[-] Please install ffmpeg manually: brew install ffmpeg"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt &> /dev/null; then
            sudo apt update && sudo apt install -y ffmpeg
        elif command -v yum &> /dev/null; then
            sudo yum install -y ffmpeg
        else
            echo "[-] Please install ffmpeg manually"
        fi
    fi
else
    echo "[+] ffmpeg already installed"
fi

echo
echo "================================"
echo "Setup complete!"
echo "================================"
echo
echo "To activate the environment:"
echo "  source venv/bin/activate"
echo
echo "To test v2 solver:"
echo "  python tests/test_v2.py"
echo
echo "To start v3 server:"
echo "  python src/recaptcha_v3.py"
echo
