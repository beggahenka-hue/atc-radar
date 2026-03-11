import math

import pygame

from utils import latlon_to_screen, latlon_to_screen_float, nm_distance
from map.map_data import (
    COASTLINES,
    WATER_AREAS,
    RUNWAYS,
    get_fixes,
    get_navaids,
    get_airspaces,
)
from config import DIM_GREEN, TEXT_DIM


def _is_line_near_screen(x1, y1, x2, y2, screen_w, screen_h, margin=120):
    min_x = min(x1, x2)
    max_x = max(x1, x2)
    min_y = min(y1, y2)
    max_y = max(y1, y2)

    if max_x < -margin or min_x > screen_w + margin:
        return False
    if max_y < -margin or min_y > screen_h + margin:
        return False
    return True


def _should_draw_airspace(asp):
    name = (asp.get("name", "") or "").upper()
    category = (asp.get("category", "") or "").upper()

    if "ESSA" in name and "CTR" in name:
        return True
    if "ARLANDA" in name and "CTR" in name:
        return True
    if "STOCKHOLM/ARLANDA" in name and "CTR" in name:
        return True
    if category == "CTR" and "ESSA" in name:
        return True

    return False


def _label_fits(display, rect):
    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()

    if rect.left < 4 or rect.top < 36:
        return False
    if rect.right > screen_w - 4 or rect.bottom > screen_h - 30:
        return False

    for other in display.label_rects:
        if rect.colliderect(other):
            return False
    return True


def _blit_label_if_free(display, text_surf, anchor_x, anchor_y, dx=6, dy=-6):
    rect = text_surf.get_rect(topleft=(int(anchor_x + dx), int(anchor_y + dy)))
    if _label_fits(display, rect):
        display.screen.blit(text_surf, rect.topleft)
        display.label_rects.append(rect)
        return True
    return False


def _runway_style_for_range(range_nm):
    if range_nm <= 20:
        return {
            "centerline_extend_px": 260.0,
            "tick_spacing_px": 60.0,
            "tick_size_px": 4.0,
            "runway_width": 3,
            "runway_core_width": 2,
            "show_runway_name": True,
            "ils_length_px": 220.0,
            "ils_half_width_px": 36.0,
        }
    elif range_nm <= 40:
        return {
            "centerline_extend_px": 180.0,
            "tick_spacing_px": 52.0,
            "tick_size_px": 4.0,
            "runway_width": 3,
            "runway_core_width": 2,
            "show_runway_name": True,
            "ils_length_px": 170.0,
            "ils_half_width_px": 28.0,
        }
    elif range_nm <= 80:
        return {
            "centerline_extend_px": 110.0,
            "tick_spacing_px": 42.0,
            "tick_size_px": 3.0,
            "runway_width": 2,
            "runway_core_width": 1,
            "show_runway_name": False,
            "ils_length_px": 110.0,
            "ils_half_width_px": 18.0,
        }
    else:
        return {
            "centerline_extend_px": 65.0,
            "tick_spacing_px": 32.0,
            "tick_size_px": 2.0,
            "runway_width": 2,
            "runway_core_width": 1,
            "show_runway_name": False,
            "ils_length_px": 70.0,
            "ils_half_width_px": 10.0,
        }


def draw_extended_centerline(
    display,
    lat1,
    lon1,
    lat2,
    lon2,
    center_lat,
    center_lon,
    zoom,
    range_nm,
    target_surface=None,
):
    surface = target_surface or display.screen
    screen_w = surface.get_width()
    screen_h = surface.get_height()

    style = _runway_style_for_range(range_nm)

    x1, y1 = latlon_to_screen_float(lat1, lon1, center_lat, center_lon, zoom, screen_w, screen_h)
    x2, y2 = latlon_to_screen_float(lat2, lon2, center_lat, center_lon, zoom, screen_w, screen_h)

    if not _is_line_near_screen(x1, y1, x2, y2, screen_w, screen_h):
        return

    dx = x2 - x1
    dy = y2 - y1

    length = math.hypot(dx, dy)
    if length == 0:
        return

    dx /= length
    dy /= length

    extend = style["centerline_extend_px"]

    start = (int(round(x1 - dx * extend)), int(round(y1 - dy * extend)))
    end = (int(round(x2 + dx * extend)), int(round(y2 + dy * extend)))

    pygame.draw.line(surface, TEXT_DIM, start, end, 1)

    tick_spacing = style["tick_spacing_px"]
    tick_size = style["tick_size_px"]
    tick_count = max(2, int(extend / max(tick_spacing, 1)) + 1)

    for i in range(-tick_count, tick_count + 1):
        px = x1 + dx * i * tick_spacing
        py = y1 + dy * i * tick_spacing

        tx1 = int(round(px - dy * tick_size))
        ty1 = int(round(py + dx * tick_size))
        tx2 = int(round(px + dy * tick_size))
        ty2 = int(round(py - dx * tick_size))

        pygame.draw.line(surface, TEXT_DIM, (tx1, ty1), (tx2, ty2), 1)


