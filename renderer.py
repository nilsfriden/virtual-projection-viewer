"""
renderer.py — OpenGL rendering via moderngl.
v1.0

Handles shader compilation, VAO/VBO setup from .obj data,
NDI texture upload, and draw calls.
"""

import moderngl
import numpy as np
import glm
import struct


def _mat4_bytes(m: glm.mat4) -> bytes:
    """Convert a PyGLM mat4 to bytes for moderngl uniform upload."""
    return struct.pack('16f',
        m[0][0], m[0][1], m[0][2], m[0][3],
        m[1][0], m[1][1], m[1][2], m[1][3],
        m[2][0], m[2][1], m[2][2], m[2][3],
        m[3][0], m[3][1], m[3][2], m[3][3],
    )


# --- Shaders ---

VERTEX_SHADER = """
#version 330 core

in vec3 in_position;
in vec2 in_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec2 v_texcoord;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(in_position, 1.0);
    v_texcoord = in_texcoord;
}
"""

FRAGMENT_SHADER = """
#version 330 core

in vec2 v_texcoord;

uniform sampler2D u_texture;
uniform float u_brightness;

out vec4 fragColor;

void main() {
    vec4 texel = texture(u_texture, v_texcoord);
    // NDI is BGRA, swap to RGBA
    fragColor = vec4(texel.b, texel.g, texel.r, texel.a) * u_brightness;
}
"""

# Simple grid shader for floor reference
GRID_VERTEX_SHADER = """
#version 330 core

in vec3 in_position;

uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_pos;

void main() {
    gl_Position = u_projection * u_view * vec4(in_position, 1.0);
    v_world_pos = in_position;
}
"""

GRID_FRAGMENT_SHADER = """
#version 330 core

in vec3 v_world_pos;
out vec4 fragColor;

void main() {
    // Grid pattern based on world position
    vec2 grid = abs(fract(v_world_pos.xz) - 0.5);
    float line = min(grid.x, grid.y);
    float alpha = 1.0 - smoothstep(0.0, 0.05, line);
    fragColor = vec4(1.0, 1.0, 1.0, alpha * 0.4);
}
"""


class SceneRenderer:
    """
    Manages the OpenGL scene: model geometry, texture, grid, and rendering.
    """

    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx

        # Compile shader programs
        self.prog = ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )
        self.grid_prog = ctx.program(
            vertex_shader=GRID_VERTEX_SHADER,
            fragment_shader=GRID_FRAGMENT_SHADER,
        )

        # State
        self.vao = None
        self.vbo = None
        self.texture = None
        self.grid_vao = None
        self.grid_vbo = None
        self.vertex_count = 0
        self.model_matrix = glm.mat4(1.0)
        self.brightness = 1.0

        # Build ground grid
        self._build_grid()

    def load_model(self, vertex_data: np.ndarray):
        """
        Load model geometry from interleaved vertex data [x, y, z, u, v].

        Args:
            vertex_data: np.ndarray of shape (N, 5), dtype float32
        """
        # Clean up previous
        if self.vbo:
            self.vbo.release()
        if self.vao:
            self.vao.release()

        self.vertex_count = len(vertex_data)
        self.vbo = self.ctx.buffer(vertex_data.astype("f4").tobytes())
        self.vao = self.ctx.vertex_array(
            self.prog,
            [(self.vbo, "3f 2f", "in_position", "in_texcoord")],
        )
        print(f"[renderer] Model loaded: {self.vertex_count} vertices")

    def update_texture(self, frame_data: np.ndarray):
        """
        Upload a BGRA video frame as the model texture.

        Args:
            frame_data: np.ndarray of shape (H, W, 4), dtype uint8, BGRA format.
        """
        h, w = frame_data.shape[:2]

        if self.texture is None or self.texture.size != (w, h):
            # (Re)create texture at new resolution
            if self.texture:
                self.texture.release()
            self.texture = self.ctx.texture((w, h), 4)
            self.texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
            print(f"[renderer] Texture created: {w}x{h}")

        # Flip vertically for OpenGL (origin at bottom-left)
        flipped = np.flipud(frame_data)
        self.texture.write(flipped.tobytes())

    def render(self, view: glm.mat4, projection: glm.mat4):
        """
        Render the scene: grid + textured model.
        """
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.clear(0.08, 0.08, 0.08, 1.0)

        # --- Render grid ---
        if self.grid_vao:
            self.grid_prog["u_view"].write(_mat4_bytes(view))
            self.grid_prog["u_projection"].write(_mat4_bytes(projection))
            self.grid_vao.render(moderngl.LINES)

        # --- Render model ---
        if self.vao and self.texture:
            self.prog["u_model"].write(_mat4_bytes(self.model_matrix))
            self.prog["u_view"].write(_mat4_bytes(view))
            self.prog["u_projection"].write(_mat4_bytes(projection))
            self.prog["u_brightness"].value = self.brightness

            self.texture.use(location=0)
            self.prog["u_texture"].value = 0

            self.vao.render(moderngl.TRIANGLES)

    def set_model_transform(self, pos: glm.vec3 = None, scale: float = 1.0,
                            rot_y: float = 0.0):
        """Update the model's world transform."""
        m = glm.mat4(1.0)
        if pos:
            m = glm.translate(m, pos)
        m = glm.rotate(m, glm.radians(rot_y), glm.vec3(0, 1, 0))
        m = glm.scale(m, glm.vec3(scale))
        self.model_matrix = m

    def rebuild_grid(self, y_level: float = 0.0,
                     center_x: float = 0.0, center_z: float = 0.0,
                     grid_size: float = 20.0):
        """Rebuild the grid at a specific Y level and XZ center."""
        if self.grid_vbo:
            self.grid_vbo.release()
        if self.grid_vao:
            self.grid_vao.release()
        self._build_grid(y_level=y_level, center_x=center_x,
                         center_z=center_z, grid_extent=grid_size)

    def _build_grid(self, size: int = 20, spacing: float = 1.0,
                    y_level: float = 0.0,
                    center_x: float = 0.0, center_z: float = 0.0,
                    grid_extent: float = 0.0):
        """Generate a ground-plane grid for spatial reference."""
        if grid_extent > 0:
            half = grid_extent
            spacing = max(0.5, grid_extent / 10.0)
            size = int(2 * half / spacing)
        else:
            half = size * spacing / 2.0

        lines = []
        for i in range(size + 1):
            p = -half + i * spacing
            # Lines along X
            lines.extend([center_x + p, y_level, center_z - half,
                          center_x + p, y_level, center_z + half])
            # Lines along Z
            lines.extend([center_x - half, y_level, center_z + p,
                          center_x + half, y_level, center_z + p])

        grid_data = np.array(lines, dtype="f4")
        self.grid_vbo = self.ctx.buffer(grid_data.tobytes())
        self.grid_vao = self.ctx.vertex_array(
            self.grid_prog,
            [(self.grid_vbo, "3f", "in_position")],
        )

    def destroy(self):
        """Release all GPU resources."""
        for resource in [self.vao, self.vbo, self.texture,
                         self.grid_vao, self.grid_vbo]:
            if resource:
                resource.release()
