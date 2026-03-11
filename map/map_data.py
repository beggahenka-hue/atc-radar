COASTLINES = [
    [
        (58.70, 16.10),
        (58.68, 16.18),
        (58.63, 16.24),
        (58.57, 16.28),
        (58.50, 16.30),
        (58.45, 16.22),
        (58.48, 16.12),
        (58.56, 16.05),
        (58.64, 16.03),
    ],
]

WATER_AREAS = [
    [
        (58.72, 16.00),
        (58.72, 16.35),
        (58.40, 16.35),
        (58.40, 16.00),
    ],
]

AIRSPACES = []
FIXES = []
NAVAIDS = []

RUNWAYS = [
    {
        "start": (59.6373, 17.9132),
        "end": (59.6664, 17.9238),
        "name": "01L/19R",
    },
    {
        "start": (59.6264, 17.9507),
        "end": (59.6485, 17.9587),
        "name": "01R/19L",
    },
    {
        "start": (59.6462, 17.8838),
        "end": (59.6522, 17.9551),
        "name": "08/26",
    },
]


def _normalize_name(text):
    return (text or "").strip().upper()


def _is_essa_ctr(name, category):
    n = _normalize_name(name)
    c = _normalize_name(category)

    if "ESSA" in n and "CTR" in n:
        return True

    if c == "CTR" and "ESSA" in n:
        return True

    if "STOCKHOLM/ARLANDA" in n and "CTR" in n:
        return True

    if "ARLANDA" in n and "CTR" in n:
        return True

    return False


def load_airspaces(openaip_provider, lamin, lamax, lomin, lomax):
    global AIRSPACES

    raw_items = openaip_provider.get_airspaces(lamin, lamax, lomin, lomax)
    airspaces = []

    for item in raw_items:
        name = item.get("name", "AIRSPACE")
        category = item.get("category", "UNKNOWN")

        # Endast operativt relevant just nu
        if not _is_essa_ctr(name, category):
            continue

        geometry = item.get("geometry", {})
        geom_type = geometry.get("type")
        coords = geometry.get("coordinates", [])

        if not coords:
            continue

        if geom_type == "Polygon":
            polygons = [coords]
        elif geom_type == "MultiPolygon":
            polygons = coords
        else:
            continue

        for poly in polygons:
            for ring in poly:
                points = []
                for p in ring:
                    if len(p) < 2:
                        continue

                    lon = p[0]
                    lat = p[1]
                    points.append((lat, lon))

                if len(points) >= 3:
                    airspaces.append({
                        "name": name,
                        "category": category,
                        "points": points,
                    })

    AIRSPACES = airspaces
    print("AIRSPACES loaded:", len(AIRSPACES))


def get_airspaces():
    return AIRSPACES


def load_navaids(openaip_provider, lamin, lamax, lomin, lomax):
    global NAVAIDS

    raw_items = openaip_provider.get_navaids(lamin, lamax, lomin, lomax)
    navaids = []

    for item in raw_items:
        name = item.get("name") or item.get("ident") or "NAV"
        nav_type = item.get("type", "NAVAID")

        geometry = item.get("geometry", {})
        coords = geometry.get("coordinates")

        if not coords or len(coords) < 2:
            continue

        lon = coords[0]
        lat = coords[1]

        navaids.append({
            "name": name,
            "type": nav_type,
            "lat": lat,
            "lon": lon,
        })

    NAVAIDS = navaids
    print("NAVAIDS loaded:", len(NAVAIDS))


def get_navaids():
    return NAVAIDS


def get_runways():
    return RUNWAYS


def load_fixes(openaip_provider, lamin, lamax, lomin, lomax):
    global FIXES

    raw_points = openaip_provider.get_reporting_points(lamin, lamax, lomin, lomax)
    fixes = []

    for item in raw_points:
        name = item.get("name") or item.get("ident") or "FIX"

        geometry = item.get("geometry", {})
        coords = geometry.get("coordinates")

        if not coords or len(coords) < 2:
            continue

        lon = coords[0]
        lat = coords[1]

        fixes.append({
            "name": name,
            "lat": lat,
            "lon": lon,
        })

    FIXES = fixes
    print("FIXES loaded:", len(FIXES))


def get_fixes():
    return FIXES

def load_map_layers(openaip, center_lat, center_lon):
    lat_margin = 1.0
    lon_margin = 1.5

    try:
        load_fixes(
            openaip,
            center_lat - lat_margin,
            center_lat + lat_margin,
            center_lon - lon_margin,
            center_lon + lon_margin,
        )
    except Exception as e:
        print("FIXES load error:", e)

    try:
        load_navaids(
            openaip,
            center_lat - lat_margin,
            center_lat + lat_margin,
            center_lon - lon_margin,
            center_lon + lon_margin,
        )
    except Exception as e:
        print("NAVAIDS load error:", e)

    try:
        load_airspaces(
            openaip,
            center_lat - lat_margin,
            center_lat + lat_margin,
            center_lon - lon_margin,
            center_lon + lon_margin,
        )
    except Exception as e:
        print("AIRSPACES load error:", e)