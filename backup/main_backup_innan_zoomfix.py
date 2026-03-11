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
from providers import OpenSkyProvider, OpenAIPProvider
from map_data import load_fixes, load_navaids, load_airspaces
from utils import latlon_to_screen, nm_distance
from tile_provider import build_basemap_surface

FETCH_INTERVAL_MS = 10000
CLICK_RADIUS_PX = 15
ZOOM_STEP_NM = 5

import time
from collections import deque

def merge_aircraft(existing_dict, new_aircraft, center_lat, center_lon, range_nm):
    now = time.time()

    # börja med de gamla targets vi redan har
    updated = dict(existing_dict)

    seen_now = set()

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

        seen_now.add(icao24)

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

    # ta bort gamla tracks först efter timeout
    to_delete = []
    for icao24, ac in updated.items():
        if now - ac.last_seen_time > ac.stale_timeout:
            to_delete.append(icao24)

    for icao24 in to_delete:
        del updated[icao24]

    return updated


def load_map_layers(openaip, center_lat, center_lon):
    lat_margin = 1.0
    lon_margin = 1.5

    try:
        load_fixes(
            openaip,
            center_lat - lat_margin,
            center_lat + lat_margin,
            center_lon - lon_margin,
            center_lon + lon_margin,
        )
    except Exception as e:
        print("FIXES load error:", e)

    try:
        load_navaids(
            openaip,
            center_lat - lat_margin,
            center_lat + lat_margin,
            center_lon - lon_margin,
            center_lon + lon_margin,
        )
    except Exception as e:
        print("NAVAIDS load error:", e)

    try:
        load_airspaces(
            openaip,
            center_lat - lat_margin,
            center_lat + lat_margin,
            center_lon - lon_margin,
            center_lon + lon_margin,
        )
    except Exception as e:
        print("AIRSPACES load error:", e)

def update_aircraft_trails(aircraft_dict, center_lat, center_lon, range_nm):
    visible_aircraft = []
    now = time.time()

    for ac in aircraft_dict.values():
        lat, lon = ac.get_smoothed_position()

        if lat is None or lon is None:
            continue

        x, y = latlon_to_screen(
            lat,
            lon,
            center_lat,
            center_lon,
            range_nm,
            WIDTH,
            HEIGHT
        )

        if now - ac.last_trail_time >= ac.trail_interval:
            if not ac.trail or abs(ac.trail[-1][0] - x) > 2 or abs(ac.trail[-1][1] - y) > 2:
                ac.trail.append((x, y))
                ac.last_trail_time = now

        visible_aircraft.append((ac, x, y))

    return visible_aircraft


def find_clicked_aircraft(aircraft_dict, mouse_pos, center_lat, center_lon, range_nm):
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
    selected_aircraft = None

    for ac in aircraft_dict.values():
        ac.selected = ac.icao24 == selected_icao24
        if ac.selected:
            selected_aircraft = ac

    return selected_aircraft


def draw_scene(display, aircraft_dict, center_lat, center_lon, range_nm, basemap_surface):
    zoom = range_nm_to_zoom(range_nm)
    display.draw_background(center_lat, center_lon, range_nm, zoom)

    if basemap_surface:
        display.screen.blit(basemap_surface, (0, 0))

   
    if hasattr(display, "draw_coastline_and_water"):
        display.draw_coastline_and_water(center_lat, center_lon, range_nm)

    display.draw_airspaces(center_lat, center_lon, range_nm)
    display.draw_runways(center_lat, center_lon, range_nm)
    display.draw_ils_layers(center_lat, center_lon, range_nm)
    display.draw_fixes(center_lat, center_lon, range_nm)
    display.draw_navaids(center_lat, center_lon, range_nm)

    visible_aircraft = update_aircraft_trails(
        aircraft_dict,
        center_lat,
        center_lon,
        range_nm,
    )

    selected_aircraft = None

    visible_aircraft.sort(key=lambda item: item[0].selected)

    for ac, sx, sy in visible_aircraft:
        display.draw_aircraft(ac, sx, sy)

        if ac.selected:
            selected_aircraft = ac

    display.draw_hmi_panels(
        target_count=len(visible_aircraft),
        status="LIVE",
        range_nm=range_nm
    )

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

    show_basemap = False
    basemap_surface = None

    load_map_layers(map_provider, center_lat, center_lon)

    aircraft_dict = {}
    selected_icao24 = None
    fetch_timer = FETCH_INTERVAL_MS

    running = True
    while running:
        dt = clock.tick(FPS)
        fetch_timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_b:
                    show_basemap = not show_basemap

                    if show_basemap:
                        basemap_surface = build_basemap_surface(
                            center_lat,
                            center_lon,
                            range_nm,
                            WIDTH,
                            HEIGHT
                        )
                        basemap_surface.set_alpha(90)
                        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                        overlay.fill((0, 20, 20, 120))
                        display.screen.blit(overlay, (0, 0))
                    else:
                        basemap_surface = None

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

                    if show_basemap:
                        basemap_surface = build_basemap_surface(
                            center_lat,
                            center_lon,
                            range_nm,
                            WIDTH,
                            HEIGHT
                        )
                        basemap_surface.set_alpha(90)
                        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                        overlay.fill((0, 20, 20, 120))
                        display.screen.blit(overlay, (0, 0))

                elif event.button == 5:
                    range_nm = min(MAX_RANGE_NM, range_nm + ZOOM_STEP_NM)

                    if show_basemap:
                        basemap_surface = build_basemap_surface(
                            center_lat,
                            center_lon,
                            range_nm,
                            WIDTH,
                            HEIGHT
                        )
                        basemap_surface.set_alpha(90)
                        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                        overlay.fill((0, 20, 20, 120))
                        display.screen.blit(overlay, (0, 0))

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

        draw_scene(
            display,
            aircraft_dict,
            center_lat,
            center_lon,
            range_nm,
            basemap_surface
        )
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()