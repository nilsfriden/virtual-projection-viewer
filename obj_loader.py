"""
obj_loader.py — Simple Wavefront .obj parser for moderngl.
v1.2 — Added bounding box calculation.

Parses vertices, texture coordinates, and faces.
Returns interleaved float32 array: [x, y, z, u, v, ...] per vertex.
"""

import numpy as np
from pathlib import Path


def load_obj(filepath: str) -> dict:
    """
    Load a .obj file and return vertex data plus bounding box.

    Returns:
        dict with:
            'vertices': np.ndarray of shape (N, 5) [x, y, z, u, v], float32
            'bounds': dict with 'min' (3,), 'max' (3,), 'center' (3,), 'size' (3,)
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"OBJ file not found: {filepath}")

    positions = []
    texcoords = []
    faces = []

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            prefix = parts[0]

            if prefix == "v" and len(parts) >= 4:
                positions.append([float(parts[1]), float(parts[2]), float(parts[3])])

            elif prefix == "vt" and len(parts) >= 3:
                texcoords.append([float(parts[1]), float(parts[2])])

            elif prefix == "f":
                face_verts = []
                for vert in parts[1:]:
                    indices = vert.split("/")
                    v_idx = int(indices[0]) - 1
                    vt_idx = -1
                    if len(indices) > 1 and indices[1]:
                        vt_idx = int(indices[1]) - 1
                    face_verts.append((v_idx, vt_idx))

                # Triangulate (fan triangulation for convex polygons)
                for i in range(1, len(face_verts) - 1):
                    faces.append(face_verts[0])
                    faces.append(face_verts[i])
                    faces.append(face_verts[i + 1])

    if not positions:
        raise ValueError(f"No vertices found in {filepath}")

    # Build interleaved array
    has_uvs = len(texcoords) > 0
    vertex_data = []

    for v_idx, vt_idx in faces:
        pos = positions[v_idx]
        if has_uvs and vt_idx >= 0:
            uv = texcoords[vt_idx]
        else:
            uv = [0.0, 0.0]
        vertex_data.append([pos[0], pos[1], pos[2], uv[0], uv[1]])

    result = np.array(vertex_data, dtype="f4")

    # Compute bounding box from raw positions
    pos_array = np.array(positions, dtype="f4")
    bbox_min = pos_array.min(axis=0)
    bbox_max = pos_array.max(axis=0)
    bbox_center = (bbox_min + bbox_max) / 2.0
    bbox_size = bbox_max - bbox_min

    print(f"[obj_loader] Loaded {filepath.name}: {len(positions)} verts, "
          f"{len(texcoords)} UVs, {len(result)} tri-verts")
    print(f"[obj_loader] Bounds: min={bbox_min}, max={bbox_max}, "
          f"size={bbox_size}")

    return {
        'vertices': result,
        'bounds': {
            'min': bbox_min,
            'max': bbox_max,
            'center': bbox_center,
            'size': bbox_size,
        }
    }


def generate_test_cube() -> dict:
    """
    Generate a simple UV-mapped cube for testing.
    Returns dict matching load_obj format.
    """
    verts = [
        # Front face (z = 1)
        [-1, -1,  1,  0, 0], [ 1, -1,  1,  1, 0], [ 1,  1,  1,  1, 1],
        [-1, -1,  1,  0, 0], [ 1,  1,  1,  1, 1], [-1,  1,  1,  0, 1],
        # Back face (z = -1)
        [ 1, -1, -1,  0, 0], [-1, -1, -1,  1, 0], [-1,  1, -1,  1, 1],
        [ 1, -1, -1,  0, 0], [-1,  1, -1,  1, 1], [ 1,  1, -1,  0, 1],
        # Left face (x = -1)
        [-1, -1, -1,  0, 0], [-1, -1,  1,  1, 0], [-1,  1,  1,  1, 1],
        [-1, -1, -1,  0, 0], [-1,  1,  1,  1, 1], [-1,  1, -1,  0, 1],
        # Right face (x = 1)
        [ 1, -1,  1,  0, 0], [ 1, -1, -1,  1, 0], [ 1,  1, -1,  1, 1],
        [ 1, -1,  1,  0, 0], [ 1,  1, -1,  1, 1], [ 1,  1,  1,  0, 1],
        # Top face (y = 1)
        [-1,  1,  1,  0, 0], [ 1,  1,  1,  1, 0], [ 1,  1, -1,  1, 1],
        [-1,  1,  1,  0, 0], [ 1,  1, -1,  1, 1], [-1,  1, -1,  0, 1],
        # Bottom face (y = -1)
        [-1, -1, -1,  0, 0], [ 1, -1, -1,  1, 0], [ 1, -1,  1,  1, 1],
        [-1, -1, -1,  0, 0], [ 1, -1,  1,  1, 1], [-1, -1,  1,  0, 1],
    ]
    data = np.array(verts, dtype="f4")
    return {
        'vertices': data,
        'bounds': {
            'min': np.array([-1, -1, -1], dtype="f4"),
            'max': np.array([1, 1, 1], dtype="f4"),
            'center': np.array([0, 0, 0], dtype="f4"),
            'size': np.array([2, 2, 2], dtype="f4"),
        }
    }
