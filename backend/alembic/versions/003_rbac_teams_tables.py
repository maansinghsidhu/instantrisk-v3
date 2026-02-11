"""RBAC and Teams tables

Revision ID: 003_rbac_teams
Revises: 002c9bbaa628
Create Date: 2026-01-25 15:00:00.000000

This migration creates tables for Role-Based Access Control (RBAC):
- permissions: Granular permissions for resources and actions
- roles: Named roles with permission collections
- role_permissions: Many-to-many association
- teams: Organizational teams within syndicates
- team_memberships: User-team-role associations
- user_permission_cache: Performance optimization cache
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_rbac_teams'
down_revision: Union[str, None] = '002c9bbaa628'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # Create permissions table
    # ==========================================================================
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('resource', sa.String(50), nullable=False, index=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('resource', 'action', name='uq_permission_resource_action'),
    )
    op.create_index('idx_permission_resource', 'permissions', ['resource'])

    # ==========================================================================
    # Create roles table
    # ==========================================================================
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('syndicate_id', sa.Integer(), sa.ForeignKey('syndicates.id'), nullable=True),
        sa.Column('hierarchy_level', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_role_syndicate', 'roles', ['syndicate_id'])

    # ==========================================================================
    # Create role_permissions association table
    # ==========================================================================
    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', sa.Integer(), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
    )

    # ==========================================================================
    # Create team_type enum
    # ==========================================================================
    team_type_enum = postgresql.ENUM(
        'underwriting', 'claims', 'compliance', 'operations', 'executive', 'technical', 'custom',
        name='teamtype',
        create_type=True
    )
    team_type_enum.create(op.get_bind(), checkfirst=True)

    # ==========================================================================
    # Create teams table
    # ==========================================================================
    op.create_table(
        'teams',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('syndicate_id', sa.Integer(), sa.ForeignKey('syndicates.id'), nullable=False, index=True),
        sa.Column('team_type', team_type_enum, nullable=False, server_default='underwriting'),
        sa.Column('team_code', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('classes_of_business', postgresql.ARRAY(sa.String()), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('syndicate_id', 'name', name='uq_team_syndicate_name'),
    )
    op.create_index('idx_team_syndicate', 'teams', ['syndicate_id'])
    op.create_index('idx_team_type', 'teams', ['team_type'])

    # ==========================================================================
    # Create team_memberships table
    # ==========================================================================
    op.create_table(
        'team_memberships',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id'), nullable=False, index=True),
        sa.Column('is_team_lead', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('start_date', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('added_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('user_id', 'team_id', name='uq_user_team'),
    )
    op.create_index('idx_membership_user', 'team_memberships', ['user_id'])
    op.create_index('idx_membership_team', 'team_memberships', ['team_id'])
    op.create_index('idx_membership_active', 'team_memberships', ['is_active'])

    # ==========================================================================
    # Create user_permission_cache table
    # ==========================================================================
    op.create_table(
        'user_permission_cache',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('permission_name', sa.String(100), nullable=False, index=True),
        sa.Column('source_team_id', sa.Integer(), nullable=True),
        sa.Column('source_role_id', sa.Integer(), nullable=True),
        sa.Column('cached_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'permission_name', name='uq_user_permission_cache'),
    )
    op.create_index('idx_user_perm_cache', 'user_permission_cache', ['user_id', 'permission_name'])

    # ==========================================================================
    # Seed default permissions
    # ==========================================================================
    permissions_table = sa.table(
        'permissions',
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('resource', sa.String),
        sa.column('action', sa.String),
        sa.column('category', sa.String),
        sa.column('is_active', sa.Boolean),
    )

    default_permissions = [
        # Assessment permissions
        {'name': 'assessment:read', 'description': 'View risk assessments', 'resource': 'assessment', 'action': 'read', 'category': 'underwriting', 'is_active': True},
        {'name': 'assessment:write', 'description': 'Create and edit risk assessments', 'resource': 'assessment', 'action': 'write', 'category': 'underwriting', 'is_active': True},
        {'name': 'assessment:approve', 'description': 'Approve risk assessments', 'resource': 'assessment', 'action': 'approve', 'category': 'underwriting', 'is_active': True},
        {'name': 'assessment:delete', 'description': 'Delete risk assessments', 'resource': 'assessment', 'action': 'delete', 'category': 'underwriting', 'is_active': True},

        # Placement permissions
        {'name': 'placement:read', 'description': 'View subscription placements', 'resource': 'placement', 'action': 'read', 'category': 'underwriting', 'is_active': True},
        {'name': 'placement:write', 'description': 'Create and edit placements', 'resource': 'placement', 'action': 'write', 'category': 'underwriting', 'is_active': True},
        {'name': 'placement:approve', 'description': 'Approve syndicate lines', 'resource': 'placement', 'action': 'approve', 'category': 'underwriting', 'is_active': True},

        # Exposure permissions
        {'name': 'exposure:read', 'description': 'View exposure data and dashboards', 'resource': 'exposure', 'action': 'read', 'category': 'underwriting', 'is_active': True},
        {'name': 'exposure:write', 'description': 'Modify exposure data', 'resource': 'exposure', 'action': 'write', 'category': 'underwriting', 'is_active': True},

        # Compliance permissions
        {'name': 'compliance:read', 'description': 'View compliance submissions and reports', 'resource': 'compliance', 'action': 'read', 'category': 'compliance', 'is_active': True},
        {'name': 'compliance:submit', 'description': 'Submit regulatory filings', 'resource': 'compliance', 'action': 'submit', 'category': 'compliance', 'is_active': True},
        {'name': 'compliance:manage', 'description': 'Manage compliance rules and configurations', 'resource': 'compliance', 'action': 'manage', 'category': 'compliance', 'is_active': True},

        # Pricing/Quote permissions
        {'name': 'pricing:read', 'description': 'View pricing models and results', 'resource': 'pricing', 'action': 'read', 'category': 'underwriting', 'is_active': True},
        {'name': 'pricing:write', 'description': 'Configure pricing models', 'resource': 'pricing', 'action': 'write', 'category': 'underwriting', 'is_active': True},
        {'name': 'quote:read', 'description': 'View quotes', 'resource': 'quote', 'action': 'read', 'category': 'underwriting', 'is_active': True},
        {'name': 'quote:write', 'description': 'Create and issue quotes', 'resource': 'quote', 'action': 'write', 'category': 'underwriting', 'is_active': True},
        {'name': 'quote:approve', 'description': 'Approve quotes', 'resource': 'quote', 'action': 'approve', 'category': 'underwriting', 'is_active': True},

        # Claims permissions
        {'name': 'claims:read', 'description': 'View claims', 'resource': 'claims', 'action': 'read', 'category': 'claims', 'is_active': True},
        {'name': 'claims:write', 'description': 'Create and edit claims', 'resource': 'claims', 'action': 'write', 'category': 'claims', 'is_active': True},
        {'name': 'claims:approve', 'description': 'Approve claim payments', 'resource': 'claims', 'action': 'approve', 'category': 'claims', 'is_active': True},

        # Document permissions
        {'name': 'document:read', 'description': 'View documents', 'resource': 'document', 'action': 'read', 'category': 'general', 'is_active': True},
        {'name': 'document:write', 'description': 'Upload and edit documents', 'resource': 'document', 'action': 'write', 'category': 'general', 'is_active': True},
        {'name': 'document:delete', 'description': 'Delete documents', 'resource': 'document', 'action': 'delete', 'category': 'general', 'is_active': True},

        # Report permissions
        {'name': 'report:read', 'description': 'View reports', 'resource': 'report', 'action': 'read', 'category': 'general', 'is_active': True},
        {'name': 'report:write', 'description': 'Generate and export reports', 'resource': 'report', 'action': 'write', 'category': 'general', 'is_active': True},

        # Team management permissions
        {'name': 'team:manage', 'description': 'Manage teams and team memberships', 'resource': 'team', 'action': 'manage', 'category': 'administration', 'is_active': True},
        {'name': 'team:read', 'description': 'View team information', 'resource': 'team', 'action': 'read', 'category': 'administration', 'is_active': True},

        # User management permissions
        {'name': 'user:manage', 'description': 'Manage user accounts', 'resource': 'user', 'action': 'manage', 'category': 'administration', 'is_active': True},
        {'name': 'user:read', 'description': 'View user information', 'resource': 'user', 'action': 'read', 'category': 'administration', 'is_active': True},

        # Integration permissions
        {'name': 'integration:read', 'description': 'View integration status', 'resource': 'integration', 'action': 'read', 'category': 'administration', 'is_active': True},
        {'name': 'integration:manage', 'description': 'Configure integrations', 'resource': 'integration', 'action': 'manage', 'category': 'administration', 'is_active': True},

        # Audit permissions
        {'name': 'audit:read', 'description': 'View audit logs', 'resource': 'audit', 'action': 'read', 'category': 'administration', 'is_active': True},
    ]

    op.bulk_insert(permissions_table, default_permissions)

    # ==========================================================================
    # Seed default roles
    # ==========================================================================
    roles_table = sa.table(
        'roles',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('is_system_role', sa.Boolean),
        sa.column('is_active', sa.Boolean),
        sa.column('syndicate_id', sa.Integer),
        sa.column('hierarchy_level', sa.Integer),
    )

    default_roles = [
        {'id': 1, 'name': 'Lead Underwriter', 'description': 'Full underwriting authority with approval rights', 'is_system_role': True, 'is_active': True, 'syndicate_id': None, 'hierarchy_level': 30},
        {'id': 2, 'name': 'Senior Underwriter', 'description': 'Experienced underwriter with most permissions', 'is_system_role': True, 'is_active': True, 'syndicate_id': None, 'hierarchy_level': 20},
        {'id': 3, 'name': 'Junior Underwriter', 'description': 'Entry-level underwriter with limited access', 'is_system_role': True, 'is_active': True, 'syndicate_id': None, 'hierarchy_level': 10},
        {'id': 4, 'name': 'Claims Handler', 'description': 'Process and manage claims', 'is_system_role': True, 'is_active': True, 'syndicate_id': None, 'hierarchy_level': 15},
        {'id': 5, 'name': 'Senior Claims Handler', 'description': 'Senior claims authority with approval rights', 'is_system_role': True, 'is_active': True, 'syndicate_id': None, 'hierarchy_level': 25},
        {'id': 6, 'name': 'Compliance Officer', 'description': 'Manage compliance and regulatory submissions', 'is_system_role': True, 'is_active': True, 'syndicate_id': None, 'hierarchy_level': 20},
        {'id': 7, 'name': 'Team Admin', 'description': 'Manage team structure and memberships', 'is_system_role': True, 'is_active': True, 'syndicate_id': None, 'hierarchy_level': 25},
        {'id': 8, 'name': 'Viewer', 'description': 'Read-only access to most resources', 'is_system_role': True, 'is_active': True, 'syndicate_id': None, 'hierarchy_level': 5},
    ]

    op.bulk_insert(roles_table, default_roles)

    # ==========================================================================
    # Seed role-permission associations
    # ==========================================================================
    # First, we need to get the permission IDs
    # We'll use raw SQL to insert the role_permissions

    # Lead Underwriter (id=1) - All underwriting + approval permissions
    lead_underwriter_permissions = [
        'assessment:read', 'assessment:write', 'assessment:approve', 'assessment:delete',
        'placement:read', 'placement:write', 'placement:approve',
        'exposure:read', 'exposure:write',
        'pricing:read', 'pricing:write',
        'quote:read', 'quote:write', 'quote:approve',
        'document:read', 'document:write', 'document:delete',
        'report:read', 'report:write',
        'team:read', 'user:read',
        'compliance:read',
    ]

    # Senior Underwriter (id=2) - Core underwriting without full approval
    senior_underwriter_permissions = [
        'assessment:read', 'assessment:write',
        'placement:read', 'placement:write',
        'exposure:read', 'exposure:write',
        'pricing:read',
        'quote:read', 'quote:write',
        'document:read', 'document:write',
        'report:read',
        'team:read', 'user:read',
    ]

    # Junior Underwriter (id=3) - Mostly read access
    junior_underwriter_permissions = [
        'assessment:read',
        'placement:read',
        'exposure:read',
        'pricing:read',
        'quote:read',
        'document:read',
        'report:read',
        'team:read',
    ]

    # Claims Handler (id=4) - Claims processing
    claims_handler_permissions = [
        'claims:read', 'claims:write',
        'document:read', 'document:write',
        'report:read',
        'team:read',
    ]

    # Senior Claims Handler (id=5) - Claims with approval
    senior_claims_handler_permissions = [
        'claims:read', 'claims:write', 'claims:approve',
        'document:read', 'document:write',
        'report:read', 'report:write',
        'team:read', 'user:read',
    ]

    # Compliance Officer (id=6) - Compliance focus
    compliance_officer_permissions = [
        'compliance:read', 'compliance:submit', 'compliance:manage',
        'assessment:read',
        'exposure:read',
        'document:read', 'document:write',
        'report:read', 'report:write',
        'audit:read',
        'team:read', 'user:read',
    ]

    # Team Admin (id=7) - Team management
    team_admin_permissions = [
        'team:manage', 'team:read',
        'user:manage', 'user:read',
        'audit:read',
        'document:read',
        'report:read',
    ]

    # Viewer (id=8) - Read only
    viewer_permissions = [
        'assessment:read',
        'placement:read',
        'exposure:read',
        'pricing:read',
        'quote:read',
        'claims:read',
        'document:read',
        'report:read',
        'team:read',
        'compliance:read',
    ]

    # Insert role_permissions using raw SQL
    role_perm_mapping = [
        (1, lead_underwriter_permissions),
        (2, senior_underwriter_permissions),
        (3, junior_underwriter_permissions),
        (4, claims_handler_permissions),
        (5, senior_claims_handler_permissions),
        (6, compliance_officer_permissions),
        (7, team_admin_permissions),
        (8, viewer_permissions),
    ]

    connection = op.get_bind()

    for role_id, perm_names in role_perm_mapping:
        for perm_name in perm_names:
            connection.execute(
                sa.text("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT :role_id, id FROM permissions WHERE name = :perm_name
                """),
                {'role_id': role_id, 'perm_name': perm_name}
            )


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_table('user_permission_cache')
    op.drop_table('team_memberships')
    op.drop_table('teams')
    op.drop_table('role_permissions')
    op.drop_table('roles')
    op.drop_table('permissions')

    # Drop enum type
    team_type_enum = postgresql.ENUM(
        'underwriting', 'claims', 'compliance', 'operations', 'executive', 'technical', 'custom',
        name='teamtype'
    )
    team_type_enum.drop(op.get_bind(), checkfirst=True)
