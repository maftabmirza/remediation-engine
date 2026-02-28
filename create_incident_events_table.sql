-- Create incident_events table with all required columns
CREATE TABLE IF NOT EXISTS incident_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id VARCHAR(255) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50),
    severity VARCHAR(50),
    priority VARCHAR(50),
    service_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    assignee VARCHAR(255),
    source VARCHAR(100),
    incident_metadata JSONB DEFAULT '{}',
    is_open BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    analyzed BOOLEAN DEFAULT FALSE,
    analyzed_at TIMESTAMP WITH TIME ZONE,
    analyzed_by UUID REFERENCES users(id),
    ai_analysis TEXT,
    recommendations_json JSONB DEFAULT '[]',
    llm_provider_id UUID REFERENCES llm_providers(id),
    analysis_count INTEGER DEFAULT 0
);

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_incident_events_incident_id ON incident_events (incident_id);
CREATE INDEX IF NOT EXISTS ix_incident_events_status ON incident_events (status);
CREATE INDEX IF NOT EXISTS ix_incident_events_severity ON incident_events (severity);
CREATE INDEX IF NOT EXISTS ix_incident_events_priority ON incident_events (priority);
CREATE INDEX IF NOT EXISTS ix_incident_events_service_name ON incident_events (service_name);
CREATE INDEX IF NOT EXISTS ix_incident_events_created_at ON incident_events (created_at);
CREATE INDEX IF NOT EXISTS ix_incident_events_source ON incident_events (source);
CREATE INDEX IF NOT EXISTS ix_incident_events_is_open ON incident_events (is_open);
CREATE INDEX IF NOT EXISTS ix_incident_events_analyzed ON incident_events (analyzed);
