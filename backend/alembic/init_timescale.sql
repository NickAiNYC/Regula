-- Initialize TimescaleDB extension
-- This script is run automatically by docker-entrypoint-initdb.d

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Enable other useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'TimescaleDB and extensions initialized successfully';
END
$$;
