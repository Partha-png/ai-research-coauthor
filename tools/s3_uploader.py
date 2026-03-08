"""
tools/s3_uploader.py – Upload generated paper artifacts to S3.

Uploads:
  - <session_id>/draft.md        (full Markdown paper draft)
  - <session_id>/references.bib  (BibTeX references)

Returns pre-signed URLs valid for 7 days so anyone with the link can download.
Falls back gracefully (returns None URLs) if S3 is unavailable.
"""

import logging
from typing import Optional

logger = logging.getLogger("ai-coauthor.s3_uploader")

PRESIGNED_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days


def upload_draft(
    session_id: str,
    markdown_text: str,
    bibtex_text: str = "",
) -> dict[str, Optional[str]]:
    """
    Upload the paper draft and BibTeX to S3 under the session's prefix.

    Parameters
    ----------
    session_id  : Unique session identifier (used as S3 key prefix).
    markdown_text : Full Markdown draft content.
    bibtex_text   : BibTeX references string (may be empty).

    Returns
    -------
    dict with keys:
        "draft_url"  – pre-signed URL for draft.md   (or None on failure)
        "bibtex_url" – pre-signed URL for references.bib (or None on failure)
    """
    result: dict[str, Optional[str]] = {"draft_url": None, "bibtex_url": None}

    try:
        from config import get_s3_client, S3_BUCKET_NAME, ensure_s3_bucket

        # Ensure bucket exists before uploading
        if not ensure_s3_bucket(S3_BUCKET_NAME):
            logger.warning("S3 bucket not available – skipping upload.")
            return result

        client = get_s3_client()

        uploads = [
            (f"{session_id}/draft.md",        markdown_text,  "text/markdown",      "draft_url"),
            (f"{session_id}/references.bib",  bibtex_text,    "text/plain",         "bibtex_url"),
        ]

        for key, content, content_type, url_key in uploads:
            if not content:
                continue
            try:
                client.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=key,
                    Body=content.encode("utf-8"),
                    ContentType=content_type,
                )
                presigned = client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": S3_BUCKET_NAME, "Key": key},
                    ExpiresIn=PRESIGNED_EXPIRY_SECONDS,
                )
                result[url_key] = presigned
                logger.info("Uploaded s3://%s/%s", S3_BUCKET_NAME, key)
            except Exception as exc:
                logger.warning("Failed to upload %s to S3: %s", key, exc)

    except Exception as exc:
        logger.warning("S3 upload skipped: %s", exc)

    return result
