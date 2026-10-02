"""Database initialization CLI.

Usage (from the backend/ directory):
    python -m app.init_db          # create/update tables + seed services
    python -m app.init_db --admin  # also create the initial ADMIN account
                                   # (uses ADMIN_EMAIL / ADMIN_PASSWORD from .env)

Phase 2 strategy (no Alembic in this project): `create_all` creates any missing
tables (expert_services), then additive, idempotent ALTERs add the new nullable
columns to existing tables. Existing rows and tables are never dropped.
"""
import logging
import sys

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import Service, User
from app.models.service import ServiceStatus
from app.models.user import UserRole

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("init_db")

# --- Seed data: the initial service catalogue ------------------------------
INITIAL_SERVICES = [
    ("Electrician", "Wiring, repairs, switchboard and fan/light installation.", 299.00),
    ("Plumber", "Leak fixes, tap/shower installation, drain unblocking.", 249.00),
    ("AC Repair", "AC servicing, gas refill, cooling troubleshooting.", 449.00),
    ("Home Cleaning", "Full-home deep cleaning, kitchen and bathroom cleaning.", 599.00),
    ("Carpenter", "Furniture repair, door/lock fixes, custom fittings.", 349.00),
    ("Painting", "Interior/exterior wall painting with putty and primer.", 999.00),
    ("Pest Control", "Cockroach, termite and general household pest treatment.", 799.00),
    ("Appliance Repair", "Washing machine, refrigerator and microwave repair.", 399.00),
]


def _ensure_database() -> None:
    """Best-effort creation of the MySQL database itself, if missing.

    Connects to the server without a default database and runs
    CREATE DATABASE IF NOT EXISTS. Silently skips for SQLite or when the
    connected user lacks CREATE privileges (a manual CREATE DATABASE is then
    required).
    """
    from app.core.config import settings

    if settings.DATABASE_URL.startswith("sqlite"):
        return
    url = make_url(settings.DATABASE_URL)
    if not url.database:
        return
    try:
        server_engine = create_engine(url.set(database=""), pool_pre_ping=True)
        with server_engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            conn.commit()
        server_engine.dispose()
        logger.info("Database %r is present.", url.database)
    except SQLAlchemyError:
        logger.warning(
            "Could not auto-create database %r (insufficient privileges?). "
            "Create it manually: CREATE DATABASE %s;",
            url.database,
            url.database,
        )


def _inspect_columns(conn, table: str) -> set[str]:
    """Return the set of column names for a table (empty if table missing)."""
    if engine.dialect.name == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {row[1] for row in rows}
    rows = conn.execute(
        text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
        ),
        {"t": table},
    ).fetchall()
    return {row[0] for row in rows}


# Additive Phase 2 columns: (table, column, MySQL DDL, SQLite DDL)
# Both variants are nullable — existing expert rows stay valid.
PHASE2_COLUMNS = [
    (
        "expert_profiles",
        "latitude",
        "ALTER TABLE expert_profiles ADD COLUMN latitude DECIMAL(10, 7) NULL",
        "ALTER TABLE expert_profiles ADD COLUMN latitude NUMERIC(10, 7) NULL",
    ),
    (
        "expert_profiles",
        "longitude",
        "ALTER TABLE expert_profiles ADD COLUMN longitude DECIMAL(11, 7) NULL",
        "ALTER TABLE expert_profiles ADD COLUMN longitude NUMERIC(11, 7) NULL",
    ),
]

# Additive Phase 6 columns: (table, column, MySQL DDL, SQLite DDL)
# All nullable / server-defaulted so existing rows stay valid. Legacy booking
# rows get 'UNPAID' automatically via the server default.
PHASE6_COLUMNS = [
    (
        "bookings",
        "payment_status",
        "ALTER TABLE bookings ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'UNPAID'",
        "ALTER TABLE bookings ADD COLUMN payment_status VARCHAR(20) NOT NULL DEFAULT 'UNPAID'",
    ),
    (
        "expert_profiles",
        "rating_avg",
        "ALTER TABLE expert_profiles ADD COLUMN rating_avg DECIMAL(3, 2) NULL",
        "ALTER TABLE expert_profiles ADD COLUMN rating_avg NUMERIC(3, 2) NULL",
    ),
    (
        "expert_profiles",
        "rating_count",
        "ALTER TABLE expert_profiles ADD COLUMN rating_count INT NOT NULL DEFAULT 0",
        "ALTER TABLE expert_profiles ADD COLUMN rating_count INT NOT NULL DEFAULT 0",
    ),
]


