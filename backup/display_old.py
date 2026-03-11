import math
import pygame

from datetime import datetime
from utils import latlon_to_screen, nm_distance, nm_to_pixels
from map_data import RUNWAYS, get_fixes, get_navaids, get_airspaces
from map_data import COASTLINES, WATER_AREAS
from config import (
    WIDTH, HEIGHT,
    BLACK, RADAR_GREEN, DIM_GREEN, SWEEP_GREEN,
    TEXT_GREEN, SELECTED_COLOR,
    SHOW_TRAILS, TRAIL_POINT_RADIUS,
    BG_DARK, PANEL_BG, PANEL_BORDER,
    TEXT_MAIN, TEXT_DIM, TEXT_WARN, TEXT_ALERT,
    RING_DIM, CROSS_DIM, INFO_BG, INFO_BORDER,
    SHOW_BASEMAP, SHOW_AIRSPACES, SHOW_FIXES, SHOW_NAVAIDS, SHOW_RANGE_RINGS,
    SHOW_RUNWAYS, SHOW_ILS, SHOW_SWEEP, SHOW_LABELS
)


class RadarDisplay:

    def handle_click(self, pos):
        for name, rect in self.layer_rects.items():
            if rect.collidepoint(pos):
                self.layer_states[name] = not self.layer_states[name]
                return True
        return False

    def draw_layer_panel(self):
        panel_w = self.side_panel_width - 20
        panel_x = WIDTH - self.side_panel_width + 10
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

    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 16)
        self.small_font = pygame.font.SysFont("consolas", 14)
        self.sweep_angle = 0
        self.label_rects = []

        self.side_panel_width = 260

        self.layer_states = {
            "Basemap": SHOW_BASEMAP,
            "Airspaces": SHOW_AIRSPACES,
            "Fixes": SHOW_FIXES,
            "Navaids": SHOW_NAVAIDS,
            "Runways": SHOW_RUNWAYS,
            "ILS": SHOW_ILS,
            "Range rings": SHOW_RANGE_RINGS,
            "Sweep": False,
            "Trails": SHOW_TRAILS,
            "Labels": SHOW_LABELS,
        }

        self.layer_rects = {}


    def draw_background(self, center_lat, center_lon, range_nm, zoom, target_count=0, qnh="1013", status="LIVE", alarm=None):
        # Reset label declutter varje frame
        self.label_rects = []

        # HMI paneler
        self.draw_hmi_panels(
            target_count=target_count,
            qnh=qnh,
            status=status,
            alarm=alarm,
            range_nm=range_nm
        )

        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        center_x = screen_w // 2
        center_y = screen_h // 2
        max_radar_radius = min(screen_w, screen_h) // 2 - 80

        # Radar-ringar med realistiska steg
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

                if radius > 0 and radius <= max_radar_radius + 20:
                    pygame.draw.circle(self.screen, RING_DIM, (center_x, center_y), radius, 1)

                    angle = math.radians(30)
                    lx = center_x + radius * math.cos(angle)
                    ly = center_y - radius * math.sin(angle)

                    label = self.small_font.render(f"{nm}", True, TEXT_DIM)
                    label_rect = label.get_rect(topleft=(int(lx + 4), int(ly - 6)))

                    if label_rect.right < WIDTH - 10 and label_rect.top > 10:
                        self.screen.blit(label, label_rect.topleft)

                nm += step

            radar_radius = max_radar_radius

            for angle in range(0, 360, 10):
                rad = math.radians(angle)

                x_outer = center_x + radar_radius * math.cos(rad)
                y_outer = center_y - radar_radius * math.sin(rad)

                if angle % 30 == 0:
                    tick_len = 14
                else:
                    tick_len = 7

                x_inner = center_x + (radar_radius - tick_len) * math.cos(rad)
                y_inner = center_y - (radar_radius - tick_len) * math.sin(rad)

                pygame.draw.line(
                    self.screen,
                    RING_DIM,
                    (int(x_inner), int(y_inner)),
                    (int(x_outer), int(y_outer)),
                    1
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

        # Yttre bearing tick marks
        radar_radius = max_radar_radius

        for angle in range(0, 360, 10):
            rad = math.radians(angle)

            x_outer = center_x + radar_radius * math.cos(rad)
            y_outer = center_y - radar_radius * math.sin(rad)

            if angle % 30 == 0:
                tick_len = 14
            else:
                tick_len = 7

            x_inner = center_x + (radar_radius - tick_len) * math.cos(rad)
            y_inner = center_y - (radar_radius - tick_len) * math.sin(rad)

            pygame.draw.line(
                self.screen,
                RING_DIM,
                (int(x_inner), int(y_inner)),
                (int(x_outer), int(y_outer)),
                1
            )

        # Bearing labels
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

        # Korslinjer
        pygame.draw.line(self.screen, CROSS_DIM, (center_x, 50), (center_x, screen_h - 50), 1)
        pygame.draw.line(self.screen, CROSS_DIM, (50, center_y), (WIDTH - 50, center_y), 1)

        # Center-markering
        pygame.draw.circle(self.screen, RADAR_GREEN, (center_x, center_y), 4, 1)
        pygame.draw.line(self.screen, RADAR_GREEN, (center_x - 8, center_y), (center_x + 8, center_y), 1)
        pygame.draw.line(self.screen, RADAR_GREEN, (center_x, center_y - 8), (center_x, center_y + 8), 1)

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

    def draw_coastline_and_water(self, center_lat, center_lon, zoom, range_nm):
        water_fill = (20, 28, 35)
        coastline_color = (70, 90, 100)

        for polygon in WATER_AREAS:
            screen_points = []

            for lat, lon in polygon:
                if nm_distance(center_lat, center_lon, lat, lon) > range_nm * 1.8:
                    continue

                x, y = latlon_to_screen(
                    lat, lon,
                    center_lat, center_lon,
                    zoom,
                    WIDTH, HEIGHT
                )
                screen_points.append((int(x), int(y)))

            if len(screen_points) >= 3:
                pygame.draw.polygon(self.screen, water_fill, screen_points)

        for line in COASTLINES:
            screen_points = []

            for lat, lon in line:
                if nm_distance(center_lat, center_lon, lat, lon) > range_nm * 1.8:
                    continue

                x, y = latlon_to_screen(
                    lat, lon,
                    center_lat, center_lon,
                    zoom,
                    WIDTH, HEIGHT
                )
                screen_points.append((int(x), int(y)))

            if len(screen_points) >= 2:
                pygame.draw.lines(self.screen, coastline_color, False, screen_points, 1)

    def draw_airspaces(self, center_lat, center_lon, zoom):
        airspaces = get_airspaces()

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        outlines = []

        for asp in airspaces:
            screen_points = []

            for lat, lon in asp["points"]:
                x, y = latlon_to_screen(
                    lat, lon,
                    center_lat, center_lon,
                    zoom,
                    WIDTH, HEIGHT
                )
                screen_points.append((int(x), int(y)))

            if len(screen_points) < 3:
                continue

            name = asp.get("name", "")
            name_upper = name.upper()

            if "CTR" in name_upper:
                fill_color = (80, 180, 140, 45)
                outline_color = (120, 220, 180)
            elif "TMA" in name_upper:
                fill_color = (80, 140, 180, 30)
                outline_color = (120, 180, 220)
            elif "FIR" in name_upper:
                fill_color = (120, 120, 140, 15)
                outline_color = (150, 150, 170)
            elif "R" in name_upper or "D" in name_upper or "P" in name_upper:
                fill_color = (180, 80, 80, 28)
                outline_color = (220, 120, 120)
            else:
                fill_color = (120, 120, 120, 20)
                outline_color = (140, 140, 140)

            pygame.draw.polygon(overlay, fill_color, screen_points)
            outlines.append((screen_points, outline_color, name))

        self.screen.blit(overlay, (0, 0))

        for screen_points, outline_color, name in outlines:
            pygame.draw.polygon(self.screen, outline_color, screen_points, 1)

            lx, ly = screen_points[0]
            txt = self.small_font.render(name, True, outline_color)
            self.screen.blit(txt, (lx + 6, ly + 6))

    def draw_fixes(self, center_lat, center_lon, zoom):
        fixes = get_fixes()
        color = (180, 180, 180)

        for fix in fixes:
            x, y = latlon_to_screen(
                fix["lat"], fix["lon"],
                center_lat, center_lon,
                zoom, WIDTH, HEIGHT
            )

            x = int(x)
            y = int(y)

            if x < 0 or x > WIDTH or y < 0 or y > HEIGHT:
                continue

            pygame.draw.line(self.screen, color, (x, y - 4), (x + 4, y), 1)
            pygame.draw.line(self.screen, color, (x + 4, y), (x, y + 4), 1)
            pygame.draw.line(self.screen, color, (x, y + 4), (x - 4, y), 1)
            pygame.draw.line(self.screen, color, (x - 4, y), (x, y - 4), 1)

            txt = self.small_font.render(fix["name"], True, color)
            self.screen.blit(txt, (x + 6, y - 6))

    def draw_navaids(self, center_lat, center_lon, zoom):
        navaids = get_navaids()
        color = (120, 200, 200)

        for nav in navaids:
            x, y = latlon_to_screen(
                nav["lat"], nav["lon"],
                center_lat, center_lon,
                zoom, WIDTH, HEIGHT
            )

            x = int(x)
            y = int(y)

            if x < 0 or x > WIDTH or y < 0 or y > HEIGHT:
                continue

            pygame.draw.line(self.screen, color, (x - 4, y), (x + 4, y), 1)
            pygame.draw.line(self.screen, color, (x, y - 4), (x, y + 4), 1)

            txt = self.small_font.render(nav["name"], True, color)
            self.screen.blit(txt, (x + 6, y - 6))

    def draw_runways(self, center_lat, center_lon, zoom):
        for rw in RUNWAYS:
            lat1, lon1 = rw["start"]
            lat2, lon2 = rw["end"]

            self.draw_extended_centerline(
                lat1, lon1, lat2, lon2,
                center_lat, center_lon,
                zoom
            )

            x1, y1 = latlon_to_screen(lat1, lon1, center_lat, center_lon, zoom, WIDTH, HEIGHT)
            x2, y2 = latlon_to_screen(lat2, lon2, center_lat, center_lon, zoom, WIDTH, HEIGHT)

            pygame.draw.line(self.screen, DIM_GREEN, (x1, y1), (x2, y2), 3)
            pygame.draw.line(self.screen, (180, 255, 220), (x1, y1), (x2, y2), 2)

            mx = (x1 + x2) // 2
            my = (y1 + y2) // 2
            txt = self.small_font.render(rw["name"], True, (180, 255, 220))
            self.screen.blit(txt, (mx + 6, my + 6))

    def draw_extended_centerline(self, lat1, lon1, lat2, lon2, center_lat, center_lon, zoom):
        x1, y1 = latlon_to_screen(lat1, lon1, center_lat, center_lon, zoom, WIDTH, HEIGHT)
        x2, y2 = latlon_to_screen(lat2, lon2, center_lat, center_lon, zoom, WIDTH, HEIGHT)

        dx = x2 - x1
        dy = y2 - y1

        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return

        dx /= length
        dy /= length

        extend = 220

        start = (x1 - dx * extend, y1 - dy * extend)
        end = (x2 + dx * extend, y2 + dy * extend)

        pygame.draw.line(self.screen, TEXT_DIM, start, end, 1)

        tick_spacing = 60
        tick_size = 4

        for i in range(-4, 5):
            px = x1 + dx * i * tick_spacing
            py = y1 + dy * i * tick_spacing

            tx1 = px - dy * tick_size
            ty1 = py + dx * tick_size
            tx2 = px + dy * tick_size
            ty2 = py - dx * tick_size

            pygame.draw.line(
                self.screen,
                TEXT_DIM,
                (tx1, ty1),
                (tx2, ty2),
                1
            )

    def draw_ils_layers(self, center_lat, center_lon, zoom):
        for rw in RUNWAYS:
            name = rw["name"]
            lat1, lon1 = rw["start"]
            lat2, lon2 = rw["end"]

            if name in ["01R/19L", "01L/19R"]:
                self.draw_ils_corridor(
                    lat1, lon1, lat2, lon2,
                    center_lat, center_lon, zoom
                )

    def draw_ils_corridor(self, lat1, lon1, lat2, lon2, center_lat, center_lon, zoom):
        x1, y1 = latlon_to_screen(lat1, lon1, center_lat, center_lon, zoom, WIDTH, HEIGHT)
        x2, y2 = latlon_to_screen(lat2, lon2, center_lat, center_lon, zoom, WIDTH, HEIGHT)

        dx = x2 - x1
        dy = y2 - y1

        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return

        dx /= length
        dy /= length

        nx = -dy
        ny = dx

        corridor_length = 180
        corridor_half_width = 35

        sx = x1
        sy = y1

        ex = sx + dx * corridor_length
        ey = sy + dy * corridor_length

        left_start = (sx + nx * corridor_half_width, sy + ny * corridor_half_width)
        left_end = (ex + nx * corridor_half_width, ey + ny * corridor_half_width)

        right_start = (sx - nx * corridor_half_width, sy - ny * corridor_half_width)
        right_end = (ex - nx * corridor_half_width, ey - ny * corridor_half_width)

        color = (60, 120, 100)

        pygame.draw.line(self.screen, color, left_start, left_end, 1)
        pygame.draw.line(self.screen, color, right_start, right_end, 1)
        pygame.draw.line(self.screen, color, left_start, right_start, 1)
        pygame.draw.line(self.screen, (70, 160, 140), (sx, sy), (ex, ey), 1)

    def draw_runway_centerline(self):
        center_x = WIDTH // 2
        center_y = HEIGHT // 2

        length = 450
        heading = math.radians(190 - 90)

        dx = math.cos(heading)
        dy = math.sin(heading)

        start = (center_x - dx * length, center_y - dy * length)
        end = (center_x + dx * length, center_y + dy * length)

        pygame.draw.line(self.screen, TEXT_DIM, start, end, 1)

        five_nm = 100
        x5 = center_x + dx * five_nm
        y5 = center_y + dy * five_nm

        pygame.draw.circle(self.screen, TEXT_DIM, (int(x5), int(y5)), 4, 1)
        label5 = self.small_font.render("5", True, TEXT_DIM)
        self.screen.blit(label5, (x5 + 6, y5 - 6))

        ten_nm = 200
        x10 = center_x + dx * ten_nm
        y10 = center_y + dy * ten_nm

        pygame.draw.circle(self.screen, TEXT_DIM, (int(x10), int(y10)), 4, 1)
        label10 = self.small_font.render("10", True, TEXT_DIM)
        self.screen.blit(label10, (x10 + 6, y10 - 6))

    def draw_sweep(self):
        center_x = WIDTH // 2
        center_y = HEIGHT // 2
        radar_radius = min(WIDTH, HEIGHT) // 2 - 80

        end_x = center_x + radar_radius * math.cos(math.radians(self.sweep_angle))
        end_y = center_y - radar_radius * math.sin(math.radians(self.sweep_angle))

        pygame.draw.line(
            self.screen,
            SWEEP_GREEN,
            (center_x, center_y),
            (int(end_x), int(end_y)),
            2
        )

        self.sweep_angle = (self.sweep_angle + 1) % 360

    def draw_trail(self, aircraft):
        if not self.layer_states.get("Trails", True):
            return

        if len(aircraft.trail) < 2:
            return

        trail_points = list(aircraft.trail)

        for i, (x, y) in enumerate(trail_points):
            fade = (i + 1) / len(trail_points)

            if fade < 0.33:
                color = (0, 60, 30)
            elif fade < 0.66:
                color = (0, 120, 60)
            else:
                color = (0, 180, 90)

            pygame.draw.circle(self.screen, color, (int(x), int(y)), TRAIL_POINT_RADIUS)

    def draw_aircraft(self, aircraft, x, y):
        self.draw_trail(aircraft)

        color = SELECTED_COLOR if aircraft.selected else RADAR_GREEN

        pygame.draw.circle(self.screen, color, (int(x), int(y)), 5, 1)
        pygame.draw.line(self.screen, color, (int(x) - 6, int(y)), (int(x) + 6, int(y)), 1)
        pygame.draw.line(self.screen, color, (int(x), int(y) - 6), (int(x), int(y) + 6), 1)

        if aircraft.selected:
            pygame.draw.circle(self.screen, color, (int(x), int(y)), 9, 1)

        if aircraft.heading is not None:
            heading_length = 16
            rad = math.radians(90 - aircraft.heading)

            hx = x + math.cos(rad) * heading_length
            hy = y - math.sin(rad) * heading_length

            pygame.draw.line(
                self.screen,
                DIM_GREEN,
                (int(x), int(y)),
                (int(hx), int(hy)),
                1
            )

        if aircraft.heading is not None and aircraft.velocity:
            predictor_minutes = 2.0
            predict_nm = aircraft.velocity * predictor_minutes / 60.0
            predict_pixels = predict_nm * 12

            rad = math.radians(90 - aircraft.heading)

            px = x + math.cos(rad) * predict_pixels
            py = y - math.sin(rad) * predict_pixels

            pygame.draw.line(
                self.screen,
                (0, 200, 120),
                (int(x), int(y)),
                (int(px), int(py)),
                1
            )

        if self.layer_states.get("Labels", True) and aircraft.callsign:
            callsign = aircraft.callsign.strip()
            alt = "-" if aircraft.altitude is None else int(aircraft.altitude / 100)

            line1 = callsign
            line2 = f"{alt:03}" if alt != "-" else "---"

            label1 = self.small_font.render(line1, True, TEXT_GREEN)
            label2 = self.small_font.render(line2, True, TEXT_GREEN)

            label_w = max(label1.get_width(), label2.get_width()) + 6
            label_h = label1.get_height() + label2.get_height() + 4

            positions = [
                (x + 18, y - 18),
                (x + 18, y + 8),
                (x - 80, y - 18),
                (x - 80, y + 8),
            ]

            label_pos = None
            label_rect = None

            for lx, ly in positions:
                rect = pygame.Rect(int(lx - 2), int(ly - 1), int(label_w), int(label_h))

                if rect.left < 0 or rect.right > WIDTH or rect.top < 0 or rect.bottom > HEIGHT:
                    continue

                target_keepout = pygame.Rect(int(x - 14), int(y - 14), 28, 28)
                if rect.colliderect(target_keepout):
                    continue

                collision = False
                for r in self.label_rects:
                    if rect.colliderect(r):
                        collision = True
                        break

                if not collision:
                    label_pos = (lx, ly)
                    label_rect = rect
                    self.label_rects.append(rect)
                    break

            if not label_pos:
                return

            label_x, label_y = label_pos

            pygame.draw.line(
                self.screen,
                DIM_GREEN,
                (int(x + 6), int(y)),
                (int(label_x - 2), int(label_y + 8)),
                1
            )

            pygame.draw.rect(
                self.screen,
                (10, 30, 10),
                (int(label_x - 2), int(label_y - 1), int(label_w), int(label_h))
            )
            pygame.draw.rect(
                self.screen,
                DIM_GREEN,
                (int(label_x - 2), int(label_y - 1), int(label_w), int(label_h)),
                1
            )

            self.screen.blit(label1, (int(label_x), int(label_y)))
            self.screen.blit(label2, (int(label_x), int(label_y + 14)))

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