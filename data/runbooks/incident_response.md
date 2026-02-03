# Incident Response Runbook
##### Credit
Auto generated data for demonstration purposes by ChatGPT


## Overview
This runbook provides guidance on responding to production incidents, from initial detection through resolution and post-mortem.

## Severity Levels

### Critical (P1)
- Complete service outage
- Data loss or corruption
- Security breach
- Response time: Immediate (< 15 minutes)

### High (P2)
- Major feature unavailable
- Significant performance degradation
- Response time: < 30 minutes

### Medium (P3)
- Minor feature issues
- Limited user impact
- Response time: < 4 hours

### Low (P4)
- Cosmetic issues
- No user impact
- Response time: Next business day

## Incident Response Steps

1. **Acknowledge and Assess**
   - Confirm the incident is real
   - Assess initial impact and severity
   - Open incident channel in Slack: #incident-YYYY-MM-DD

2. **Assemble Response Team**
   - Incident Commander (IC): Coordinates response
   - Technical Lead: Drives investigation
   - Communications Lead: Updates stakeholders

3. **Investigate and Diagnose**
   - Check monitoring dashboards
   - Review recent deployments
   - Examine logs in Elasticsearch
   - Check infrastructure health

4. **Contain and Mitigate**
   - Implement temporary fixes
   - Consider rollback if deployment-related
   - Scale resources if capacity issue

5. **Resolve**
   - Deploy permanent fix
   - Verify fix effectiveness
   - Monitor for regression

6. **Close and Document**
   - Update status page
   - Notify stakeholders
   - Schedule post-mortem

## Useful Commands

### Check Service Health
```bash
kubectl get pods -n production
kubectl describe pod <pod-name> -n production
kubectl logs <pod-name> -n production --tail=100
```

### Rollback Deployment
```bash
kubectl rollout undo deployment/<service-name> -n production
kubectl rollout status deployment/<service-name> -n production
```

### Database Queries
```sql
-- Check connection count
SELECT count(*) FROM pg_stat_activity;

-- Kill idle connections
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' AND query_start < now() - interval '1 hour';
```

## Escalation Contacts

| Role | Primary | Secondary |
|------|---------|-----------|
| On-call Engineer | PagerDuty | Slack #oncall |
| Database Admin | @db-team | dba@company.com |
| Infrastructure | @infra-team | infra@company.com |
| Security | @security-team | security@company.com |

## Post-Mortem Template

1. Incident Summary
2. Timeline of Events
3. Root Cause Analysis
4. Impact Assessment
5. What Went Well
6. What Could Be Improved
7. Action Items
