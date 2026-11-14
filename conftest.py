"""Pytest setup: one database for the whole test session."""

import pytest

from app import db


@pytest.fixture(scope="session", autouse=True)
def database():
    db.init()
    yield
