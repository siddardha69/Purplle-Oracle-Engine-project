from typing import List, Tuple, Dict, Any, Optional
from shapely.geometry import Point, Polygon

class SpatialZone:
    """
    Wraps standard Shapely polygons outlining specific physical shopping sections.
    Handles point-in-polygon checks to evaluate zone interactions.
    """
    def __init__(self, name: str, vertices: List[Tuple[float, float]]):
        self.name = name
        self.vertices = vertices
        # Safe constructor protecting against non-polygon dimensional shapes
        if len(vertices) < 3:
            raise ValueError(f"Polygon zones require at least 3 vertex pairs. Zone: {name}")
        self.polygon = Polygon(vertices)

    def contains_point(self, x: float, y: float) -> bool:
        """
        Evaluates whether standard spatial coordinates fall inside this layout zone.
        """
        point = Point(x, y)
        return self.polygon.contains(point)

    def distance_to_point(self, x: float, y: float) -> float:
        """
        Computes metric distance from point to zone boundary (useful for proximity indicators).
        """
        point = Point(x, y)
        return self.polygon.distance(point)

def parse_layout_zones(layout_dict: Dict[str, Any]) -> List[SpatialZone]:
    """
    Parses layout dictionary definitions (typically store_layout.json) 
    into lists of active SpatialZone objects.
    """
    spatial_zones = []
    zones_data = layout_dict.get("zones", {})
    
    for zone_name, coordinates in zones_data.items():
        try:
            # Enforce vertices list conversion
            vertices = [tuple(coord) for coord in coordinates]
            spatial_zones.append(SpatialZone(zone_name, vertices))
        except Exception as e:
            from loguru import logger
            logger.error(f"Failed to parse spatial layout coordinates for zone {zone_name}. Error: {e}")
            
    return spatial_zones

def get_bottom_center(bbox: List[float]) -> Tuple[float, float]:
    """
    Returns center bottom coordinate of a visual detection box: (x1, y1, x2, y2).
    This serves as the floor coordinate index (standing location of customer).
    """
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2
    cy = y2
    return cx, cy
