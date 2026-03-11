import time
from collections import deque

from config import TRAIL_LENGTH
from models import Aircraft
from utils import nm_distance


def merge_aircraft(existing_dict, new_aircraft, center_lat, center_lon, range_nm):
    now = time.time()
    updated = dict(existing_dict)

    keep_range_nm = max(range_nm * 2.5, range_nm + 20)

    for fresh in new_aircraft:
        icao24 = fresh.icao24
        callsign = (fresh.callsign or "").strip()
        lat = fresh.lat
        lon = fresh.lon
        altitude = fresh.altitude
        velocity = fresh.velocity
        heading = fresh.heading

        if not icao24 or lat is None or lon is None:
            continue

        if nm_distance(center_lat, center_lon, lat, lon) > keep_range_nm:
            continue

        if icao24 in updated:
            ac = updated[icao24]
            ac.callsign = callsign
            ac.update_position(lat, lon, altitude, velocity, heading)
            ac.last_seen_time = now
        else:
            ac = Aircraft(
                icao24=icao24,
                callsign=callsign,
                lat=lat,
                lon=lon,
                altitude=altitude,
                velocity=velocity,
                heading=heading,
            )
            ac.trail = deque(maxlen=TRAIL_LENGTH)
            ac.last_seen_time = now
            updated[icao24] = ac

    to_delete = []
    for icao24, ac in updated.items():
        if now - ac.last_seen_time > ac.stale_timeout:
            to_delete.append(icao24)

    for icao24 in to_delete:
        del updated[icao24]

    return updated