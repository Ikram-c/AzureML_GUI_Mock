# cl_ui/status_bar.py
from tkinter import ttk

# Centralized application configuration
from config_loader import CONFIG

try:
    from cloud_utils.zoomcontroller import ZoomController
except ImportError:
    ZoomController = None

class StatusBar(ttk.Frame):
    """
    A status bar for displaying application status messages, progress, and zoom controls.
    """

    def __init__(self, parent):
        """
        Initializes the StatusBar.
        """
        super().__init__(parent)

        # Status label expands to take available space
        self.status_label = ttk.Label(self, text="Ready", anchor="w")
        self.status_label.pack(side="left", padx=5, fill="x", expand=True)

        # Optional Zoom label + slider (shown if app provides `root.zoom`)
        self.zoom_label = None
        self.zoom_slider = None
        if hasattr(self.master, "zoom") and self.master.zoom and ZoomController:
            # label
            self.zoom_label = ttk.Label(self, text="Zoom")
            self.zoom_label.pack(side="right", padx=(0, 2))

            # slider
            self.zoom_slider = ttk.Scale(
                self,
                from_=ZoomController.MIN_SCALE,
                to=ZoomController.MAX_SCALE,
                value=self.master.zoom.scale,
                command=lambda v: self.master.zoom.set_scale(float(v))
            )
            self.zoom_slider.pack(side="right", padx=5)

        # Progress bar for long-running operations
        progress_bar_length = CONFIG['ui']['status_bar']['progress_bar_length']
        self.progress_bar = ttk.Progressbar(
            self, orient="horizontal", mode='determinate', length=progress_bar_length
        )
        self.progress_bar.pack(side="right", padx=5)

    def set_status(self, text: str, color: str = "black"):
        """
        Updates the text and color of the status label.
        """
        self.status_label.config(text=text, foreground=color)
        self.update_idletasks()  # Force UI to update immediately

    def set_progress_mode(self, mode: str, maximum: int = 100):
        """
        Sets the mode of the progress bar.
        """
        self.progress_bar.config(mode=mode, maximum=maximum, value=0)
        if mode == 'indeterminate':
            self.progress_bar.start()
        else:
            self.progress_bar.stop()

    def update_progress(self, value: int):
        """Updates the value of the determinate progress bar."""
        self.progress_bar.config(value=value)

    def clear_progress(self):
        """Resets and hides the progress bar."""
        self.progress_bar.stop()
        self.progress_bar.config(value=0)

    def sync_zoom(self, value: float):
        """Update the zoom slider position to match the current zoom."""
        if self.zoom_slider:
            self.zoom_slider.set(value)
