#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-_}"
EMAIL="${2:-}"
APP_DIR="/opt/flexa"
REPO_URL="https://github.com/yosthindorelien305-byte/RENEROVKA.git"

IS_IP=false
if [[ "$TARGET" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [ "$TARGET" = "_" ] || [ -z "$TARGET" ]; then
  IS_IP=true
fi

echo "=== 1. Installing packages ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git python3 nginx certbot python3-certbot-nginx ufw curl

echo "=== 2. Cloning/Updating repository ==="
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --all
  git -C "$APP_DIR" reset --hard origin/main
else
  git clone "$REPO_URL" "$APP_DIR"
fi

echo "=== 3. Setting up systemd service ==="
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
systemctl restart flexa

echo "=== 4. Configuring Nginx ==="
CONF_NAME="flexa"

if [ "$IS_IP" = true ]; then
  cat > "/etc/nginx/sites-available/$CONF_NAME" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

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
else
  CONF_NAME="$TARGET"
  cat > "/etc/nginx/sites-available/$CONF_NAME" <<EOF
server {
    listen 80;
    server_name $TARGET www.$TARGET;

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
fi

rm -f /etc/nginx/sites-enabled/default
ln -sf "/etc/nginx/sites-available/$CONF_NAME" "/etc/nginx/sites-enabled/$CONF_NAME"
nginx -t
systemctl reload nginx

echo "=== 5. Configuring Firewall ==="
ufw allow OpenSSH || true
ufw allow 'Nginx Full' || true

if [ "$IS_IP" = false ]; then
  echo "=== 6. Obtaining SSL Certificate via Let's Encrypt ==="
  if [ -n "$EMAIL" ]; then
    certbot --nginx -d "$TARGET" -d "www.$TARGET" --non-interactive --agree-tos -m "$EMAIL" --redirect || true
  else
    certbot --nginx -d "$TARGET" -d "www.$TARGET" --non-interactive --agree-tos --register-unsafely-without-email --redirect || true
  fi
  echo "=== DONE ==="
  echo "Site URL: https://$TARGET"
else
  SERVER_IP=$(curl -s -4 ifconfig.me || echo "your-server-ip")
  echo "=== DONE ==="
  echo "Site URL: http://$SERVER_IP"
fi

echo "Service status: systemctl status flexa --no-pager"