def _migrate_phase2() -> None:
    """Additive, idempotent migrations — never drops data.

    Runs the Phase 2 column adds, then the Phase 6 column adds (payment_status
    on bookings, rating aggregates on expert_profiles). New tables (payments,
    reviews) are created by create_all before this is called.
    """
    with engine.connect() as conn:
        for table, column, mysql_ddl, sqlite_ddl in [*PHASE2_COLUMNS, *PHASE6_COLUMNS]:
            columns = _inspect_columns(conn, table)
            if not columns:
                continue  # table doesn't exist yet; create_all will make it fresh
            if column in columns:
                continue
            ddl = sqlite_ddl if engine.dialect.name == "sqlite" else mysql_ddl
            logger.info("Migrating: %s", ddl)
            conn.execute(text(ddl))
            conn.commit()
        _normalize_legacy_values(conn)


def _normalize_legacy_values(conn) -> None:
    """Map Phase 1 free-text values onto the Phase 2 enums (data-safe).

    - availability: anything outside {AVAILABLE, UNAVAILABLE} → AVAILABLE
    - verification_status: legacy APPROVED → VERIFIED
    """
    result = conn.execute(
        text(
            "UPDATE expert_profiles SET availability = 'AVAILABLE' "
            "WHERE availability IS NULL OR availability NOT IN ('AVAILABLE', 'UNAVAILABLE')"
        )
    )
    if result.rowcount:
        logger.info("Normalized %d legacy availability value(s).", result.rowcount)
    result = conn.execute(
        text(
            "UPDATE expert_profiles SET verification_status = 'VERIFIED' "
            "WHERE verification_status = 'APPROVED'"
        )
    )
    if result.rowcount:
        logger.info("Migrated %d legacy APPROVED status(es) to VERIFIED.", result.rowcount)
    conn.commit()


def reset_database() -> None:
    """Drop and recreate all tables to reset AUTO_INCREMENT IDs back to 1."""
    _ensure_database()
    logger.info("Resetting database (dropping all existing tables) ...")
    with engine.connect() as conn:
        if engine.dialect.name == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f"DROP TABLE IF EXISTS `{table.name}`;"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            conn.commit()
        else:
            Base.metadata.drop_all(bind=engine)
    logger.info("Database reset: all old tables removed.")


def init_db(seed_admin: bool = False, reset: bool = False) -> None:
    """Create the database, all tables and seed the initial services."""
    if reset:
        reset_database()
    else:
        _ensure_database()
    logger.info("Creating database tables ...")
    Base.metadata.create_all(bind=engine)
    _migrate_phase2()

    db = SessionLocal()
    try:
        existing = db.execute(select(Service)).scalars().all()
        existing_names = {s.name for s in existing}
        created = []
        for name, description, base_price in INITIAL_SERVICES:
            if name not in existing_names:
                db.add(
                    Service(
                        name=name,
                        description=description,
                        base_price=base_price,
                        status=ServiceStatus.ACTIVE,
                    )
                )
                created.append(name)
        if created:
            db.commit()
            logger.info("Seeded services (IDs starting from 1): %s", ", ".join(created))
        else:
            logger.info("Initial services already present (%d).", len(existing_names))

        if seed_admin:
            _seed_admin(db)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error during initialization")
        raise
    finally:
        db.close()
    logger.info("Database initialization complete.")


def _seed_admin(db) -> None:
    """Create the initial ADMIN account from env settings if absent."""
    from app.core.config import settings

    existing = db.execute(
        select(User).where(User.email == settings.ADMIN_EMAIL.lower().strip())
    ).scalar_one_or_none()
    if existing is not None:
        logger.info("Admin account already exists: %s", settings.ADMIN_EMAIL)
        return
    db.add(
        User(
            name=settings.ADMIN_NAME,
            email=settings.ADMIN_EMAIL.lower().strip(),
            phone="0000000000",
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    db.commit()
    logger.info("Seeded ADMIN account (User ID = 1): %s", settings.ADMIN_EMAIL)


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    create_admin = "--admin" in sys.argv
    init_db(seed_admin=create_admin, reset=reset)