def draw_runways(display, center_lat, center_lon, zoom, range_nm):
    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()
    style = _runway_style_for_range(range_nm)

    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)

    for rw in RUNWAYS:
        lat1, lon1 = rw["start"]
        lat2, lon2 = rw["end"]

        x1f, y1f = latlon_to_screen_float(lat1, lon1, center_lat, center_lon, zoom, screen_w, screen_h)
        x2f, y2f = latlon_to_screen_float(lat2, lon2, center_lat, center_lon, zoom, screen_w, screen_h)

        if not _is_line_near_screen(x1f, y1f, x2f, y2f, screen_w, screen_h, margin=200):
            continue

        draw_extended_centerline(
            display,
            lat1,
            lon1,
            lat2,
            lon2,
            center_lat,
            center_lon,
            zoom,
            range_nm,
            target_surface=overlay,
        )

        x1 = int(round(x1f))
        y1 = int(round(y1f))
        x2 = int(round(x2f))
        y2 = int(round(y2f))

        pygame.draw.line(overlay, DIM_GREEN, (x1, y1), (x2, y2), style["runway_width"])
        pygame.draw.line(overlay, (180, 255, 220), (x1, y1), (x2, y2), style["runway_core_width"])

        if style["show_runway_name"]:
            mx = int(round((x1f + x2f) / 2.0))
            my = int(round((y1f + y2f) / 2.0))

            txt = display.small_font.render(rw["name"], True, (180, 255, 220))
            _blit_label_if_free(display, txt, mx, my, dx=6, dy=6)

    display.screen.blit(overlay, (0, 0))


def draw_coastline_and_water(display, center_lat, center_lon, zoom, range_nm):
    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()

    water_fill = (20, 28, 35)
    coastline_color = (70, 90, 100)

    for polygon in WATER_AREAS:
        screen_points = []

        for lat, lon in polygon:
            if nm_distance(center_lat, center_lon, lat, lon) > range_nm * 1.8:
                continue

            x, y = latlon_to_screen(lat, lon, center_lat, center_lon, zoom, screen_w, screen_h)
            screen_points.append((int(x), int(y)))

        if len(screen_points) >= 3:
            pygame.draw.polygon(display.screen, water_fill, screen_points)

    for line in COASTLINES:
        screen_points = []

        for lat, lon in line:
            if nm_distance(center_lat, center_lon, lat, lon) > range_nm * 1.8:
                continue

            x, y = latlon_to_screen(lat, lon, center_lat, center_lon, zoom, screen_w, screen_h)
            screen_points.append((int(x), int(y)))

        if len(screen_points) >= 2:
            pygame.draw.lines(display.screen, coastline_color, False, screen_points, 1)


def draw_airspaces(display, center_lat, center_lon, zoom, range_nm, declutter):
    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()

    airspaces = get_airspaces()
    if not airspaces:
        return

    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)

    for asp in airspaces:
        if not _should_draw_airspace(asp):
            continue

        raw_points = asp.get("points", [])
        if len(raw_points) < 3:
            continue

        screen_points = []
        visible_count = 0

        for lat, lon in raw_points:
            x, y = latlon_to_screen(
                lat,
                lon,
                center_lat,
                center_lon,
                zoom,
                screen_w,
                screen_h,
            )

            screen_points.append((int(round(x)), int(round(y))))

            if -200 <= x <= screen_w + 200 and -200 <= y <= screen_h + 200:
                visible_count += 1

        if visible_count == 0:
            continue

        fill_color = (80, 180, 140, 18)
        outline_color = (120, 220, 180)

        pygame.draw.polygon(overlay, fill_color, screen_points)
        pygame.draw.polygon(overlay, outline_color, screen_points, 1)

        name = asp.get("name", "")
        if name and range_nm <= 40:
            lx, ly = screen_points[0]
            txt = display.small_font.render(name, True, TEXT_DIM)
            _blit_label_if_free(display, txt, lx, ly, dx=6, dy=6)

    display.screen.blit(overlay, (0, 0))


