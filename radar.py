import math
import pygame

from datetime import datetime
from utils import latlon_to_screen, nm_distance
from map_data import RUNWAYS, get_fixes, get_navaids, get_airspaces
from map_data import COASTLINES, WATER_AREAS
from config import (
    WIDTH, HEIGHT,
    BLACK, RADAR_GREEN, DIM_GREEN, SWEEP_GREEN,
    TEXT_GREEN, SELECTED_COLOR,
    SHOW_TRAILS, TRAIL_POINT_RADIUS,
    BG_DARK, PANEL_BG, PANEL_BORDER,
    TEXT_MAIN, TEXT_DIM, TEXT_WARN, TEXT_ALERT,
    RING_DIM, CROSS_DIM, INFO_BG, INFO_BORDER
)


class RadarDisplay:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 16)
        self.small_font = pygame.font.SysFont("consolas", 14)
        self.sweep_angle = 0
        self.label_rects = []

    def draw_background(self, center_lat, center_lon, range_nm, zoom):
        self.screen.fill(BG_DARK)

        # Reset label declutter varje frame
        self.label_rects = []

        self.draw_hmi_panels()

        center_x = WIDTH // 2
        center_y = HEIGHT // 2
        radar_radius = min(WIDTH, HEIGHT) // 2 - 80

        # Radar-ringar
        for i in range(1, 7):
            radius = int(radar_radius * i / 6)

            pygame.draw.circle(self.screen, RING_DIM, (center_x, center_y), radius, 1)

            nm = int(40 * i / 6)
            label = self.small_font.render(f"{nm}", True, TEXT_DIM)
            self.screen.blit(label, (center_x + radius + 4, center_y - 6))

        # Korslinjer
        pygame.draw.line(self.screen, CROSS_DIM, (center_x, 50), (center_x, HEIGHT - 50), 1)
        pygame.draw.line(self.screen, CROSS_DIM, (50, center_y), (WIDTH - 50, center_y), 1)

        # Center markering
        pygame.draw.circle(self.screen, RADAR_GREEN, (center_x, center_y), 4, 1)
        pygame.draw.line(self.screen, RADAR_GREEN, (center_x - 8, center_y), (center_x + 8, center_y), 1)
        pygame.draw.line(self.screen, RADAR_GREEN, (center_x, center_y - 8), (center_x, center_y + 8), 1)

    def draw_hmi_panels(self, target_count=0, qnh="1013", status="LIVE", alarm=None, range_nm=40):
        width = self.screen.get_width()
        height = self.screen.get_height()

        top_h = 34
        bottom_h = 28

        # Top panel
        top_rect = pygame.Rect(0, 0, width, top_h)
        pygame.draw.rect(self.screen, PANEL_BG, top_rect)
        pygame.draw.line(self.screen, PANEL_BORDER, (0, top_h - 1), (width, top_h - 1), 1)

        # Bottom panel
        bottom_rect = pygame.Rect(0, height - bottom_h, width, bottom_h)
        pygame.draw.rect(self.screen, PANEL_BG, bottom_rect)
        pygame.draw.line(self.screen, PANEL_BORDER, (0, height - bottom_h), (width, height - bottom_h), 1)

        # Top text
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

        # Bottom text
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

    def draw_coastline_and_water(self, center_lat, center_lon, range_nm):
        water_fill = (20, 28, 35)
        coastline_color = (70, 90, 100)

        # Vattenpolygoner
        for polygon in WATER_AREAS:
            skip = True
            for lat, lon in polygon:
                if nm_distance(center_lat, center_lon, lat, lon) < range_nm * 1.5:
                    skip = False
                    break

            if skip:
                continue

            screen_points = []
            for lat, lon in polygon:
                x, y = latlon_to_screen(
                    lat, lon,
                    center_lat, center_lon,
                    range_nm,
                    WIDTH, HEIGHT
                )
                screen_points.append((int(x), int(y)))

            if len(screen_points) >= 3:
                pygame.draw.polygon(self.screen, water_fill, screen_points)

        # Kustlinjer
        for line in COASTLINES:
            screen_points = []

            for lat, lon in line:
                dist = nm_distance(center_lat, center_lon, lat, lon)
                if dist > range_nm * 1.8:
                    continue

                x, y = latlon_to_screen(
                    lat, lon,
                    center_lat, center_lon,
                    range_nm,
                    WIDTH, HEIGHT
                )
                screen_points.append((int(x), int(y)))

            if len(screen_points) >= 2:
                pygame.draw.lines(self.screen, coastline_color, False, screen_points, 1)

    def draw_airspaces(self, center_lat, center_lon, range_nm):
        airspaces = get_airspaces()

        outline_color = (70, 70, 70)
        fill_color = (18, 18, 18)

        for asp in airspaces:
            screen_points = []

            for lat, lon in asp["points"]:
                x, y = latlon_to_screen(
                    lat, lon,
                    center_lat, center_lon,
                    range_nm, WIDTH, HEIGHT
                )
                screen_points.append((int(x), int(y)))

            if len(screen_points) < 3:
                continue

            pygame.draw.polygon(self.screen, fill_color, screen_points)
            pygame.draw.polygon(self.screen, outline_color, screen_points, 1)

            lx, ly = screen_points[0]
            txt = self.small_font.render(asp["name"], True, outline_color)
            self.screen.blit(txt, (lx + 6, ly + 6))

    def draw_fixes(self, center_lat, center_lon, range_nm):
        fixes = get_fixes()
        color = (180, 180, 180)

        for fix in fixes:
            x, y = latlon_to_screen(
                fix["lat"], fix["lon"],
                center_lat, center_lon,
                range_nm, WIDTH, HEIGHT
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

    def draw_navaids(self, center_lat, center_lon, range_nm):
        navaids = get_navaids()
        color = (120, 200, 200)

        for nav in navaids:
            x, y = latlon_to_screen(
                nav["lat"], nav["lon"],
                center_lat, center_lon,
                range_nm, WIDTH, HEIGHT
            )

            x = int(x)
            y = int(y)

            if x < 0 or x > WIDTH or y < 0 or y > HEIGHT:
                continue

            pygame.draw.line(self.screen, color, (x - 4, y), (x + 4, y), 1)
            pygame.draw.line(self.screen, color, (x, y - 4), (x, y + 4), 1)

            txt = self.small_font.render(nav["name"], True, color)
            self.screen.blit(txt, (x + 6, y - 6))

    def draw_runways(self, center_lat, center_lon, range_nm):
        for rw in RUNWAYS:
            lat1, lon1 = rw["start"]
            lat2, lon2 = rw["end"]

            self.draw_extended_centerline(
                lat1, lon1, lat2, lon2,
                center_lat, center_lon,
                range_nm
            )

            x1, y1 = latlon_to_screen(lat1, lon1, center_lat, center_lon, range_nm, WIDTH, HEIGHT)
            x2, y2 = latlon_to_screen(lat2, lon2, center_lat, center_lon, range_nm, WIDTH, HEIGHT)

            pygame.draw.line(self.screen, DIM_GREEN, (x1, y1), (x2, y2), 3)
            pygame.draw.line(self.screen, (180, 255, 220), (x1, y1), (x2, y2), 2)

            mx = (x1 + x2) // 2
            my = (y1 + y2) // 2
            txt = self.small_font.render(rw["name"], True, (180, 255, 220))
            self.screen.blit(txt, (mx + 6, my + 6))

    def draw_extended_centerline(self, lat1, lon1, lat2, lon2, center_lat, center_lon, range_nm):
        x1, y1 = latlon_to_screen(lat1, lon1, center_lat, center_lon, range_nm, WIDTH, HEIGHT)
        x2, y2 = latlon_to_screen(lat2, lon2, center_lat, center_lon, range_nm, WIDTH, HEIGHT)

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

    def draw_ils_layers(self, center_lat, center_lon, range_nm):
        for rw in RUNWAYS:
            name = rw["name"]
            lat1, lon1 = rw["start"]
            lat2, lon2 = rw["end"]

            if name in ["01R/19L", "01L/19R"]:
                self.draw_ils_corridor(
                    lat1, lon1, lat2, lon2,
                    center_lat, center_lon, range_nm
                )

    def draw_ils_corridor(self, lat1, lon1, lat2, lon2, center_lat, center_lon, range_nm):
        x1, y1 = latlon_to_screen(lat1, lon1, center_lat, center_lon, range_nm, WIDTH, HEIGHT)
        x2, y2 = latlon_to_screen(lat2, lon2, center_lat, center_lon, range_nm, WIDTH, HEIGHT)

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
        if not SHOW_TRAILS:
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

        # Tydligare targetsymbol
        pygame.draw.circle(self.screen, color, (int(x), int(y)), 5, 1)
        pygame.draw.line(self.screen, color, (int(x) - 6, int(y)), (int(x) + 6, int(y)), 1)
        pygame.draw.line(self.screen, color, (int(x), int(y) - 6), (int(x), int(y) + 6), 1)

        if aircraft.selected:
            pygame.draw.circle(self.screen, color, (int(x), int(y)), 9, 1)

        # Kort heading-vector
        if aircraft.heading is not None:
            length = 20
            rad = math.radians(90 - aircraft.heading)

            hx = x + math.cos(rad) * length
            hy = y - math.sin(rad) * length

            pygame.draw.line(
                self.screen,
                RADAR_GREEN,
                (int(x), int(y)),
                (int(hx), int(hy)),
                1
            )

        # Vector predictor, ca 2 min
        if aircraft.heading is not None and aircraft.velocity:
            predict_nm = aircraft.velocity / 30.0
            predict_length = predict_nm * 12

            rad = math.radians(90 - aircraft.heading)

            px = x + math.cos(rad) * predict_length
            py = y - math.sin(rad) * predict_length

            pygame.draw.line(
                self.screen,
                (0, 200, 120),
                (int(x), int(y)),
                (int(px), int(py)),
                1
            )

        if aircraft.callsign:
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
        panel_x = WIDTH - 320
        panel_y = 20
        panel_w = 280
        panel_h = 180

        pygame.draw.rect(self.screen, (10, 30, 10), (panel_x, panel_y, panel_w, panel_h))
        pygame.draw.rect(self.screen, DIM_GREEN, (panel_x, panel_y, panel_w, panel_h), 1)

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