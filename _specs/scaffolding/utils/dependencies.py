from unittest import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.tables import Base

SQLALCHEMY_DATABASE_URL = "postgresql://localhost/test_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

needed_tables = ['user', 'agent', 'credential']
tables = [table for table in Base.metadata.tables.values() if table.name in needed_tables]
Base.metadata.create_all(bind=engine, tables=tables)

test_db = mock.MagicMock()

def get_test_db():
  try:  # yield test_db
    db = TestingSessionLocal()
    yield db
  finally:
    db.close()

def load_test_engine():
  pass