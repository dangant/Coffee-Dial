import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import serializer, COOKIE_NAME
from app.database import Base, get_db
from app.main import app
from app.services.lookup_service import seed_lookups
from app.services.recommendation_service import seed_rules

engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestSession()
    seed_rules(db)
    seed_lookups(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        # Set auth cookie so tests bypass login
        token = serializer.dumps("authenticated")
        c.cookies.set(COOKIE_NAME, token)
        yield c
    app.dependency_overrides.clear()
