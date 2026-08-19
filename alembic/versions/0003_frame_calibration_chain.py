"""publish parent frame and integer calibration steps"""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "coordinate_frames",
        sa.Column("parent_frame_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "coordinate_frames",
        sa.Column(
            "calibration_steps",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.create_foreign_key(
        "fk_coordinate_frames_parent",
        "coordinate_frames",
        "coordinate_frames",
        ["parent_frame_id"],
        ["id"],
    )
    op.alter_column("coordinate_frames", "calibration_steps", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_coordinate_frames_parent", "coordinate_frames", type_="foreignkey")
    op.drop_column("coordinate_frames", "calibration_steps")
    op.drop_column("coordinate_frames", "parent_frame_id")
