from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.update({
    "ENVIRONMENT": "development",
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_REGION": "us-east-1",
    "S3_BUCKET_NAME": "test-bucket",
    "S3_ENDPOINT_URL": "",
    "SQS_QUEUE_URL": "",
})

from app.config import Settings, get_settings  # noqa: E402
from app.main import app  # noqa: E402


def _test_settings() -> Settings:
    return Settings(
        environment="development",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        s3_endpoint_url=None,
        sqs_queue_url=None,
    )


app.dependency_overrides[get_settings] = _test_settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
