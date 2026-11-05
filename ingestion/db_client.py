"""DB Timetables API: auth headers, ~50 calls/min spacing, retries on 429/5xx."""
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ingestion.settings import env

MIN_SPACING_S = 1.2  # 50 calls/min, under the 60/min Marketplace limit


class DBClient:
    def __init__(self):
        self.base = env("DB_BASE_URL").rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "DB-Client-Id": env("DB_CLIENT_ID"),
            "DB-Api-Key": env("DB_API_KEY"),
            "Accept": "application/xml",
        })
        retry = Retry(total=4, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET",), respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.calls = 0
        self._last = 0.0

    def get(self, path: str) -> bytes:
        wait = self._last + MIN_SPACING_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self.calls += 1
        resp = self.session.get(f"{self.base}/{path}", timeout=30)
        resp.raise_for_status()
        return resp.content

    def fchg(self, eva: int) -> bytes:
        return self.get(f"fchg/{eva}")

    def plan(self, eva: int, yymmdd: str, hh: str) -> bytes:
        return self.get(f"plan/{eva}/{yymmdd}/{hh}")
