from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from flask import current_app

# Create Base at module level (this is fine)
Base = declarative_base()

# Don't create engine/session at module level
_engine = None
_db_session = None

def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            f'postgresql+psycopg2://{current_app.config["PG_USER"]}:'
            f'{current_app.config["PG_PASS"]}@localhost/tbdr'
        )
    return _engine

def get_db_session():
    """Get or create the database session."""
    global _db_session
    if _db_session is None:
        _db_session = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
        )
        Base.query = _db_session.query_property()
    return _db_session

def init_db():
    """Initialize the database - create all tables."""
    import tbdr.models
    Base.metadata.create_all(bind=get_engine())

# Backward compatibility: Create a proxy that forwards all attribute access to the lazy session
class _DBSessionProxy:
    """Proxy object that lazily gets the db_session when accessed."""
    def __getattr__(self, name):
        return getattr(get_db_session(), name)
    
    def __call__(self):
        return get_db_session()

db_session = _DBSessionProxy()