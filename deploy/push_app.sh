#!/usr/bin/env bash
# Copy the current project to the public server and restart the app there.
#
#   deploy/push_app.sh <server-ip> [ssh-key]
#
# Run it from the project folder, in Git Bash on Windows or any shell with tar and ssh. It copies
# the code, the web files (with web/brand/, which is not in the repository) and the data. It does
# not touch the server's .env.
set -euo pipefail

IP="${1:?usage: deploy/push_app.sh <server-ip> [ssh-key]}"
KEY="${2:-$HOME/.ssh/money_mentor_verda}"
SSH="ssh -i $KEY -o ConnectTimeout=10 -o BatchMode=yes root@$IP"

tar --exclude='__pycache__' --exclude='*.pyc' -czf - app web scripts data deploy run.py requirements.txt LICENSE README.md |
  $SSH 'tar -xzf - -C /root/money-mentor && sed -i "s/\r$//" /root/money-mentor/deploy/*.sh && systemctl restart money-mentor && sleep 3 && systemctl is-active money-mentor'
$SSH 'curl -s http://127.0.0.1:8000/api/health | head -c 120; echo'
