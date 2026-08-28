from tbdr import create_app
from tbdr.db import Base, get_engine, init_db

app = create_app()

with app.app_context():
    import tbdr.models
    Base.metadata.drop_all(bind=get_engine())
    init_db()
    print("✓ Tables recreated successfully!")