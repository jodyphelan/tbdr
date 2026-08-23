import os

# Set the environment variable to point to your settings file
if not os.environ.get('YOURAPPLICATION_SETTINGS'):
    print("Please set the YOURAPPLICATION_SETTINGS environment variable to point to your settings file.")
    quit()


from tbdr import create_app
from tbdr.db import init_db

app = create_app()
with app.app_context():
    init_db()
    print("✓ Tables created successfully!")