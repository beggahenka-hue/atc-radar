import pygame


FETCH_INTERVAL_MS = 10000


class TrafficProvider:
    def __init__(self, opensky_provider, fetch_interval_ms=FETCH_INTERVAL_MS):
        self.opensky_provider = opensky_provider
        self.fetch_interval_ms = fetch_interval_ms
        self.last_fetch_ms = -fetch_interval_ms

    def should_fetch(self, now_ms):
        return now_ms - self.last_fetch_ms >= self.fetch_interval_ms

    def fetch_if_due(self, now_ms):
        if not self.should_fetch(now_ms):
            return None

        self.last_fetch_ms = now_ms

        try:
            return self.opensky_provider.fetch()
        except Exception as e:
            print("OpenSky fetch error:", e)
            return []