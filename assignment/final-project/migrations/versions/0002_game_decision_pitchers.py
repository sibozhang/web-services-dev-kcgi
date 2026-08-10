"""Add winning, losing, and save pitchers to games.

Revision ID: 0002_game_decision_pitchers
Revises: 0001_initial
"""

import sqlalchemy as sa
from alembic import op


revision = "0002_game_decision_pitchers"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    existing_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("games")
    }
    columns = (
        ("winning_pitcher_id", "fk_games_winning_pitcher_id_players"),
        ("losing_pitcher_id", "fk_games_losing_pitcher_id_players"),
        ("save_pitcher_id", "fk_games_save_pitcher_id_players"),
    )
    missing_columns = [item for item in columns if item[0] not in existing_columns]
    if not missing_columns:
        return

    # batch_alter_table keeps this migration usable with both PostgreSQL and the
    # SQLite database used by the automated test suite.
    with op.batch_alter_table("games") as batch_op:
        for column_name, _constraint_name in missing_columns:
            batch_op.add_column(sa.Column(column_name, sa.Integer(), nullable=True))
        for column_name, constraint_name in missing_columns:
            batch_op.create_foreign_key(
                constraint_name,
                "players",
                [column_name],
                ["id"],
            )


def downgrade():
    existing_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("games")
    }
    columns = (
        ("save_pitcher_id", "fk_games_save_pitcher_id_players"),
        ("losing_pitcher_id", "fk_games_losing_pitcher_id_players"),
        ("winning_pitcher_id", "fk_games_winning_pitcher_id_players"),
    )
    present_columns = [item for item in columns if item[0] in existing_columns]
    if not present_columns:
        return

    existing_constraints = {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_foreign_keys("games")
        if constraint.get("name")
    }
    with op.batch_alter_table("games") as batch_op:
        for _column_name, constraint_name in present_columns:
            if constraint_name in existing_constraints:
                batch_op.drop_constraint(constraint_name, type_="foreignkey")
        for column_name, _constraint_name in present_columns:
            batch_op.drop_column(column_name)
