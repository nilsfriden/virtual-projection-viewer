"""
ndi_input.py — NDI source discovery and frame capture.
v1.0

Wraps ndi-python for source discovery and video frame reception.
Falls back to a test-pattern generator if NDI is not available,
so the rest of the app can be developed without NDI installed.

Requires:
  - pip install ndi-python
  - NDI Runtime installed: https://ndi.video/tools/
"""

import numpy as np
import time

# --- Try to import NDI bindings ---
try:
    import NDIlib as ndi
    NDI_AVAILABLE = True
except ImportError:
    NDI_AVAILABLE = False
    print("[ndi_input] WARNING: ndi-python not found. Using test pattern fallback.")
    print("           Install with: pip install ndi-python")
    print("           Also install NDI Runtime from https://ndi.video/tools/")


class NDIReceiver:
    """
    Discovers NDI sources on the network and receives BGRA video frames.
    """

    def __init__(self):
        self._finder = None
        self._recv = None
        self._connected_source_name: str = ""
        self._sources: list = []
        self._frame_width: int = 0
        self._frame_height: int = 0
        self._initialized = False

        if NDI_AVAILABLE:
            if not ndi.initialize():
                print("[ndi_input] ERROR: Failed to initialize NDI.")
                return
            self._finder = ndi.find_create_v2()
            if self._finder is None:
                print("[ndi_input] ERROR: Failed to create NDI finder.")
                return
            self._initialized = True
            print("[ndi_input] NDI initialized. Searching for sources...")

    @property
    def available(self) -> bool:
        return self._initialized

    @property
    def connected_source(self) -> str:
        return self._connected_source_name

    @property
    def frame_width(self) -> int:
        return self._frame_width

    @property
    def frame_height(self) -> int:
        return self._frame_height

    def discover_sources(self, wait_ms: int = 500) -> list[str]:
        """
        Returns a list of NDI source names currently visible on the network.
        """
        if not self._initialized:
            return []

        # Give the finder a moment to discover
        ndi.find_wait_for_sources(self._finder, wait_ms)
        sources = ndi.find_get_current_sources(self._finder)
        self._sources = sources
        return [s.ndi_name for s in sources]

    def connect(self, source_name: str) -> bool:
        """
        Connect to a specific NDI source by name.
        """
        if not self._initialized:
            return False

        # Find the matching source object
        target = None
        for s in self._sources:
            if s.ndi_name == source_name:
                target = s
                break

        if target is None:
            print(f"[ndi_input] Source not found: {source_name}")
            return False

        # Disconnect existing receiver
        self.disconnect()

        # Create receiver
        recv_create = ndi.RecvCreateV3()
        recv_create.color_format = ndi.RECV_COLOR_FORMAT_BGRX_BGRA
        self._recv = ndi.recv_create_v3(recv_create)

        if self._recv is None:
            print("[ndi_input] ERROR: Failed to create NDI receiver.")
            return False

        ndi.recv_connect(self._recv, target)
        self._connected_source_name = source_name
        print(f"[ndi_input] Connected to: {source_name}")
        return True

    def disconnect(self):
        """Disconnect from current source."""
        if self._recv is not None:
            ndi.recv_destroy(self._recv)
            self._recv = None
            self._connected_source_name = ""

    def capture_frame(self) -> np.ndarray | None:
        """
        Attempt to capture a single video frame.

        Returns:
            np.ndarray of shape (height, width, 4) in BGRA format, or None.
        """
        if self._recv is None:
            return None

        try:
            # ndi-python returns (frame_type, video, audio, metadata)
            result = ndi.recv_capture_v2(self._recv, 0)
            frame_type = result[0]
            video_frame = result[1]

            if frame_type == ndi.FRAME_TYPE_VIDEO and video_frame is not None:
                self._frame_width = video_frame.xres
                self._frame_height = video_frame.yres

                # Copy frame data to numpy array
                frame_data = np.copy(video_frame.data)

                # Free the NDI frame buffer
                try:
                    ndi.recv_free_video_v2(self._recv, video_frame)
                except (TypeError, AttributeError):
                    pass  # Some versions manage memory automatically

                return frame_data.reshape((self._frame_height, self._frame_width, 4))

        except Exception as e:
            print(f"[ndi_input] Capture error: {e}")

        return None

    def destroy(self):
        """Clean up NDI resources."""
        self.disconnect()
        if self._finder is not None:
            ndi.find_destroy(self._finder)
            self._finder = None
        if self._initialized:
            ndi.destroy()
            self._initialized = False


class TestPatternGenerator:
    """
    Generates a simple animated test pattern when NDI is unavailable.
    Outputs BGRA uint8 arrays matching the NDI frame format.
    """

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self._frame_count = 0
        self._sources = ["Test Pattern 1080p", "Test Pattern 720p"]

    @property
    def available(self) -> bool:
        return True

    @property
    def connected_source(self) -> str:
        return "Test Pattern"

    @property
    def frame_width(self) -> int:
        return self.width

    @property
    def frame_height(self) -> int:
        return self.height

    def discover_sources(self, wait_ms: int = 500) -> list[str]:
        return list(self._sources)

    def connect(self, source_name: str) -> bool:
        if "720" in source_name:
            self.width, self.height = 1280, 720
        else:
            self.width, self.height = 1920, 1080
        print(f"[test_pattern] Using {self.width}x{self.height} test pattern")
        return True

    def disconnect(self):
        pass

    def capture_frame(self) -> np.ndarray:
        """Generate a color-bar test pattern with moving indicator."""
        frame = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        # Color bars (BGRA)
        colors = [
            (255, 255, 255, 255),  # White
            (0,   255, 255, 255),  # Yellow (BGR)
            (255, 255, 0,   255),  # Cyan
            (0,   255, 0,   255),  # Green
            (255, 0,   255, 255),  # Magenta
            (0,   0,   255, 255),  # Red
            (255, 0,   0,   255),  # Blue
            (0,   0,   0,   255),  # Black
        ]

        bar_width = self.width // len(colors)
        for i, color in enumerate(colors):
            x_start = i * bar_width
            x_end = (i + 1) * bar_width if i < len(colors) - 1 else self.width
            frame[:, x_start:x_end] = color

        # Moving vertical line as a "signal alive" indicator
        line_x = int((self._frame_count * 3) % self.width)
        frame[:, max(0, line_x - 1):min(self.width, line_x + 2)] = (0, 128, 255, 255)

        self._frame_count += 1
        return frame

    def destroy(self):
        pass


def create_receiver() -> NDIReceiver | TestPatternGenerator:
    """
    Factory: returns NDIReceiver if NDI is available, otherwise TestPatternGenerator.
    """
    if NDI_AVAILABLE:
        recv = NDIReceiver()
        if recv.available:
            return recv
        print("[ndi_input] NDI init failed, falling back to test pattern.")
    return TestPatternGenerator()
