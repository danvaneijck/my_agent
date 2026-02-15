# ModuFlow Production Deployment Guide

This guide covers deploying ModuFlow to production at agent.danvan.xyz with HTTPS and OAuth authentication.

## Prerequisites

- A server with Docker and Docker Compose installed
- Domain name (agent.danvan.xyz) pointing to your server
- Root or sudo access on the server
- Ports 80 and 443 open in firewall

## DNS Configuration

### Step 1: Configure DNS Records

Set up the following DNS records for agent.danvan.xyz:

```
Type    Name    Value               TTL
A       @       YOUR_SERVER_IP      300
AAAA    @       YOUR_SERVER_IPv6    300 (optional)
```

**Verify DNS propagation:**
```bash
dig agent.danvan.xyz
# or
nslookup agent.danvan.xyz
```

Wait for DNS to propagate (can take 5-60 minutes).

## SSL Certificate Setup

ModuFlow uses Let's Encrypt for free SSL certificates via Certbot.

### Step 2: Install Certbot

**On Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

**On CentOS/RHEL:**
```bash
sudo yum install certbot python3-certbot-nginx
```

### Step 3: Obtain SSL Certificate

**Option A: Using Certbot standalone (recommended for first-time setup)**

Stop nginx if running:
```bash
sudo systemctl stop nginx
```

Obtain certificate:
```bash
sudo certbot certonly --standalone \
  -d agent.danvan.xyz \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email
```

**Option B: Using webroot method (if nginx is already running)**

```bash
sudo certbot certonly --webroot \
  -w /var/www/certbot \
  -d agent.danvan.xyz \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email
```

**Certificates will be stored at:**
- Certificate: `/etc/letsencrypt/live/agent.danvan.xyz/fullchain.pem`
- Private Key: `/etc/letsencrypt/live/agent.danvan.xyz/privkey.pem`

### Step 4: Set Up Auto-Renewal

Let's Encrypt certificates expire after 90 days. Set up automatic renewal:

```bash
# Test renewal
sudo certbot renew --dry-run

# Add cron job for automatic renewal
sudo crontab -e
```

Add this line to run renewal check twice daily:
```
0 0,12 * * * certbot renew --quiet --post-hook "systemctl reload nginx"
```

## Nginx Configuration

### Step 5: Install Nginx

```bash
# Ubuntu/Debian
sudo apt install nginx

# CentOS/RHEL
sudo yum install nginx
```

### Step 6: Configure Nginx

Copy the production nginx configuration:

```bash
# From your project root
sudo cp agent/nginx/agent.danvan.xyz.conf /etc/nginx/sites-available/agent.danvan.xyz

# Enable the site (Ubuntu/Debian)
sudo ln -s /etc/nginx/sites-available/agent.danvan.xyz /etc/nginx/sites-enabled/

# CentOS/RHEL: add to nginx.conf instead
sudo cp agent/nginx/agent.danvan.xyz.conf /etc/nginx/conf.d/
```

### Step 7: Create Certbot Webroot Directory

```bash
sudo mkdir -p /var/www/certbot
sudo chown -R www-data:www-data /var/www/certbot  # Ubuntu/Debian
# or
sudo chown -R nginx:nginx /var/www/certbot  # CentOS/RHEL
```

### Step 8: Test and Reload Nginx

```bash
# Test configuration
sudo nginx -t

# If test passes, reload nginx
sudo systemctl reload nginx

# Enable nginx to start on boot
sudo systemctl enable nginx
```

## Application Configuration

### Step 9: Configure Environment Variables

Update your `.env` file in `agent/` directory:

```bash
# Domain configuration
PORTAL_PUBLIC_URL=https://agent.danvan.xyz

# OAuth configuration - update redirect URIs
# Discord: https://discord.com/developers/applications
# Set redirect URI to: https://agent.danvan.xyz/auth/discord/callback

# Telegram: @BotFather
# Set domain to: agent.danvan.xyz

# Slack: https://api.slack.com/apps
# Set redirect URL to: https://agent.danvan.xyz/auth/slack/callback

# CORS configuration
ALLOWED_ORIGINS=https://agent.danvan.xyz

# Database (ensure these are set securely)
POSTGRES_PASSWORD=your_secure_password_here

# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# Platform bot tokens
DISCORD_TOKEN=...
TELEGRAM_TOKEN=...
SLACK_BOT_TOKEN=...
SLACK_APP_TOKEN=...
```

### Step 10: Update OAuth Redirect URIs

#### Discord OAuth
1. Go to https://discord.com/developers/applications
2. Select your application
3. Navigate to OAuth2 → General
4. Add redirect URI: `https://agent.danvan.xyz/auth/discord/callback`
5. Save changes

#### Slack OAuth
1. Go to https://api.slack.com/apps
2. Select your app
3. Navigate to OAuth & Permissions
4. Add redirect URL: `https://agent.danvan.xyz/auth/slack/callback`
5. Update your `.env` with the new client ID and secret

#### GitHub OAuth (if using)
1. Go to GitHub Settings → Developer settings → OAuth Apps
2. Create new OAuth App or update existing
3. Set Homepage URL: `https://agent.danvan.xyz`
4. Set Authorization callback URL: `https://agent.danvan.xyz/auth/github/callback`

## Deployment

### Step 11: Pull and Build

```bash
cd /path/to/your/project/agent
git pull origin main
make build
```

### Step 12: Start Services

```bash
# First-time setup (runs migrations, creates bucket, default persona)
make setup

# Start all services
make up

# Check status
make status
make logs
```

### Step 13: Create Owner Account

```bash
# Create owner account with your Discord/Telegram/Slack ID
make create-owner DISCORD_ID=your_discord_id

# Or create via CLI
docker compose exec core python /app/cli.py user create-owner \
  --platform discord \
  --platform-id your_discord_id
```

