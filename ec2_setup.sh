#!/bin/bash
# ec2_setup.sh – Run this ONCE on a fresh Ubuntu 22.04 EC2 instance
# Usage: bash ec2_setup.sh

set -e

echo "=== 1. System update ==="
sudo apt-get update -y
sudo apt-get upgrade -y

echo "=== 2. Install Python 3.11 + pip + git ==="
sudo apt-get install -y python3.11 python3.11-venv python3-pip git

echo "=== 3. Clone the repo ==="
# Replace with your actual GitHub repo URL
git clone https://github.com/YOUR_USERNAME/ai-research-coauthor.git
cd ai-research-coauthor

echo "=== 4. Create virtual environment and install deps ==="
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== 5. Copy .env file ==="
echo "ACTION NEEDED: Upload your .env file to /home/ubuntu/ai-research-coauthor/.env"
echo "  From your Windows machine run:"
echo "  scp -i your-key.pem .env ubuntu@<EC2_PUBLIC_IP>:/home/ubuntu/ai-research-coauthor/.env"

echo "=== 6. Install and enable systemd service ==="
sudo cp streamlit_app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable streamlit_app
sudo systemctl start streamlit_app

echo ""
echo "=== DONE ==="
echo "App is running at: http://$(curl -s ifconfig.me):8501"
echo "Check status: sudo systemctl status streamlit_app"
echo "View logs:    sudo journalctl -u streamlit_app -f"
