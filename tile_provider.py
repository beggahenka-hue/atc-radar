import math
import os

import pygame
import requests

from utils import latlon_to_world_pixels, range_nm_to_zoom

TILE_SIZE = 256
TILE_SERVER = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
CACHE_DIR = "cache/tiles"

tile_surface_cache = {}


def ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)


def clamp_tile_y(y, zoom):
    max_tile = (2 ** zoom) - 1
    return max(0, min(y, max_tile))


def wrap_tile_x(x, zoom):
    max_tile = 2 ** zoom
    return x % max_tile


def fetch_tile(z, x, y):
    ensure_cache()

    x = wrap_tile_x(x, z)
    y = clamp_tile_y(y, z)

    path = f"{CACHE_DIR}/{z}_{x}_{y}.png"

    if os.path.exists(path):
        return path

    url = TILE_SERVER.format(z=z, x=x, y=y)

    try:
        headers = {"User-Agent": "ATC-Radar-v3 (educational project)"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            with open(path, "wb") as f:
                f.write(response.content)
            return path
    except Exception:
        pass

    return None


def load_tile_surface(z, x, y):
    x = wrap_tile_x(x, z)
    y = clamp_tile_y(y, z)

    key = (z, x, y)

    # Redan cachead surface
    if key in tile_surface_cache:
        return tile_surface_cache[key]

    path = fetch_tile(z, x, y)
    if not path:
        return None

    try:
        surface = pygame.image.load(path).convert()
    except Exception:
        return None

    tile_surface_cache[key] = surface

    # Enkel cache-begränsning för att minska minnesväxt över tid
    max_cache_size = 600
    if len(tile_surface_cache) > max_cache_size:
        oldest_key = next(iter(tile_surface_cache))
        if oldest_key != key:
            tile_surface_cache.pop(oldest_key, None)

    return surface


def build_basemap_surface(center_lat, center_lon, range_nm, width, height):
    zoom = range_nm_to_zoom(range_nm)

    center_wx, center_wy = latlon_to_world_pixels(center_lat, center_lon, zoom)

    half_w = width * 0.5
    half_h = height * 0.5

    top_left_wx = center_wx - half_w
    top_left_wy = center_wy - half_h

    start_tile_x = math.floor(top_left_wx / TILE_SIZE)
    start_tile_y = math.floor(top_left_wy / TILE_SIZE)

    first_tile_screen_x = int(round(start_tile_x * TILE_SIZE - top_left_wx))
    first_tile_screen_y = int(round(start_tile_y * TILE_SIZE - top_left_wy))

    surface = pygame.Surface((width, height)).convert()
    surface.fill((0, 0, 0))

    tiles_x = math.ceil(width / TILE_SIZE) + 2
    tiles_y = math.ceil(height / TILE_SIZE) + 2

    for dx in range(tiles_x):
        for dy in range(tiles_y):
            tx = start_tile_x + dx
            ty = start_tile_y + dy

            tile = load_tile_surface(zoom, tx, ty)
            if tile is None:
                continue

            px = first_tile_screen_x + dx * TILE_SIZE
            py = first_tile_screen_y + dy * TILE_SIZE

            surface.blit(tile, (px, py))

    dark_overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    dark_overlay.fill((0, 20, 24, 150))
    surface.blit(dark_overlay, (0, 0))

    radar_tint = pygame.Surface((width, height), pygame.SRCALPHA)
    radar_tint.fill((0, 40, 30, 45))
    surface.blit(radar_tint, (0, 0))

    return surface