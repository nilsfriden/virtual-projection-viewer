"""
main.py — Virtual Projection Viewer
v1.4 — Refined UI, persistent settings, white grid.

Usage:
    python main.py                          # Starts with test cube or last model
    python main.py --model room.obj         # Load a specific .obj model

Controls (Maya-style):
    Alt + LMB drag    Orbit (tumble)
    Alt + MMB drag    Pan
    Alt + RMB drag    Dolly
    Scroll            Dolly
    F                 Fit camera to model
    Escape            Quit
"""

import sys
import argparse
import time
from pathlib import Path

import moderngl
import numpy as np
import glm

from imgui_bundle import imgui, hello_imgui

from camera import Camera
from renderer import SceneRenderer
from ndi_input import create_receiver
from obj_loader import load_obj, generate_test_cube
from settings import load_settings, save_settings


SIDEBAR_WIDTH = 340


class App:
    VERSION = "1.4"
    WINDOW_TITLE = f"Virtual Projection Viewer v{VERSION}"

    def __init__(self, args):
        self.args = args
        self.settings = load_settings()

        # Initialised in post_init()
        self.ctx: moderngl.Context | None = None
        self.scene: SceneRenderer | None = None

        # Camera — restore from settings
        self.camera = Camera()
        s = self.settings
        self.camera.target_x = s["camera_target_x"]
        self.camera.target_y = s["camera_target_y"]
        self.camera.target_z = s["camera_target_z"]
        self.camera.azimuth = s["camera_azimuth"]
        self.camera.elevation = s["camera_elevation"]
        self.camera.distance = s["camera_distance"]
        self.camera.fov = args.fov if args.fov else s["camera_fov"]

        # NDI
        self.ndi = create_receiver()
        self.ndi_sources: list[str] = []
        self.ndi_selected_idx: int = -1
        self._ndi_auto_connect = s["last_ndi_source"]

        # Model transform — restore from settings
        self.model_pos = [s["model_pos_x"], s["model_pos_y"], s["model_pos_z"]]
        self.model_scale = s["model_scale"]
        self.model_rot_y = s["model_rot_y"]

        # Texture
        self.texture_rotation: int = s["texture_rotation"]
        self._prev_rotation: int = self.texture_rotation
        self._rotation_labels = ["0°", "90°", "180°", "270°"]
        self._last_frame: np.ndarray | None = None

        # Resolution
        self.res_scale: int = s["res_scale"]
        self._prev_res_scale: int = self.res_scale
        self._res_labels = ["Full", "1/2", "1/4", "1/8"]
        self._res_factors = [1, 2, 4, 8]

        # Model state
        self._last_bounds: dict | None = None
        self._model_path: str = s["last_model_path"]
        self._brightness: float = s["brightness"]
        self._model_loaded_from_settings = bool(self._model_path)

        # Timing
        self._fps_counter = 0
        self._fps_time = time.perf_counter()
        self._fps_display = 0.0

    # -------------------------------------------------------------------
    # hello_imgui callbacks
    # -------------------------------------------------------------------

    def post_init(self):
        self.ctx = moderngl.create_context(standalone=False)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.scene = SceneRenderer(self.ctx)
        self.scene.brightness = self._brightness

        # Load model: CLI arg > saved path > test cube
        model_path = self.args.model or self._model_path
        self._load_model(model_path if model_path else None,
                         fit_camera=not self._model_loaded_from_settings)
        print(f"[app] OpenGL context ready — moderngl {moderngl.__version__}")

        # Auto-discover and connect to last NDI source
        if self._ndi_auto_connect:
            self.ndi_sources = self.ndi.discover_sources(wait_ms=1500)
            for i, name in enumerate(self.ndi_sources):
                if name == self._ndi_auto_connect:
                    self.ndi_selected_idx = i
                    self.ndi.connect(name)
                    break

    def custom_background(self):
        if self.ctx is None or self.scene is None:
            return

        # NDI capture + texture processing
        frame = self.ndi.capture_frame()
        new_frame = frame is not None
        rotation_changed = self.texture_rotation != self._prev_rotation
        scale_changed = self.res_scale != self._prev_res_scale

        if new_frame:
            self._last_frame = frame

        if (new_frame or rotation_changed or scale_changed) and self._last_frame is not None:
            processed = self._last_frame
            factor = self._res_factors[self.res_scale]
            if factor > 1:
                processed = processed[::factor, ::factor]
            if self.texture_rotation != 0:
                processed = np.rot90(processed, k=self.texture_rotation)
            self.scene.update_texture(np.ascontiguousarray(processed))
            self._prev_rotation = self.texture_rotation
            self._prev_res_scale = self.res_scale

        # Viewport
        io = imgui.get_io()
        fb_scale = io.display_framebuffer_scale
        width = int(io.display_size.x * fb_scale.x)
        height = int(io.display_size.y * fb_scale.y)
        if width <= 0 or height <= 0:
            return

        self.ctx.viewport = (0, 0, width, height)
        aspect = width / height

        self.scene.set_model_transform(
            pos=glm.vec3(*self.model_pos),
            scale=self.model_scale,
            rot_y=self.model_rot_y,
        )

        view = self.camera.get_view_matrix()
        proj = self.camera.get_projection_matrix(aspect)
        self.scene.render(view, proj)
        self._update_fps()

    def show_gui(self):
        self._handle_mouse()
        self._handle_keyboard()
        self._draw_sidebar()

    def before_exit(self):
        self._save_current_settings()
        print("[app] Shutting down...")
        self.ndi.destroy()
        if self.scene:
            self.scene.destroy()

    # -------------------------------------------------------------------
    # Sidebar UI
    # -------------------------------------------------------------------

    def _draw_sidebar(self):
        io = imgui.get_io()
        display_h = io.display_size.y

        imgui.set_next_window_pos((0, 0), imgui.Cond_.always)
        imgui.set_next_window_size((SIDEBAR_WIDTH, display_h), imgui.Cond_.always)
        imgui.set_next_window_bg_alpha(0.85)

        flags = (imgui.WindowFlags_.no_title_bar
                 | imgui.WindowFlags_.no_resize
                 | imgui.WindowFlags_.no_move
                 | imgui.WindowFlags_.no_collapse)
        imgui.begin("##sidebar", flags=flags)

        # One consistent width for all widgets — leave 120px for labels
        imgui.push_item_width(-120)

        # --- Status ---
        imgui.text(f"FPS: {self._fps_display:.0f}")
        if self._last_frame is not None:
            factor = self._res_factors[self.res_scale]
            h, w = self._last_frame.shape[:2]
            imgui.same_line()
            imgui.text_colored(
                imgui.ImVec4(0.5, 0.5, 0.5, 1.0),
                f"  {w // factor}x{h // factor}"
            )
        connected = self.ndi.connected_source
        if connected:
            imgui.text_colored(imgui.ImVec4(0.4, 1.0, 0.4, 1.0), connected)
        else:
            imgui.text_colored(imgui.ImVec4(0.5, 0.5, 0.5, 1.0), "No NDI source")
        imgui.separator()

        # --- NDI Source ---
        if imgui.collapsing_header("NDI Source"):
            if imgui.button("Refresh Sources", (-1, 0)):
                self.ndi_sources = self.ndi.discover_sources(wait_ms=1000)
                print(f"[app] Found {len(self.ndi_sources)} NDI source(s)")
            if self.ndi_sources:
                for i, name in enumerate(self.ndi_sources):
                    is_selected = (i == self.ndi_selected_idx)
                    clicked, _ = imgui.selectable(name, is_selected)
                    if clicked:
                        self.ndi_selected_idx = i
                        self.ndi.connect(name)

        # --- Display ---
        if imgui.collapsing_header("Display", imgui.TreeNodeFlags_.default_open):
            changed, new_rot = imgui.combo(
                "Rotation", self.texture_rotation, self._rotation_labels)
            if changed:
                self.texture_rotation = new_rot

            changed, new_res = imgui.combo(
                "Quality", self.res_scale, self._res_labels)
            if changed:
                self.res_scale = new_res

            _, self.scene.brightness = imgui.slider_float(
                "Brightness", self.scene.brightness, 0.0, 2.0)

        # --- Camera ---
        if imgui.collapsing_header("Camera", imgui.TreeNodeFlags_.default_open):
            _, self.camera.target_x = imgui.drag_float(
                "Target X", self.camera.target_x, 0.05)
            _, self.camera.target_y = imgui.drag_float(
                "Target Y", self.camera.target_y, 0.05)
            _, self.camera.target_z = imgui.drag_float(
                "Target Z", self.camera.target_z, 0.05)
            _, self.camera.azimuth = imgui.slider_float(
                "Azimuth", self.camera.azimuth, -180.0, 180.0)
            _, self.camera.elevation = imgui.slider_float(
                "Elevation", self.camera.elevation, -89.0, 89.0)
            _, self.camera.distance = imgui.drag_float(
                "Distance", self.camera.distance, 0.1, 0.1, 500.0)
            _, self.camera.fov = imgui.slider_float(
                "FOV", self.camera.fov, 10.0, 150.0)

            if imgui.button("Fit"):
                if self._last_bounds:
                    self.camera.fit_to_bounds(self._last_bounds)
            imgui.same_line()
            if imgui.button("Reset"):
                self.camera.reset()

        # --- Model Transform (collapsed by default — rarely needed) ---
        if imgui.collapsing_header("Model Transform"):
            _, self.model_pos[0] = imgui.drag_float(
                "Pos X##m", self.model_pos[0], 0.05)
            _, self.model_pos[1] = imgui.drag_float(
                "Pos Y##m", self.model_pos[1], 0.05)
            _, self.model_pos[2] = imgui.drag_float(
                "Pos Z##m", self.model_pos[2], 0.05)
            _, self.model_scale = imgui.drag_float(
                "Scale", self.model_scale, 0.01, 0.01, 50.0)
            _, self.model_rot_y = imgui.slider_float(
                "Rot Y", self.model_rot_y, -180.0, 180.0)

        imgui.pop_item_width()

        # --- Load + shortcuts ---
        imgui.separator()
        imgui.spacing()
        if imgui.button("Load .obj...", (-1, 0)):
            self._open_file_dialog()
        imgui.spacing()
        imgui.text_colored(
            imgui.ImVec4(0.4, 0.4, 0.4, 1.0),
            "Alt+LMB Orbit  Alt+MMB Pan\n"
            "Alt+RMB/Scroll Dolly  F Fit"
        )

        imgui.end()

    # -------------------------------------------------------------------
    # Input: Maya-style
    # -------------------------------------------------------------------

    def _handle_mouse(self):
        io = imgui.get_io()
        if io.want_capture_mouse:
            return

        alt_held = (imgui.is_key_down(imgui.Key.left_alt)
                    or imgui.is_key_down(imgui.Key.right_alt))

        if alt_held:
            dx = io.mouse_delta.x
            dy = io.mouse_delta.y

            if io.mouse_down[0]:
                self.camera.orbit(dx, dy)
            elif io.mouse_down[2]:
                self.camera.pan(dx, dy)
            elif io.mouse_down[1]:
                self.camera.dolly(dy, sensitivity=0.005)

        if abs(io.mouse_wheel) > 0.01:
            self.camera.dolly(io.mouse_wheel, sensitivity=0.1)

    def _handle_keyboard(self):
        io = imgui.get_io()
        if io.want_capture_keyboard:
            return

        if imgui.is_key_pressed(imgui.Key.f):
            if self._last_bounds:
                self.camera.fit_to_bounds(self._last_bounds)

        if imgui.is_key_pressed(imgui.Key.escape):
            hello_imgui.get_runner_params().app_shall_exit = True

    # -------------------------------------------------------------------
    # Model loading
    # -------------------------------------------------------------------

    def _load_model(self, model_path: str | None, fit_camera: bool = True):
        if model_path:
            path = Path(model_path)
            if path.exists():
                result = load_obj(str(path))
                self.scene.load_model(result['vertices'])
                self._last_bounds = result['bounds']
                self._model_path = str(path)
                if fit_camera:
                    self._fit_to_model(result['bounds'])
                else:
                    # Still reposition grid even when not fitting camera
                    self._position_grid(result['bounds'])
                print(f"[app] Loaded model: {path}")
                return
            else:
                print(f"[app] Model not found: {path}, using test cube")

        result = generate_test_cube()
        self.scene.load_model(result['vertices'])
        self._last_bounds = result['bounds']
        self._model_path = ""
        if fit_camera:
            self._fit_to_model(result['bounds'])
        print("[app] Using test cube (no .obj specified)")

    def _fit_to_model(self, bounds: dict):
        self.camera.fit_to_bounds(bounds)
        self._position_grid(bounds)
        self.model_pos = [0.0, 0.0, 0.0]
        self.model_scale = 1.0
        self.model_rot_y = 0.0

    def _position_grid(self, bounds: dict):
        if self.scene:
            y_floor = float(bounds['min'][1])
            cx = float(bounds['center'][0])
            cz = float(bounds['center'][2])
            grid_size = float(max(bounds['size'][0], bounds['size'][2])) * 1.5
            self.scene.rebuild_grid(
                y_level=y_floor, center_x=cx, center_z=cz,
                grid_size=max(grid_size, 5.0)
            )

    def _open_file_dialog(self):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            filepath = filedialog.askopenfilename(
                title="Select .obj model",
                filetypes=[("Wavefront OBJ", "*.obj"), ("All files", "*.*")],
            )
            root.destroy()
            if filepath:
                result = load_obj(filepath)
                self.scene.load_model(result['vertices'])
                self._last_bounds = result['bounds']
                self._model_path = filepath
                self._fit_to_model(result['bounds'])
        except Exception as e:
            print(f"[app] File dialog error: {e}")

    # -------------------------------------------------------------------
    # Settings persistence
    # -------------------------------------------------------------------

    def _save_current_settings(self):
        s = {
            "camera_target_x": self.camera.target_x,
            "camera_target_y": self.camera.target_y,
            "camera_target_z": self.camera.target_z,
            "camera_azimuth": self.camera.azimuth,
            "camera_elevation": self.camera.elevation,
            "camera_distance": self.camera.distance,
            "camera_fov": self.camera.fov,
            "model_pos_x": self.model_pos[0],
            "model_pos_y": self.model_pos[1],
            "model_pos_z": self.model_pos[2],
            "model_scale": self.model_scale,
            "model_rot_y": self.model_rot_y,
            "brightness": self.scene.brightness if self.scene else 1.0,
            "texture_rotation": self.texture_rotation,
            "res_scale": self.res_scale,
            "last_model_path": self._model_path,
            "last_ndi_source": self.ndi.connected_source or "",
        }
        save_settings(s)

    def _update_fps(self):
        self._fps_counter += 1
        now = time.perf_counter()
        elapsed = now - self._fps_time
        if elapsed >= 1.0:
            self._fps_display = self._fps_counter / elapsed
            self._fps_counter = 0
            self._fps_time = now


def main():
    parser = argparse.ArgumentParser(
        description="Virtual Projection Viewer — Preview NDI on 3D models"
    )
    parser.add_argument(
        "--model", "-m", type=str, default=None,
        help="Path to .obj model file",
    )
    parser.add_argument(
        "--fov", type=float, default=None,
        help="Initial field of view in degrees",
    )
    args = parser.parse_args()

    app = App(args)

    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = App.WINDOW_TITLE
    params.app_window_params.window_geometry.size = (1600, 900)

    params.callbacks.post_init = app.post_init
    params.callbacks.custom_background = app.custom_background
    params.callbacks.show_gui = app.show_gui
    params.callbacks.before_exit = app.before_exit

    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.no_default_window
    )

    print(f"[app] Starting {App.WINDOW_TITLE}")
    hello_imgui.run(params)


if __name__ == "__main__":
    main()
