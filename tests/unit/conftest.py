import pytest


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    pass
