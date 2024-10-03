#!/bin/bash

apt update && apt install git python3 python3-pip neofetch -y
git clone https://github.com/midori01/pagermaid.git /var/lib/pagermaid
pip3 install -r /var/lib/pagermaid/requirements.txt --break-system-packages
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
systemctl daemon-reload && systemctl enable pagermaid
read -p "API ID: " api_id
read -p "API Hash: " api_hash
sed -i "s/^api_id:.*/api_id: \"$api_id\"/" /var/lib/pagermaid/data/config.yml
sed -i "s/^api_hash:.*/api_hash: \"$api_hash\"/" /var/lib/pagermaid/data/config.yml
read -p "Custom command prefix? (Default: N) [Y/N]: " modify_prefix
if [[ "$modify_prefix" =~ ^[Yy]$ ]]; then
    read -p "New command prefix: " new_prefix
    if [[ -z "$new_prefix" ]]; then
        echo "Cannot be empty."
        exit 1
    fi
    sed -i.bak "s/,|，/${new_prefix}/g" /var/lib/pagermaid/pagermaid/listener.py
fi
echo "done"
