"""Add server-authoritative community, interaction, and submission state."""

import sqlalchemy as sa
from alembic import op

revision = "20261015_0009"
down_revision = "20261014_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_entities",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column("workspace_id", sa.String(100), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("provenance", sa.String(32), nullable=False),
        sa.Column("catalog_version", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("workspace_id", "kind", "slug", name="uq_community_entity_slug"),
    )
    op.create_index("ix_community_entity_feed", "community_entities", ["workspace_id", "kind", "status"])
    op.create_table(
        "community_respects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("content_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("user_id", "workspace_id", "content_id", name="uq_community_respect_owner"),
    )
    op.create_table(
        "community_comments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("content_id", sa.String(200), nullable=False),
        sa.Column("author_user_id", sa.String(200), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("parent_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_community_comment_content", "community_comments", ["workspace_id", "content_id", "created_at"])
    op.create_table(
        "community_annotations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("content_id", sa.String(200), nullable=False),
        sa.Column("author_user_id", sa.String(200), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("timestamp_seconds", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("source_ids_json", sa.JSON(), nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_community_annotation_content", "community_annotations", ["workspace_id", "content_id", "timestamp_seconds"])
    op.create_table(
        "community_submissions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("owner_user_id", sa.String(200), nullable=False),
        sa.Column("submission_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(4000), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("reviewer_note", sa.String(2000), nullable=False, server_default=""),
        sa.Column("reviewed_by", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("submitted_at", sa.String(40), nullable=False, server_default=""),
        sa.Column("published_at", sa.String(40), nullable=False, server_default=""),
    )
    op.create_index("ix_community_submission_owner", "community_submissions", ["workspace_id", "owner_user_id", "updated_at"])
    op.create_index("ix_community_submission_queue", "community_submissions", ["workspace_id", "status", "updated_at"])
    op.create_table(
        "community_submission_revisions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("submission_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["community_submissions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("submission_id", "version", name="uq_community_submission_revision"),
    )
    op.create_table(
        "community_submission_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("submission_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("actor_user_id", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=False),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["community_submissions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_community_submission_event", "community_submission_events", ["submission_id", "created_at"])
    op.create_table(
        "community_import_receipts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("workspace_id", sa.String(100), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("user_id", "workspace_id", "fingerprint", name="uq_community_import_fingerprint"),
    )


def downgrade() -> None:
    op.drop_table("community_import_receipts")
    op.drop_index("ix_community_submission_event", table_name="community_submission_events")
    op.drop_table("community_submission_events")
    op.drop_table("community_submission_revisions")
    op.drop_index("ix_community_submission_queue", table_name="community_submissions")
    op.drop_index("ix_community_submission_owner", table_name="community_submissions")
    op.drop_table("community_submissions")
    op.drop_index("ix_community_annotation_content", table_name="community_annotations")
    op.drop_table("community_annotations")
    op.drop_index("ix_community_comment_content", table_name="community_comments")
    op.drop_table("community_comments")
    op.drop_table("community_respects")
    op.drop_index("ix_community_entity_feed", table_name="community_entities")
    op.drop_table("community_entities")
