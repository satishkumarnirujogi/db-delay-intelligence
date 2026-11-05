"""Uploads gzipped raw responses to the private Supabase `bronze` bucket."""
import gzip
from urllib.parse import urlsplit

import requests

from ingestion.settings import env


def upload_raw(path: str, content: bytes, bucket: str = "bronze") -> None:
    u = urlsplit(env("SUPABASE_URL"))  # tolerate a pasted .../rest/v1/ suffix
    key = env("SUPABASE_SERVICE_KEY")
    resp = requests.post(
        f"{u.scheme}://{u.netloc}/storage/v1/object/{bucket}/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/gzip", "x-upsert": "true"},
        data=gzip.compress(content),
        timeout=30,
    )
    resp.raise_for_status()
