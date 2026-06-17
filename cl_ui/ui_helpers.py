# cl_ui/ui_helpers.py
import threading
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import ttk, messagebox

from screeninfo import get_monitors

# Centralized application configuration
from config_loader import CONFIG


class _ThreadHandler:
    """Helper class to run a function in a background thread."""

    def __init__(self, root, target_func, callback):
        self.root = root
        self.target_func = target_func
        self.callback = callback

    def run(self):
        thread = threading.Thread(target=self._execute, daemon=True)
        thread.start()

    def _execute(self):
        """Executes the target function and schedules the callback."""
        try:
            result = self.target_func()
            if self.callback:
                self.root.after(0, partial(self.callback, result, None))
        except Exception as e:
            if self.callback:
                self.root.after(0, partial(self.callback, None, e))


def run_in_thread(root: tk.Tk, target_func, callback=None):
    """
    Public helper function to run a task in a background thread.
    """
    _ThreadHandler(root, target_func, callback).run()


def set_initial_window_size(root: tk.Tk):
    """
    Calculates an appropriate initial size and position for the main window
    based on the primary monitor and settings from the config file.
    """
    try:
        monitor = max(get_monitors(), key=lambda m: m.width * m.height)
        screen_width, screen_height = monitor.width, monitor.height
        monitor_x, monitor_y = monitor.x, monitor.y
    except Exception:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        monitor_x, monitor_y = 0, 0

    # Use ratios from config file to determine window size
    win_config = CONFIG['ui']['window']
    app_width = int(screen_width * win_config['initial_width_ratio'])
    app_height = int(screen_height * win_config['initial_height_ratio'])

    center_x = monitor_x + (screen_width - app_width) // 2
    center_y = monitor_y + (screen_height - app_height) // 2

    root.geometry(f"{app_width}x{app_height}+{center_x}+{center_y}")
    root.minsize(
        int(screen_width * win_config['min_width_ratio']),
        int(screen_height * win_config['min_height_ratio'])
    )


def show_auth_help(parent: tk.Tk):
    """Displays a Toplevel window with Azure authentication help text."""
    help_window = tk.Toplevel(parent)
    help_window.title("Azure Authentication Help")

    # Use dimensions from config file
    dialog_config = CONFIG['ui']['help_dialog']
    help_window.geometry(f"{dialog_config['width']}x{dialog_config['height']}")
    help_window.transient(parent)
    help_window.grab_set()

    # Use font from config file
    title_font = tuple(CONFIG['ui']['fonts']['help_title'])
    ttk.Label(help_window, text="Azure Authentication Options", font=title_font).pack(pady=(20, 10))

    help_text = (
        "This application uses DefaultAzureCredential, which finds the best "
        "way to authenticate. For the best experience, sign in with the Azure CLI.\n\n"
        "1. Install Azure CLI\n"
        "   The most reliable method. After installing, run 'az login' in your terminal.\n\n"
        "2. Connect with Account Key\n"
        "   Enter your storage account name and an access key manually.\n\n"
        "3. Automatic Credential Detection\n"
        "   If you are logged into other tools (like VS Code), the application may "
        "detect your credentials automatically."
    )

    text_frame = ttk.Frame(help_window, padding=20)
    text_frame.pack(fill=tk.BOTH, expand=True)
    text_box = tk.Text(text_frame, wrap=tk.WORD, background=help_window.cget('bg'))
    text_box.insert(tk.END, help_text)
    text_box.config(state=tk.DISABLED)
    text_box.pack(fill=tk.BOTH, expand=True)

    button_frame = ttk.Frame(help_window, padding=10)
    button_frame.pack(fill=tk.X)
    install_url = "https://docs.microsoft.com/cli/azure/install-azure-cli"
    ttk.Button(button_frame, text="Install Azure CLI", command=lambda: webbrowser.open(install_url)).pack(side=tk.LEFT,
                                                                                                          padx=10)
    ttk.Button(button_frame, text="Close", command=help_window.destroy).pack(side=tk.RIGHT, padx=10)


def show_message(msg_type: str, title: str, message: str, parent=None):
    """Shows a standard messagebox."""
    msg_func = getattr(messagebox, f"show{msg_type.lower()}", messagebox.showinfo)
    msg_func(title, message, parent=parent)


def copy_to_clipboard(window: tk.Tk, text: str):
    """Helper to copy text to the clipboard."""
    window.clipboard_clear()
    window.clipboard_append(text)
    window.update()
