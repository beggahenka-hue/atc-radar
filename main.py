import math
import sys
import time
from collections import deque

import pygame

from config import (
    BG_DARK,
    DEFAULT_RANGE_NM,
    FPS,
    RADAR_CENTER_LAT,
    RADAR_CENTER_LON,
    TRAIL_LENGTH,
    ZOOM_LEVELS_NM,
)
from display.radar_display import RadarDisplay
from map_data import load_airspaces, load_fixes, load_navaids
from models import Aircraft
from providers import OpenAIPProvider, OpenSkyProvider
from tile_provider import build_basemap_surface
from utils import (
    get_declutter_profile,
    latlon_to_screen,
    latlon_to_world_pixels,
    nm_distance,
    range_nm_to_zoom,
    screen_to_latlon,
    world_pixels_to_latlon,
)

FETCH_INTERVAL_MS = 10000
CLICK_RADIUS_PX = 15
WHEEL_DEBOUNCE_MS = 90
BASEMAP_IDLE_REBUILD_MS = 180


def merge_aircraft(existing_dict, new_aircraft, center_lat, center_lon, range_nm):
    now = time.time()
    updated = dict(existing_dict)

    # Behåll lite marginal utanför aktuell range så targets inte försvinner
    # direkt vid pan/zoom eller när de ligger nära kanten.
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


def update_aircraft_trails(aircraft_dict, center_lat, center_lon, zoom, screen_w, screen_h):
    visible_aircraft = []
    now = time.time()

    for ac in aircraft_dict.values():
        lat, lon = ac.get_smoothed_position(now)

        if lat is None or lon is None:
            continue

        x, y = latlon_to_screen(
            lat,
            lon,
            center_lat,
            center_lon,
            zoom,
            screen_w,
            screen_h,
        )

        if now - ac.last_trail_time >= ac.trail_interval:
            if not ac.trail:
                ac.trail.append((lat, lon))
                ac.last_trail_time = now
            else:
                prev_lat, prev_lon = ac.trail[-1]
                moved_nm = nm_distance(prev_lat, prev_lon, lat, lon)

                if moved_nm >= 0.03:
                    ac.trail.append((lat, lon))
                    ac.last_trail_time = now

        visible_aircraft.append((ac, x, y))

    return visible_aircraft


