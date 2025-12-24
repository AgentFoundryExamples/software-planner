"""create_jobs_table

Revision ID: 20399264179a
Revises: 
Create Date: 2025-12-24 03:55:54.466219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20399264179a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create jobs table with required columns and indexes."""
    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('job_id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('model', sa.String(255), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('job_id')
    )
    
    # Create indexes for common query patterns
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_created_at', 'jobs', ['created_at'])


def downgrade() -> None:
    """Downgrade schema - drop jobs table and indexes."""
    # Indexes are dropped automatically with the table in PostgreSQL
    op.drop_table('jobs')
