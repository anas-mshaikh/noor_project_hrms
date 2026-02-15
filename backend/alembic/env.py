from pathlib import Path
import sys

from alembic import context
from sqlalchemy import create_engine, pool

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from app.core.config import settings
from app.db.base import Base
import app.models  # noqa: F401


config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_schemas=True,
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        settings.database_url,
        poolclass=pool.NullPool,
        connect_args={
            "options": (
                "-csearch_path="
                "tenancy,iam,hr_core,workflow,dms,"
                "vision,attendance,hr,mobile,face,imports,analytics,skills,work,"
                "audit,public"
            )
        },
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=True,
            version_table_schema="public",
            # `alembic_version` is managed by Alembic and should never be autogen'd.
            include_object=lambda obj, name, type_, reflected, compare_to: not (
                type_ == "table" and name == "alembic_version"
            ),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