def find_clicked_aircraft(aircraft_dict, mouse_pos, center_lat, center_lon, zoom, screen_w, screen_h):
    mx, my = mouse_pos
    clicked = None
    min_dist = CLICK_RADIUS_PX

    for ac in aircraft_dict.values():
        lat = ac.lat
        lon = ac.lon

        if lat is None or lon is None:
            continue

        sx, sy = latlon_to_screen(
            lat,
            lon,
            center_lat,
            center_lon,
            zoom,
            screen_w,
            screen_h,
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


def rebuild_basemap_if_needed(display, center_lat, center_lon, range_nm, screen):
    if not display.layer_states.get("Basemap", True):
        return None

    screen_w = screen.get_width()
    screen_h = screen.get_height()

    basemap_surface = build_basemap_surface(
        center_lat,
        center_lon,
        range_nm,
        screen_w,
        screen_h,
    )

    if basemap_surface is None:
        return None

    # Lätt tonad så radaroverlay fortfarande dominerar visuellt
    basemap_surface = basemap_surface.convert_alpha()
    basemap_surface.set_alpha(90)

    return basemap_surface


def get_basemap_offset(current_center_lat, current_center_lon, basemap_center, range_nm, screen_w, screen_h):
    """
    Beräkna hur mycket en redan renderad basemap ska förskjutas på skärmen
    när radarcentrum har ändrats sedan basemapen byggdes.

    Vi räknar offset direkt i world pixels för att få samma geometri som
    tile-systemet och minska känslan av glidning vid pan/zoom.
    """
    if basemap_center is None:
        return 0, 0

    basemap_lat, basemap_lon = basemap_center
    zoom = range_nm_to_zoom(range_nm)

    current_wx, current_wy = latlon_to_world_pixels(current_center_lat, current_center_lon, zoom)
    basemap_wx, basemap_wy = latlon_to_world_pixels(basemap_lat, basemap_lon, zoom)

    offset_x = int(round(basemap_wx - current_wx))
    offset_y = int(round(basemap_wy - current_wy))

    return offset_x, offset_y


def draw_scene(display, aircraft_dict, center_lat, center_lon, range_nm, basemap_surface, basemap_center):
    zoom = range_nm_to_zoom(range_nm)
    declutter = get_declutter_profile(range_nm)

    # Gör aktuell visning tillgänglig för render-funktionerna
    display.current_range_nm = range_nm
    display.current_zoom = zoom
    display.current_center_lat = center_lat
    display.current_center_lon = center_lon

    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()

    visible_aircraft = update_aircraft_trails(
        aircraft_dict,
        center_lat,
        center_lon,
        zoom,
        screen_w,
        screen_h,
    )

    # Basrensning
    display.screen.fill(BG_DARK)

    # Basemap först
    if display.layer_states.get("Basemap", True) and basemap_surface:
        offset_x, offset_y = get_basemap_offset(
            center_lat,
            center_lon,
            basemap_center,
            range_nm,
            screen_w,
            screen_h,
        )
        display.screen.blit(basemap_surface, (offset_x, offset_y))

    # HMI / bakgrund
    # Viktigt att detta kommer innan labels börjar ritas,
    # eftersom label_rects nollställs här.
    display.draw_background(
        center_lat,
        center_lon,
        range_nm,
        zoom,
        target_count=len(visible_aircraft),
        qnh="1013",
        status="LIVE",
        alarm=None,
    )

    # Kartlager
    if display.layer_states.get("Basemap", True):
        display.draw_coastline_and_water(center_lat, center_lon, zoom, range_nm)

    if display.layer_states.get("Airspaces", True):
        display.draw_airspaces(center_lat, center_lon, zoom, range_nm, declutter)

    if display.layer_states.get("ILS", True):
        display.draw_ils_layers(center_lat, center_lon, zoom, range_nm)

    if display.layer_states.get("Runways", True):
        display.draw_runways(center_lat, center_lon, zoom, range_nm)

    if display.layer_states.get("Fixes", True):
        display.draw_fixes(center_lat, center_lon, zoom, range_nm, declutter)

    if display.layer_states.get("Navaids", True):
        display.draw_navaids(center_lat, center_lon, zoom, range_nm, declutter)

    # Targets
    selected_aircraft = None

    # Rita först alla oselekterade targets
    for ac, sx, sy in visible_aircraft:
        if not ac.selected:
            display.draw_aircraft(ac, sx, sy, declutter, center_lat, center_lon, zoom)

    # Rita vald target sist så den hamnar överst
    for ac, sx, sy in visible_aircraft:
        if ac.selected:
            display.draw_aircraft(ac, sx, sy, declutter, center_lat, center_lon, zoom)
            selected_aircraft = ac

    # Sweep ovanpå kartlager/targets
    if display.layer_states.get("Sweep", True):
        display.draw_sweep()

    # Paneler sist
    display.draw_info_panel(selected_aircraft)
    display.draw_layer_panel()

def get_pan_speed_nm_per_sec(range_nm, fast=False):
    base = max(2.0, range_nm * 0.9)
    if fast:
        base *= 2.5
    return base


def apply_continuous_pan(center_lat, center_lon, range_nm, dt_seconds, keys):
    up = keys[pygame.K_UP] or keys[pygame.K_w]
    down = keys[pygame.K_DOWN] or keys[pygame.K_s]
    left = keys[pygame.K_LEFT] or keys[pygame.K_a]
    right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

    if not (up or down or left or right):
        return center_lat, center_lon, False

    fast = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
    speed_nm_s = get_pan_speed_nm_per_sec(range_nm, fast=fast)
    move_nm = speed_nm_s * dt_seconds

    dlat = 0.0
    dlon = 0.0

    if up:
        dlat += move_nm / 60.0
    if down:
        dlat -= move_nm / 60.0

    cos_lat = math.cos(math.radians(center_lat))
    if abs(cos_lat) < 0.1:
        cos_lat = 0.1

    lon_deg_per_nm = 1.0 / (60.0 * cos_lat)

    if right:
        dlon += move_nm * lon_deg_per_nm
    if left:
        dlon -= move_nm * lon_deg_per_nm

    return center_lat + dlat, center_lon + dlon, True


def get_pixels_per_nm(center_lat, center_lon, range_nm, screen_w, screen_h):
    zoom = range_nm_to_zoom(range_nm)

    _, y0 = latlon_to_screen(
        center_lat,
        center_lon,
        center_lat,
        center_lon,
        zoom,
        screen_w,
        screen_h,
    )

    _, y1 = latlon_to_screen(
        center_lat + (1.0 / 60.0),
        center_lon,
        center_lat,
        center_lon,
        zoom,
        screen_w,
        screen_h,
    )

    px_per_nm = abs(y1 - y0)
    return max(px_per_nm, 0.01)


def apply_mouse_drag_pan(
    drag_start_mouse,
    drag_start_center,
    mouse_pos,
    range_nm,
    screen_w,
    screen_h,
):
    if not drag_start_mouse or not drag_start_center:
        return drag_start_center[0], drag_start_center[1]

    start_mx, start_my = drag_start_mouse
    mx, my = mouse_pos

    dx = mx - start_mx
    dy = my - start_my

    start_lat, start_lon = drag_start_center

    px_per_nm = get_pixels_per_nm(
        start_lat,
        start_lon,
        range_nm,
        screen_w,
        screen_h,
    )

    move_nm_x = -dx / px_per_nm
    move_nm_y = dy / px_per_nm

    new_lat = start_lat + (move_nm_y / 60.0)

    cos_lat = math.cos(math.radians(new_lat))
    if abs(cos_lat) < 0.1:
        cos_lat = 0.1

    new_lon = start_lon + (move_nm_x / (60.0 * cos_lat))

    return new_lat, new_lon


def zoom_about_mouse(center_lat, center_lon, old_range_nm, new_range_nm, mouse_pos, screen_w, screen_h):
    old_zoom = range_nm_to_zoom(old_range_nm)
    new_zoom = range_nm_to_zoom(new_range_nm)

    mx, my = mouse_pos

    target_lat, target_lon = screen_to_latlon(
        mx,
        my,
        center_lat,
        center_lon,
        old_zoom,
        screen_w,
        screen_h,
    )

    target_wx, target_wy = latlon_to_world_pixels(target_lat, target_lon, new_zoom)

    new_center_wx = target_wx - (mx - screen_w / 2)
    new_center_wy = target_wy - (my - screen_h / 2)

    new_center_lat, new_center_lon = world_pixels_to_latlon(
        new_center_wx,
        new_center_wy,
        new_zoom,
    )

    return new_center_lat, new_center_lon


def main():
    pygame.init()

    screen = pygame.display.set_mode((1400, 900))
    pygame.display.set_caption("ATC Radar v3")
    clock = pygame.time.Clock()

    display = RadarDisplay(screen)
    traffic_provider = OpenSkyProvider()
    map_provider = OpenAIPProvider()

    center_lat = RADAR_CENTER_LAT
    center_lon = RADAR_CENTER_LON

    zoom_index = ZOOM_LEVELS_NM.index(DEFAULT_RANGE_NM)
    range_nm = ZOOM_LEVELS_NM[zoom_index]

    basemap_surface = None
    basemap_center = None
    basemap_range_nm = None
    basemap_dirty = False
    last_navigation_ms = 0

    if display.layer_states.get("Basemap", True):
        basemap_surface = rebuild_basemap_if_needed(
            display,
            center_lat,
            center_lon,
            range_nm,
            screen,
        )
        basemap_center = (center_lat, center_lon)
        basemap_range_nm = range_nm

    aircraft_dict = {}
    selected_icao24 = None
    fetch_timer = FETCH_INTERVAL_MS
    last_wheel_time = 0

    dragging = False
    drag_start_mouse = None
    drag_start_center = None

    map_layers_loaded = False

    running = True
    while running:
        dt_ms = clock.tick(FPS)
        dt_seconds = dt_ms / 1000.0
        fetch_timer += dt_ms
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_b:
                    display.layer_states["Basemap"] = not display.layer_states.get("Basemap", True)

                    if display.layer_states.get("Basemap", True):
                        basemap_surface = rebuild_basemap_if_needed(
                            display,
                            center_lat,
                            center_lon,
                            range_nm,
                            screen,
                        )
                        basemap_center = (center_lat, center_lon)
                        basemap_range_nm = range_nm
                        basemap_dirty = False
                    else:
                        basemap_surface = None
                        basemap_center = None
                        basemap_range_nm = None
                        basemap_dirty = False

                elif event.key == pygame.K_r:
                    center_lat = RADAR_CENTER_LAT
                    center_lon = RADAR_CENTER_LON
                    last_navigation_ms = now_ms
                    basemap_dirty = True

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if display.handle_click(event.pos):
                        if not display.layer_states.get("Basemap", True):
                            basemap_surface = None
                            basemap_center = None
                            basemap_range_nm = None
                            basemap_dirty = False
                        elif basemap_surface is None:
                            basemap_surface = rebuild_basemap_if_needed(
                                display,
                                center_lat,
                                center_lon,
                                range_nm,
                                screen,
                            )
                            basemap_center = (center_lat, center_lon)
                            basemap_range_nm = range_nm
                            basemap_dirty = False
                        continue

                    zoom = range_nm_to_zoom(range_nm)
                    clicked = find_clicked_aircraft(
                        aircraft_dict,
                        event.pos,
                        center_lat,
                        center_lon,
                        zoom,
                        screen.get_width(),
                        screen.get_height(),
                    )

                    selected_icao24 = clicked.icao24 if clicked else None
                    set_selected_aircraft(aircraft_dict, selected_icao24)

                elif event.button == 3:
                    dragging = True
                    drag_start_mouse = event.pos
                    drag_start_center = (center_lat, center_lon)

                elif event.button in (4, 5):
                    if now_ms - last_wheel_time < WHEEL_DEBOUNCE_MS:
                        continue
                    last_wheel_time = now_ms

                    old_range = range_nm
                    old_center_lat = center_lat
                    old_center_lon = center_lon

                    if event.button == 4:
                        zoom_index = max(0, zoom_index - 1)
                    else:
                        zoom_index = min(len(ZOOM_LEVELS_NM) - 1, zoom_index + 1)

                    range_nm = ZOOM_LEVELS_NM[zoom_index]

                    if range_nm != old_range:
                        center_lat, center_lon = zoom_about_mouse(
                            old_center_lat,
                            old_center_lon,
                            old_range,
                            range_nm,
                            pygame.mouse.get_pos(),
                            screen.get_width(),
                            screen.get_height(),
                        )
                        last_navigation_ms = now_ms

                        if display.layer_states.get("Basemap", True):
                            basemap_surface = rebuild_basemap_if_needed(
                                display,
                                center_lat,
                                center_lon,
                                range_nm,
                                screen,
                            )
                            basemap_center = (center_lat, center_lon)
                            basemap_range_nm = range_nm
                            basemap_dirty = False

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:
                    dragging = False
                    drag_start_mouse = None
                    drag_start_center = None
                    last_navigation_ms = now_ms
                    basemap_dirty = True

            elif event.type == pygame.MOUSEMOTION:
                if dragging and drag_start_mouse and drag_start_center:
                    new_center_lat, new_center_lon = apply_mouse_drag_pan(
                        drag_start_mouse,
                        drag_start_center,
                        event.pos,
                        range_nm,
                        screen.get_width(),
                        screen.get_height(),
                    )

                    if new_center_lat != center_lat or new_center_lon != center_lon:
                        center_lat = new_center_lat
                        center_lon = new_center_lon
                        last_navigation_ms = now_ms
                        basemap_dirty = True

        if not dragging:
            keys = pygame.key.get_pressed()
            new_center_lat, new_center_lon, key_center_changed = apply_continuous_pan(
                center_lat,
                center_lon,
                range_nm,
                dt_seconds,
                keys,
            )
            if key_center_changed:
                center_lat = new_center_lat
                center_lon = new_center_lon
                last_navigation_ms = now_ms
                basemap_dirty = True

        if display.layer_states.get("Basemap", True) and basemap_surface is None:
            basemap_surface = rebuild_basemap_if_needed(
                display,
                center_lat,
                center_lon,
                range_nm,
                screen,
            )
            basemap_center = (center_lat, center_lon)
            basemap_range_nm = range_nm
            basemap_dirty = False

        if (
            display.layer_states.get("Basemap", True)
            and basemap_surface is not None
            and basemap_range_nm != range_nm
        ):
            basemap_surface = rebuild_basemap_if_needed(
                display,
                center_lat,
                center_lon,
                range_nm,
                screen,
            )
            basemap_center = (center_lat, center_lon)
            basemap_range_nm = range_nm
            basemap_dirty = False

        if (
            display.layer_states.get("Basemap", True)
            and basemap_dirty
            and basemap_range_nm == range_nm
            and now_ms - last_navigation_ms >= BASEMAP_IDLE_REBUILD_MS
        ):
            basemap_surface = rebuild_basemap_if_needed(
                display,
                center_lat,
                center_lon,
                range_nm,
                screen,
            )
            basemap_center = (center_lat, center_lon)
            basemap_range_nm = range_nm
            basemap_dirty = False

        draw_scene(
            display,
            aircraft_dict,
            center_lat,
            center_lon,
            range_nm,
            basemap_surface,
            basemap_center,
        )
        pygame.display.flip()

        if not map_layers_loaded:
            try:
                load_map_layers(map_provider, center_lat, center_lon)
                map_layers_loaded = True
            except Exception as e:
                print("Map layer load error:", e)

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

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()