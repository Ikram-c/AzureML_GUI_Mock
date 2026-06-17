# cl_ui/navigation_panel.py
import tkinter as tk
from functools import partial
from tkinter import ttk

# Centralized application configuration
from config_loader import CONFIG


class NavigationPanel(ttk.Frame):
    """
    A navigation panel with buttons to switch between the main application views.
    """

    def __init__(self, parent, view_map: dict):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.buttons = {}
        self.view_map = view_map
        self._create_navigation_buttons()
        self._set_initial_state()

    def _create_navigation_buttons(self):
        """Creates all navigation buttons organized by sections."""
        button_sections = {
            "Authentication": [("Connect to Azure", "connect")],
            "Source Control": [("GitHub Tools", "github")],
            "Azure Storage": [("Storage Manager", "storage")],
            "Azure Machine Learning": [("ML Workspace", "ml"), ("Job Monitor", "monitor")]
        }
        row_index = 0
        for section_name, section_buttons in button_sections.items():
            if row_index > 0:
                ttk.Separator(self, orient='horizontal').grid(row=row_index, column=0, sticky='ew', pady=10)
                row_index += 1

            # Use font from config file for the section label
            section_font = tuple(CONFIG['ui']['fonts']['nav_section'])
            ttk.Label(self, text=section_name, font=section_font).grid(
                row=row_index, column=0, sticky='w', pady=(5, 2)
            )
            row_index += 1

            for button_text, view_name in section_buttons:
                if view_name in self.view_map:
                    button = self._create_nav_button(button_text, view_name)
                    button.grid(row=row_index, column=0, sticky="ew", pady=1, padx=(10, 0))
                    row_index += 1

        # Add spacer to push content to the top
        self.rowconfigure(row_index, weight=1)

    def _create_nav_button(self, text: str, view_name: str) -> ttk.Button:
        """Creates a single navigation button."""
        command = partial(self.view_map.get(view_name, lambda: None))
        button = ttk.Button(self, text=text, command=command)
        self.buttons[view_name] = button
        return button

    def _set_initial_state(self):
        """Sets the initial state of navigation buttons."""
        self.set_azure_buttons_state("disabled")
        self.set_button_state("connect", "normal")
        self.set_button_state("github", "normal")

    def set_azure_buttons_state(self, state: str):
        """Enables or disables all buttons related to Azure services."""
        for view_name in ["storage", "ml", "monitor"]:
            self.set_button_state(view_name, state)

    def set_button_state(self, view_name: str, state: str):
        """Sets the state of a specific navigation button."""
        if view_name in self.buttons:
            self.buttons[view_name].config(state=state)

    def highlight_current_view(self, current_view: str):
        """Highlights the button for the currently active view."""
        # This can be expanded with custom styles if needed
        for view_name, button in self.buttons.items():
            style = "Accent.TButton" if view_name == current_view else "TButton"
            button.config(style=style)

