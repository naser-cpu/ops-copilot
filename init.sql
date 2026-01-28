-- Initialize database schema and seed data

-- Requests table (main table for tracking lab requests)
CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text TEXT NOT NULL,
    priority VARCHAR(10) NOT NULL DEFAULT 'normal',
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    plan JSONB,
    tool_calls JSONB DEFAULT '[]'::jsonb,
    result JSONB,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Index for status queries
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at DESC);

-- Incidents table (for query_incidents tool)
CREATE TABLE IF NOT EXISTS incidents (
    id VARCHAR(20) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    service VARCHAR(100),
    root_cause TEXT,
    resolution TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    tags TEXT[]
);

-- Index for incident searches
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_service ON incidents(service);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at DESC);

-- Seed sample incidents
INSERT INTO incidents (id, title, description, severity, status, service, root_cause, resolution, created_at, resolved_at, tags) VALUES
(
    'INC-001',
    'Database connection pool exhaustion',
    'Production database experiencing connection pool exhaustion causing intermittent 500 errors. Multiple services affected.',
    'critical',
    'resolved',
    'postgres-primary',
    'Connection leak in payment service due to missing connection.close() in error handler',
    'Fixed connection handling in payment service, increased pool size from 20 to 50 as temporary measure',
    NOW() - INTERVAL '7 days',
    NOW() - INTERVAL '6 days 18 hours',
    ARRAY['database', 'connection-pool', 'payment-service']
),
(
    'INC-002',
    'Redis cluster failover during peak traffic',
    'Redis sentinel triggered automatic failover during Black Friday traffic spike. 2 minute service degradation.',
    'high',
    'resolved',
    'redis-cluster',
    'Memory pressure on primary node exceeded threshold, triggering premature failover',
    'Increased memory limits, tuned sentinel timing parameters, added read replicas',
    NOW() - INTERVAL '14 days',
    NOW() - INTERVAL '14 days' + INTERVAL '2 hours',
    ARRAY['redis', 'failover', 'high-traffic']
),
(
    'INC-003',
    'API gateway timeout errors',
    'Intermittent 504 Gateway Timeout errors on /api/v2/orders endpoint during morning traffic.',
    'medium',
    'resolved',
    'api-gateway',
    'Slow database queries due to missing index on orders.customer_id column',
    'Added composite index on orders(customer_id, created_at), query time reduced from 2s to 50ms',
    NOW() - INTERVAL '3 days',
    NOW() - INTERVAL '2 days 20 hours',
    ARRAY['api', 'timeout', 'database', 'indexing']
),
(
    'INC-004',
    'Memory leak in worker service',
    'Worker pods being OOMKilled every 4-6 hours. Gradual memory increase observed.',
    'high',
    'resolved',
    'worker-service',
    'Large objects not being garbage collected due to circular references in task results',
    'Refactored result handling to break circular references, added explicit cleanup in task completion',
    NOW() - INTERVAL '21 days',
    NOW() - INTERVAL '20 days',
    ARRAY['memory-leak', 'kubernetes', 'oom']
),
(
    'INC-005',
    'SSL certificate expiration',
    'SSL certificate for api.example.com expired causing service outage for external clients.',
    'critical',
    'resolved',
    'infrastructure',
    'Certificate renewal automation failed silently, monitoring did not catch expiration warning',
    'Renewed certificate manually, fixed cert-manager configuration, added expiration alerts at 30/14/7 days',
    NOW() - INTERVAL '30 days',
    NOW() - INTERVAL '30 days' + INTERVAL '45 minutes',
    ARRAY['ssl', 'certificate', 'automation']
),
(
    'INC-006',
    'Disk space alert on logging cluster',
    'Elasticsearch cluster disk usage at 85%, approaching critical threshold.',
    'medium',
    'open',
    'elasticsearch',
    NULL,
    NULL,
    NOW() - INTERVAL '1 day',
    NULL,
    ARRAY['elasticsearch', 'disk-space', 'logging']
),
(
    'INC-007',
    'High CPU usage on authentication service',
    'Authentication service pods showing sustained 90%+ CPU usage. Login latency increased.',
    'high',
    'investigating',
    'auth-service',
    NULL,
    NULL,
    NOW() - INTERVAL '2 hours',
    NULL,
    ARRAY['cpu', 'performance', 'authentication']
),
(
    'INC-008',
    'Kafka consumer lag increasing',
    'Consumer group order-processor showing increasing lag on orders topic. Processing delay of 5+ minutes.',
    'medium',
    'open',
    'kafka',
    NULL,
    NULL,
    NOW() - INTERVAL '4 hours',
    NULL,
    ARRAY['kafka', 'consumer-lag', 'orders']
);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for requests table
DROP TRIGGER IF EXISTS update_requests_updated_at ON requests;
CREATE TRIGGER update_requests_updated_at
    BEFORE UPDATE ON requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
