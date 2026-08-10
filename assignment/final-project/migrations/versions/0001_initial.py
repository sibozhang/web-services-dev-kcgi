"""Initial MLB Dugout schema.

Revision ID: 0001_initial
Revises:
"""
from alembic import op

from app.extensions import db


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 模型包含显式唯一约束、外键和命名约定；首次迁移从同一 metadata 建表。
    db.metadata.create_all(bind=op.get_bind())


def downgrade():
    db.metadata.drop_all(bind=op.get_bind())

