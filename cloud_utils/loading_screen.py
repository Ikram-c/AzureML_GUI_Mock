# loading_screen.py
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

# Centralized application configuration
from config_loader import CONFIG


class LoadingScreen(tk.Toplevel):
    """
    A frameless, centered loading screen that shows progress during application startup.
    All UI elements scale relative to the screen size based on config settings.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.scale_factor = 2

        self.overrideredirect(True)

        self._size_and_center_window()
        self._setup_ui()

    def _setup_ui(self):
        """Creates the labels and progress bar for the loading screen, scaled appropriately."""
        padding = int(20 * self.scale_factor)
        title_font_size = max(12, int(16 * self.scale_factor))
        status_font_size = max(9, int(10 * self.scale_factor))

        main_frame = ttk.Frame(self, padding=padding, style="Card.TFrame")
        main_frame.pack(fill="both", expand=True)

        style = ttk.Style(self)
        style.configure("Card.TFrame", background="#333333")

        title_font = ("Arial", title_font_size, "bold")
        title_label = ttk.Label(
            main_frame,
            text="Cloud Development Tools",
            font=title_font,
            background="#333333",
            foreground="#FFFFFF"
        )
        title_label.pack(pady=(0, int(10 * self.scale_factor)))

        status_font = ("Arial", status_font_size)
        self.status_label = ttk.Label(
            main_frame,
            text="Starting...",
            font=status_font,
            background="#333333",
            foreground="#CCCCCC"
        )
        self.status_label.pack(pady=int(5 * self.scale_factor), padx=padding)

        self.progress_bar = ttk.Progressbar(
            main_frame,
            orient="horizontal",
            mode='indeterminate'
        )
        self.progress_bar.pack(pady=(int(10 * self.scale_factor), 0), fill="x", expand=True,
                               padx=int(10 * self.scale_factor))
        self.progress_bar.start(10)

    def _size_and_center_window(self):
        """Sets the window size relative to the screen, calculates the scale factor, and centers the window."""
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        print(f"DEBUG: Detected screen size: {screen_width}x{screen_height}")

        # Use settings from the config file
        ls_config = CONFIG['ui']['loading_screen']
        width = int(screen_width * ls_config['width_ratio'])
        width = max(ls_config['min_width'], min(ls_config['max_width'], width))

        self.scale_factor = width / ls_config['scale_base_width']
        height = int(width / ls_config['aspect_ratio'])

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        self.geometry(f'{width}x{height}+{x}+{y}')

    def update_status(self, text: str):
        """Updates the text on the status label."""
        self.status_label.config(text=text)
        self.update()

    def close(self):
        """Stops the progress bar and destroys the window."""
        self.progress_bar.stop()
        self.destroy()
