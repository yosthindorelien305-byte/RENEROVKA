#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
APP_DIR="/opt/flexa"
REPO_URL="https://github.com/yosthindorelien305-byte/RENEROVKA.git"

if [ -z "$DOMAIN" ]; then
  echo "Usage: bash setup_vps.sh <domain> [email]"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git python3 nginx certbot python3-certbot-nginx ufw

if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --all
  git -C "$APP_DIR" reset --hard origin/main
else
  git clone "$REPO_URL" "$APP_DIR"
fi

cat > /etc/systemd/system/flexa.service <<'EOF'
[Unit]
Description=Flexa Fitness Web App & API
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/flexa
Environment=PORT=8095
ExecStart=/usr/bin/python3 /opt/flexa/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now flexa

cat > "/etc/nginx/sites-available/$DOMAIN" <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8095;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

ufw allow OpenSSH || true
ufw allow 'Nginx Full' || true

if [ -n "$EMAIL" ]; then
  certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect || true
else
  certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect || true
fi

echo "=== DONE ==="
echo "Service status: systemctl status flexa --no-pager"
echo "Site URL: https://$DOMAIN"
