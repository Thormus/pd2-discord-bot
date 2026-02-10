#!/bin/bash
set -e

cd "$(dirname "$0")"

git pull
sudo systemctl restart pd2bot
echo "Bot updated and restarted successfully."
