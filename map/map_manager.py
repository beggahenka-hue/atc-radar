import math
import pygame

from config import DEFAULT_RANGE_NM, RADAR_CENTER_LAT, RADAR_CENTER_LON, ZOOM_LEVELS_NM
from map.tiles import build_basemap_surface
from utils import (
    latlon_to_screen,
    latlon_to_world_pixels,
    range_nm_to_zoom,
    screen_to_latlon,
    world_pixels_to_latlon,
)

WHEEL_DEBOUNCE_MS = 90
BASEMAP_IDLE_REBUILD_MS = 180


class MapManager:
    def __init__(self, screen, display):
        self.screen = screen
        self.display = display

        self.center_lat = RADAR_CENTER_LAT
        self.center_lon = RADAR_CENTER_LON

        self.zoom_index = ZOOM_LEVELS_NM.index(DEFAULT_RANGE_NM)
        self.range_nm = ZOOM_LEVELS_NM[self.zoom_index]

        self.basemap_surface = None
        self.basemap_center = None
        self.basemap_range_nm = None
        self.basemap_dirty = False
        self.last_navigation_ms = 0
        self.last_wheel_time = 0

        self.dragging = False
        self.drag_start_mouse = None
        self.drag_start_center = None

        if self.display.layer_states.get("Basemap", True):
            self._rebuild_basemap()
            self.basemap_center = (self.center_lat, self.center_lon)
            self.basemap_range_nm = self.range_nm

    def reset_view(self, now_ms):
        self.center_lat = RADAR_CENTER_LAT
        self.center_lon = RADAR_CENTER_LON
        self.last_navigation_ms = now_ms
        self.basemap_dirty = True

    def handle_layer_toggle(self):
        if not self.display.layer_states.get("Basemap", True):
            self.basemap_surface = None
            self.basemap_center = None
            self.basemap_range_nm = None
            self.basemap_dirty = False
        elif self.basemap_surface is None:
            self._rebuild_basemap()
            self.basemap_center = (self.center_lat, self.center_lon)
            self.basemap_range_nm = self.range_nm
            self.basemap_dirty = False

    def handle_mouse_down(self, event, now_ms):
        if event.button == 3:
            self.dragging = True
            self.drag_start_mouse = event.pos
            self.drag_start_center = (self.center_lat, self.center_lon)
            return

        if event.button not in (4, 5):
            return

        if now_ms - self.last_wheel_time < WHEEL_DEBOUNCE_MS:
            return

        self.last_wheel_time = now_ms
        old_range = self.range_nm
        old_center_lat = self.center_lat
        old_center_lon = self.center_lon

        if event.button == 4:
            self.zoom_index = max(0, self.zoom_index - 1)
        else:
            self.zoom_index = min(len(ZOOM_LEVELS_NM) - 1, self.zoom_index + 1)

        self.range_nm = ZOOM_LEVELS_NM[self.zoom_index]

        if self.range_nm != old_range:
            self.center_lat, self.center_lon = self._zoom_about_mouse(
                old_center_lat,
                old_center_lon,
                old_range,
                self.range_nm,
                pygame.mouse.get_pos(),
            )
            self.last_navigation_ms = now_ms

            if self.display.layer_states.get("Basemap", True):
                self._rebuild_basemap()
                self.basemap_center = (self.center_lat, self.center_lon)
                self.basemap_range_nm = self.range_nm
                self.basemap_dirty = False

    def handle_mouse_up(self, event, now_ms):
        if event.button == 3:
            self.dragging = False
            self.drag_start_mouse = None
            self.drag_start_center = None
            self.last_navigation_ms = now_ms
            self.basemap_dirty = True

    def handle_mouse_motion(self, event, now_ms):
        if not (self.dragging and self.drag_start_mouse and self.drag_start_center):
            return

        new_center_lat, new_center_lon = self._apply_mouse_drag_pan(
            self.drag_start_mouse,
            self.drag_start_center,
            event.pos,
        )

        if new_center_lat != self.center_lat or new_center_lon != self.center_lon:
            self.center_lat = new_center_lat
            self.center_lon = new_center_lon
            self.last_navigation_ms = now_ms
            self.basemap_dirty = True

    def update(self, dt_seconds, keys, now_ms):
        if not self.dragging:
            new_center_lat, new_center_lon, key_center_changed = self._apply_continuous_pan(
                self.center_lat,
                self.center_lon,
                self.range_nm,
                dt_seconds,
                keys,
            )

            if key_center_changed:
                self.center_lat = new_center_lat
                self.center_lon = new_center_lon
                self.last_navigation_ms = now_ms
                self.basemap_dirty = True

        if self.display.layer_states.get("Basemap", True) and self.basemap_surface is None:
            self._rebuild_basemap()
            self.basemap_center = (self.center_lat, self.center_lon)
            self.basemap_range_nm = self.range_nm
            self.basemap_dirty = False

        if (
            self.display.layer_states.get("Basemap", True)
            and self.basemap_surface is not None
            and self.basemap_range_nm != self.range_nm
        ):
            self._rebuild_basemap()
            self.basemap_center = (self.center_lat, self.center_lon)
            self.basemap_range_nm = self.range_nm
            self.basemap_dirty = False

        if (
            self.display.layer_states.get("Basemap", True)
            and self.basemap_dirty
            and self.basemap_range_nm == self.range_nm
            and now_ms - self.last_navigation_ms >= BASEMAP_IDLE_REBUILD_MS
        ):
            self._rebuild_basemap()
            self.basemap_center = (self.center_lat, self.center_lon)
            self.basemap_range_nm = self.range_nm
            self.basemap_dirty = False

    def get_basemap_offset(self):
        if self.basemap_center is None:
            return 0, 0

        basemap_lat, basemap_lon = self.basemap_center
        zoom = range_nm_to_zoom(self.range_nm)

        current_wx, current_wy = latlon_to_world_pixels(self.center_lat, self.center_lon, zoom)
        basemap_wx, basemap_wy = latlon_to_world_pixels(basemap_lat, basemap_lon, zoom)

        offset_x = int(round(basemap_wx - current_wx))
        offset_y = int(round(basemap_wy - current_wy))
        return offset_x, offset_y

    def _rebuild_basemap(self):
        if not self.display.layer_states.get("Basemap", True):
            self.basemap_surface = None
            return

        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        basemap_surface = build_basemap_surface(
            self.center_lat,
            self.center_lon,
            self.range_nm,
            screen_w,
            screen_h,
        )

        if basemap_surface is None:
            self.basemap_surface = None
            return

        basemap_surface = basemap_surface.convert_alpha()
        basemap_surface.set_alpha(90)
        self.basemap_surface = basemap_surface

    def _get_pan_speed_nm_per_sec(self, range_nm, fast=False):
        base = max(2.0, range_nm * 0.9)
        if fast:
            base *= 2.5
        return base

    def _apply_continuous_pan(self, center_lat, center_lon, range_nm, dt_seconds, keys):
        up = keys[pygame.K_UP] or keys[pygame.K_w]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

        if not (up or down or left or right):
            return center_lat, center_lon, False

        fast = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        speed_nm_s = self._get_pan_speed_nm_per_sec(range_nm, fast=fast)
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

    def _get_pixels_per_nm(self, center_lat, center_lon, range_nm):
        zoom = range_nm_to_zoom(range_nm)
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

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

    def _apply_mouse_drag_pan(self, drag_start_mouse, drag_start_center, mouse_pos):
        start_mx, start_my = drag_start_mouse
        mx, my = mouse_pos

        dx = mx - start_mx
        dy = my - start_my

        start_lat, start_lon = drag_start_center
        px_per_nm = self._get_pixels_per_nm(start_lat, start_lon, self.range_nm)

        move_nm_x = -dx / px_per_nm
        move_nm_y = dy / px_per_nm

        new_lat = start_lat + (move_nm_y / 60.0)

        cos_lat = math.cos(math.radians(new_lat))
        if abs(cos_lat) < 0.1:
            cos_lat = 0.1

        new_lon = start_lon + (move_nm_x / (60.0 * cos_lat))
        return new_lat, new_lon

    def _zoom_about_mouse(self, center_lat, center_lon, old_range_nm, new_range_nm, mouse_pos):
        old_zoom = range_nm_to_zoom(old_range_nm)
        new_zoom = range_nm_to_zoom(new_range_nm)

        mx, my = mouse_pos
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

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

        return world_pixels_to_latlon(new_center_wx, new_center_wy, new_zoom)