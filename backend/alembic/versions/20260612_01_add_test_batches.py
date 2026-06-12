"""add test batches and Unity project leases

Revision ID: 20260612_01
Revises:
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260612_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("parent_task_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_scene_index", sa.Integer(), nullable=False),
        sa.Column("scene_total", sa.Integer(), nullable=False),
        sa.Column("unity_project_path", sa.String(length=1024), nullable=False),
        sa.Column("unity_project_key", sa.String(length=64), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("decision_version", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["parent_task_id"], ["test_tasks.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_task_id"),
    )
    op.create_index("ix_test_batches_id", "test_batches", ["id"])
    op.create_index("ix_test_batches_parent_task_id", "test_batches", ["parent_task_id"])
    op.create_index("ix_test_batches_project_id", "test_batches", ["project_id"])
    op.create_index("ix_test_batches_status", "test_batches", ["status"])
    op.create_index("ix_test_batches_unity_project_key", "test_batches", ["unity_project_key"])

    op.create_table(
        "test_batch_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("scene_index", sa.Integer(), nullable=False),
        sa.Column("scene_resource_id", sa.String(length=200), nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=True),
        sa.Column("scene_display_name", sa.String(length=200), nullable=False),
        sa.Column("unity_scene_path", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("current_task_id", sa.Integer(), nullable=True),
        sa.Column("current_session_id", sa.Integer(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("attempt_history", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["test_batches.id"]),
        sa.ForeignKeyConstraint(["current_session_id"], ["test_sessions.id"]),
        sa.ForeignKeyConstraint(["current_task_id"], ["test_tasks.id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["scene_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_batch_items_batch_id", "test_batch_items", ["batch_id"])
    op.create_index("ix_test_batch_items_id", "test_batch_items", ["id"])
    op.create_index("ix_test_batch_items_status", "test_batch_items", ["status"])

    op.create_table(
        "unity_project_leases",
        sa.Column("project_key", sa.String(length=64), nullable=False),
        sa.Column("project_path", sa.String(length=1024), nullable=False),
        sa.Column("owner_type", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("parent_task_id", sa.Integer(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_task_id"], ["test_tasks.id"]),
        sa.PrimaryKeyConstraint("project_key"),
    )


def downgrade() -> None:
    op.drop_table("unity_project_leases")
    op.drop_index("ix_test_batch_items_status", table_name="test_batch_items")
    op.drop_index("ix_test_batch_items_id", table_name="test_batch_items")
    op.drop_index("ix_test_batch_items_batch_id", table_name="test_batch_items")
    op.drop_table("test_batch_items")
    op.drop_index("ix_test_batches_unity_project_key", table_name="test_batches")
    op.drop_index("ix_test_batches_status", table_name="test_batches")
    op.drop_index("ix_test_batches_project_id", table_name="test_batches")
    op.drop_index("ix_test_batches_parent_task_id", table_name="test_batches")
    op.drop_index("ix_test_batches_id", table_name="test_batches")
    op.drop_table("test_batches")
