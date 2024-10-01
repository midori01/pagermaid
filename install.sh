#!/bin/bash

apt update && apt install git wget curl python3 python3-pip neofetch -y
git clone https://github.com/TeamPGM/PagerMaid-Pyro.git /var/lib/pagermaid
pip3 install -r /var/lib/pagermaid/requirements.txt --break-system-packages
mkdir -p /var/lib/pagermaid/data
wget -P /var/lib/pagermaid/data https://raw.githubusercontent.com/midori01/pagermaid/refs/heads/main/data/config.yml
cat <<'TEXT' > /etc/systemd/system/pagermaid.service
[Unit]
Description=PagerMaid-Pyro Telegram Utility Daemon
After=network.target

[Install]
WantedBy=multi-user.target

[Service]
Type=simple
WorkingDirectory=/var/lib/pagermaid
ExecStart=/usr/bin/python3 -m pagermaid
Restart=always
TEXT
systemctl daemon-reload
systemctl enable pagermaid
