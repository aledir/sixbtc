-- ==============================================================================
-- SIXBTC DATABASE INITIALIZATION
-- ==============================================================================
-- This script is automatically executed by PostgreSQL on container startup
-- Creates necessary extensions and performs initial setup

-- Enable UUID extension (for unique strategy IDs)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for text search (pattern matching)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create database if it doesn't exist (PostgreSQL 15+)
-- Note: This is redundant if DB is created via POSTGRES_DB env var
-- but included for completeness

-- Grant necessary permissions
-- (user already has permissions via POSTGRES_USER)

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'SixBTC database initialized successfully';
END $$;
