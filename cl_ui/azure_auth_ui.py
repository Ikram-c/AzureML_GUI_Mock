# cl_ui/azure_auth_ui.py
import tkinter as tk
from tkinter import ttk

from cl_ui.ui_helpers import show_auth_help


class AzureConnectView(ttk.Frame):
    """
    The main view for Azure authentication and storage connection.
    This class creates all UI widgets and provides internal helper methods for the
    callbacks controller to update the UI state.
    """

    def __init__(self, parent, app_controller):
        """
        Initializes the ConnectView.

        Args:
            parent: The parent tkinter frame.
            app_controller: The main application controller instance.
        """
        super().__init__(parent, padding=10)
        self.pack(fill="both", expand=True)
        self.app = app_controller

    
        cb = self.app.azure_callbacks

        # --- Build UI Panels ---
        self._build_authentication_panel(cb)
        self._build_storage_settings_panel(cb)

        # --- Initial State Check ---
        # Trigger the initial check for cached credentials at startup.
        cb.handle_check_cached_login()

    def _build_authentication_panel(self, cb):
        """Creates the widgets for user authentication."""
        auth_frame = ttk.LabelFrame(self, text="Azure Authentication", padding=10)
        auth_frame.pack(fill=tk.X, pady=5)

        # User status label
        self.user_label = ttk.Label(auth_frame, text="Checking status...", foreground="grey")
        self.user_label.pack(anchor="w", pady=(0, 5))

        # Buttons for different login methods
        buttons_frame = ttk.Frame(auth_frame)
        buttons_frame.pack(fill=tk.X)

        ttk.Button(
            buttons_frame, text="Sign in (Browser)", command=cb.handle_interactive_login
        ).pack(side="left", padx=(0, 5))

        # Note: If you re-introduce the device code flow, you would add its button here.

        ttk.Button(buttons_frame, text="Sign Out", command=self.app.sign_out).pack(
            side="left", padx=5
        )
        ttk.Button(
            buttons_frame, text="Help", command=lambda: show_auth_help(self.app.root)
        ).pack(side="right")

    def _build_storage_settings_panel(self, cb):
        """Creates the widgets for connecting to a specific storage account."""
        self.settings_panel = ttk.LabelFrame(self, text="Storage Connection", padding=10)
        self.settings_panel.pack(fill=tk.X, pady=5)
        self.settings_panel.columnconfigure(1, weight=1)

        # --- Part 1: Connect with Access Key (Manual) ---
        key_frame = ttk.Frame(self.settings_panel)
        key_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        key_frame.columnconfigure(1, weight=1)

        ttk.Label(key_frame, text="Account Name:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.account_entry = ttk.Entry(key_frame)
        self.account_entry.grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(key_frame, text="Access Key:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.key_entry = ttk.Entry(key_frame, show="*")
        self.key_entry.grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Button(key_frame, text="Connect with Key", command=cb.handle_connect_with_key).grid(
            row=2, column=1, sticky="e", pady=5, padx=5
        )

        ttk.Separator(self.settings_panel, orient='horizontal').grid(
            row=1, column=0, columnspan=2, sticky='ew', pady=10
        )

        # --- Part 2: Connect via Signed-in Account (Recommended) ---
        auth_conn_frame = ttk.Frame(self.settings_panel)
        auth_conn_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        auth_conn_frame.columnconfigure(1, weight=1)

        ttk.Button(auth_conn_frame, text="Refresh Accounts", command=cb.handle_refresh_storage_accounts).grid(
            row=0, column=0, padx=5
        )

        ttk.Label(auth_conn_frame, text="Storage Account:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.account_combobox = ttk.Combobox(auth_conn_frame, state="readonly")
        self.account_combobox.grid(row=1, column=1, sticky="ew", padx=5)
        self.account_combobox.bind("<<ComboboxSelected>>", cb.handle_account_selected)

        ttk.Label(auth_conn_frame, text="Container:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.container_combobox = ttk.Combobox(auth_conn_frame, state="readonly")
        self.container_combobox.grid(row=2, column=1, sticky="ew", padx=5)
        self.container_combobox.bind("<<ComboboxSelected>>", cb.handle_container_selected)

        self.connection_status = ttk.Label(auth_conn_frame, text="Not connected", foreground="grey")
        self.connection_status.grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=(10, 0))

    # --- Internal UI Helper Methods ---

    def _update_user_label(self, text: str, color: str):
        """Internal helper to safely update the user status label."""
        self.user_label.config(text=text, foreground=color)

    def _update_connection_status(self, text: str, color: str):
        """Internal helper to update the storage connection status label."""
        self.connection_status.config(text=text, foreground=color)

    def _populate_storage_accounts(self, accounts_list: list):
        """Clears and populates the storage account combobox."""
        if not accounts_list:
            display_values = ["No accounts found"]
        else:
            display_values = [f"{acc['name']} ({acc['resource_group']})" for acc in accounts_list]

        self.account_combobox['values'] = display_values
        self.account_combobox.set("Select a storage account...")
        # Clear dependent combobox
        self.container_combobox.set('')
        self.container_combobox['values'] = []

    def _populate_containers(self, container_list: list):
        """Clears and populates the container combobox."""
        if not container_list:
            display_values = ["No containers found"]
        else:
            display_values = container_list

        self.container_combobox['values'] = display_values
        self.container_combobox.set("Select a container...")
