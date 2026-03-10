import math
import pygame

from config import DIM_GREEN, RADAR_GREEN, SELECTED_COLOR, TEXT_GREEN, TRAIL_POINT_RADIUS
from utils import latlon_to_screen


def draw_trail(display, aircraft, center_lat, center_lon, zoom):
    if not display.layer_states.get("Trails", True):
        return

    if len(aircraft.trail) < 2:
        return

    screen_w = display.screen.get_width()
    screen_h = display.screen.get_height()

    trail_points = []
    margin = 20

    for lat, lon in aircraft.trail:
        x, y = latlon_to_screen(
            lat,
            lon,
            center_lat,
            center_lon,
            zoom,
            screen_w,
            screen_h,
        )

        if -margin <= x <= screen_w + margin and -margin <= y <= screen_h + margin:
            trail_points.append((int(x), int(y)))

    if len(trail_points) < 2:
        return

    # Rita först svaga segment för bättre sammanhängande trail-känsla
    for i in range(1, len(trail_points)):
        x1, y1 = trail_points[i - 1]
        x2, y2 = trail_points[i]

        fade = i / len(trail_points)

        if fade < 0.33:
            color = (0, 50, 25)
        elif fade < 0.66:
            color = (0, 100, 50)
        else:
            color = (0, 160, 80)

        pygame.draw.line(display.screen, color, (x1, y1), (x2, y2), 1)

    # Rita sedan punkterna ovanpå, med starkare intensitet närmare nutid
    for i, (x, y) in enumerate(trail_points):
        fade = (i + 1) / len(trail_points)

        if fade < 0.33:
            color = (0, 60, 30)
            radius = max(1, TRAIL_POINT_RADIUS - 1)
        elif fade < 0.66:
            color = (0, 120, 60)
            radius = TRAIL_POINT_RADIUS
        else:
            color = (0, 180, 90)
            radius = TRAIL_POINT_RADIUS

        pygame.draw.circle(display.screen, color, (x, y), radius)


def draw_aircraft(display, aircraft, x, y, declutter, center_lat, center_lon, zoom):
    draw_trail(display, aircraft, center_lat, center_lon, zoom)

    from hmi_profile import get_hmi_profile
    from utils import nm_to_pixels

    range_nm = getattr(display, "current_range_nm", 40)
    profile = get_hmi_profile(range_nm)
    symbol = profile["target_symbol"]

    color = SELECTED_COLOR if aircraft.selected else RADAR_GREEN
    label_color = SELECTED_COLOR if aircraft.selected else TEXT_GREEN

    ix = int(x)
    iy = int(y)

    # Target symbol
    pygame.draw.circle(display.screen, color, (ix, iy), symbol, 1)

    pygame.draw.line(
        display.screen,
        color,
        (ix - symbol - 1, iy),
        (ix + symbol + 1, iy),
        1,
    )

    pygame.draw.line(
        display.screen,
        color,
        (ix, iy - symbol - 1),
        (ix, iy + symbol + 1),
        1,
    )

    if aircraft.selected:
        pygame.draw.circle(display.screen, color, (ix, iy), symbol + 4, 1)

    # Heading vector
    if aircraft.heading is not None:
        heading_length = max(12, symbol * 3)
        rad = math.radians(90 - aircraft.heading)

        hx = x + math.cos(rad) * heading_length
        hy = y - math.sin(rad) * heading_length

        pygame.draw.line(
            display.screen,
            DIM_GREEN,
            (ix, iy),
            (int(hx), int(hy)),
            1,
        )

    # Predictor - använd riktig zoomberoende skala
    if aircraft.heading is not None and aircraft.velocity:
        predictor_minutes = profile.get(
            "predictor_minutes",
            declutter.get("predictor_minutes", 2.0),
        )
        predict_nm = aircraft.velocity * predictor_minutes / 60.0
        predict_pixels = nm_to_pixels(center_lat, center_lon, zoom, predict_nm)

        rad = math.radians(90 - aircraft.heading)

        px = x + math.cos(rad) * predict_pixels
        py = y - math.sin(rad) * predict_pixels

        pygame.draw.line(
            display.screen,
            DIM_GREEN,
            (ix, iy),
            (int(px), int(py)),
            1,
        )

    # Labels
    if display.layer_states.get("Labels", True) and aircraft.callsign:
        callsign = aircraft.callsign.strip()
        alt = "-" if aircraft.altitude is None else int(aircraft.altitude / 100)

        mode = profile.get("label_mode", declutter.get("label_mode", "normal"))

        line1 = callsign
        if mode == "minimal":
            line2 = None
        else:
            line2 = f"{alt:03}" if alt != "-" else "---"

        label1 = display.small_font.render(line1, True, label_color)

        if line2 is not None:
            label2 = display.small_font.render(line2, True, label_color)
            label_w = max(label1.get_width(), label2.get_width()) + 6
            label_h = label1.get_height() + label2.get_height() + 4
            line2_y = label1.get_height()
        else:
            label2 = None
            label_w = label1.get_width() + 6
            label_h = label1.get_height() + 4
            line2_y = 0

        screen_w = display.screen.get_width()
        screen_h = display.screen.get_height()

        offset = max(18, symbol * 3)
        left_offset = max(80, label_w + 16)

        positions = [
            ("right_up", x + offset, y - offset),
            ("right_down", x + offset, y + 8),
            ("left_up", x - left_offset, y - offset),
            ("left_down", x - left_offset, y + 8),
        ]

        label_pos = None
        label_side = None

        for side, lx, ly in positions:
            rect = pygame.Rect(int(lx - 2), int(ly - 1), int(label_w), int(label_h))

            if rect.left < 0 or rect.right > screen_w or rect.top < 0 or rect.bottom > screen_h:
                continue

            keepout = max(14, symbol + 8)
            target_keepout = pygame.Rect(
                int(x - keepout),
                int(y - keepout),
                keepout * 2,
                keepout * 2,
            )
            if rect.colliderect(target_keepout):
                continue

            collision = any(rect.colliderect(r) for r in display.label_rects)
            if not collision:
                label_pos = (lx, ly)
                label_side = side
                display.label_rects.append(rect)
                break

        if not label_pos:
            return

        label_x, label_y = label_pos

        # Leader line får rätt anslutningspunkt beroende på sida
        if label_side.startswith("right"):
            leader_end_x = int(label_x - 2)
            leader_start_x = ix + symbol
        else:
            leader_end_x = int(label_x + label_w - 2)
            leader_start_x = ix - symbol

        leader_end_y = int(label_y + min(8, label_h // 2))

        pygame.draw.line(
            display.screen,
            DIM_GREEN,
            (leader_start_x, iy),
            (leader_end_x, leader_end_y),
            1,
        )

        pygame.draw.rect(
            display.screen,
            (10, 30, 10),
            (int(label_x - 2), int(label_y - 1), int(label_w), int(label_h)),
        )
        pygame.draw.rect(
            display.screen,
            DIM_GREEN,
            (int(label_x - 2), int(label_y - 1), int(label_w), int(label_h)),
            1,
        )

        display.screen.blit(label1, (int(label_x), int(label_y)))

        if label2 is not None:
            display.screen.blit(label2, (int(label_x), int(label_y + line2_y)))