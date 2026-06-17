# cl_cb/azure_callbacks.py
from tkinter import messagebox, simpledialog

# Centralized application configuration
from config_loader import CONFIG


class AzureCallbacks:
    """
    Handles callback logic for the ConnectView, acting as a controller
    that connects the UI to the backend AzureAuthHandler.
    """

    def __init__(self, app_controller):
        self.app = app_controller
        self._login_in_progress = False
        self._cached_storage_accounts = []

    # --- Authentication Callbacks ---

    def handle_interactive_login(self):
        """Handles the interactive Azure login flow."""
        if self._login_in_progress:
            return
        self._login_in_progress = True
        self.app.update_status("Opening browser for sign-in...")
        view = self.app.connect_view
        if view:
            view._update_user_label("Signing in...", "blue")
        self.app.run_in_thread(self._interactive_login_task, self._on_login_complete)

    def _interactive_login_task(self):
        """Task to run interactive login in a background thread."""
        try:
            from azure.identity import InteractiveBrowserCredential
            from azure.mgmt.subscription import SubscriptionClient

            credential = InteractiveBrowserCredential(
                client_id=CONFIG['api']['azure']['cli_client_id'],
                timeout=CONFIG['api']['timeouts']['interactive_login_seconds'],
                redirect_uri=CONFIG['api']['azure']['default_redirect_uri']
            )
            token = credential.get_token("https://management.azure.com/.default")
            if not token:
                raise ConnectionError("Failed to obtain authentication token.")

            self.app.backend.azure_auth.credential = credential
            sub_client = SubscriptionClient(credential)
            tenants = list(sub_client.tenants.list())
            if not tenants:
                raise ConnectionError("Authenticated, but no accessible tenants found.")
            return f"Signed in to tenant: {tenants[0].tenant_id[:8]}..."
        except Exception as e:
            self.app.backend.azure_auth.credential = None
            raise ConnectionError(f"Authentication failed: {e}")

    def handle_check_cached_login(self):
        """Checks for cached credentials and updates the UI."""
        self.app.update_status("Checking for cached Azure credentials...")
        self.app.run_in_thread(
            self.app.backend.azure_auth.check_cached_login,
            self._on_cached_login_complete
        )

    def _on_login_complete(self, user_display_name, error):
        """Generic callback for when any login attempt completes."""
        self._login_in_progress = False
        view = self.app.connect_view
        if not view: return

        if error:
            view._update_user_label("Not signed in", "red")
            self.app.update_status("Authentication failed.", "red")
            messagebox.showerror("Authentication Error", str(error))
        else:
            view._update_user_label(user_display_name, "green")
            self.app.update_status("Authentication successful.", "green")
            self.handle_refresh_storage_accounts()

    def _on_cached_login_complete(self, user_display_name, error):
        """Callback specifically for cached login check."""
        view = self.app.connect_view
        if not view: return

        if error:
            view._update_user_label("Not signed in", "red")
            self.app.update_status("No cached credentials found.")
        else:
            view._update_user_label(user_display_name, "green")
            self.app.update_status("Using cached credentials.", "green")
            self.handle_refresh_storage_accounts()

    # --- Connection & Resource Callbacks ---

    def handle_connect_with_key(self):
        """Connects to a storage account using its name and an access key."""
        view = self.app.connect_view
        if not view: return

        name = view.account_entry.get().strip()
        key = view.key_entry.get().strip()
        if not name or not key:
            messagebox.showerror("Input Error", "Account Name and Access Key are required.")
            return

        rules = CONFIG['validation']['storage_account_name']
        if not (rules['min_len'] <= len(name) <= rules['max_len']):
            msg = f"Storage account name must be between {rules['min_len']} and {rules['max_len']} characters."
            messagebox.showerror("Invalid Input", msg)
            return
        if not name.islower() or not name.isalnum():
            msg = "Storage account name must contain only lowercase letters and numbers."
            messagebox.showerror("Invalid Input", msg)
            return

        self.app.update_status(f"Connecting to {name}...")

        def on_connect_complete(container_list, error):
            if not self.app.connect_view: return
            if error:
                messagebox.showerror("Connection Error", f"Failed to connect: {error}")
                self.app.connect_view._update_connection_status("Connection failed", "red")
            else:
                self.app.connect_view._update_user_label(f"Connected via Access Key to {name}", "blue")
                self.app.connect_view._update_connection_status(f"Connected to {name}", "green")
                self.app.connect_view._populate_containers(container_list)

        self.app.run_in_thread(
            lambda: self.app.backend.azure_auth.connect_with_key(name, key),
            on_connect_complete
        )

    def handle_refresh_storage_accounts(self):
        """Fetches storage accounts for the signed-in user."""
        if not self.app.backend.azure_auth.credential:
            return
        self.app.update_status("Fetching storage accounts...")

        def on_fetch_complete(accounts_list, error):
            if not self.app.connect_view: return
            if error:
                messagebox.showerror("Azure Error", f"Failed to fetch storage accounts: {error}")
            else:
                self._cached_storage_accounts = accounts_list
                self.app.connect_view._populate_storage_accounts(accounts_list)
                self.app.update_status(f"Found {len(accounts_list)} storage account(s).")

        self.app.run_in_thread(self.app.backend.azure_auth.fetch_storage_accounts, on_fetch_complete)

    def handle_account_selected(self, event=None):
        """Fetches containers for the selected storage account."""
        view = self.app.connect_view
        if not view: return

        selected_text = view.account_combobox.get()
        if not selected_text or "Select" in selected_text: return
        account_name = selected_text.split(' ')[0]

        self.app.update_status(f"Fetching containers for {account_name}...")
        view._update_connection_status("Connecting...", "blue")

        def on_fetch_complete(container_list, error):
            if not self.app.connect_view: return
            if error:
                messagebox.showerror("Azure Error", f"Failed to fetch containers: {error}")
                self.app.connect_view._update_connection_status("Connection failed", "red")
            else:
                self.app.connect_view._update_connection_status(f"Connected to {account_name}", "green")
                self.app.connect_view._populate_containers(container_list)
                self.app.update_status(f"Found {len(container_list)} container(s).")

        self.app.run_in_thread(
            lambda: self.app.backend.azure_auth.fetch_containers(account_name),
            on_fetch_complete
        )

    def handle_container_selected(self, event=None):
        """Sets the selected container in the backend and enables dependent UI."""
        view = self.app.connect_view
        if not view: return

        container = view.container_combobox.get()
        if not container or "Select" in container or "No containers" in container: return

        self.app.backend.azure_auth.container_name = container
        self.app.update_status(f"Container '{container}' selected.", "blue")
        self.app.nav_panel.set_azure_buttons_state("normal")
