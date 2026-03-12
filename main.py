import sys
import pygame

from config import (
    BG_DARK,
    FPS,
)

from display.radar_display import RadarDisplay
from map.map_manager import MapManager
from map.map_data import load_map_layers
from traffic.traffic_manager import TrafficManager
from providers.opensky import OpenAIPProvider, OpenSkyProvider
from utils import get_declutter_profile, range_nm_to_zoom

from display.render_scene import draw_scene


def main():

    pygame.init()

    screen = pygame.display.set_mode((1400, 900))
    pygame.display.set_caption("ATC Radar v4")

    clock = pygame.time.Clock()

    display = RadarDisplay(screen)

    opensky_provider = OpenSkyProvider()
    map_provider = OpenAIPProvider()

    traffic_manager = TrafficManager(opensky_provider)
    map_manager = MapManager(screen, display)

    aircraft_dict = traffic_manager.get_aircraft()

    selected_icao24 = None
    map_layers_loaded = False

    running = True

    while running:

        dt_ms = clock.tick(FPS)
        dt_seconds = dt_ms / 1000.0
        now_ms = pygame.time.get_ticks()

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_b:
                    display.layer_states["Basemap"] = not display.layer_states.get("Basemap", True)
                    map_manager.handle_layer_toggle()

                elif event.key == pygame.K_r:
                    map_manager.reset_view(now_ms)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if display.handle_click(event.pos):
                        map_manager.handle_layer_toggle()
                        continue

                    zoom = range_nm_to_zoom(map_manager.range_nm)
                    clicked = find_clicked_aircraft(
                        aircraft_dict,
                        event.pos,
                        map_manager.center_lat,
                        map_manager.center_lon,
                        zoom,
                        screen.get_width(),
                        screen.get_height(),
                    )
                    selected_icao24 = clicked.icao24 if clicked else None
                    set_selected_aircraft(aircraft_dict, selected_icao24)

                else:
                    map_manager.handle_mouse_down(event, now_ms)

            elif event.type == pygame.MOUSEBUTTONUP:
                map_manager.handle_mouse_up(event, now_ms)

            elif event.type == pygame.MOUSEMOTION:
                map_manager.handle_mouse_motion(event, now_ms)

        keys = pygame.key.get_pressed()
        map_manager.update(dt_seconds, keys, now_ms)

        if not map_layers_loaded:
            try:
                load_map_layers(
                    map_provider,
                    map_manager.center_lat,
                    map_manager.center_lon,
                )
                map_layers_loaded = True
            except Exception as e:
                print("Map layer load error:", e)

        aircraft_dict = traffic_manager.update(now_ms)

        draw_scene(
            display,
            aircraft_dict,
            map_manager.center_lat,
            map_manager.center_lon,
            map_manager.range_nm,
            map_manager.basemap_surface,
            map_manager.basemap_center,
        )

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()