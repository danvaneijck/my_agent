# ModuFlow Production Deployment Checklist

Use this checklist to ensure a smooth and secure production deployment of ModuFlow at agent.danvan.xyz.

## Pre-Deployment

### Infrastructure Setup

- [ ] Server provisioned with adequate resources
  - Minimum: 2 CPU cores, 4GB RAM, 20GB storage
  - Recommended: 4 CPU cores, 8GB RAM, 50GB storage
- [ ] Docker and Docker Compose installed
- [ ] Git installed and configured
- [ ] SSH access configured with key-based authentication
- [ ] Firewall configured (ports 22, 80, 443 open)
- [ ] Non-root user created for running services

### DNS Configuration

- [ ] Domain agent.danvan.xyz pointing to server IP
- [ ] DNS A record configured
- [ ] DNS AAAA record configured (if using IPv6)
- [ ] DNS propagation verified (`dig agent.danvan.xyz`)
- [ ] TTL set appropriately (300-3600 seconds)

### SSL Certificate

- [ ] Certbot installed on server
- [ ] SSL certificate obtained for agent.danvan.xyz
- [ ] Certificate renewal tested (`certbot renew --dry-run`)
- [ ] Auto-renewal cron job configured
- [ ] Certificate files readable by nginx user

### Web Server

- [ ] Nginx installed
- [ ] Production nginx config copied to `/etc/nginx/sites-available/`
- [ ] Site enabled (symlink created or included in nginx.conf)
- [ ] Certbot webroot directory created (`/var/www/certbot`)
- [ ] Nginx configuration tested (`nginx -t`)
- [ ] Nginx service enabled to start on boot

## Environment Configuration

### Application Variables

- [ ] `.env` file created from `.env.example`
- [ ] `.env` file permissions set (chmod 600)
- [ ] `.env` file excluded from version control

### Database Configuration

- [ ] `POSTGRES_PASSWORD` set to strong, random password
- [ ] `DATABASE_URL` updated with correct credentials
- [ ] Database password stored in secure password manager

### Storage Configuration

- [ ] `MINIO_SECRET_KEY` set to strong, random password
- [ ] `MINIO_PUBLIC_URL` set to `https://agent.danvan.xyz/files`
- [ ] MinIO credentials stored in password manager

### LLM API Keys

- [ ] At least one LLM provider configured
- [ ] `ANTHROPIC_API_KEY` set (if using Claude)
- [ ] `OPENAI_API_KEY` set (if using OpenAI)
- [ ] `GOOGLE_API_KEY` set (if using Gemini)
- [ ] API keys tested and valid
- [ ] Rate limits and quotas understood

### Platform Bot Tokens

- [ ] Discord bot created and token obtained
- [ ] `DISCORD_TOKEN` set in `.env`
- [ ] Discord bot invited to servers
- [ ] Telegram bot created via @BotFather
- [ ] `TELEGRAM_TOKEN` set in `.env`
- [ ] Slack app created and tokens obtained
- [ ] `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` set

### OAuth Configuration

- [ ] Discord OAuth application created
- [ ] Discord redirect URI set to `https://agent.danvan.xyz/auth/discord/callback`
- [ ] `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` set
- [ ] Google OAuth application created (if using)
- [ ] Google redirect URI set to `https://agent.danvan.xyz/auth/google/callback`
- [ ] `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` set
- [ ] GitHub OAuth application created (if using)
- [ ] GitHub redirect URI set to `https://agent.danvan.xyz/auth/github/callback`
- [ ] `PORTAL_OAUTH_REDIRECT_URI` set to `https://agent.danvan.xyz/auth/callback`
- [ ] `PORTAL_PUBLIC_URL` set to `https://agent.danvan.xyz`
- [ ] `ALLOWED_ORIGINS` set to `https://agent.danvan.xyz`

### Security Secrets

- [ ] `PORTAL_JWT_SECRET` generated (`openssl rand -hex 32`)
- [ ] `CREDENTIAL_ENCRYPTION_KEY` generated (Fernet key)
- [ ] All secrets stored in password manager
- [ ] Secrets never committed to git

### Module-Specific Configuration

- [ ] Claude Code credentials path configured (if using)
- [ ] SSH keys mounted for git operations (if needed)
- [ ] Garmin credentials set (if using garmin module)
- [ ] Renpho credentials set (if using renpho module)
- [ ] Atlassian credentials configured (if using)
- [ ] Deploy domain set for deployer module

## Build and Deployment

### Application Build

