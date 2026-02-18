FROM nginx:1.27-alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Create directories for certbot
RUN mkdir -p /var/www/certbot

# Generate self-signed placeholder certs so nginx can start before certbot runs.
# certbot will overwrite these with real certs via the shared volume.
RUN apk add --no-cache openssl \
    && mkdir -p /etc/nginx/ssl \
    && openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
       -keyout /etc/nginx/ssl/placeholder.key \
       -out /etc/nginx/ssl/placeholder.crt \
       -subj "/CN=placeholder" \
    && apk del openssl

# Bootstrap script: creates symlinks from letsencrypt paths to placeholders
# if real certs don't exist yet
COPY docker-entrypoint-bootstrap.sh /docker-entrypoint.d/05-bootstrap-certs.sh

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
