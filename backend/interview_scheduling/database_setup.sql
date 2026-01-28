-- Interview Scheduling Database Schema

-- Main scheduling sessions table
CREATE TABLE IF NOT EXISTS interview_scheduling_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) UNIQUE NOT NULL,
    applicant_name VARCHAR(255) NOT NULL,
    applicant_phone VARCHAR(20) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    position VARCHAR(255) NOT NULL,
    job_id VARCHAR(100),
    candidate_id INTEGER,
    location VARCHAR(255),
    available_slots JSONB NOT NULL,
    conversation_history JSONB DEFAULT '[]',
    selected_date VARCHAR(100),
    selected_time VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',  -- pending, pending_confirmation, confirmed, failed, custom_request
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast phone number lookups
CREATE INDEX IF NOT EXISTS idx_phone ON interview_scheduling_sessions(applicant_phone);
CREATE INDEX IF NOT EXISTS idx_session_id ON interview_scheduling_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_status ON interview_scheduling_sessions(status);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
CREATE TRIGGER update_scheduling_sessions_updated_at 
    BEFORE UPDATE ON interview_scheduling_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
