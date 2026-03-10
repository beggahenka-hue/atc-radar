from collections import deque
from dataclasses import dataclass, field
from typing import Optional
import time

from config import TRAIL_LENGTH


@dataclass
class Aircraft:
    icao24: str
    callsign: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    altitude: Optional[float] = None
    velocity: Optional[float] = None
    heading: Optional[float] = None
    selected: bool = False

    trail: deque = field(default_factory=lambda: deque(maxlen=TRAIL_LENGTH))

    prev_lat: Optional[float] = None
    prev_lon: Optional[float] = None
    target_lat: Optional[float] = None
    target_lon: Optional[float] = None
    last_update_time: float = field(default_factory=time.time)
    smooth_duration: float = 3.0

    last_seen_time: float = field(default_factory=time.time)
    stale_timeout: float = 20.0

    last_trail_time: float = field(default_factory=time.time)
    trail_interval: float = 0.5

    def __post_init__(self):
        if self.lat is not None and self.lon is not None:
            self.prev_lat = self.lat
            self.prev_lon = self.lon
            self.target_lat = self.lat
            self.target_lon = self.lon

    def update_position(self, lat, lon, altitude, velocity, heading):
        now = time.time()

        current_lat, current_lon = self.get_smoothed_position(now)

        self.prev_lat = current_lat
        self.prev_lon = current_lon
        self.target_lat = lat
        self.target_lon = lon

        self.lat = lat
        self.lon = lon
        self.altitude = altitude
        self.velocity = velocity
        self.heading = heading
        self.last_update_time = now
        self.last_seen_time = now

    def get_smoothed_position(self, now=None):
        if now is None:
            now = time.time()

        if self.target_lat is None or self.target_lon is None:
            return self.lat, self.lon

        if self.prev_lat is None or self.prev_lon is None:
            return self.target_lat, self.target_lon

        if self.smooth_duration <= 0:
            return self.target_lat, self.target_lon

        elapsed = now - self.last_update_time
        alpha = max(0.0, min(1.0, elapsed / self.smooth_duration))

        # Smoothstep för mjuk men stabil interpolation
        alpha = alpha * alpha * (3.0 - 2.0 * alpha)

        draw_lat = self.prev_lat + (self.target_lat - self.prev_lat) * alpha
        draw_lon = self.prev_lon + (self.target_lon - self.prev_lon) * alpha

        return draw_lat, draw_lon