import time
import requests

from config import (
    LAMIN,
    LAMAX,
    LOMIN,
    LOMAX,
    OPENSKY_CLIENT_ID,
    OPENSKY_CLIENT_SECRET,
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

    def _get_token(self):
        if self.access_token and time.time() < self.token_expires_at - 60:
            return self.access_token

        response = requests.post(
            self.token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": OPENSKY_CLIENT_ID,
                "client_secret": OPENSKY_CLIENT_SECRET,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        self.access_token = data["access_token"]
        expires_in = data.get("expires_in", 1800)
        self.token_expires_at = time.time() + expires_in
        return self.access_token

    def fetch(self):
        params = {
            "lamin": LAMIN,
            "lamax": LAMAX,
            "lomin": LOMIN,
            "lomax": LOMAX,
        }

        try:
            token = self._get_token()
            response = requests.get(
                self.url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print("OpenSky error:", e)
            return []

        states = data.get("states")
        if not states:
            return []

        aircraft_list = []

        for s in states:
            try:
                icao24 = s[0]
                callsign = s[1].strip() if s[1] else ""
                lon = s[5]
                lat = s[6]
                altitude = s[7]
                velocity = s[9]
                heading = s[10]

                if not icao24 or lat is None or lon is None:
                    continue

                aircraft_list.append(
                    Aircraft(
                        icao24=icao24,
                        callsign=callsign,
                        lat=lat,
                        lon=lon,
                        altitude=altitude,
                        velocity=velocity,
                        heading=heading,
                    )
                )
            except Exception:
                continue

        return aircraft_list


class OpenAIPProvider:
    BASE_URL = "https://api.core.openaip.net/api"
    API_KEY = "AIPKEY"

    def get_airspaces(self, lamin, lamax, lomin, lomax):
        url = f"{self.BASE_URL}/airspaces"

        headers = {
            "x-openaip-api-key": self.API_KEY,
            "accept": "application/json",
        }

        params = {
            "bbox": f"{lomin},{lamin},{lomax},{lamax}"
        }

        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()

        data = r.json()
        return data.get("items", [])

    def get_navaids(self, lamin, lamax, lomin, lomax):
        url = f"{self.BASE_URL}/navaids"

        headers = {
            "x-openaip-api-key": self.API_KEY,
            "accept": "application/json",
        }

        params = {
            "bbox": f"{lomin},{lamin},{lomax},{lamax}"
        }

        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()

        data = r.json()
        return data.get("items", [])

    def get_airport(self, icao):
        url = f"{self.BASE_URL}/airports"

        headers = {
            "x-openaip-api-key": self.API_KEY,
            "accept": "application/json",
        }

        params = {
            "search": icao
        }

        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()

        data = r.json()
        items = data.get("items", [])

        for item in items:
            code = item.get("icaoCode")
            if code and code.upper() == icao.upper():
                return item

        return None

    def get_reporting_points(self, lamin, lamax, lomin, lomax):
        url = f"{self.BASE_URL}/reporting-points"

        headers = {
            "x-openaip-api-key": self.API_KEY,
            "accept": "application/json",
        }

        params = {
            "bbox": f"{lomin},{lamin},{lomax},{lamax}"
        }

        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()

        data = r.json()
        return data.get("items", [])