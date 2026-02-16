"""
V6 visual debug. Folium only. No FastAPI. Debug-only.
"""

import folium
from typing import List

from backend.v6.domain.models import Employee, NetworkDesign

_COLORS = [
    "red", "blue", "green", "purple", "orange", "darkred", "lightred",
    "beige", "darkblue", "darkgreen", "cadetblue", "darkpurple", "pink",
]


def visualize_network(network_design: NetworkDesign, employees: List[Employee]) -> folium.Map:
    """
    Plot employees (blue dots), shuttle stops (red circles), routes (colored polylines).
    Popup shows occupancy per route.
    """
    if not employees and not network_design.stops:
        center = (40.42, -3.70)
    elif network_design.stops:
        center = (network_design.stops[0].lat, network_design.stops[0].lng)
    else:
        center = (employees[0].home_lat, employees[0].home_lng)

    m = folium.Map(location=center, zoom_start=12)

    for emp in employees:
        folium.CircleMarker(
            location=(emp.home_lat, emp.home_lng),
            radius=4,
            color="blue",
            fill=True,
            fill_opacity=0.8,
            popup=emp.employee_id,
        ).add_to(m)

    stop_by_id = {s.stop_id: s for s in network_design.stops}

    for i, route in enumerate(network_design.routes):
        color = _COLORS[i % len(_COLORS)]
        coords = []
        for sid in route.stop_ids:
            if sid in stop_by_id:
                s = stop_by_id[sid]
                coords.append((s.lat, s.lng))
        if coords:
            folium.PolyLine(coords, color=color, weight=4, opacity=0.8).add_to(m)
        occ = len(route.employee_ids) / route.capacity if route.capacity else 0
        label = f"Route {route.route_id}: occupancy {occ:.0%} ({len(route.employee_ids)}/{route.capacity})"
        if coords:
            folium.Marker(
                coords[0],
                popup=label,
                icon=folium.Icon(color=color, icon="bus", prefix="fa"),
            ).add_to(m)

    for stop in network_design.stops:
        folium.CircleMarker(
            location=(stop.lat, stop.lng),
            radius=10,
            color="red",
            fill=True,
            fill_opacity=0.7,
            weight=2,
            popup=f"Stop {stop.stop_id} — {len(stop.employee_ids)} employees",
        ).add_to(m)

    return m
