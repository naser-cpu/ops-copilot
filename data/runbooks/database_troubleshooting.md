# Database Troubleshooting Guide

## Credit
Auto generated data for demonstration purposes by ChatGPT

## Overview
This guide covers common database issues and their solutions, focusing on PostgreSQL and connection management.

## Common Issues

### Connection Pool Exhaustion

**Symptoms:**
- "connection pool exhausted" errors
- Slow response times
- Intermittent 500 errors

**Diagnosis:**
```sql
-- Check active connections
SELECT count(*), state 
FROM pg_stat_activity 
GROUP BY state;

-- Find long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';
```

**Solutions:**
1. Increase connection pool size (temporary)
2. Find and fix connection leaks in application code
3. Add connection timeouts
4. Implement connection health checks

### Connection Timeouts

**Symptoms:**
- "connection timed out" errors
- Slow initial connections
- Intermittent connectivity

**Diagnosis:**
1. Check network latency between app and database
2. Verify database server load
3. Check for firewall issues

**Solutions:**
1. Increase connection timeout settings
2. Add retry logic with exponential backoff
3. Use connection poolers like PgBouncer
4. Check and optimize network path

### Slow Queries

**Symptoms:**
- High response times
- CPU spikes on database server
- Lock contention

**Diagnosis:**
```sql
-- Enable query logging
SET log_min_duration_statement = 1000;  -- Log queries > 1 second

-- Find missing indexes
SELECT schemaname, tablename, seq_scan, seq_tup_read, 
       idx_scan, idx_tup_fetch
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan;

-- Analyze query plan
EXPLAIN ANALYZE <your_query>;
```

**Solutions:**
1. Add appropriate indexes
2. Optimize query structure
3. Update table statistics: `ANALYZE table_name;`
4. Consider partitioning large tables

### Lock Contention

**Symptoms:**
- Queries hanging
- Deadlock errors
- Transaction timeouts

**Diagnosis:**
```sql
-- Find blocking queries
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

**Solutions:**
1. Keep transactions short
2. Access tables in consistent order
3. Use row-level locking where possible
4. Set appropriate lock timeouts

## Connection String Best Practices

```python
# Recommended connection settings
DATABASE_URL = "postgresql://user:pass@host:5432/db"

# SQLAlchemy engine configuration
engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # Base pool size
    max_overflow=20,        # Allow up to 30 total connections
    pool_pre_ping=True,     # Verify connections before use
    pool_recycle=3600,      # Recycle connections every hour
    connect_args={
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000"  # 30 second query timeout
    }
)
```

## Monitoring Queries

```sql
-- Database size
SELECT pg_database_size(current_database()) / 1024 / 1024 AS size_mb;

-- Table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

-- Cache hit ratio (should be > 99%)
SELECT 
  sum(heap_blks_read) as heap_read,
  sum(heap_blks_hit)  as heap_hit,
  sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
FROM pg_statio_user_tables;
```

## Emergency Procedures

### Kill All Connections to Database
```sql
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'your_database' AND pid <> pg_backend_pid();
```

### Force Checkpoint
```sql
CHECKPOINT;
```

### Vacuum Full (Use with Caution)
```sql
VACUUM FULL ANALYZE table_name;
```
