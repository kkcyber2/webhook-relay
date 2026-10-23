import pytest

from relay import app as app_module


@pytest.fixture()
def client():
    app_module.store.clear()
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as c:
        yield c
