import time
from typing import List, Optional

import requests

from config import (
    LAMIN,
    LAMAX,
    LOMIN,
    LOMAX,
    OPENSKY_CLIENT_ID,
    OPENSKY_CLIENT_SECRET,
    OPENAIP_API_KEY,
)
from models import Aircraft

OPENSKY_URL = "https://opensky-network.org/api/states/all"
TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"


class OpenSkyProvider:
    def __init__(self):
        self.url = OPENSKY_URL
        self.token_url = TOKEN_URL
        self.access_token = None
        self.token_expires_at = 0
        self.session = requests.Session()

    def _token_valid(self):
        return bool(self.access_token) and time.time() < (self.token_expires_at - 60)

    def _get_token(self, force_refresh=False):
        if not force_refresh and self._token_valid():
            return self.access_token

        response = self.session.post(
            self.token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": OPENSKY_CLIENT_ID,
                "client_secret": OPENSKY_CLIENT_SECRET,
            },
            timeout=10,
        )

        print("OpenSky token status:", response.status_code)
        response.raise_for_status()

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("OpenSky token response saknar access_token")

        expires_in = data.get("expires_in", 1800)
        self.access_token = token
        self.token_expires_at = time.time() + expires_in

        print("OpenSky token acquired, expires_in:", expires_in)
        return token

    def _fetch_states(self, token):
        params = {
            "lamin": LAMIN,
            "lamax": LAMAX,
            "lomin": LOMIN,
            "lomax": LOMAX,
        }

        print("OpenSky bbox:", LAMIN, LAMAX, LOMIN, LOMAX)

        response = self.session.get(
            self.url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )

        print("OpenSky request URL:", response.url)
        print("OpenSky status:", response.status_code)
        print("OpenSky rate remaining:", response.headers.get("X-Rate-Limit-Remaining"))
        print("OpenSky retry after:", response.headers.get("X-Rate-Limit-Retry-After-Seconds"))

        if response.status_code == 401:
            print("OpenSky 401 -> refresh token och försök igen")
            token = self._get_token(force_refresh=True)
            response = self.session.get(
                self.url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            print("OpenSky retry status:", response.status_code)

        response.raise_for_status()

        data = response.json()
        print("OpenSky response keys:", list(data.keys()) if isinstance(data, dict) else type(data))

        if isinstance(data, dict):
            states = data.get("states", [])
            print("OpenSky raw states count:", len(states))
            if states:
                print("OpenSky first raw state:", states[0])
            else:
                print("OpenSky returned empty states list")
                print("OpenSky response body:", data)

        return data

    def _safe_strip(self, value: Optional[str]) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _in_bbox(self, lat, lon):
        if lat is None or lon is None:
            return False
        return LAMIN <= lat <= LAMAX and LOMIN <= lon <= LOMAX

    def _parse_state(self, state) -> Optional[Aircraft]:
        try:
            if not state or len(state) < 11:
                return None

            icao24 = self._safe_strip(state[0]).lower()
            callsign = self._safe_strip(state[1])
            lon = state[5]
            lat = state[6]
            altitude = state[7]
            velocity = state[9]
            heading = state[10]

            if not icao24:
                return None

            if lat is None or lon is None:
                return None

            if not self._in_bbox(lat, lon):
                return None

            return Aircraft(
                icao24=icao24,
                callsign=callsign,
                lat=lat,
                lon=lon,
                altitude=altitude,
                velocity=velocity,
                heading=heading,
            )
        except Exception as e:
            print("Parse error for state:", state)
            print("Reason:", e)
            return None

    def get_aircraft(self) -> List[Aircraft]:
        try:
            token = self._get_token()
            data = self._fetch_states(token)

            if not isinstance(data, dict):
                print("OpenSky: oväntad response-typ")
                return []

            states = data.get("states")
            if states is None:
                print("OpenSky: response saknar 'states'")
                return []

            print("OpenSky: börjar parsing av", len(states), "states")

            aircraft_list = []

            short_rows = 0
            missing_icao = 0
            missing_position = 0
            outside_bbox = 0
            parsed_ok = 0

            for state in states:
                if not state or len(state) < 11:
                    short_rows += 1
                    continue

                icao24 = self._safe_strip(state[0]).lower()
                lon = state[5]
                lat = state[6]

                if not icao24:
                    missing_icao += 1
                    continue

                if lat is None or lon is None:
                    missing_position += 1
                    continue

                if not self._in_bbox(lat, lon):
                    outside_bbox += 1
                    continue

                aircraft = self._parse_state(state)
                if aircraft:
                    aircraft_list.append(aircraft)
                    parsed_ok += 1

            print("OpenSky parse summary:")
            print("  raw states       :", len(states))
            print("  short rows       :", short_rows)
            print("  missing icao24   :", missing_icao)
            print("  missing position :", missing_position)
            print("  outside bbox     :", outside_bbox)
            print("  parsed aircraft  :", parsed_ok)

            if aircraft_list:
                a0 = aircraft_list[0]
                print(
                    "First parsed aircraft:",
                    a0.icao24, a0.callsign, a0.lat, a0.lon, a0.altitude, a0.velocity, a0.heading
                )
            else:
                print("No aircraft survived parsing/filtering")

            return aircraft_list

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            print(f"OpenSky HTTP error: {status} - {e}")
            if e.response is not None:
                try:
                    print("OpenSky error body:", e.response.text[:1000])
                except Exception:
                    pass
            return []
        except Exception as e:
            print("OpenSky general error:", e)
            return []

    # Kompatibilitet med äldre main.py
    def fetch(self) -> List[Aircraft]:
        return self.get_aircraft()


class OpenAIPProvider:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "x-openaip-client-id": OPENAIP_API_KEY,
            "Accept": "application/json",
        })

    # Kompatibilitet med äldre main.py
    def get_reporting_points(self, *args, **kwargs):
        return self.get_fixes(*args, **kwargs)

    def get_fixes(self, *args, **kwargs):
        return []

    def get_navaids(self, *args, **kwargs):
        return []

    def get_airspaces(self, *args, **kwargs):
        return []