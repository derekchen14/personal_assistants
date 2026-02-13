import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.tables import Base

ENV = os.getenv("SOLEDA_ENV", "development")

if ENV == "production": 
    # In production, use Render's DB_DSN environment variable
    ENV_DB_DSN = os.getenv("DB_DSN")
else:
    load_dotenv('./database/.env') 
    # Use staging database from .env file if not in production
    ENV_DB_DSN = os.getenv("STAGING_DB_DSN", "")

# sqlalchemy does not support postgres://
# https://docs.sqlalchemy.org/en/20/core/engines.html#postgresql
DB_DSN = ENV_DB_DSN.replace("postgres://", "postgresql://")

engine = None
SessionLocal = None

def load_engine():
  global engine, SessionLocal
  if engine is None:
    # Connecting to your database with the SQLAlchemy engine
    engine = create_engine(DB_DSN)
  if SessionLocal is None:
    # Defining a session factory (SessionLocal) using that engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
  

def get_db():
  load_engine()

  # supply database sessions
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()

# ---Create new migration ---
# alembic revision -m "Message describing this migration"
# ----- run migrations -----
# alembic upgrade head
