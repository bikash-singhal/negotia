from unittest.mock import MagicMock, patch

import pytest

from app.aws.session import get_bedrock_runtime_client
from app.core.config import settings


def test_client_factory_uses_configured_profile_and_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "aws_profile", "local-development")
    monkeypatch.setattr(settings, "aws_region", "eu-west-1")
    client = object()

    with patch("app.aws.session.boto3.Session") as session_factory:
        session = MagicMock()
        session.client.return_value = client
        session_factory.return_value = session

        result = get_bedrock_runtime_client()

    assert result is client
    session_factory.assert_called_once_with(
        profile_name="local-development",
        region_name="eu-west-1",
    )
    session.client.assert_called_once_with("bedrock-runtime")


@pytest.mark.parametrize("profile", ["", None])
def test_client_factory_omits_empty_profile(
    monkeypatch: pytest.MonkeyPatch,
    profile: str | None,
) -> None:
    monkeypatch.setattr(settings, "aws_profile", profile)
    monkeypatch.setattr(settings, "aws_region", "ap-south-1")

    with patch("app.aws.session.boto3.Session") as session_factory:
        session = MagicMock()
        session_factory.return_value = session

        get_bedrock_runtime_client()

    session_factory.assert_called_once_with(region_name="ap-south-1")
    session.client.assert_called_once_with("bedrock-runtime")