## Verification

### Step 14: Test the Deployment

1. **HTTPS Access**: Visit https://agent.danvan.xyz
   - Should load without certificate warnings
   - Lock icon should be visible in browser

2. **OAuth Flow**:
   - Click "Login with Discord" (or other provider)
   - Should redirect to provider
   - Should redirect back to agent.danvan.xyz
   - Should show authenticated state

3. **WebSocket Connection**:
   - Open browser DevTools → Network → WS
   - Should see successful WebSocket connection

4. **API Endpoints**:
   ```bash
   curl https://agent.danvan.xyz/api/health
   # Should return: {"status":"ok"}
   ```

5. **Bot Integration**:
   - Message your Discord/Telegram/Slack bot
   - Should receive responses
   - Check logs: `make logs-core`

## Troubleshooting

### SSL Certificate Issues

**Certificate not found:**
```bash
# Verify certificate exists
sudo ls -la /etc/letsencrypt/live/agent.danvan.xyz/

# Re-obtain certificate
sudo certbot certonly --standalone -d agent.danvan.xyz
```

**Certificate expired:**
```bash
# Manually renew
sudo certbot renew

# Reload nginx
sudo systemctl reload nginx
```

### Nginx Issues

**502 Bad Gateway:**
```bash
# Check if portal service is running
docker compose ps portal

# Check portal logs
make logs-module M=portal

# Restart portal
docker compose restart portal
```

**CORS Errors:**
- Verify `ALLOWED_ORIGINS` in `.env` includes `https://agent.danvan.xyz`
- Check nginx CORS headers in `/etc/nginx/sites-available/agent.danvan.xyz`
- Restart nginx: `sudo systemctl reload nginx`

### OAuth Issues

**Redirect mismatch:**
- Verify OAuth redirect URIs match exactly: `https://agent.danvan.xyz/auth/{provider}/callback`
- Check for http vs https
- Ensure no trailing slashes

**OAuth fails with CORS:**
- Check browser console for specific error
- Verify `Access-Control-Allow-Credentials: true` header is present
- Check that cookies are being set with `Secure` and `SameSite` attributes

### Database Connection Issues

```bash
# Check if database is running
docker compose ps postgres

# Test database connection
docker compose exec core python -c "from shared.database import get_session_factory; print('DB OK')"

# Check database logs
docker compose logs postgres
```

### Port Conflicts

```bash
# Check if ports 80 and 443 are available
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :443

# If another service is using ports, stop it or change nginx ports
```

## Security Checklist

- [ ] SSL certificate is valid and trusted
- [ ] HSTS header is enabled (after verifying HTTPS works)
- [ ] Firewall allows only ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
- [ ] Strong passwords for database and admin accounts
- [ ] Environment variables are not committed to git
- [ ] OAuth secrets are kept secure
- [ ] Regular security updates for server OS
- [ ] Backup strategy in place for database
- [ ] Monitoring and alerting configured

## Monitoring

### Health Checks

```bash
# Check all services
make status

# Check specific service health
curl https://agent.danvan.xyz/api/health

# Check logs
make logs
make logs-core
make logs-module M=portal
```

### Log Locations

**Nginx logs:**
- Access: `/var/log/nginx/agent.danvan.xyz.access.log`
- Error: `/var/log/nginx/agent.danvan.xyz.error.log`

**Application logs:**
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f portal
docker compose logs -f core
```

### Metrics

Set up monitoring for:
- CPU and memory usage
- Disk space
- Database connections
- API response times
- Error rates
- SSL certificate expiration

## Backup Strategy

### Database Backup

```bash
# Manual backup
docker compose exec postgres pg_dump -U agent agent > backup_$(date +%Y%m%d).sql

# Automated daily backup (add to crontab)
0 2 * * * cd /path/to/project/agent && docker compose exec -T postgres pg_dump -U agent agent > /backups/agent_$(date +\%Y\%m\%d).sql
```

### Full System Backup

```bash
# Backup entire data directory
tar -czf agent_backup_$(date +%Y%m%d).tar.gz \
  /var/lib/docker/volumes/agent_postgres_data \
  /var/lib/docker/volumes/agent_redis_data \
  /var/lib/docker/volumes/agent_minio_data \
  /path/to/project/agent/.env
```

## Updates and Maintenance

### Updating the Application

```bash
cd /path/to/project/agent

# Pull latest changes
git pull origin main

# Rebuild and restart
make build
make restart

# Run any new migrations
make migrate
```

### Updating Dependencies

```bash
# Rebuild specific service
make build-core
make build-module M=portal

# Restart services
make restart
```

## Rollback Procedure

If something goes wrong:

```bash
# Stop services
make down

# Checkout previous version
git checkout <previous-commit-hash>

# Rebuild
make build

# Start services
make up
```

## Performance Optimization

### Nginx Caching

Add to nginx config for static assets:
```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### Database Tuning

Adjust PostgreSQL settings in docker-compose.yml:
```yaml
environment:
  POSTGRES_SHARED_BUFFERS: 256MB
  POSTGRES_EFFECTIVE_CACHE_SIZE: 1GB
  POSTGRES_MAX_CONNECTIONS: 100
```

### Container Resource Limits

Add resource limits in docker-compose.yml:
```yaml
services:
  portal:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
```

## Additional Resources

- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [ModuFlow Brand Guidelines](BRANDING.md)
- [Module Documentation](modules/)

## Support

For issues or questions:
- Check logs: `make logs`
- Review this guide
- Check GitHub issues
- Open a new issue with details

---

**Last Updated**: February 15, 2026
**Version**: 1.0
