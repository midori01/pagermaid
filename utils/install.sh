#!/bin/bash

apt update && apt install git wget curl python3 python3-pip neofetch -y
git clone https://github.com/TeamPGM/PagerMaid-Pyro.git /var/lib/pagermaid
pip3 install -r /var/lib/pagermaid/requirements.txt --break-system-packages
mkdir -p /var/lib/pagermaid/data
wget -P /var/lib/pagermaid/data https://raw.githubusercontent.com/midori01/pagermaid/main/data/config.yml

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

read -p "Custom command prefix? (Default: N) [Y/N]: " modify_prefix
[[ "$modify_prefix" =~ ^[Yy]$ ]] || { echo "No change."; exit; }
read -p "New command prefix: " new_prefix
if [[ -z "$new_prefix" ]]; then
    echo "Cannot be empty."
    exit 1
fi
sed -i.bak "s/,|，/${new_prefix}/g" /var/lib/pagermaid/pagermaid/listener.py

cd /var/lib/pagermaid && python3 -m pagermaid
