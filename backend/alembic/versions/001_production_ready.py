"""Production database optimizations with TimescaleDB

Revision ID: 001_production_ready
Revises: 
Create Date: 2025-01-16 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_production_ready'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Production-ready database setup with:
    - TimescaleDB hypertables for time-series data
    - Optimized indexes for common queries
    - Row-level security policies for multi-tenancy
    - Partitioning for large-scale storage
    """
    
    # Create enum types
    op.execute("""
        CREATE TYPE subscription_tier AS ENUM ('trial', 'basic', 'professional', 'enterprise');
        CREATE TYPE claim_status AS ENUM ('pending', 'processed', 'violation', 'appealed', 'resolved');
        CREATE TYPE appeal_status AS ENUM ('draft', 'submitted', 'under_review', 'approved', 'denied');
    """)
    
    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('npi_number', sa.String(10), nullable=True, unique=True),
        sa.Column('geographic_region', sa.String(50), nullable=False),
        sa.Column('subscription_tier', postgresql.ENUM('trial', 'basic', 'professional', 'enterprise', name='subscription_tier'), nullable=False, server_default='trial'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('mfa_secret', sa.String(32), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Providers table
    op.create_table(
        'providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('npi', sa.String(10), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('specialty', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Claims table (will be converted to hypertable)
    op.create_table(
        'claims',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('providers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('claim_id', sa.String(50), nullable=False),
        sa.Column('payer_id', sa.String(50), nullable=False),
        sa.Column('payer_name', sa.String(255), nullable=True),
        sa.Column('patient_id', sa.String(50), nullable=True),
        sa.Column('service_date', sa.Date(), nullable=False),
        sa.Column('cpt_code', sa.String(10), nullable=False),
        sa.Column('billed_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('paid_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('mandate_rate', sa.Numeric(10, 2), nullable=True),
        sa.Column('is_violation', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('violation_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'processed', 'violation', 'appealed', 'resolved', name='claim_status'), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )
    
    # Appeals table
    op.create_table(
        'appeals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('claim_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('claims.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', postgresql.ENUM('draft', 'submitted', 'under_review', 'approved', 'denied', name='appeal_status'), nullable=False, server_default='draft'),
        sa.Column('submitted_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('appeal_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('recovered_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Rate database table
    op.create_table(
        'rate_database',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('cpt_code', sa.String(10), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('base_rate', sa.Numeric(10, 2), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('cola_percentage', sa.Numeric(5, 4), nullable=False, server_default='0.0284'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Audit log table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('changes', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    
    # Convert claims table to TimescaleDB hypertable
    op.execute("""
        SELECT create_hypertable('claims', 'service_date', 
            chunk_time_interval => INTERVAL '1 month',
            if_not_exists => TRUE
        );
    """)
    
    # Create optimized indexes
    # Organizations
    op.create_index('idx_organizations_npi', 'organizations', ['npi_number'])
    op.create_index('idx_organizations_active', 'organizations', ['is_active'])
    
    # Users
    op.create_index('idx_users_org', 'users', ['organization_id'])
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_active', 'users', ['is_active'])
    
    # Providers
    op.create_index('idx_providers_org', 'providers', ['organization_id'])
    op.create_index('idx_providers_npi', 'providers', ['npi'])
    
    # Claims (time-series optimized)
    op.create_index('idx_claims_org_date', 'claims', ['organization_id', 'service_date'], postgresql_using='btree')
    op.create_index('idx_claims_payer_date', 'claims', ['payer_id', 'service_date'], postgresql_using='btree')
    op.create_index('idx_claims_provider', 'claims', ['provider_id'])
    op.create_index('idx_claims_violation', 'claims', ['is_violation', 'service_date'], postgresql_using='btree')
    op.create_index('idx_claims_status', 'claims', ['status'])
    op.create_index('idx_claims_cpt', 'claims', ['cpt_code'])
    
    # Appeals
    op.create_index('idx_appeals_org', 'appeals', ['organization_id'])
    op.create_index('idx_appeals_claim', 'appeals', ['claim_id'])
    op.create_index('idx_appeals_status', 'appeals', ['status'])
    
    # Rate database
    op.create_index('idx_rates_cpt_date', 'rate_database', ['cpt_code', 'effective_date'])
    op.create_index('idx_rates_active', 'rate_database', ['is_active'])
    
    # Audit logs (time-series)
    op.create_index('idx_audit_org_created', 'audit_logs', ['organization_id', 'created_at'])
    op.create_index('idx_audit_user', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    
    # Enable Row-Level Security
    op.execute("""
        -- Enable RLS on all multi-tenant tables
        ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
        ALTER TABLE users ENABLE ROW LEVEL SECURITY;
        ALTER TABLE providers ENABLE ROW LEVEL SECURITY;
        ALTER TABLE claims ENABLE ROW LEVEL SECURITY;
        ALTER TABLE appeals ENABLE ROW LEVEL SECURITY;
        ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
        
        -- Create RLS policies for organizations
        CREATE POLICY org_isolation_policy ON organizations
            USING (id = current_setting('app.current_org_id', TRUE)::uuid);
        
        -- Create RLS policies for users
        CREATE POLICY user_isolation_policy ON users
            USING (organization_id = current_setting('app.current_org_id', TRUE)::uuid);
        
        -- Create RLS policies for providers
        CREATE POLICY provider_isolation_policy ON providers
            USING (organization_id = current_setting('app.current_org_id', TRUE)::uuid);
        
        -- Create RLS policies for claims
        CREATE POLICY claim_isolation_policy ON claims
            USING (organization_id = current_setting('app.current_org_id', TRUE)::uuid);
        
        -- Create RLS policies for appeals
        CREATE POLICY appeal_isolation_policy ON appeals
            USING (organization_id = current_setting('app.current_org_id', TRUE)::uuid);
        
        -- Create RLS policies for audit logs
        CREATE POLICY audit_isolation_policy ON audit_logs
            USING (organization_id = current_setting('app.current_org_id', TRUE)::uuid);
    """)
    
    # Create updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Add updated_at triggers
    for table in ['organizations', 'users', 'providers', 'claims', 'appeals', 'rate_database']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)
    
    # Create data retention policy for old claims (keep 7 years for compliance)
    op.execute("""
        SELECT add_retention_policy('claims', INTERVAL '7 years', if_not_exists => TRUE);
    """)
    
    # Create continuous aggregates for performance
    op.execute("""
        -- Daily violation summary
        CREATE MATERIALIZED VIEW IF NOT EXISTS claims_daily_summary
        WITH (timescaledb.continuous) AS
        SELECT 
            time_bucket('1 day', service_date) AS day,
            organization_id,
            payer_id,
            COUNT(*) as total_claims,
            SUM(CASE WHEN is_violation THEN 1 ELSE 0 END) as violation_count,
            SUM(violation_amount) as total_violation_amount,
            AVG(paid_amount) as avg_paid_amount
        FROM claims
        GROUP BY day, organization_id, payer_id;
        
        -- Add refresh policy (every hour)
        SELECT add_continuous_aggregate_policy('claims_daily_summary',
            start_offset => INTERVAL '1 month',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        );
    """)


def downgrade() -> None:
    """Revert production optimizations"""
    
    # Drop continuous aggregates
    op.execute("DROP MATERIALIZED VIEW IF EXISTS claims_daily_summary CASCADE;")
    
    # Drop triggers
    for table in ['organizations', 'users', 'providers', 'claims', 'appeals', 'rate_database']:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")
    
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    # Disable RLS
    for table in ['organizations', 'users', 'providers', 'claims', 'appeals', 'audit_logs']:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    
    # Drop tables
    op.drop_table('audit_logs')
    op.drop_table('rate_database')
    op.drop_table('appeals')
    op.drop_table('claims')
    op.drop_table('providers')
    op.drop_table('users')
    op.drop_table('organizations')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS appeal_status;")
    op.execute("DROP TYPE IF EXISTS claim_status;")
    op.execute("DROP TYPE IF EXISTS subscription_tier;")
