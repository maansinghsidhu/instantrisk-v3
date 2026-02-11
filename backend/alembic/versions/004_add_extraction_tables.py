"""Add extraction tables for intelligent document extraction

Revision ID: 004_extraction
Revises: 003  (adjust based on your actual revision chain)
Create Date: 2025-01-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_extraction'
down_revision = None  # Adjust to point to previous migration
branch_labels = None
depends_on = None


def upgrade():
    """Create extraction-related tables."""

    # Create document_extractions table
    op.create_table(
        'document_extractions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('detected_type', sa.String(50), nullable=False),
        sa.Column('type_confidence', sa.Float(), nullable=False, default=0.0),
        sa.Column('type_confidence_level', sa.String(20), nullable=False),
        sa.Column('matched_keywords', postgresql.JSON(astext_type=sa.Text()), default=[]),
        sa.Column('matched_sections', postgresql.JSON(astext_type=sa.Text()), default=[]),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('extracted_data', postgresql.JSON(astext_type=sa.Text()), default={}),
        sa.Column('is_valid', sa.Boolean(), nullable=False, default=False),
        sa.Column('completeness_score', sa.Float(), default=0.0),
        sa.Column('required_fields_found', postgresql.JSON(astext_type=sa.Text()), default=[]),
        sa.Column('required_fields_missing', postgresql.JSON(astext_type=sa.Text()), default=[]),
        sa.Column('validation_errors', postgresql.JSON(astext_type=sa.Text()), default=[]),
        sa.Column('validation_warnings', postgresql.JSON(astext_type=sa.Text()), default=[]),
        sa.Column('overall_confidence', sa.Float(), default=0.0),
        sa.Column('overall_confidence_level', sa.String(20), nullable=False),
        sa.Column('fields_requiring_review', postgresql.JSON(astext_type=sa.Text()), default=[]),
        sa.Column('processing_time_ms', sa.Float(), default=0.0),
        sa.Column('rag_context_used', sa.Boolean(), default=False),
        sa.Column('similar_documents_found', sa.Integer(), default=0),
        sa.Column('raw_text_hash', sa.String(64), nullable=True),
        sa.Column('reviewed', sa.Boolean(), default=False),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_extraction_doc_status', 'document_extractions', ['document_id', 'status'])
    op.create_index('ix_extraction_confidence', 'document_extractions', ['overall_confidence'])
    op.create_index('ix_extraction_type', 'document_extractions', ['detected_type'])
    op.create_index(op.f('ix_document_extractions_id'), 'document_extractions', ['id'])

    # Create extraction_corrections table
    op.create_table(
        'extraction_corrections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('extraction_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('field_path', sa.String(255), nullable=True),
        sa.Column('original_value', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('corrected_value', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('original_confidence', sa.Float(), nullable=True),
        sa.Column('extraction_pattern', sa.Text(), nullable=True),
        sa.Column('correction_type', sa.String(30), nullable=False),
        sa.Column('correction_reason', sa.Text(), nullable=True),
        sa.Column('corrected_by', sa.Integer(), nullable=False),
        sa.Column('applied_to_model', sa.Boolean(), default=False),
        sa.Column('pattern_improvement_suggested', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['extraction_id'], ['document_extractions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['corrected_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_correction_field', 'extraction_corrections', ['field_name', 'correction_type'])
    op.create_index('ix_correction_user', 'extraction_corrections', ['corrected_by', 'created_at'])
    op.create_index(op.f('ix_extraction_corrections_id'), 'extraction_corrections', ['id'])
    op.create_index(op.f('ix_extraction_corrections_extraction_id'), 'extraction_corrections', ['extraction_id'])

    # Create training_samples table
    op.create_table(
        'training_samples',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sample_id', sa.String(100), nullable=False),
        sa.Column('extraction_id', sa.Integer(), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('text_hash', sa.String(64), nullable=False),
        sa.Column('extracted_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('ground_truth', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('has_ground_truth', sa.Boolean(), default=False),
        sa.Column('overall_confidence', sa.Float(), default=0.0),
        sa.Column('used_for_training', sa.Boolean(), default=False),
        sa.Column('training_batch', sa.String(50), nullable=True),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(50), default='extraction'),
        sa.Column('quality_score', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['extraction_id'], ['document_extractions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sample_id', name='uq_training_sample_id'),
        sa.UniqueConstraint('text_hash', name='uq_training_sample_text')
    )
    op.create_index('ix_sample_type_truth', 'training_samples', ['document_type', 'has_ground_truth'])
    op.create_index('ix_sample_training', 'training_samples', ['used_for_training', 'quality_score'])
    op.create_index(op.f('ix_training_samples_id'), 'training_samples', ['id'])
    op.create_index(op.f('ix_training_samples_sample_id'), 'training_samples', ['sample_id'])

    # Create extraction_accuracy_metrics table
    op.create_table(
        'extraction_accuracy_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('document_type', sa.String(50), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_extractions', sa.Integer(), default=0),
        sa.Column('total_corrections', sa.Integer(), default=0),
        sa.Column('accuracy_rate', sa.Float(), default=0.0),
        sa.Column('missing_value_count', sa.Integer(), default=0),
        sa.Column('false_positive_count', sa.Integer(), default=0),
        sa.Column('wrong_value_count', sa.Integer(), default=0),
        sa.Column('formatting_count', sa.Integer(), default=0),
        sa.Column('high_confidence_count', sa.Integer(), default=0),
        sa.Column('medium_confidence_count', sa.Integer(), default=0),
        sa.Column('low_confidence_count', sa.Integer(), default=0),
        sa.Column('avg_confidence_when_corrected', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('field_name', 'document_type', 'period_start', name='uq_metric_scope_period')
    )
    op.create_index('ix_metric_scope', 'extraction_accuracy_metrics', ['field_name', 'document_type'])
    op.create_index('ix_metric_period', 'extraction_accuracy_metrics', ['period_start', 'period_end'])
    op.create_index(op.f('ix_extraction_accuracy_metrics_id'), 'extraction_accuracy_metrics', ['id'])

    # Create extraction_patterns table
    op.create_table(
        'extraction_patterns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('document_type', sa.String(50), nullable=True),
        sa.Column('pattern_regex', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('capture_group', sa.Integer(), default=1),
        sa.Column('requires_cleaning', sa.Boolean(), default=False),
        sa.Column('cleaning_function', sa.String(100), nullable=True),
        sa.Column('times_used', sa.Integer(), default=0),
        sa.Column('times_correct', sa.Integer(), default=0),
        sa.Column('times_corrected', sa.Integer(), default=0),
        sa.Column('accuracy_rate', sa.Float(), default=0.0),
        sa.Column('avg_confidence', sa.Float(), default=0.0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('source', sa.String(50), default='manual'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('field_name', 'document_type', 'pattern_regex', name='uq_pattern')
    )
    op.create_index('ix_pattern_field_type', 'extraction_patterns', ['field_name', 'document_type'])
    op.create_index('ix_pattern_active_priority', 'extraction_patterns', ['is_active', 'priority'])
    op.create_index(op.f('ix_extraction_patterns_id'), 'extraction_patterns', ['id'])


def downgrade():
    """Drop extraction-related tables."""
    op.drop_table('extraction_patterns')
    op.drop_table('extraction_accuracy_metrics')
    op.drop_table('training_samples')
    op.drop_table('extraction_corrections')
    op.drop_table('document_extractions')
