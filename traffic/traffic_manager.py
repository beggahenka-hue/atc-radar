import time
from typing import Dict, Iterable

from models import Aircraft
from traffic.traffic_provider import TrafficProvider


class TrafficManager:

    def __init__(self, opensky_provider):
        self.traffic_source = TrafficProvider(opensky_provider)
        self.aircraft_dict: Dict[str, Aircraft] = {}

    def get_aircraft(self) -> Dict[str, Aircraft]:
        return self.aircraft_dict

    def update(self, now_ms) -> Dict[str, Aircraft]:

        fresh_aircraft = self.traffic_source.fetch_if_due(now_ms)

        if fresh_aircraft is not None:
            self._merge_aircraft(fresh_aircraft)

        self._remove_stale_aircraft()
        self._update_smoothed_positions()

        return self.aircraft_dict

    def _merge_aircraft(self, fresh_aircraft: Iterable[Aircraft]) -> None:

        now = time.time()

        for incoming in fresh_aircraft:

            if not incoming.icao24:
                continue

            icao24 = incoming.icao24.lower().strip()

            if icao24 in self.aircraft_dict:

                existing = self.aircraft_dict[icao24]

                existing.callsign = incoming.callsign or existing.callsign
                existing.prev_lat = existing.lat
                existing.prev_lon = existing.lon

                existing.target_lat = incoming.lat
                existing.target_lon = incoming.lon

                existing.altitude = incoming.altitude
                existing.velocity = incoming.velocity
                existing.heading = incoming.heading

                existing.last_update_time = now
                existing.last_seen_time = now

            else:

                aircraft = Aircraft(
                    icao24=icao24,
                    callsign=incoming.callsign or "",
                    lat=incoming.lat,
                    lon=incoming.lon,
                    altitude=incoming.altitude,
                    velocity=incoming.velocity,
                    heading=incoming.heading,
                )

                aircraft.prev_lat = incoming.lat
                aircraft.prev_lon = incoming.lon
                aircraft.target_lat = incoming.lat
                aircraft.target_lon = incoming.lon

                aircraft.last_update_time = now
                aircraft.last_seen_time = now

                self.aircraft_dict[icao24] = aircraft

    def _remove_stale_aircraft(self) -> None:

        now = time.time()
        stale_keys = []

        for icao24, aircraft in self.aircraft_dict.items():

            timeout = getattr(aircraft, "stale_timeout", 20.0)

            if now - aircraft.last_seen_time > timeout:
                stale_keys.append(icao24)

        for icao24 in stale_keys:
            del self.aircraft_dict[icao24]

    def _update_smoothed_positions(self) -> None:

        now = time.time()

        for aircraft in self.aircraft_dict.values():

            if aircraft.target_lat is None or aircraft.target_lon is None:
                continue

            if aircraft.prev_lat is None or aircraft.prev_lon is None:
                aircraft.lat = aircraft.target_lat
                aircraft.lon = aircraft.target_lon
                continue

            smooth_duration = max(getattr(aircraft, "smooth_duration", 3.0), 0.001)

            elapsed = now - aircraft.last_update_time

            t = min(max(elapsed / smooth_duration, 0.0), 1.0)

            aircraft.lat = aircraft.prev_lat + (aircraft.target_lat - aircraft.prev_lat) * t
            aircraft.lon = aircraft.prev_lon + (aircraft.target_lon - aircraft.prev_lon) * t