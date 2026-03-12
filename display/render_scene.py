from config import BG_DARK
from utils import (
    get_declutter_profile,
    latlon_to_screen,
    latlon_to_world_pixels,
    range_nm_to_zoom,
)


def get_basemap_offset(current_center_lat, current_center_lon, basemap_center, range_nm):
    if basemap_center is None:
        return 0, 0

    basemap_lat, basemap_lon = basemap_center
    zoom = range_nm_to_zoom(range_nm)

    current_wx, current_wy = latlon_to_world_pixels(current_center_lat, current_center_lon, zoom)
    basemap_wx, basemap_wy = latlon_to_world_pixels(basemap_lat, basemap_lon, zoom)

    offset_x = int(round(basemap_wx - current_wx))
    offset_y = int(round(basemap_wy - current_wy))
    return offset_x, offset_y


def draw_scene(
    display,
    aircraft_dict,
    center_lat,
    center_lon,
    range_nm,
    basemap_surface,
    basemap_center,
):
    zoom = range_nm_to_zoom(range_nm)
    declutter = get_declutter_profile(range_nm)

    display.current_range_nm = range_nm
    display.current_zoom = zoom
    display.current_center_lat = center_lat
    display.current_center_lon = center_lon

    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()

    visible_aircraft = []

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

        visible_aircraft.append((ac, sx, sy))

    display.screen.fill(BG_DARK)

    if display.layer_states.get("Basemap", True) and basemap_surface:
        offset_x, offset_y = get_basemap_offset(
            center_lat,
            center_lon,
            basemap_center,
            range_nm,
        )
        display.screen.blit(basemap_surface, (offset_x, offset_y))

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

    selected_aircraft = None

    for ac, sx, sy in visible_aircraft:
        if not ac.selected:
            display.draw_aircraft(ac, sx, sy, declutter, center_lat, center_lon, zoom)

    for ac, sx, sy in visible_aircraft:
        if ac.selected:
            display.draw_aircraft(ac, sx, sy, declutter, center_lat, center_lon, zoom)
            selected_aircraft = ac

    if display.layer_states.get("Sweep", True):
        display.draw_sweep()

    display.draw_info_panel(selected_aircraft)
    display.draw_layer_panel()