# Deployment Documentation

Production deployment, infrastructure management, and operations documentation.

## Purpose

This directory contains guides for deploying and operating the agent system in production environments.

## Documents

| Document | Purpose | Read When |
|----------|---------|-----------|
| [Production Setup](production-setup.md) | Production deployment guide | Deploying to production |
| [Secrets Management](secrets-management.md) | API keys and credentials | Managing secrets |
| [Monitoring](monitoring.md) | Observability and alerting | Setting up monitoring |
| [Backup & Restore](backup-restore.md) | Data protection procedures | Implementing backups |
| [Scaling](scaling.md) | Horizontal scaling strategies | Scaling the system |

## Production Checklist

### Before Deployment

- [ ] Configure environment variables in production `.env`
- [ ] Set strong `POSTGRES_PASSWORD` and `PORTAL_API_KEY`
- [ ] Configure LLM API keys (at least one provider)
- [ ] Set up platform bot tokens
- [ ] Configure external service credentials (Jira, Garmin, etc.)
- [ ] Review security settings

### Infrastructure

- [ ] PostgreSQL with persistent volume
- [ ] Redis with persistence enabled
- [ ] MinIO with backup strategy
- [ ] Reverse proxy (nginx) for HTTPS
- [ ] SSL/TLS certificates
- [ ] Firewall rules

### Operations

- [ ] Set up log aggregation
- [ ] Configure health checks
- [ ] Set up monitoring and alerting
- [ ] Implement backup procedures
- [ ] Document recovery procedures
- [ ] Create runbooks for common tasks

## Quick References

### Environment Configuration

See [Production Setup](production-setup.md) for:
- Required vs optional variables
- Security best practices
- Resource limits
- Network configuration

### Secrets

See [Secrets Management](secrets-management.md) for:
- Secret rotation procedures
- Per-user credential storage
- API key management
- Encryption at rest

### Monitoring

See [Monitoring](monitoring.md) for:
- Log aggregation setup
- Metrics to track
- Alert thresholds
- Dashboard configuration

### Backups

See [Backup & Restore](backup-restore.md) for:
- Automated backup scripts
- Restore procedures
- Disaster recovery plans
- Data retention policies

## Related Documentation

- [Architecture/Deployment](../architecture/deployment.md) — Infrastructure architecture
- [Troubleshooting](../troubleshooting/) — Diagnosing production issues

---

[Back to Documentation Index](../INDEX.md)
