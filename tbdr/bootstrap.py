"""Create the tbdr database schema for a fresh PostgreSQL volume."""

from . import create_app
from .db import init_db


def main() -> None:
    app = create_app()
    with app.app_context():
        init_db()


if __name__ == '__main__':
    main()
