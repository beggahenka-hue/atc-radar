import sys
import pygame

from config import (
    WIDTH,
    HEIGHT,
    FPS,
    TRAIL_LENGTH,
    RADAR_CENTER_LAT,
    RADAR_CENTER_LON,
    DEFAULT_RANGE_NM,
    MIN_RANGE_NM,
    MAX_RANGE_NM,
)

from models import Aircraft
from display_backup_innan_zoomfix import RadarDisplay
from backup.providers_backup import OpenSkyProvider, OpenAIPProvider
from map_data import load_fixes, load_navaids, load_airspaces
from utils import latlon_to_screen, nm_distance


FETCH_INTERVAL_MS = 10000
CLICK_RADIUS_PX = 15
ZOOM_STEP_NM = 5


def merge_aircraft(existing_dict, new_aircraft, center_lat, center_lon, range_nm):
    """
    Merge fresh aircraft data into existing track dictionary.
    Keeps previous Aircraft objects alive when possible so trails/selection survive.
    Filters out aircraft outside current radar range.
    """
    updated = {}

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

        if nm_distance(center_lat, center_lon, lat, lon) > range_nm:
            continue

        if icao24 in existing_dict:
            ac = existing_dict[icao24]
            ac.callsign = callsign
            ac.update_position(lat, lon, altitude, velocity, heading)
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
            ac.trail = ac.trail.__class__(maxlen=TRAIL_LENGTH)

        updated[icao24] = ac

    return updated


def load_map_layers(openaip, center_lat, center_lon):
    """
    Load static map layers around radar center.
    """
    lat_margin = 1.0
    lon_margin = 1.5

    load_fixes(
        openaip,
        center_lat - lat_margin,
        center_lat + lat_margin,
        center_lon - lon_margin,
        center_lon + lon_margin,
    )

    load_navaids(
        openaip,
        center_lat - lat_margin,
        center_lat + lat_margin,
        center_lon - lon_margin,
        center_lon + lon_margin,
    )

    load_airspaces(
        openaip,
        center_lat - lat_margin,
        center_lat + lat_margin,
        center_lon - lon_margin,
        center_lon + lon_margin,
    )


def update_aircraft_trails(aircraft_dict, center_lat, center_lon, range_nm):
    """
    Update screen-space trail points for each aircraft.
    Returns list of tuples: (aircraft, sx, sy)
    """
    visible_aircraft = []

    for ac in aircraft_dict.values():
        sx, sy = latlon_to_screen(
            ac.lat,
            ac.lon,
            center_lat,
            center_lon,
            range_nm,
            WIDTH,
            HEIGHT,
        )

        if len(ac.trail) == 0:
            ac.trail.append((sx, sy))
        else:
            last_x, last_y = ac.trail[-1]
            if abs(sx - last_x) > 1 or abs(sy - last_y) > 1:
                ac.trail.append((sx, sy))

        visible_aircraft.append((ac, sx, sy))

    return visible_aircraft


def find_clicked_aircraft(aircraft_dict, mouse_pos, center_lat, center_lon, range_nm):
    """
    Find nearest aircraft within CLICK_RADIUS_PX.
    """
    mx, my = mouse_pos
    clicked = None
    min_dist = CLICK_RADIUS_PX

    for ac in aircraft_dict.values():
        sx, sy = latlon_to_screen(
            ac.lat,
            ac.lon,
            center_lat,
            center_lon,
            range_nm,
            WIDTH,
            HEIGHT,
        )

        dist = ((mx - sx) ** 2 + (my - sy) ** 2) ** 0.5
        if dist < min_dist:
            clicked = ac
            min_dist = dist

    return clicked


def set_selected_aircraft(aircraft_dict, selected_icao24):
    """
    Apply selection state to all aircraft.
    """
    selected_aircraft = None

    for ac in aircraft_dict.values():
        ac.selected = ac.icao24 == selected_icao24
        if ac.selected:
            selected_aircraft = ac

    return selected_aircraft


def draw_scene(display, aircraft_dict, center_lat, center_lon, range_nm):
    """
    Render one full radar frame.
    """
    display.draw_background()

    # Kartlager – coastline/water bör ligga här när du lagt till metoden i display.py
    if hasattr(display, "draw_coastline_and_water"):
        display.draw_coastline_and_water(center_lat, center_lon, range_nm)

    # Baslager
    if hasattr(display, "draw_range_rings"):
        display.draw_range_rings(center_lat, center_lon, range_nm)

    display.draw_airspaces(center_lat, center_lon, range_nm)
    display.draw_runways(center_lat, center_lon, range_nm)
    display.draw_ils_layers(center_lat, center_lon, range_nm)
    display.draw_fixes(center_lat, center_lon, range_nm)
    display.draw_navaids(center_lat, center_lon, range_nm)

    # Trafik
    visible_aircraft = update_aircraft_trails(
        aircraft_dict,
        center_lat,
        center_lon,
        range_nm,
    )

    selected_aircraft = None

    # Rita oselekterade först, selekterad sist så den hamnar överst
    visible_aircraft.sort(key=lambda item: item[0].selected)

    for ac, sx, sy in visible_aircraft:
        # Om du senare bygger vector predictor i display.py,
        # låt draw_aircraft() hantera det där.
        display.draw_aircraft(ac, sx, sy)

        if ac.selected:
            selected_aircraft = ac

    display.draw_sweep()
    display.draw_info_panel(selected_aircraft)


def main():
    pygame.init()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("ATC Radar v3")
    clock = pygame.time.Clock()

    display = RadarDisplay(screen)
    traffic_provider = OpenSkyProvider()
    map_provider = OpenAIPProvider()

    center_lat = RADAR_CENTER_LAT
    center_lon = RADAR_CENTER_LON
    range_nm = DEFAULT_RANGE_NM

    load_map_layers(map_provider, center_lat, center_lon)

    aircraft_dict = {}
    selected_icao24 = None
    fetch_timer = FETCH_INTERVAL_MS  # fetch direkt vid start

    running = True
    while running:
        dt = clock.tick(FPS)
        fetch_timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    clicked = find_clicked_aircraft(
                        aircraft_dict,
                        pygame.mouse.get_pos(),
                        center_lat,
                        center_lon,
                        range_nm,
                    )

                    selected_icao24 = clicked.icao24 if clicked else None
                    set_selected_aircraft(aircraft_dict, selected_icao24)

                elif event.button == 4:
                    range_nm = max(MIN_RANGE_NM, range_nm - ZOOM_STEP_NM)

                elif event.button == 5:
                    range_nm = min(MAX_RANGE_NM, range_nm + ZOOM_STEP_NM)

        if fetch_timer >= FETCH_INTERVAL_MS:
            try:
                fresh_aircraft = traffic_provider.fetch()
                aircraft_dict = merge_aircraft(
                    aircraft_dict,
                    fresh_aircraft,
                    center_lat,
                    center_lon,
                    range_nm,
                )

                set_selected_aircraft(aircraft_dict, selected_icao24)

            except Exception as e:
                print("OpenSky fetch error:", e)

            fetch_timer = 0

        draw_scene(display, aircraft_dict, center_lat, center_lon, range_nm)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()