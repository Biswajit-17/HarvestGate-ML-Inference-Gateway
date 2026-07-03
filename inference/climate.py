"""
climate.py — Async weather resolver fetching live rainfall averages from Open-Meteo.

Calculates 10-year rolling daily rainfall averages and falls back
to historical defaults from state_defaults.json if external APIs fail.
Uses a time-to-live cache to prevent API rate limits.
"""

import datetime
import json
import logging
from typing import Dict, Optional, Tuple
import httpx

from gateway.security import verify_file_integrity

logger = logging.getLogger("harvestgate.climate")


class ClimateResolver:

    def __init__(self, defaults_path: str):
        # 1. Verify file integrity
        if not verify_file_integrity(defaults_path):
            raise ValueError("Defaults file integrity mismatch.")

        # 2. Load defaults
        with open(defaults_path, "r", encoding="utf-8") as f:
            self.defaults: Dict[str, dict] = json.load(f)

        # 3. Simple in-memory cache with expiry
        # Key: (state, district) -> (timestamp, data_dict)
        self._cache: Dict[Tuple[str, Optional[str]], Tuple[datetime.datetime, dict]] = {}
        self.CACHE_TTL = datetime.timedelta(hours=24)

    def _get_historical_fallback(self, state: str, district: Optional[str]) -> Tuple[dict, str]:
        """Retrieve state or district defaults from pre-computed JSON."""
        # Resolve Odisha to Orissa spelling
        lookup_state = state
        if lookup_state.upper() == "ODISHA":
            lookup_state = "Orissa"

        state_data = self.defaults.get(lookup_state, {})
        if not state_data:
            raise ValueError(f"State '{state}' not found in historical defaults.")

        # Try district first if provided
        if district:
            normalized_dist = district.strip()
            # Try exact case match first, then case-insensitive
            districts = state_data.get("districts", {})
            dist_data = districts.get(normalized_dist)

            if not dist_data:
                # Case-insensitive scan
                for d_name, d_val in districts.items():
                    if d_name.upper() == normalized_dist.upper():
                        dist_data = d_val
                        break

            if dist_data:
                logger.info(f"Using historical district averages for: {district}, {state}")
                return dist_data, "historical-district"

        # Fallback to state defaults
        logger.info(f"Using historical state averages for: {state}")
        return state_data.get("state_defaults", {}), "historical-state"

    async def resolve(self, state: str, district: Optional[str] = None) -> Tuple[dict, str]:
        """
        Resolve climate data for a given region.

        Checks cache first, then calls Nominatim and Open-Meteo APIs.
        Falls back to pre-computed averages if APIs are down.

        Returns:
            Tuple[climate_dict, source_string]
        """
        cache_key = (state, district)
        now = datetime.datetime.now()

        # Check cache
        if cache_key in self._cache:
            timestamp, cached_data = self._cache[cache_key]
            if now - timestamp < self.CACHE_TTL:
                logger.info(f"Serving climate from cache: {district}, {state}")
                return cached_data, "cached"

        try:
            # ── 1. Geocoding via Nominatim ──
            query = f"{district},{state}+India" if district else f"{state}+India"
            headers = {"User-Agent": "HarvestGateInferenceGateway/1.0"}

            async with httpx.AsyncClient(headers=headers, timeout=5.0) as client:
                geo_res = await client.get(
                    f"https://nominatim.openstreetmap.org/search?q={query}&format=json"
                )

                if geo_res.status_code != 200 or not geo_res.json():
                    logger.warning(
                        f"Geocoding failed for {query} (status: {geo_res.status_code}). Using fallback."
                    )
                    fallback_data, source = self._get_historical_fallback(state, district)
                    return fallback_data, source

                lat = geo_res.json()[0]["lat"]
                lon = geo_res.json()[0]["lon"]

                # ── 2. Call Open-Meteo Archive API ──
                # Dynamic 10-year rolling window ending at last complete year
                end_year = now.year - 1
                start_year = end_year - 9
                start_date = f"{start_year}-01-01"
                end_date = f"{end_year}-12-31"

                weather_url = (
                    f"https://archive-api.open-meteo.com/v1/archive?"
                    f"latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}"
                    f"&daily=precipitation_sum&timezone=auto"
                )

                weather_res = await client.get(weather_url, timeout=10.0)

                if weather_res.status_code != 200:
                    logger.warning(
                        f"Open-Meteo failed (status: {weather_res.status_code}). Using fallback."
                    )
                    fallback_data, source = self._get_historical_fallback(state, district)
                    return fallback_data, source

                # ── 3. Aggregate PrecipitationSum ──
                data = weather_res.json()
                dates = data["daily"]["time"]
                precip = data["daily"]["precipitation_sum"]

                yearly = {
                    y: {"annual": 0.0, "kharif": 0.0, "rabi": 0.0}
                    for y in range(start_year, end_year + 1)
                }

                for d, p in zip(dates, precip):
                    if p is None:
                        continue
                    parts = d.split("-")
                    year = int(parts[0])
                    month = int(parts[1])

                    if year not in yearly:
                        continue

                    yearly[year]["annual"] += p
                    if 6 <= month <= 9:
                        yearly[year]["kharif"] += p
                    elif month >= 10 or month <= 3:
                        yearly[year]["rabi"] += p

                # Compute 10-year average
                n_years = len(yearly)
                annual_avg = sum(yearly[y]["annual"] for y in yearly) / n_years
                kharif_avg = sum(yearly[y]["kharif"] for y in yearly) / n_years
                rabi_avg = sum(yearly[y]["rabi"] for y in yearly) / n_years

                # Get historical defaults to complete the profile (NPK & Irrigation ratio)
                fallback_profile, _ = self._get_historical_fallback(state, district)

                climate_profile = {
                    "n_avg": fallback_profile.get("n_avg", 50.0),
                    "p_avg": fallback_profile.get("p_avg", 30.0),
                    "k_avg": fallback_profile.get("k_avg", 20.0),
                    "annual_rainfall_avg": round(annual_avg, 1),
                    "kharif_rainfall_avg": round(kharif_avg, 1),
                    "rabi_rainfall_avg": round(rabi_avg, 1),
                    "irrigation_ratio_avg": fallback_profile.get("irrigation_ratio_avg", 0.15),
                }

                # Update cache
                self._cache[cache_key] = (now, climate_profile)
                logger.info(f"Successfully resolved live climate for {district}, {state}")
                return climate_profile, "open-meteo"

        except Exception as e:
            logger.error(f"Unexpected error in climate resolution: {e}. Falling back.")
            fallback_data, source = self._get_historical_fallback(state, district)
            return fallback_data, source
