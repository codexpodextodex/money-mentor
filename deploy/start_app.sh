#!/usr/bin/env bash
# Run the app on a small Ubuntu machine, behind HTTPS.
#
# Before this: copy the project to /root/money-mentor (from a machine that has web/brand/ and
# data/) and put a .env there with the model settings. Then:  HOST=<name> ./deploy/start_app.sh
# With no HOST, the machine's public address is turned into a name with sslip.io, for example
# 203-0-113-10.sslip.io, so Caddy can get a certificate without a domain of our own.
set -euo pipefail

APP_DIR="${APP_DIR:-/root/money-mentor}"
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq python3-venv caddy curl >/dev/null

cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -q duckdb fastapi "uvicorn[standard]" httpx

cat > /etc/systemd/system/money-mentor.service <<UNIT
[Unit]
Description=Money Mentor
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python run.py --host 127.0.0.1 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT

IP="$(curl -s -4 https://ifconfig.me || hostname -I | awk '{print $1}')"
HOST="${HOST:-${IP//./-}.sslip.io}"

cat > /etc/caddy/Caddyfile <<CADDY
$HOST {
	encode gzip
	# A demo in a bank's colours should not turn up in search results.
	header X-Robots-Tag "noindex, nofollow"
	reverse_proxy 127.0.0.1:8000
}
CADDY

systemctl daemon-reload
systemctl enable --now money-mentor >/dev/null 2>&1
systemctl restart money-mentor
systemctl restart caddy
echo "https://$HOST"
