import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.core.database import Base, get_db
from app.core.redis import get_redis, MockRedis
from app.main import app

# Create in-memory SQLite database engine isolated for test suites
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function", autouse=True)
def init_db():
    """
    Initializes clean database table schemas before every test block.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """
    Supplies isolated, transaction-rolled-back database session contexts.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def mock_redis():
    """
    Supplies clean in-memory mock Redis cache adapters.
    """
    return MockRedis()

@pytest.fixture(scope="function")
def client(db_session, mock_redis):
    """
    FastAPI TestClient injecting mock dependencies to isolate routers.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    def override_get_redis():
        return mock_redis

    # Override target dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    with TestClient(app) as test_client:
        yield test_client
        
    # Tear down overrides
    app.dependency_overrides.clear()