def draw_fixes(display, center_lat, center_lon, zoom, range_nm, declutter):
    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()

    fixes = get_fixes()
    color = (180, 180, 180)
    show_fix_names = declutter.get("show_fix_names", True)

    if range_nm <= 20:
        symbol_r = 4
        text_dx = 8
        text_dy = -8
    elif range_nm <= 40:
        symbol_r = 3
        text_dx = 7
        text_dy = -7
    elif range_nm <= 80:
        symbol_r = 2
        text_dx = 6
        text_dy = -6
    else:
        symbol_r = 2
        text_dx = 5
        text_dy = -5

    for fix in fixes:
        lat = fix["lat"]
        lon = fix["lon"]

        if nm_distance(center_lat, center_lon, lat, lon) > range_nm * 1.15:
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

        if x < -20 or x > screen_w + 20 or y < -20 or y > screen_h + 20:
            continue

        x = int(round(x))
        y = int(round(y))

        pygame.draw.line(display.screen, color, (x, y - symbol_r), (x + symbol_r, y), 1)
        pygame.draw.line(display.screen, color, (x + symbol_r, y), (x, y + symbol_r), 1)
        pygame.draw.line(display.screen, color, (x, y + symbol_r), (x - symbol_r, y), 1)
        pygame.draw.line(display.screen, color, (x - symbol_r, y), (x, y - symbol_r), 1)

        if show_fix_names:
            txt = display.small_font.render(fix["name"], True, color)
            _blit_label_if_free(display, txt, x, y, dx=text_dx, dy=text_dy)


def draw_navaids(display, center_lat, center_lon, zoom, range_nm, declutter):
    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()

    navaids = get_navaids()
    color = (120, 200, 200)
    show_navaid_names = declutter.get("show_navaid_names", True)

    if range_nm <= 20:
        symbol_r = 4
        text_dx = 8
        text_dy = -8
    elif range_nm <= 40:
        symbol_r = 3
        text_dx = 7
        text_dy = -7
    elif range_nm <= 80:
        symbol_r = 2
        text_dx = 6
        text_dy = -6
    else:
        symbol_r = 2
        text_dx = 5
        text_dy = -5

    for nav in navaids:
        lat = nav["lat"]
        lon = nav["lon"]

        if nm_distance(center_lat, center_lon, lat, lon) > range_nm * 1.2:
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

        if x < -20 or x > screen_w + 20 or y < -20 or y > screen_h + 20:
            continue

        x = int(round(x))
        y = int(round(y))

        pygame.draw.line(display.screen, color, (x - symbol_r, y), (x + symbol_r, y), 1)
        pygame.draw.line(display.screen, color, (x, y - symbol_r), (x, y + symbol_r), 1)

        if show_navaid_names:
            txt = display.small_font.render(nav["name"], True, color)
            _blit_label_if_free(display, txt, x, y, dx=text_dx, dy=text_dy)
            

def draw_ils_layers(display, center_lat, center_lon, zoom, range_nm):
    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()
    style = _runway_style_for_range(range_nm)

    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)

    for rw in RUNWAYS:
        if rw["name"] in ["01R/19L", "01L/19R"]:
            lat1, lon1 = rw["start"]
            lat2, lon2 = rw["end"]
            draw_ils_corridor(
                overlay,
                lat1,
                lon1,
                lat2,
                lon2,
                center_lat,
                center_lon,
                zoom,
                style["ils_length_px"],
                style["ils_half_width_px"],
            )

    display.screen.blit(overlay, (0, 0))


def draw_ils_corridor(
    surface,
    lat1,
    lon1,
    lat2,
    lon2,
    center_lat,
    center_lon,
    zoom,
    corridor_length,
    corridor_half_width,
):
    screen_w = surface.get_width()
    screen_h = surface.get_height()

    x1, y1 = latlon_to_screen_float(lat1, lon1, center_lat, center_lon, zoom, screen_w, screen_h)
    x2, y2 = latlon_to_screen_float(lat2, lon2, center_lat, center_lon, zoom, screen_w, screen_h)

    if not _is_line_near_screen(x1, y1, x2, y2, screen_w, screen_h, margin=200):
        return

    dx = x2 - x1
    dy = y2 - y1

    length = math.hypot(dx, dy)
    if length == 0:
        return

    dx /= length
    dy /= length

    nx = -dy
    ny = dx

    sx = x1
    sy = y1

    ex = sx + dx * corridor_length
    ey = sy + dy * corridor_length

    left_start = (int(round(sx + nx * corridor_half_width)), int(round(sy + ny * corridor_half_width)))
    left_end = (int(round(ex + nx * corridor_half_width)), int(round(ey + ny * corridor_half_width)))

    right_start = (int(round(sx - nx * corridor_half_width)), int(round(sy - ny * corridor_half_width)))
    right_end = (int(round(ex - nx * corridor_half_width)), int(round(ey - ny * corridor_half_width)))

    center_start = (int(round(sx)), int(round(sy)))
    center_end = (int(round(ex)), int(round(ey)))

    color = (60, 120, 100)

    pygame.draw.line(surface, color, left_start, left_end, 1)
    pygame.draw.line(surface, color, right_start, right_end, 1)
    pygame.draw.line(surface, color, left_start, right_start, 1)
    pygame.draw.line(surface, (70, 160, 140), center_start, center_end, 1)