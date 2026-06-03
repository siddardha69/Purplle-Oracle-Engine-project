# 🗺️ Store Layout Specifications

Place store spatial layouts coordinate mappings inside this directory.

## Expected Specifications:
- **Format**: `store_layout.json`
- **Fields**: Must contain a `"zones"` mapping where each zone ID defines lists of coordinates: `[[x1, y1], [x2, y2], ..., [xN, yN]]`.
- **Validation**: Vertex chains must outline fully closed spatial polygons with correct Shapely geometry structure.
