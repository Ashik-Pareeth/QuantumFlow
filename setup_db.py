from db.database import engine, Base
from sqlalchemy import text
import db.models  # noqa: F401 - Imports the models to register them

print("1. Building standard PostgreSQL tables...")
Base.metadata.create_all(bind=engine)

print("2. Attempting to convert 'candles' to a TimescaleDB Hypertable...")
try:
    with engine.connect() as conn:
        # This is the magic TimescaleDB command. It chunks the data by the 'time' column.
        conn.execute(
            text("SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);")
        )
        conn.commit()
    print("Hypertable created successfully! Ready for high-frequency data.")
except Exception as e:
    print("Note: Could not create hypertable (TimescaleDB might not be installed).")
    print(f"Standard PostgreSQL table will be used instead. Error: {e}")

print("\nDatabase setup complete.")
