# cl_ui/github_ui.py
import tkinter as tk
from tkinter import ttk, scrolledtext

# Centralized application configuration
from config_loader import CONFIG


class GitHubView(ttk.Frame):
    """
    The main view for all GitHub-related operations.
    This class creates the UI widgets and provides methods to interact with them.
    """

    def __init__(self, parent, app_controller):
        super().__init__(parent, padding=10)
        self.pack(fill="both", expand=True)
        self.app = app_controller
        cb = self.app.github_callbacks

        # --- UI Construction ---
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", pady=(0, 10))

        self.login_cli_button = ttk.Button(control_frame, text="Login with GitHub CLI", command=cb.handle_login_cli)
        self.login_cli_button.pack(side="left", padx=(0, 5))
        self.login_device_button = ttk.Button(control_frame, text="Login with OAuth", command=cb.handle_login_device_flow)
        self.login_device_button.pack(side="left", padx=(0, 5))
        self.load_repos_button = ttk.Button(control_frame, text="Load Repositories", command=cb.handle_load_repos, state="disabled")
        self.load_repos_button.pack(side="left", padx=5)

        paned_window = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned_window.pack(fill="both", expand=True)

        main_content_frame = ttk.Frame(paned_window)
        paned_window.add(main_content_frame, weight=1)

        url_clone_frame = ttk.LabelFrame(main_content_frame, text="Clone from URL", padding=10)
        url_clone_frame.pack(fill="x", pady=5)
        url_clone_frame.columnconfigure(1, weight=1)
        ttk.Label(url_clone_frame, text="Repo URL:").grid(row=0, column=0, sticky="w", padx=5)
        self.url_entry = ttk.Entry(url_clone_frame)
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(url_clone_frame, text="Clone", command=cb.handle_clone_from_url).grid(row=0, column=2, padx=5)

        list_frame = ttk.LabelFrame(main_content_frame, text="Or Select From Your Repositories")
        list_frame.pack(fill="both", expand=True, pady=5)

        self.repo_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE)
        self.repo_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.repo_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.repo_listbox.config(yscrollcommand=scrollbar.set)

        repo_actions_frame = ttk.Frame(list_frame)
        repo_actions_frame.pack(fill="x", pady=5, padx=5)
        self.clone_button = ttk.Button(repo_actions_frame, text="Clone Selected", command=cb.handle_clone, state="disabled")
        self.clone_button.pack(side="left")
        self.open_browser_button = ttk.Button(repo_actions_frame, text="Open in Browser", command=cb.handle_open_browser, state="disabled")
        self.open_browser_button.pack(side="left", padx=5)

        console_frame = ttk.LabelFrame(paned_window, text="Console Output")
        paned_window.add(console_frame, weight=1)

        self.console_text = scrolledtext.ScrolledText(
            console_frame, wrap=tk.WORD, height=10,
            background="#2d2d2d", foreground="#cccccc",
            font=tuple(CONFIG['ui']['fonts']['default_console'])
        )
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cb.handle_check_auth()

    def _set_ui_state(self, state: str):
        """Controls the state of buttons based on auth status."""
        is_auth = state == 'authenticated'
        self.login_cli_button.config(state="disabled" if is_auth else "normal")
        self.login_device_button.config(state="disabled" if is_auth else "normal")
        self.load_repos_button.config(state="normal" if is_auth else "disabled")
        self.clone_button.config(state="normal" if is_auth else "disabled")
        self.open_browser_button.config(state="normal" if is_auth else "disabled")

    def _write_to_console(self, text: str):
        self.console_text.insert(tk.END, text)
        self.console_text.see(tk.END)

    def _populate_repo_list(self, repos: list):
        self._clear_repo_list()
        for repo in repos:
            visibility = "[Private]" if repo.get("visibility") == "private" else "[Public]"
            self.repo_listbox.insert(tk.END, f"{visibility} {repo['nameWithOwner']}")

    def _get_selected_repo_name(self) -> str | None:
        selection_indices = self.repo_listbox.curselection()
        if not selection_indices:
            return None
        selected_item = self.repo_listbox.get(selection_indices[0])
        # Use offset from config to parse name correctly
        name_start_index = selected_item.find(']') + CONFIG['parsing']['github_repo_name_offset']
        return selected_item[name_start_index:]

    def _clear_repo_list(self):
        self.repo_listbox.delete(0, tk.END)
