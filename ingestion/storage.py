"""Supabase Storage: upload raw responses / Parquet to the private `bronze` bucket, delete old files."""
import gzip
from urllib.parse import urlsplit

import requests

from ingestion.settings import env


def _base_and_headers() -> tuple[str, dict]:
    u = urlsplit(env("SUPABASE_URL"))  # tolerate a pasted .../rest/v1/ suffix
    key = env("SUPABASE_SERVICE_KEY")
    return f"{u.scheme}://{u.netloc}/storage/v1", {"apikey": key, "Authorization": f"Bearer {key}"}


def upload(path: str, data: bytes, content_type: str, bucket: str = "bronze") -> None:
    base, headers = _base_and_headers()
    resp = requests.post(f"{base}/object/{bucket}/{path}",
                         headers={**headers, "Content-Type": content_type, "x-upsert": "true"},
                         data=data, timeout=60)
    resp.raise_for_status()


def upload_raw(path: str, content: bytes, bucket: str = "bronze") -> None:
    upload(path, gzip.compress(content), "application/gzip", bucket)


def download(path: str, bucket: str = "bronze") -> bytes | None:
    """Returns the file, or None if it does not exist."""
    base, headers = _base_and_headers()
    resp = requests.get(f"{base}/object/{bucket}/{path}", headers=headers, timeout=60)
    if resp.status_code in (400, 404):  # Supabase answers 400 "Object not found"
        return None
    resp.raise_for_status()
    return resp.content


def delete(paths: list[str], bucket: str = "bronze") -> int:
    base, headers = _base_and_headers()
    for i in range(0, len(paths), 500):
        resp = requests.delete(f"{base}/object/{bucket}", headers=headers,
                               json={"prefixes": paths[i:i + 500]}, timeout=60)
        resp.raise_for_status()
    return len(paths)
