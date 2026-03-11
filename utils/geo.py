import math

TILE_SIZE = 256
MAX_MERCATOR_LAT = 85.05112878


def clamp_lat(lat):
    return max(min(lat, MAX_MERCATOR_LAT), -MAX_MERCATOR_LAT)


def nm_distance(lat1, lon1, lat2, lon2):
    earth_radius_nm = 3440.065

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_nm * c


def latlon_to_world_pixels(lat, lon, zoom):
    lat = clamp_lat(lat)
    lat_rad = math.radians(lat)

    world_size = TILE_SIZE * (2 ** zoom)

    x = ((lon + 180.0) / 360.0) * world_size

    mercator = math.log(math.tan((math.pi / 4.0) + (lat_rad / 2.0)))
    y = (1.0 - (mercator / math.pi)) * 0.5 * world_size

    return x, y


def world_pixels_to_latlon(wx, wy, zoom):
    scale = TILE_SIZE * (2 ** zoom)

    lon = (wx / scale) * 360.0 - 180.0

    n = math.pi - (2.0 * math.pi * wy / scale)
    lat = math.degrees(math.atan(math.sinh(n)))
    lat = clamp_lat(lat)

    return lat, lon


def world_to_screen_float(wx, wy, center_wx, center_wy, width, height):
    """
    Konverterar world pixel-koordinater till skärmkoordinater
    relativt aktuellt radarcenter.
    """

    dx = wx - center_wx
    dy = wy - center_wy

    sx = dx + width * 0.5
    sy = dy + height * 0.5

    return sx, sy


def world_to_screen(wx, wy, center_wx, center_wy, width, height):
    sx, sy = world_to_screen_float(wx, wy, center_wx, center_wy, width, height)
    return int(round(sx)), int(round(sy))


def latlon_to_screen_float(lat, lon, center_lat, center_lon, zoom, width, height):
    wx, wy = latlon_to_world_pixels(lat, lon, zoom)
    cwx, cwy = latlon_to_world_pixels(center_lat, center_lon, zoom)
    return world_to_screen_float(wx, wy, cwx, cwy, width, height)


def latlon_to_screen(lat, lon, center_lat, center_lon, zoom, width, height):
    sx, sy = latlon_to_screen_float(lat, lon, center_lat, center_lon, zoom, width, height)
    return int(round(sx)), int(round(sy))


def screen_to_latlon(sx, sy, center_lat, center_lon, zoom, width, height):
    center_wx, center_wy = latlon_to_world_pixels(center_lat, center_lon, zoom)

    wx = center_wx + (sx - width / 2.0)
    wy = center_wy + (sy - height / 2.0)

    return world_pixels_to_latlon(wx, wy, zoom)


def nm_to_pixels(center_lat, center_lon, zoom, nm):
    delta_lat = nm / 60.0

    _, y1 = latlon_to_world_pixels(center_lat, center_lon, zoom)
    _, y2 = latlon_to_world_pixels(center_lat + delta_lat, center_lon, zoom)

    return abs(y2 - y1)


def range_nm_to_zoom(range_nm):
    if range_nm <= 10:
        return 11
    elif range_nm <= 20:
        return 10
    elif range_nm <= 40:
        return 9
    elif range_nm <= 80:
        return 8
    else:
        return 7


def get_declutter_profile(range_nm):
    if range_nm <= 20:
        return {
            "fix_stride": 1,
            "show_fix_names": True,
            "show_navaid_names": True,
            "show_airspace_names": True,
            "label_mode": "full",
            "predictor_minutes": 2.0,
        }

    elif range_nm <= 40:
        return {
            "fix_stride": 2,
            "show_fix_names": True,
            "show_navaid_names": False,
            "show_airspace_names": False,
            "label_mode": "normal",
            "predictor_minutes": 1.5,
        }

    else:
        return {
            "fix_stride": 4,
            "show_fix_names": False,
            "show_navaid_names": False,
            "show_airspace_names": False,
            "label_mode": "minimal",
            "predictor_minutes": 1.0,
        }