- [ ] Latest code pulled from repository
- [ ] Branch verified (should be on `main` or release branch)
- [ ] Docker images built (`make build`)
- [ ] Build completed without errors
- [ ] Image sizes reasonable (not bloated)

### Database Setup

- [ ] Database migrations run (`make migrate`)
- [ ] Migrations completed successfully
- [ ] Default persona created
- [ ] MinIO bucket created
- [ ] Database backup taken before deployment

### Initial User Setup

- [ ] Owner account created (`make create-owner DISCORD_ID=...`)
- [ ] Owner permissions verified
- [ ] Test user created for validation
- [ ] User token budgets configured

### Service Startup

- [ ] All services started (`make up`)
- [ ] All containers running (`docker compose ps`)
- [ ] No containers in restart loop
- [ ] Health checks passing
- [ ] Logs checked for errors (`make logs`)

## Testing and Validation

### HTTPS and SSL

- [ ] https://agent.danvan.xyz loads without warnings
- [ ] SSL certificate valid and trusted
- [ ] No mixed content warnings
- [ ] Certificate chain complete
- [ ] HSTS header enabled (optional, enable after verification)

### Frontend Testing

- [ ] Homepage loads correctly
- [ ] Logo and branding display properly
- [ ] Navigation works
- [ ] Responsive design works on mobile
- [ ] No console errors in browser DevTools
- [ ] Static assets load (CSS, JS, images)
- [ ] Favicon displays correctly

### OAuth Flow Testing

- [ ] "Login with Discord" button works
- [ ] OAuth redirect to Discord successful
- [ ] Redirect back to agent.danvan.xyz successful
- [ ] User session created
- [ ] User profile displays correctly
- [ ] Logout works
- [ ] Session persistence works (refresh page)
- [ ] Multiple OAuth providers tested (if configured)

### API Testing

- [ ] Health endpoint works (`curl https://agent.danvan.xyz/api/health`)
- [ ] API returns JSON responses
- [ ] Authentication required for protected endpoints
- [ ] CORS headers present and correct
- [ ] Rate limiting works (if configured)

### WebSocket Testing

- [ ] WebSocket connection establishes
- [ ] Real-time updates work
- [ ] Connection survives page refresh
- [ ] Reconnection works after disconnect

### Bot Integration Testing

- [ ] Discord bot responds to messages
- [ ] Telegram bot responds to messages
- [ ] Slack bot responds to messages
- [ ] Bot webhooks work (if configured)
- [ ] File uploads work
- [ ] Attachments handled correctly

### Module Testing

- [ ] Research module works (web search)
- [ ] Code executor module works (run Python)
- [ ] File manager module works (create, read documents)
- [ ] Knowledge module works (remember, recall)
- [ ] Claude Code module works (if configured)
- [ ] Deployer module works (if configured)
- [ ] Custom modules work (test each)

### Database Testing

- [ ] Conversations persisted correctly
- [ ] User data stored properly
- [ ] Messages saved to database
- [ ] Token usage tracked
- [ ] Memory summaries created
- [ ] Database queries performant

### File Storage Testing

- [ ] Files upload to MinIO
- [ ] Files accessible via public URL
- [ ] File permissions correct
- [ ] Large files (10MB+) upload successfully
- [ ] File downloads work

## Security Validation

### SSL/TLS Security

- [ ] TLS 1.2 and 1.3 enabled only
- [ ] Strong cipher suites configured
- [ ] SSL Labs test passed (A rating)
- [ ] Certificate transparency verified

### Application Security

- [ ] Security headers present (X-Frame-Options, etc.)
- [ ] CSRF protection enabled
- [ ] XSS protection headers set
- [ ] SQL injection prevention verified
- [ ] Input validation working
- [ ] Rate limiting configured

### Access Control

- [ ] Guest users have limited permissions
- [ ] User permissions enforced
- [ ] Admin tools restricted
- [ ] Owner-only modules protected
- [ ] Token budgets enforced

### Data Protection

- [ ] Database password secure
- [ ] API keys not exposed in logs
- [ ] Credentials encrypted at rest
- [ ] No sensitive data in error messages
- [ ] CORS restricted to production domain

## Monitoring and Logging

### Application Monitoring

- [ ] Logs accessible (`make logs`)
- [ ] Log rotation configured
- [ ] Error tracking setup (optional: Sentry)
- [ ] Uptime monitoring configured (optional)
- [ ] Alert system configured (optional)

### System Monitoring

