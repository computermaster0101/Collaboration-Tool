#!/bin/sh
# Replace environment variables in Nginx config
envsubst '${ROOM_DOMAIN_ADDRESS}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Start supervisord
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
