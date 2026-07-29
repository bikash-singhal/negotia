from typing import Any

import boto3

from app.core.config import settings


def get_bedrock_runtime_client() -> Any:
    if settings.aws_profile:
        session = boto3.Session(
            profile_name=settings.aws_profile,
            region_name=settings.aws_region,
        )
    else:
        session = boto3.Session(region_name=settings.aws_region)

    return session.client("bedrock-runtime")