- [ ] CPU usage monitored
- [ ] Memory usage monitored
- [ ] Disk space monitored
- [ ] Network traffic monitored
- [ ] Docker container health monitored

### Database Monitoring

- [ ] PostgreSQL logs accessible
- [ ] Slow query logging enabled
- [ ] Connection pool monitored
- [ ] Database size tracked

### Log Analysis

- [ ] Nginx access logs reviewed
- [ ] Nginx error logs reviewed
- [ ] Application logs reviewed
- [ ] No critical errors in logs
- [ ] Warning patterns identified

## Backup and Recovery

### Backup Configuration

- [ ] Database backup script created
- [ ] Backup cron job scheduled (daily)
- [ ] Backup storage location configured
- [ ] Backup retention policy defined (30 days)
- [ ] Full system backup taken

### Backup Testing

- [ ] Database backup tested
- [ ] Backup restore tested on separate environment
- [ ] Backup files encrypted (optional)
- [ ] Offsite backup configured (recommended)

### Recovery Plan

- [ ] Disaster recovery plan documented
- [ ] Rollback procedure documented
- [ ] Team members trained on recovery
- [ ] Recovery time objective (RTO) defined
- [ ] Recovery point objective (RPO) defined

## Performance Optimization

### Frontend Performance

- [ ] Static assets cached (1 year expiry)
- [ ] Gzip/Brotli compression enabled
- [ ] Images optimized
- [ ] JavaScript minified
- [ ] CSS minified
- [ ] Lighthouse score checked (>90 recommended)

### Backend Performance

- [ ] Database indexes created
- [ ] Query performance optimized
- [ ] Connection pooling configured
- [ ] Redis caching utilized
- [ ] API response times acceptable (<500ms)

### Infrastructure Performance

- [ ] Container resource limits set
- [ ] PostgreSQL tuned for workload
- [ ] Nginx worker processes optimized
- [ ] Disk I/O optimized (SSD recommended)

## Documentation

### Internal Documentation

- [ ] Deployment process documented
- [ ] Configuration variables documented
- [ ] Troubleshooting guide created
- [ ] Team runbook created
- [ ] Architecture diagram updated

### User Documentation

- [ ] User guide available
- [ ] OAuth setup instructions clear
- [ ] Module documentation complete
- [ ] FAQ created
- [ ] Support contact information provided

## Post-Deployment

### User Communication

- [ ] Deployment announcement prepared
- [ ] Known issues documented
- [ ] Feature highlights prepared
- [ ] User migration guide (if applicable)

### Team Handoff

- [ ] Deployment notes shared with team
- [ ] Access credentials shared securely
- [ ] On-call schedule established
- [ ] Escalation path defined

### Final Verification

- [ ] Production URL bookmarked
- [ ] Monitoring dashboards bookmarked
- [ ] Emergency contacts documented
- [ ] All stakeholders notified

### Post-Launch Monitoring

- [ ] Monitor for 24 hours post-launch
- [ ] Check logs hourly for first day
- [ ] Track user signups and activity
- [ ] Monitor error rates
- [ ] Collect user feedback

## Rollback Plan

In case of critical issues:

- [ ] Rollback procedure documented
- [ ] Previous version tagged in git
- [ ] Database backup available
- [ ] Rollback tested in staging
- [ ] Team trained on rollback process

**Rollback Steps:**
1. Stop all services: `make down`
2. Checkout previous version: `git checkout <tag>`
3. Rebuild: `make build`
4. Restore database backup (if needed)
5. Start services: `make up`
6. Verify functionality

## Success Criteria

Deployment is considered successful when:

- [ ] Website accessible at https://agent.danvan.xyz
- [ ] No SSL warnings or errors
- [ ] OAuth login works for all providers
- [ ] Bot integrations functional
- [ ] All modules operational
- [ ] No critical errors in logs
- [ ] Performance metrics acceptable
- [ ] Security scans passed
- [ ] Backup system working
- [ ] Monitoring active

## Notes

**Deployment Date:** _________________

**Deployed By:** _________________

**Version/Tag:** _________________

**Issues Encountered:**
-
-
-

**Post-Deployment Actions:**
-
-
-

**Sign-off:**
- Deployed by: _________________ Date: _________
- Reviewed by: _________________ Date: _________
- Approved by: _________________ Date: _________

---

**Related Documentation:**
- [Deployment Guide](DEPLOYMENT.md)
- [Brand Guidelines](BRANDING.md)
- [Module Documentation](modules/)
- [Project README](../../README.md)
