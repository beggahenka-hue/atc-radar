# Skärm
WIDTH = 1400
HEIGHT = 900
FPS = 30

# Radarcenter ESSA
RADAR_CENTER_LAT = 59.6519
RADAR_CENTER_LON = 17.9186

# Range / zoom
ZOOM_LEVELS_NM = [10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100, 120, 160]

DEFAULT_RANGE_NM = 40
MIN_RANGE_NM = min(ZOOM_LEVELS_NM)
MAX_RANGE_NM = max(ZOOM_LEVELS_NM)

# Grundfärger
BLACK = (0, 0, 0)

# Klassiska radar-färger
RADAR_GREEN = (0, 255, 120)
DIM_GREEN = (0, 120, 60)
SWEEP_GREEN = (80, 255, 160)
TEXT_GREEN = (120, 255, 180)
SELECTED_COLOR = (255, 255, 255)

# Radar / HMI
BG_DARK = (3, 10, 12)
RADAR_BG = (2, 14, 16)

PANEL_BG = (8, 22, 24)
PANEL_BORDER = (40, 110, 95)

TEXT_MAIN = (120, 255, 180)
TEXT_DIM = (70, 150, 120)
TEXT_WARN = (255, 210, 90)
TEXT_ALERT = (255, 120, 120)

RING_DIM = (60, 110, 110)
CROSS_DIM = (0, 85, 65)

INFO_BG = (6, 24, 12)
INFO_BORDER = (0, 150, 100)

# Trails
TRAIL_LENGTH = 20
TRAIL_POINT_RADIUS = 2
SHOW_TRAILS = True

# OpenSky bounding box kring ESSA
LAMIN = 57.0
LAMAX = 60.5
LOMIN = 15.0
LOMAX = 20.0

# Tile / map projection
TILE_SIZE = 256

# Tile zoom limits
MIN_TILE_ZOOM = 7
MAX_TILE_ZOOM = 12

# Lager-visning
SHOW_BASEMAP = True
SHOW_AIRSPACES = True
SHOW_FIXES = True
SHOW_NAVAIDS = True
SHOW_RANGE_RINGS = True
SHOW_RUNWAYS = True
SHOW_ILS = True
SHOW_SWEEP = False
SHOW_LABELS = True

# API credentials
OPENSKY_CLIENT_ID = "henrikberggren-api-client"

import os
from dotenv import load_dotenv

load_dotenv()

OPENSKY_CLIENT_ID = os.getenv("OPENSKY_CLIENT_ID", "")
OPENSKY_CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_SECRET", "")