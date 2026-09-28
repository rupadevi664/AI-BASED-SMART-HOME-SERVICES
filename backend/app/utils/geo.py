"""Geospatial utilities (static profile coordinates — no live GPS)."""
import math

EARTH_RADIUS_KM = 6371.0


def calculate_distance(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    """Haversine great-circle distance between two points, in kilometers.

    a = sin^2(dLat/2) + cos(lat1) * cos(lat2) * sin^2(dLon/2)
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = EARTH_RADIUS_KM * c      (Earth radius ~= 6371 km)
    """
    if None in (latitude_1, longitude_1, latitude_2, longitude_2):
        raise ValueError("All four coordinate values are required")

    phi_1 = math.radians(float(latitude_1))
    phi_2 = math.radians(float(latitude_2))
    delta_phi = math.radians(float(latitude_2) - float(latitude_1))
    delta_lambda = math.radians(float(longitude_2) - float(longitude_1))

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda / 2) ** 2
    )
    # Guard against tiny floating-point excursions outside [0, 1].
    a = min(1.0, max(0.0, a))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c
