"""Command-line entry points for ops tasks."""
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.bootstrap import ensure_bootstrap_admin
from prism_api.config import Settings, get_settings


def bootstrap_admin(settings: Settings | None = None) -> None:
    """Create the bootstrap admin if no users exist and credentials are set."""
    s = settings or get_settings()
    engine = create_engine(s.database_url)
    with sessionmaker(bind=engine)() as session:
        ensure_bootstrap_admin(
            session, email=s.admin_email, password=s.admin_password
        )
        session.commit()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: prism-api <bootstrap-admin>", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "bootstrap-admin":
        bootstrap_admin()
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
