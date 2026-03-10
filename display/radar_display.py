import math
from datetime import datetime

import pygame

from .render_aircraft import draw_aircraft, draw_trail
from .render_map import (
    draw_airspaces,
    draw_coastline_and_water,
    draw_fixes,
    draw_ils_layers,
    draw_navaids,
    draw_runways,
)
from config import (
    CROSS_DIM,
    INFO_BG,
    INFO_BORDER,
    PANEL_BG,
    PANEL_BORDER,
    RING_DIM,
    SHOW_AIRSPACES,
    SHOW_BASEMAP,
    SHOW_FIXES,
    SHOW_ILS,
    SHOW_LABELS,
    SHOW_NAVAIDS,
    SHOW_RANGE_RINGS,
    SHOW_RUNWAYS,
    SHOW_SWEEP,
    SHOW_TRAILS,
    SWEEP_GREEN,
    TEXT_ALERT,
    TEXT_DIM,
    TEXT_GREEN,
    TEXT_MAIN,
    TEXT_WARN,
)
from utils import nm_to_pixels


class RadarDisplay:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 16)
        self.small_font = pygame.font.SysFont("consolas", 14)
        self.sweep_angle = 0
        self.label_rects = []
        self.side_panel_width = 260

        # Aktuell visningsstatus sätts i draw_scene()
        # men defaultvärden här gör renderingen robust redan från start.
        self.current_range_nm = 40
        self.current_zoom = 9
        self.current_center_lat = 59.6519
        self.current_center_lon = 17.9186

        self.layer_states = {
            "Basemap": SHOW_BASEMAP,
            "Airspaces": SHOW_AIRSPACES,
            "Fixes": SHOW_FIXES,
            "Navaids": SHOW_NAVAIDS,
            "Runways": SHOW_RUNWAYS,
            "ILS": SHOW_ILS,
            "Range rings": SHOW_RANGE_RINGS,
            "Sweep": SHOW_SWEEP,
            "Trails": SHOW_TRAILS,
            "Labels": SHOW_LABELS,
        }

        self.layer_rects = {}

    def handle_click(self, pos):
        for name, rect in self.layer_rects.items():
            if rect.collidepoint(pos):
                self.layer_states[name] = not self.layer_states[name]
                return True
        return False

    def draw_layer_panel(self):
        screen_w = self.screen.get_width()
        panel_w = self.side_panel_width - 20
        panel_x = screen_w - self.side_panel_width + 10
        panel_y = 250
        panel_h = 300

        pygame.draw.rect(self.screen, INFO_BG, (panel_x, panel_y, panel_w, panel_h))
        pygame.draw.rect(self.screen, INFO_BORDER, (panel_x, panel_y, panel_w, panel_h), 1)

        title = self.font.render("LAYERS", True, TEXT_GREEN)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        self.layer_rects = {}

        start_y = panel_y + 42
        row_h = 24
        box_size = 12

        for i, (name, enabled) in enumerate(self.layer_states.items()):
            row_y = start_y + i * row_h

            click_rect = pygame.Rect(panel_x + 8, row_y - 2, panel_w - 16, 20)
            self.layer_rects[name] = click_rect

            box_rect = pygame.Rect(panel_x + 10, row_y, box_size, box_size)
            pygame.draw.rect(self.screen, TEXT_DIM, box_rect, 1)

            if enabled:
                inner = box_rect.inflate(-4, -4)
                pygame.draw.rect(self.screen, TEXT_GREEN, inner)

            txt = self.small_font.render(name, True, TEXT_MAIN)
            self.screen.blit(txt, (panel_x + 30, row_y - 2))

    def draw_background(
        self,
        center_lat,
        center_lon,
        range_nm,
        zoom,
        target_count=0,
        qnh="1013",
        status="LIVE",
        alarm=None,
    ):
        self.label_rects = []

        self.draw_hmi_panels(
            target_count=target_count,
            qnh=qnh,
            status=status,
            alarm=alarm,
            range_nm=range_nm,
        )

        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        center_x = screen_w // 2
        center_y = screen_h // 2
        max_radar_radius = min(screen_w, screen_h) // 2 - 80

        if range_nm <= 20:
            step = 5
        elif range_nm <= 60:
            step = 10
        else:
            step = 20

        if self.layer_states.get("Range rings", True):
            nm = step
            while nm <= range_nm:
                radius = int(nm_to_pixels(center_lat, center_lon, zoom, nm))

                if 0 < radius <= max_radar_radius + 20:
                    pygame.draw.circle(self.screen, RING_DIM, (center_x, center_y), radius, 1)

                    angle = math.radians(30)
                    lx = center_x + radius * math.cos(angle)
                    ly = center_y - radius * math.sin(angle)

                    label = self.small_font.render(f"{nm}", True, TEXT_DIM)
                    label_rect = label.get_rect(topleft=(int(lx + 4), int(ly - 6)))

                    if label_rect.right < screen_w - 10 and label_rect.top > 10:
                        self.screen.blit(label, label_rect.topleft)

                nm += step

            radar_radius = max_radar_radius

            for angle in range(0, 360, 10):
                rad = math.radians(angle)

                x_outer = center_x + radar_radius * math.cos(rad)
                y_outer = center_y - radar_radius * math.sin(rad)

                tick_len = 14 if angle % 30 == 0 else 7

                x_inner = center_x + (radar_radius - tick_len) * math.cos(rad)
                y_inner = center_y - (radar_radius - tick_len) * math.sin(rad)

                pygame.draw.line(
                    self.screen,
                    RING_DIM,
                    (int(x_inner), int(y_inner)),
                    (int(x_outer), int(y_outer)),
                    1,
                )

            bearing_labels = [
                ("000", 90),
                ("090", 0),
                ("180", 270),
                ("270", 180),
            ]

            label_radius = radar_radius + 18

            for text, angle_deg in bearing_labels:
                rad = math.radians(angle_deg)
                lx = center_x + label_radius * math.cos(rad)
                ly = center_y - label_radius * math.sin(rad)
                surf = self.small_font.render(text, True, TEXT_DIM)
                rect = surf.get_rect(center=(int(lx), int(ly)))
                self.screen.blit(surf, rect.topleft)

        pygame.draw.line(self.screen, CROSS_DIM, (center_x, 50), (center_x, screen_h - 50), 1)
        pygame.draw.line(self.screen, CROSS_DIM, (50, center_y), (screen_w - 50, center_y), 1)

    def draw_hmi_panels(self, target_count=0, qnh="1013", status="LIVE", alarm=None, range_nm=40):
        width = self.screen.get_width()
        height = self.screen.get_height()

        top_h = 34
        bottom_h = 28

        top_rect = pygame.Rect(0, 0, width, top_h)
        pygame.draw.rect(self.screen, PANEL_BG, top_rect)
        pygame.draw.line(self.screen, PANEL_BORDER, (0, top_h - 1), (width, top_h - 1), 1)

        bottom_rect = pygame.Rect(0, height - bottom_h, width, bottom_h)
        pygame.draw.rect(self.screen, PANEL_BG, bottom_rect)
        pygame.draw.line(self.screen, PANEL_BORDER, (0, height - bottom_h), (width, height - bottom_h), 1)

        utc_now = datetime.utcnow().strftime("%H:%M:%SZ")
        left_text = "ESSA RADAR"
        center_text = f"RANGE {int(range_nm)} NM"
        right_text = f"QNH {qnh}   UTC {utc_now}"

        left_surf = self.small_font.render(left_text, True, TEXT_MAIN)
        center_surf = self.small_font.render(center_text, True, TEXT_MAIN)
        right_surf = self.small_font.render(right_text, True, TEXT_MAIN)

        self.screen.blit(left_surf, (10, 8))
        self.screen.blit(center_surf, (width // 2 - center_surf.get_width() // 2, 8))
        self.screen.blit(right_surf, (width - right_surf.get_width() - 10, 8))

        alarm_text = alarm if alarm else "NO ACTIVE ALARMS"
        alarm_color = TEXT_ALERT if alarm else TEXT_DIM

        status_left = f"SOURCE {status}"
        status_mid = f"TARGETS {target_count}"
        status_right = alarm_text

        left2 = self.small_font.render(status_left, True, TEXT_MAIN if status == "LIVE" else TEXT_WARN)
        mid2 = self.small_font.render(status_mid, True, TEXT_MAIN)
        right2 = self.small_font.render(status_right, True, alarm_color)

        self.screen.blit(left2, (10, height - bottom_h + 6))
        self.screen.blit(mid2, (width // 2 - mid2.get_width() // 2, height - bottom_h + 6))
        self.screen.blit(right2, (width - right2.get_width() - 10, height - bottom_h + 6))

    def draw_sweep(self):
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        center_x = screen_w // 2
        center_y = screen_h // 2
        radar_radius = min(screen_w, screen_h) // 2 - 80

        end_x = center_x + radar_radius * math.cos(math.radians(self.sweep_angle))
        end_y = center_y - radar_radius * math.sin(math.radians(self.sweep_angle))

        pygame.draw.line(
            self.screen,
            SWEEP_GREEN,
            (center_x, center_y),
            (int(end_x), int(end_y)),
            2,
        )

        self.sweep_angle = (self.sweep_angle + 1) % 360

    def draw_info_panel(self, selected_aircraft):
        panel_w = self.side_panel_width - 20
        screen_w = self.screen.get_width()
        panel_x = screen_w - self.side_panel_width + 10
        panel_y = 44
        panel_h = 190

        pygame.draw.rect(self.screen, INFO_BG, (panel_x, panel_y, panel_w, panel_h))
        pygame.draw.rect(self.screen, INFO_BORDER, (panel_x, panel_y, panel_w, panel_h), 1)

        title = self.font.render("TARGET INFO", True, TEXT_GREEN)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        if not selected_aircraft:
            txt = self.small_font.render("No target selected", True, TEXT_GREEN)
            self.screen.blit(txt, (panel_x + 10, panel_y + 45))
            return

        lines = [
            f"Callsign: {selected_aircraft.callsign.strip() if selected_aircraft.callsign else '-'}",
            f"ICAO24: {selected_aircraft.icao24}",
            f"Lat: {selected_aircraft.lat:.4f}",
            f"Lon: {selected_aircraft.lon:.4f}",
            f"Alt: {int(selected_aircraft.altitude) if selected_aircraft.altitude else '-'} ft",
            f"Speed: {int(selected_aircraft.velocity) if selected_aircraft.velocity else '-'} kt",
            f"Heading: {int(selected_aircraft.heading) if selected_aircraft.heading is not None else '-'}",
        ]

        for i, line in enumerate(lines):
            txt = self.small_font.render(line, True, TEXT_GREEN)
            self.screen.blit(txt, (panel_x + 10, panel_y + 45 + i * 20))

    draw_aircraft = draw_aircraft
    draw_trail = draw_trail

    draw_coastline_and_water = draw_coastline_and_water
    draw_airspaces = draw_airspaces
    draw_fixes = draw_fixes
    draw_ils_layers = draw_ils_layers
    draw_navaids = draw_navaids
    draw_runways = draw_runways