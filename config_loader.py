# config_loader.py
import os
import sys
import yaml
from tkinter import messagebox


def load_config():
    """
    Loads the configuration from cloud_config.yaml.
    Searches for the file in the script's directory and the current working directory.
    """
    config_filename = "cloud_configs/cloud_config.yaml"

    # Determine the base path (for PyInstaller/cx_Freeze compatibility)
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(base_path, config_filename)

    if not os.path.exists(config_path):
        # Fallback to current working directory if not found next to script/executable
        config_path = os.path.join(os.getcwd(), config_filename)

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file '{config_filename}' not found in "
            f"'{base_path}' or '{os.getcwd()}'."
        )

    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        return config_data
    except yaml.YAMLError as e:
        raise IOError(f"Error parsing YAML file '{config_path}': {e}")
    except Exception as e:
        raise IOError(f"Could not read configuration file '{config_path}': {e}")


# Load the configuration once when the module is imported
try:
    CONFIG = load_config()
except (FileNotFoundError, IOError) as e:
    # Handle missing config gracefully for UI applications
    error_title = "Configuration Error"
    error_message = f"A critical error occurred while loading the configuration:\n\n{e}\n\nThe application cannot start."

    # Try to show a message box, but fall back to console print
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(error_title, error_message)
    except Exception:
        print(f"CRITICAL ERROR: {error_message}")

    sys.exit(1)

