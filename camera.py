"""
camera.py — Orbit camera with Maya-style controls.
v1.3 — Replaced FPS camera with orbit camera (target + azimuth/elevation/distance).

Controls (in main.py):
    Alt + LMB drag  = Orbit (tumble)
    Alt + MMB drag  = Pan
    Alt + RMB drag  = Dolly
    Scroll          = Dolly
"""

import glm
import math
import numpy as np


class Camera:
    def __init__(self):
        # Target point (what the camera orbits around / looks at)
        self.target_x: float = 0.0
        self.target_y: float = 0.0
        self.target_z: float = 0.0

        # Orbit parameters
        self.azimuth: float = 0.0      # Horizontal angle (degrees), 0 = looking along -Z
        self.elevation: float = 20.0   # Vertical angle (degrees), 0 = level
        self.distance: float = 10.0    # Distance from target

        # Lens
        self.fov: float = 60.0

        # Clipping
        self.near: float = 0.01
        self.far: float = 500.0

    def _get_position(self) -> glm.vec3:
        """Calculate camera position from orbit parameters."""
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)

        # Spherical to cartesian (camera position relative to target)
        x = self.distance * math.cos(el) * math.sin(az)
        y = self.distance * math.sin(el)
        z = self.distance * math.cos(el) * math.cos(az)

        return glm.vec3(
            self.target_x + x,
            self.target_y + y,
            self.target_z + z,
        )

    def get_view_matrix(self) -> glm.mat4:
        """Build the view matrix: look from position toward target."""
        pos = self._get_position()
        target = glm.vec3(self.target_x, self.target_y, self.target_z)
        up = glm.vec3(0, 1, 0)
        return glm.lookAt(pos, target, up)

    def get_projection_matrix(self, aspect_ratio: float) -> glm.mat4:
        """Build perspective projection matrix."""
        fov_rad = glm.radians(max(self.fov, 1.0))
        return glm.perspective(fov_rad, aspect_ratio, self.near, self.far)

    def get_right_vector(self) -> glm.vec3:
        """Get the camera's local right direction (for panning)."""
        az = math.radians(self.azimuth)
        return glm.vec3(math.cos(az), 0, -math.sin(az))

    def get_up_vector(self) -> glm.vec3:
        """Get the camera's local up direction (for panning)."""
        # Simplified: always world-up projected onto camera plane
        return glm.vec3(0, 1, 0)

    def orbit(self, delta_x: float, delta_y: float, sensitivity: float = 0.3):
        """Orbit around the target (Alt + LMB)."""
        self.azimuth -= delta_x * sensitivity
        self.elevation += delta_y * sensitivity
        self.elevation = max(-89.0, min(89.0, self.elevation))

    def pan(self, delta_x: float, delta_y: float, sensitivity: float = 0.005):
        """Pan the target point (Alt + MMB)."""
        scale = self.distance * sensitivity
        right = self.get_right_vector()
        self.target_x -= right.x * delta_x * scale
        self.target_z -= right.z * delta_x * scale
        self.target_y += delta_y * scale

    def dolly(self, amount: float, sensitivity: float = 0.1):
        """Move closer/farther from target (Alt + RMB or scroll)."""
        self.distance *= (1.0 - amount * sensitivity)
        self.distance = max(0.1, min(1000.0, self.distance))

    def fit_to_bounds(self, bounds: dict):
        """
        Position the camera to see the entire model.

        Args:
            bounds: dict with 'min', 'max', 'center', 'size' as np.ndarray(3,)
        """
        center = bounds['center']
        size = bounds['size']

        max_dim = float(max(size[0], size[1], size[2]))
        if max_dim < 0.001:
            max_dim = 2.0

        # Target = center of model
        self.target_x = float(center[0])
        self.target_y = float(center[1])
        self.target_z = float(center[2])

        # Distance to see the whole model
        half_fov = math.radians(self.fov / 2.0)
        self.distance = (max_dim / 2.0) / math.tan(half_fov) * 1.5

        # Level view, from the front
        self.azimuth = 0.0
        self.elevation = 15.0

        # Adjust clipping
        self.near = max(0.01, max_dim * 0.001)
        self.far = max(500.0, self.distance * 5.0)

        print(f"[camera] Fit to model: target=({self.target_x:.1f}, "
              f"{self.target_y:.1f}, {self.target_z:.1f}), "
              f"distance={self.distance:.1f}")

    def reset(self):
        """Reset camera to default position."""
        self.__init__()
