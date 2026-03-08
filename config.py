"""
config.py – Central configuration for AI Research Co-Author.
Loads environment variables, initialises AWS clients, and exposes
all knobs as typed constants so nothing is hard-coded elsewhere.
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# ─────────────────────────────────────────────
# Load .env (if present) before anything else
# ─────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai-coauthor")


# ─────────────────────────────────────────────
# AWS / Bedrock settings
# ─────────────────────────────────────────────
AWS_REGION: str = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")

BEDROCK_LLM_MODEL: str = os.getenv(
    "BEDROCK_LLM_MODEL", "us.amazon.nova-lite-v1:0"
)
BEDROCK_EMBED_MODEL: str = os.getenv(
    "BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v1"
)

# ─────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────
S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "ai-research-coauthor-mvp")
DYNAMODB_TABLE_NAME: str = os.getenv("DYNAMODB_TABLE_NAME", "research_sessions")

# ─────────────────────────────────────────────
# Pipeline knobs
# ─────────────────────────────────────────────
MAX_PAPERS: int = int(os.getenv("MAX_PAPERS", "10"))
MAX_TOKENS_SUMMARY: int = int(os.getenv("MAX_TOKENS_SUMMARY", "800"))
MAX_TOKENS_SECTION: int = int(os.getenv("MAX_TOKENS_SECTION", "2500"))
EMBEDDING_DIM: int = 1536  # titan-embed-text-v1 output size
FAISS_TOP_K: int = 5
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))

# ─────────────────────────────────────────────
# Local / demo mode (no AWS creds → fallback)
# ─────────────────────────────────────────────
USE_MOCK_LLM: bool = os.getenv("USE_MOCK_LLM", "false").lower() == "true"
LOCAL_SESSION_DIR: Path = Path(__file__).parent / ".sessions"
LOCAL_SESSION_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# Supported output formats
# ─────────────────────────────────────────────
SUPPORTED_FORMATS = ["IEEE", "ACM", "APA", "MLA"]

# ─────────────────────────────────────────────
# AWS client factory (lazy, cached)
# ─────────────────────────────────────────────
_boto_kwargs = dict(region_name=AWS_REGION)
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    _boto_kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
    _boto_kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY


def get_bedrock_client():
    """Return a boto3 bedrock-runtime client (cached after first call)."""
    import boto3
    if not hasattr(get_bedrock_client, "_client"):
        get_bedrock_client._client = boto3.client("bedrock-runtime", **_boto_kwargs)
    return get_bedrock_client._client


def get_s3_client():
    import boto3
    if not hasattr(get_s3_client, "_client"):
        get_s3_client._client = boto3.client("s3", **_boto_kwargs)
    return get_s3_client._client


def get_dynamodb_resource():
    import boto3
    if not hasattr(get_dynamodb_resource, "_resource"):
        get_dynamodb_resource._resource = boto3.resource("dynamodb", **_boto_kwargs)
    return get_dynamodb_resource._resource


def ensure_dynamodb_table(table_name: str = DYNAMODB_TABLE_NAME) -> bool:
    """
    Create the DynamoDB table if it does not already exist.
    Uses PAY_PER_REQUEST (on-demand) billing — no provisioned capacity needed.
    Returns True if the table is ready, False on any error.
    """
    try:
        import boto3
        client = boto3.client("dynamodb", **_boto_kwargs)
        existing = client.list_tables()["TableNames"]  # already a list of strings
        if table_name not in existing:
            logger.info("Creating DynamoDB table: %s", table_name)
            client.create_table(
                TableName=table_name,
                KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "session_id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            # Wait until ACTIVE
            waiter = client.get_waiter("table_exists")
            waiter.wait(TableName=table_name, WaiterConfig={"Delay": 2, "MaxAttempts": 20})
            logger.info("DynamoDB table '%s' created and active.", table_name)
        else:
            logger.info("DynamoDB table '%s' already exists.", table_name)
        return True
    except Exception as exc:
        logger.warning("Could not ensure DynamoDB table: %s", exc)
        return False


def ensure_s3_bucket(bucket_name: str = S3_BUCKET_NAME) -> bool:
    """
    Create the S3 bucket if it does not already exist.
    Handles the us-east-1 quirk where CreateBucketConfiguration must be omitted.
    Returns True if the bucket is ready, False on any error.
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        client = boto3.client("s3", **_boto_kwargs)
        try:
            client.head_bucket(Bucket=bucket_name)
            logger.info("S3 bucket '%s' already exists.", bucket_name)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("404", "NoSuchBucket"):
                logger.info("Creating S3 bucket: %s in region %s", bucket_name, AWS_REGION)
                if AWS_REGION == "us-east-1":
                    client.create_bucket(Bucket=bucket_name)
                else:
                    client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
                    )
                logger.info("S3 bucket '%s' created.", bucket_name)
            else:
                raise
        return True
    except Exception as exc:
        logger.warning("Could not ensure S3 bucket: %s", exc)
        return False


# ─────────────────────────────────────────────
# Bedrock helper: invoke the configured LLM
# ─────────────────────────────────────────────
def invoke_claude(
    prompt: str,
    system: str = "",
    max_tokens: int = MAX_TOKENS_SECTION,
    temperature: float = LLM_TEMPERATURE,
) -> str:
    """
    Call an LLM via the Bedrock Converse API.
    Works with any model: Claude, Amazon Nova, Titan, etc.
    The function name is kept as invoke_claude for backwards compatibility.
    """
    if USE_MOCK_LLM:
        return f"[MOCK RESPONSE for prompt: {prompt[:80]}...]"

    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise RuntimeError(
            "AWS credentials are not set. Please fill in AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY in your .env file, then restart the app."
        )

    try:
        client = get_bedrock_client()

        # Build Converse API request (works for all Bedrock models)
        converse_kwargs: dict = {
            "modelId": BEDROCK_LLM_MODEL,
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ],
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            converse_kwargs["system"] = [{"text": system}]

        response = client.converse(**converse_kwargs)
        return response["output"]["message"]["content"][0]["text"]

    except Exception as exc:
        err = str(exc)
        if any(k in err for k in [
            "NoCredentialsError", "InvalidClientTokenId",
            "AccessDenied", "INVALID_PAYMENT_INSTRUMENT",
            "UnrecognizedClientException",
        ]):
            raise RuntimeError(
                f"AWS access failed: {err}\n"
                "Check your credentials and payment method in the AWS console."
            ) from exc
        raise


def get_embedding(text: str) -> list[float]:
    """Return a 1536-dim embedding vector for the given text using Titan."""
    if USE_MOCK_LLM:
        import random, hashlib
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        return [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]

    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        # Fallback to deterministic mock embedding if no creds
        import random, hashlib
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        return [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]

    try:
        client = get_bedrock_client()
        raw = client.invoke_model(
            modelId=BEDROCK_EMBED_MODEL,
            body=json.dumps({"inputText": text[:8000]}),
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(raw["body"].read())["embedding"]
    except Exception:
        # Fallback to deterministic mock on any error
        import random, hashlib
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        return [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
