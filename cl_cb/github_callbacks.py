# cl_cb/github_callbacks.py
from functools import partial
from tkinter import simpledialog, messagebox

# Centralized application configuration
from config_loader import CONFIG


class GitHubCallbacks:
    """
    Handles all callback logic for the GitHubView, acting as a controller
    that connects the UI to the backend GitHubHandler.
    """

    def __init__(self, app_controller):
        self.app = app_controller

    # --- Authentication Callbacks ---

    def handle_login_device_flow(self):
        """Initiates the GitHub OAuth Device Flow."""
        view = self.app.github_view
        if view:
            view._set_ui_state('loading')
        self.app.update_status("Starting GitHub OAuth Device Flow...")
        self.app.run_in_thread(self._login_device_flow_task)

    def _login_device_flow_task(self):
        """Background task for handling the device flow process."""
        try:
            flow_data = self.app.backend.github.start_device_flow()
            user_code = flow_data["user_code"]
            verification_uri = flow_data["verification_uri"]

            # Schedule UI update on the main thread
            self.app.root.after(0, lambda: self._write_to_console_safe(
                f"\n--- GitHub Authentication ---\n"
                f"Please visit: {verification_uri}\n"
                f"And enter code: {user_code}\n"
                f"Waiting for authorization...\n"
            ))
            self.app.backend.github.poll_for_token(self._on_auth_success, self._on_auth_failure)
        except Exception as e:
            self._on_auth_failure(e)

    def handle_login_cli(self):
        """Initiates authentication using the GitHub CLI."""
        view = self.app.github_view
        if view:
            view._set_ui_state('loading')
        self.app.update_status("Starting GitHub CLI login...")
        self.app.run_in_thread(self._login_cli_task)

    def _login_cli_task(self):
        """Background task for handling the GitHub CLI login process."""
        line_callback = lambda line: self.app.root.after(0, self._write_to_console_safe, line)
        try:
            result = self.app.backend.github.login_with_cli(line_callback)
            self.app.root.after(0, lambda: self._on_auth_success(result))
        except Exception as e:
            self._on_auth_failure(e)

    def _on_auth_success(self, result_message):
        """Callback for successful authentication."""
        self.app.root.after(0, lambda: self.app.update_status(result_message))
        self.app.root.after(0, self.handle_load_repos)  # Auto-load repos
        self.app.root.after(0, lambda: self._set_ui_state_safe('authenticated'))

    def _on_auth_failure(self, exception):
        """Callback for failed authentication."""
        self.app.root.after(0, lambda: self.app.show_error(f"Authentication Failed: {exception}"))
        self.app.root.after(0, lambda: self._set_ui_state_safe('unauthenticated'))

    def handle_check_auth(self):
        """Checks initial authentication status."""
        self.app.update_status("Ready. Please log in to GitHub.")
        self._set_ui_state_safe('unauthenticated')

    # --- Repository Callbacks ---

    def handle_load_repos(self):
        """Initiates fetching of user's repositories."""
        view = self.app.github_view
        if not view: return
        self.app.update_status("Fetching repositories...")
        view._set_ui_state('loading')
        view._clear_repo_list()
        self.app.run_in_thread(self._load_repos_task)

    def _load_repos_task(self):
        """Background task to fetch repositories."""
        line_callback = lambda line: self.app.root.after(0, self._write_to_console_safe, line)
        try:
            repos = self.app.backend.github.fetch_repos(line_callback)
            self.app.root.after(0, lambda: self._populate_repo_list_safe(repos))
            self.app.root.after(0, lambda: self.app.update_status(f"Loaded {len(repos)} repositories."))
        except Exception as e:
            self.app.root.after(0, lambda: self.app.show_error(f"Failed to load repos: {e}"))
        finally:
            self.app.root.after(0, lambda: self._set_ui_state_safe('authenticated'))

    # --- Cloning Callbacks ---

    def handle_clone(self):
        """Clones the repository selected in the listbox."""
        view = self.app.github_view
        if not view: return
        repo_full_name = view._get_selected_repo_name()
        if not repo_full_name:
            self.app.show_error("No repository selected.")
            return
        self._initiate_clone_task(repo_to_clone=repo_full_name)

    def handle_clone_from_url(self):
        """Clones a repository from a user-provided URL."""
        repo_url = self.app.github_view.url_entry.get().strip()
        if not repo_url:
            self.app.show_error("Please enter a repository URL.")
            return
        self._initiate_clone_task(repo_to_clone=repo_url, is_url=True)

    def _initiate_clone_task(self, repo_to_clone, is_url=False):
        """Helper to set up and run the clone task in a background thread."""
        self.app.update_status(f"Cloning {repo_to_clone}...")
        if self.app.github_view:
            self.app.github_view._set_ui_state('loading')
        task = partial(self._clone_task, repo_to_clone=repo_to_clone, is_url=is_url)
        self.app.run_in_thread(task)

    def _clone_task(self, repo_to_clone, is_url=False):
        """Background task for cloning a repository."""
        line_callback = lambda line: self.app.root.after(0, self._write_to_console_safe, line)
        try:
            if is_url:
                result = self.app.backend.github.clone_repo_from_url(repo_to_clone, line_callback)
            else:
                result = self.app.backend.github.clone_repo(repo_to_clone, line_callback)
            self.app.root.after(0, lambda: messagebox.showinfo("Success", result))
            self.app.root.after(0, lambda: self.app.update_status("Clone successful."))
        except Exception as e:
            self.app.root.after(0, lambda: self.app.show_error(f"Clone failed: {e}"))
        finally:
            self.app.root.after(0, lambda: self._set_ui_state_safe('authenticated'))

    def handle_open_browser(self):
        """Opens the selected repository in the default web browser."""
        view = self.app.github_view
        repo_full_name = view._get_selected_repo_name()
        if repo_full_name:
            status_message = self.app.backend.github.open_repo_in_browser(repo_full_name)
            self.app.update_status(status_message)
        else:
            self.app.show_error("No repository selected.")

    # --- UI Helper Methods ---

    def _set_ui_state_safe(self, state):
        """Safely updates the UI state from a background thread."""
        if self.app.github_view:
            self.app.github_view._set_ui_state(state)

    def _write_to_console_safe(self, text):
        """Safely writes text to the console from a background thread."""
        if self.app.github_view:
            self.app.github_view._write_to_console(text)

    def _populate_repo_list_safe(self, repos):
        """Safely populates the repository list from a background thread."""
        if self.app.github_view:
            self.app.github_view._populate_repo_list(repos)

