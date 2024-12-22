#!/bin/sh
# Replace environment variables in Nginx config
envsubst '${ROOM_DOMAIN_ADDRESS} ${DOMAIN_ADDRESS}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
envsubst '${SERVICE_URL}' < /opt/excalidraw/excalidraw-app/index.html.template > /opt/excalidraw/excalidraw-app/index.html
envsubst '${SERVICE_URL}' < /opt/socket-server/static/index.html.template > /opt/socket-server/static/index.html

# Start supervisord
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
