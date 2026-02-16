from collections.abc import Generator

from pgvector.psycopg import register_vector
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.auth import models as _iam_models  # noqa: F401
from app.domains.hr_core import models as _hr_core_models  # noqa: F401
from app.domains.tenancy import models as _tenancy_models  # noqa: F401
from app.models import models as _app_models  # noqa: F401

# Load all mapped tables into shared metadata for every process (API + workers).
# Without this, worker-only processes can fail FK resolution on flush/commit for
# models that reference canonical vNext schemas (tenancy/iam/hr_core).

engine = create_engine(
    settings.database_url,
    echo=settings.sqlalchemy_echo,
    pool_pre_ping=True,
    # Prefer explicit schemas on SQLAlchemy models, but keep a safe search_path
    # to protect any legacy raw SQL (or extension objects) that may rely on it.
    connect_args={
        "options": (
            "-csearch_path="
            "tenancy,iam,hr_core,workflow,dms,"
            "vision,attendance,hr,mobile,face,imports,analytics,skills,work,"
            "audit,public"
        )
    },
)


@event.listens_for(engine, "connect")
def _register_vector(dbapi_connection, _connection_record) -> None:
    register_vector(dbapi_connection)


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
