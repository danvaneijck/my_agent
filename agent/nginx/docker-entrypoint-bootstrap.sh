#!/bin/sh
# Bootstrap script: ensures SSL cert paths exist before nginx starts.
# If real certs (from certbot) aren't present, symlink to the self-signed placeholders.
# This lets nginx start for the initial ACME challenge on port 80.

set -e

for domain in agent.danvan.xyz apps.danvan.xyz; do
    cert_dir="/etc/letsencrypt/live/$domain"
    if [ ! -f "$cert_dir/fullchain.pem" ]; then
        echo "bootstrap: creating placeholder certs for $domain"
        mkdir -p "$cert_dir"
        ln -sf /etc/nginx/ssl/placeholder.crt "$cert_dir/fullchain.pem"
        ln -sf /etc/nginx/ssl/placeholder.key "$cert_dir/privkey.pem"
    fi
done

exec "$@"
