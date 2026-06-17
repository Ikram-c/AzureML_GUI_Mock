# main_app.py
"""
Cloud Development Tools - Main Application

A comprehensive desktop application for managing Azure cloud resources and GitHub repositories.
Provides integrated tools for blob storage, machine learning workspaces, and source control.

Author: Development Team
Version: 2.0.0
License: MIT
"""

import logging
import os
import sys
import tkinter as tk
import traceback
from functools import partial
from tkinter import ttk
from types import SimpleNamespace# cl_ui/azure_ml_ui.py
import tkinter as tk
from datetime import datetime
from tkinter import ttk


class AzureMLView(ttk.Frame):
    """
    The main view for all Azure Machine Learning operations.
    This class creates the UI for connecting to a workspace and then reveals
    operational panels for submitting jobs and viewing resources.
    """

    def __init__(self, parent, app_controller):
        """
        Initializes the AzureMLView.

        Args:
            parent: The parent tkinter frame.
            app_controller: The main application controller instance.
        """
        super().__init__(parent, padding=10)
        self.pack(fill="both", expand=True)
        self.app = app_controller

        # Get a reference to the callbacks controller for Azure ML
        cb = self.app.ml_callbacks

        # --- State and Widget Storage ---
        self.job_panel_vars = {
            'code_path': tk.StringVar(value="No path selected."),
            'full_code_path': None,
            'code_type': tk.StringVar(value="directory"),
            'env_option': tk.StringVar(value="conda"),
            'conda_file_path': tk.StringVar(value="environment.yml")
        }

        # --- Build Top-Level Layout ---
        self._build_connect_panel(cb)

        # The content_frame will hold the operational tabs after connection
        self.content_frame = ttk.Frame(self)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.operational_notebook = None  # Will be created on successful connect

        # --- Initial Data Load ---
        cb.handle_load_subscriptions()

    def _build_connect_panel(self, cb):
        """Builds the panel for connecting to a workspace."""
        self.connect_panel = ttk.LabelFrame(self, text="Azure ML Connection", padding=10)
        self.connect_panel.pack(fill=tk.X)
        self.connect_panel.columnconfigure(1, weight=1)

        # Subscription Dropdown
        ttk.Label(self.connect_panel, text="Subscription:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.connect_panel.sub_combo = ttk.Combobox(self.connect_panel, state="readonly", values=["Loading..."])
        self.connect_panel.sub_combo.grid(row=0, column=1, sticky="ew", padx=5)
        self.connect_panel.sub_combo.bind("<<ComboboxSelected>>", cb.handle_subscription_selected)

        # Resource Group Dropdown
        ttk.Label(self.connect_panel, text="Resource Group:").grid(row=1, column=0, sticky="w", pady=2, padx=5)
        self.connect_panel.rg_combo = ttk.Combobox(self.connect_panel, state="disabled")
        self.connect_panel.rg_combo.grid(row=1, column=1, sticky="ew", padx=5)
        self.connect_panel.rg_combo.bind("<<ComboboxSelected>>", cb.handle_rg_selected)

        # Workspace Dropdown
        ttk.Label(self.connect_panel, text="ML Workspace:").grid(row=2, column=0, sticky="w", pady=2, padx=5)
        self.connect_panel.ws_combo = ttk.Combobox(self.connect_panel, state="disabled")
        self.connect_panel.ws_combo.grid(row=2, column=1, sticky="ew", padx=5)
        self.connect_panel.ws_combo.bind("<<ComboboxSelected>>", lambda e: self.connect_button.config(state="normal"))

        # Connect Button
        self.connect_button = ttk.Button(
            self.connect_panel, text="Connect to Workspace", command=cb.handle_connect_to_workspace, state="disabled"
        )
        self.connect_button.grid(row=3, column=1, sticky="e", pady=(10, 0), padx=5)

    def _on_successful_connect(self):
        """Callback executed after a successful connection to an ML workspace."""
        if self.operational_notebook:
            self.operational_notebook.destroy()  # Clear previous tabs if any

        self.operational_notebook = ttk.Notebook(self.content_frame)
        self.operational_notebook.pack(fill="both", expand=True)

        # Create the different operational tabs
        job_tab = ttk.Frame(self.operational_notebook)
        compute_tab = ttk.Frame(self.operational_notebook)
        model_tab = ttk.Frame(self.operational_notebook)

        self.operational_notebook.add(job_tab, text="Submit Job")
        self.operational_notebook.add(compute_tab, text="Compute Targets")
        self.operational_notebook.add(model_tab, text="Registered Models")

        # Build the content for each tab
        self._build_job_panel(job_tab, self.app.ml_callbacks)
        self._build_compute_panel(compute_tab, self.app.ml_callbacks)
        self._build_model_panel(model_tab, self.app.ml_callbacks)

    def _build_job_panel(self, parent, cb):
        """Builds the UI for submitting a new ML Job."""
        # Use a canvas with a scrollbar for potentially long forms
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding=10)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        container = ttk.LabelFrame(scrollable_frame, text="Job Configuration", padding=15)
        container.pack(fill="x", expand=True)
        container.columnconfigure(1, weight=1)

        # Job Name
        ttk.Label(container, text="Job Display Name:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.job_name_entry = ttk.Entry(container)
        self.job_name_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.job_name_entry.insert(0, f"job-{datetime.now():%Y%m%d-%H%M%S}")

        # Compute Target
        ttk.Label(container, text="Compute Target:").grid(row=1, column=0, sticky="w", pady=2, padx=5)
        self.compute_combo = ttk.Combobox(container, state="readonly")
        self.compute_combo.grid(row=1, column=1, sticky="ew", padx=5)
        self._load_computes_for_job_panel()  # Populate this dropdown

        # Code Path
        ttk.Label(container, text="Code Path:").grid(row=2, column=0, sticky="w", pady=2, padx=5)
        path_frame = ttk.Frame(container)
        path_frame.grid(row=2, column=1, sticky="ew")
        path_frame.columnconfigure(0, weight=1)
        ttk.Label(path_frame, textvariable=self.job_panel_vars['code_path']).pack(side="left",
                                                                                  fill="x",
                                                                                  expand=True, padx=5)
        ttk.Button(path_frame, text="Browse...", command=cb.handle_select_code_path).pack(side="left")

        # Entry Script
        ttk.Label(container, text="Command:").grid(row=3, column=0, sticky="w", pady=2, padx=5)
        self.entry_script_entry = ttk.Entry(container)
        self.entry_script_entry.grid(row=3, column=1, sticky="ew", padx=5)
        self.entry_script_entry.insert(0, "python train.py")

        # Environment
        env_frame = ttk.LabelFrame(container, text="Environment", padding=10)
        env_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)

        # --- Conda Option ---
        ttk.Radiobutton(env_frame, text="Conda File:", variable=self.job_panel_vars['env_option'], value="conda").pack(
            anchor="w")

        # Frame to hold the conda file entry and browse button
        conda_file_frame = ttk.Frame(env_frame)
        conda_file_frame.pack(fill='x', expand=True, padx=25, pady=(2, 5))

        self.conda_file_entry = ttk.Entry(conda_file_frame, textvariable=self.job_panel_vars['conda_file_path'])
        self.conda_file_entry.pack(side='left', fill='x', expand=True)

        ttk.Button(conda_file_frame, text="Browse...", command=cb.handle_select_conda_file).pack(side='left',
                                                                                                 padx=(5, 0))

        # --- Docker Option ---
        ttk.Radiobutton(env_frame, text="Docker Image:", variable=self.job_panel_vars['env_option'],
                        value="docker").pack(anchor="w")
        self.docker_image_entry = ttk.Entry(env_frame)
        self.docker_image_entry.pack(fill="x", padx=25, pady=2)

        # Submit Button
        self.submit_button = ttk.Button(scrollable_frame, text="Submit Job", command=cb.handle_submit_job)
        self.submit_button.pack(pady=10)

    def _build_compute_panel(self, parent, cb):
        """Builds the UI for viewing compute targets."""
        tree_frame = ttk.Frame(parent, padding=10)
        tree_frame.pack(fill="both", expand=True)
        columns = ("Name", "Type", "State", "Location")
        self.compute_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col in columns:
            self.compute_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.compute_tree.yview)
        self.compute_tree.configure(yscrollcommand=scrollbar.set)
        self.compute_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(parent, text="Refresh List", command=cb.handle_refresh_computes).pack(pady=5, padx=10, anchor="e")
        cb.handle_refresh_computes()  # Initial load

    def _build_model_panel(self, parent, cb):
        """Builds the UI for viewing registered models."""
        tree_frame = ttk.Frame(parent, padding=10)
        tree_frame.pack(fill="both", expand=True)
        columns = ("Name", "Version", "Created At")
        self.model_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col in columns:
            self.model_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.model_tree.yview)
        self.model_tree.configure(yscrollcommand=scrollbar.set)
        self.model_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(parent, text="Refresh List", command=cb.handle_refresh_models).pack(pady=5, padx=10, anchor="e")
        cb.handle_refresh_models()  # Initial load

    # --- Internal UI Helper Methods for Callbacks ---

    def _populate_subscriptions(self, subs):
        display_names = [sub['name'] for sub in subs] if subs else ["No subscriptions found"]
        self.connect_panel.sub_combo["values"] = display_names
        self.connect_panel.sub_combo.set("Select a Subscription" if subs else display_names[0])

    def _populate_resource_groups(self, groups):
        self.connect_panel.rg_combo["values"] = groups if groups else ["No resource groups found"]
        self.connect_panel.rg_combo.config(state="readonly")
        self.connect_panel.rg_combo.set("Select a Resource Group" if groups else "No resource groups found")

    def _populate_workspaces(self, workspaces):
        display_names = [ws['name'] for ws in workspaces] if workspaces else ["No ML workspaces found"]
        self.connect_panel.ws_combo["values"] = display_names
        self.connect_panel.ws_combo.config(state="readonly")
        self.connect_panel.ws_combo.set("Select an ML Workspace" if workspaces else display_names[0])

    def _reset_rg_and_ws_combos(self):
        self.connect_panel.rg_combo.set('')
        self.connect_panel.rg_combo.config(state="disabled")
        self._reset_ws_combo()

    def _reset_ws_combo(self):
        self.connect_panel.ws_combo.set('')
        self.connect_panel.ws_combo.config(state="disabled")
        self.connect_button.config(state="disabled")

    def _clear_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def _populate_compute_tree(self, computes):
        if not computes:
            self.compute_tree.insert("", "end", values=("No compute targets found.", "", "", ""))
            return
        for compute in sorted(computes, key=lambda c: c.name):
            self.compute_tree.insert("", "end", values=(
                getattr(compute, 'name', 'N/A'),
                getattr(compute, 'type', 'N/A'),
                getattr(compute, 'state', 'N/A'),
                getattr(compute, 'location', 'N/A')
            ))

    def _populate_model_tree(self, models):
        if not models:
            self.model_tree.insert("", "end", values=("No registered models found.", "", ""))
            return
        for model in sorted(models, key=lambda m: m.name):
            created_at = model.creation_context.created_at.strftime(
                "%Y-%m-%d %H:%M") if model.creation_context else "N/A"
            self.model_tree.insert("", "end", values=(model.name, model.version, created_at))

    def _set_submit_button_state(self, state):
        if hasattr(self, 'submit_button'):
            self.submit_button.config(state=state)

    def _load_computes_for_job_panel(self):
        """Populates the compute dropdown in the job panel."""

        def on_fetch_complete(computes, error):
            if error:
                self.compute_combo["values"] = ["Error loading"]
            else:
                # Filter for AML compute clusters only, as they are used for training jobs
                compute_names = [c.name for c in computes if c.type == 'amlcompute']
                self.compute_combo["values"] = compute_names if compute_names else ["No compute clusters"]
                if compute_names: self.compute_combo.set(compute_names[0])

        self.app.run_in_thread(self.app.backend.ml.list_computes, on_fetch_complete)

# Import dependency management
from app_setup import DEPENDENCY_STATUS, run_startup_checks, get_dependency_report
# Backend Handlers - Core business logic
from cl_be.azure_auth_handler import AzureAuthHandler
from cl_be.azure_blob_handler import AzureBlobHandler
from cl_be.azure_ml_handler import AzureMLHandler
from cl_be.github_handler import GitHubHandler
# Callback Controllers - UI event handlers
from cl_cb.azure_callbacks import AzureCallbacks
from cl_cb.azure_ml_callbacks import AzureMLCallbacks
from cl_cb.azure_ml_job_monitor_callbacks import JobMonitorCallbacks
from cl_cb.blob_callbacks import BlobCallbacks
from cl_cb.github_callbacks import GitHubCallbacks
# UI Views - User interface components
from cl_ui.azure_auth_ui import AzureConnectView
from cl_ui.azure_ml_job_monitor_ui import JobMonitorView
from cl_ui.azure_ml_ui import AzureMLView
from cl_ui.azure_storage_ui import AzureStorageView
from cl_ui.github_ui import GitHubView
from cl_ui.navigation_panel import NavigationPanel
from cl_ui.status_bar import StatusBar
# UI Helpers - Utility functions
from cl_ui.ui_helpers import set_initial_window_size, run_in_thread, show_message


# Configure logging
def setup_logging():
    """Configure application logging."""
    log_dir = os.path.join(os.path.expanduser("~"), ".cloud_tools", "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "application.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)


# Initialize logger
logger = setup_logging()


class CloudToolsApp:
    """
    Main controller class for the Cloud Development Tools application.

    This class orchestrates the entire application, managing:
    - Backend service initialization
    - UI component coordination
    - View switching and state management
    - Error handling and user feedback
    - Application lifecycle
    """

    def __init__(self, main_root: tk.Tk):
        """
        Initialize the main application.

        Args:
            main_root: The root Tkinter window
        """
        self.root = main_root
        self.current_view_name = None
        self.initialization_complete = False

        # Application metadata
        self.app_info = {
            "name": "Cloud Development Tools",
            "version": "2.0.0",
            "author": "Development Team",
            "description": "Integrated Azure and GitHub management tools"
        }

        try:
            self._initialize_application()
        except Exception as init_error:
            logger.error("Failed to initialize application: %s", str(init_error))
            self._handle_initialization_error(init_error)

    def _initialize_application(self):
        """Initialize all application components in the correct order."""
        # Step 1: Configure main window
        self._setup_main_window()

        # Step 2: Initialize backend services
        self._initialize_backend_services()

        # Step 3: Initialize callback controllers
        self._initialize_callback_controllers()

        # Step 4: Initialize UI components
        self._initialize_ui_components()

        # Step 5: Setup main layout
        self._setup_main_layout()

        # Step 6: Set initial state
        self._set_initial_state()

        # Step 7: Perform post-initialization tasks
        self._post_initialization_setup()

        self.initialization_complete = True
        self.update_status("Application initialized successfully.")

    def _setup_main_window(self):
        """Configure the main application window."""
        self.root.title(f"{self.app_info['name']} v{self.app_info['version']}")
        set_initial_window_size(self.root)
        self.root.configure(padx=10, pady=10)

        # Set minimum window size
        self.root.minsize(800, 600)

        # Configure window closing behavior
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Set window icon if available
        try:
            # Attempt to load application icon
            icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.ico')
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            else:
                logger.info("Application icon not found at %s, continuing without icon", icon_path)
        except (tk.TclError, OSError) as icon_error:
            logger.warning("Failed to load application icon: %s", str(icon_error))
        except Exception as unexpected_error:
            logger.error("Unexpected error loading icon: %s", str(unexpected_error))

    def _initialize_backend_services(self):
        """Initialize all backend service handlers."""
        self.backend = SimpleNamespace()

        try:
            # Initialize core services
            self.backend.azure_auth = AzureAuthHandler()
            self.backend.blob = AzureBlobHandler()
            self.backend.ml = AzureMLHandler()
            self.backend.github = GitHubHandler()

            # Validate services
            self._validate_backend_services()

        except Exception as e:
            raise RuntimeError(f"Failed to initialize backend services: {str(e)}")

    def _validate_backend_services(self):
        """Validate that all backend services are properly initialized."""
        required_services = ['azure_auth', 'blob', 'ml', 'github']

        for service_name in required_services:
            if not hasattr(self.backend, service_name):
                raise RuntimeError(f"Backend service '{service_name}' not initialized")

            service = getattr(self.backend, service_name)
            if service is None:
                raise RuntimeError(f"Backend service '{service_name}' is None")

    def _initialize_callback_controllers(self):
        """Initialize all callback controller instances."""
        try:
            # Create callback controllers that handle UI events
            self.azure_callbacks = AzureCallbacks(self)
            self.blob_callbacks = BlobCallbacks(self)
            self.ml_callbacks = AzureMLCallbacks(self)
            self.job_monitor_callbacks = JobMonitorCallbacks(self)
            self.github_callbacks = GitHubCallbacks(self)

        except Exception as e:
            raise RuntimeError(f"Failed to initialize callback controllers: {str(e)}")

    def _initialize_ui_components(self):
        """Initialize UI component references."""
        # Create attributes to hold current view instances
        self.connect_view = None
        self.storage_view = None
        self.ml_view = None
        self.job_monitor_view = None
        self.github_view = None

    def _setup_main_layout(self):
        """Initialize the main application layout with navigation and content areas."""
        # Configure grid weights for responsive layout
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Create view switching map
        view_map = {
            "connect": partial(self._switch_view, "connect"),
            "storage": partial(self._switch_view, "storage"),
            "ml": partial(self._switch_view, "ml"),
            "monitor": partial(self._switch_view, "monitor"),
            "github": partial(self._switch_view, "github"),
        }

        # Create navigation panel
        self.nav_panel = NavigationPanel(self.root, view_map)
        self.nav_panel.grid(row=0, column=0, sticky="ns", padx=(0, 10))

        # Create main content area
        self.main_content_frame = ttk.Frame(self.root)
        self.main_content_frame.grid(row=0, column=1, sticky="nsew")

        # Create status bar
        self.status_bar = StatusBar(self.root)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def _set_initial_state(self):
        """Set the initial application state and load the first view."""
        # Disable Azure-dependent features initially
        self.nav_panel.set_azure_buttons_state("disabled")

        # Load the initial view
        self._switch_view("connect")

    def _post_initialization_setup(self):
        """Perform post-initialization setup tasks."""
        # Update window title with dependency info
        available_features = self._get_available_features()
        if available_features:
            feature_count = len(available_features)
            self.root.title(f"{self.app_info['name']} v{self.app_info['version']} ({feature_count} features available)")

        # Start periodic status checks
        self._start_periodic_tasks()

    @staticmethod
    def _get_available_features() -> list:
        """Get list of available features based on dependencies."""
        features = ["Core UI"]

        if DEPENDENCY_STATUS.get("azure_sdk", False):
            features.extend(["Azure Storage", "Azure ML"])

        if DEPENDENCY_STATUS.get("pygithub", False) or DEPENDENCY_STATUS.get("git", False):
            features.append("GitHub Integration")

        if DEPENDENCY_STATUS.get("pillow", False):
            features.append("Image Preview")

        return features

    def _start_periodic_tasks(self):
        """Start background tasks for periodic updates."""

        # Check for updates every 30 seconds
        def periodic_check():
            if self.initialization_complete:
                try:
                    self._update_connection_status()
                except Exception as status_error:
                    logger.warning("Periodic status check failed: %s", str(status_error))

            # Schedule next check
            self.root.after(30000, periodic_check)

        # Start the periodic check
        self.root.after(5000, periodic_check)  # First check after 5 seconds

    def _update_connection_status(self):
        """Update the connection status indicators."""
        if hasattr(self, 'status_bar'):
            # Check Azure connection
            azure_connected = bool(self.backend.azure_auth.credential or
                                   self.backend.azure_auth.blob_service_client)

            # Check GitHub connection
            github_connected = bool(self.backend.github.is_authenticated)

            # Update status if needed
            connections = []
            if azure_connected:
                connections.append("Azure")
            if github_connected:
                connections.append("GitHub")

            if connections and self.current_view_name != "connect":
                connection_text = f"Connected: {', '.join(connections)}"
                # Only update if status hasn't been updated recently
                current_status = self.status_bar.status_label.cget('text')
                if not current_status.startswith("Connected:"):
                    self.update_status(connection_text, "green")

    # --- View Management ---

    def _clear_main_content(self):
        """Clear the main content area and reset view references."""
        for widget in self.main_content_frame.winfo_children():
            widget.destroy()

        # Clear view references to prevent memory leaks
        self.connect_view = None
        self.storage_view = None
        self.ml_view = None
        self.job_monitor_view = None
        self.github_view = None

    def _switch_view(self, view_name: str):
        """
        Switch to the specified view with proper validation and error handling.

        Args:
            view_name: Name of the view to switch to
        """
        if self.current_view_name == view_name:
            return  # Don't reload the same view

        try:
            # Validate view switch
            if not self._validate_view_switch(view_name):
                return

            # Clear current content
            self._clear_main_content()

            # Update current view tracking
            self.current_view_name = view_name

            # Update navigation highlighting
            self.nav_panel.highlight_current_view(view_name)

            # Create the new view
            self._create_view(view_name)

        except Exception as e:
            self._handle_view_switch_error(view_name, e)

    def _validate_view_switch(self, view_name: str) -> bool:
        """
        Validate whether switching to the specified view is allowed.

        Args:
            view_name: Name of the view to validate

        Returns:
            bool: True if view switch is allowed, False otherwise
        """
        # Define view classes for validation
        view_classes = {
            "connect": AzureConnectView,
            "storage": AzureStorageView,
            "ml": AzureMLView,
            "monitor": JobMonitorView,
            "github": GitHubView,
        }

        if view_name not in view_classes:
            show_message("error", "Invalid View", f"View '{view_name}' is not recognized.")
            return False

        # Check dependency requirements
        if view_name == "github" and not (DEPENDENCY_STATUS.get("git", False) or
                                          DEPENDENCY_STATUS.get("pygithub", False)):
            show_message("info", "Dependencies Required",
                         "GitHub features require Git and/or PyGithub libraries. "
                         "Please install the missing dependencies to use this feature.")
            self._switch_view("connect")
            return False

        # Check Azure authentication requirements
        auth_handler = self.backend.azure_auth

        if view_name in ["storage", "ml", "monitor"] and not auth_handler.credential:
            show_message("info", "Authentication Required",
                         "Please sign in to your Azure account on the 'Connect' page first.")
            self._switch_view("connect")
            return False

        if view_name == "storage" and not auth_handler.container_name:
            show_message("info", "Connection Required",
                         "Please select a Storage Account and Container on the 'Connect' page first.")
            self._switch_view("connect")
            return False

        if view_name == "monitor" and not self.backend.ml.ml_client:
            show_message("info", "ML Workspace Required",
                         "Please connect to an Azure ML Workspace on the 'Azure ML' page first.")
            self._switch_view("ml")
            return False

        return True

    def _create_view(self, view_name: str):
        """
        Create and display the specified view.

        Args:
            view_name: Name of the view to create
        """
        view_classes = {
            "connect": AzureConnectView,
            "storage": AzureStorageView,
            "ml": AzureMLView,
            "monitor": JobMonitorView,
            "github": GitHubView,
        }

        view_class = view_classes.get(view_name)
        if not view_class:
            raise ValueError(f"Unknown view: {view_name}")

        try:
            # Create the view instance
            view_instance = view_class(self.main_content_frame, self)

            # Store reference to the view
            setattr(self, f"{view_name}_view", view_instance)

            # Update status
            view_display_names = {
                "connect": "Azure Connection",
                "storage": "Storage Manager",
                "ml": "ML Workspace",
                "monitor": "Job Monitor",
                "github": "GitHub Tools"
            }

            display_name = view_display_names.get(view_name, view_name.title())
            self.update_status(f"{display_name} loaded.")

        except Exception as view_error:
            # Show error in the content area instead of crashing
            logger.error("Failed to create view '%s': %s", view_name, str(view_error))
            self._create_error_view(view_name, view_error)

    def _create_error_view(self, view_name: str, error: Exception):
        """Create an error view when normal view creation fails."""
        error_frame = ttk.Frame(self.main_content_frame)
        error_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(error_frame, text=f"Error Loading {view_name.title()} View",
                  font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        error_text = tk.Text(error_frame, height=10, wrap=tk.WORD)
        error_text.pack(fill="both", expand=True)
        error_text.insert("1.0", f"Error: {str(error)}\n\nTraceback:\n{traceback.format_exc()}")
        error_text.config(state=tk.DISABLED)

        ttk.Button(error_frame, text="Return to Connect View",
                   command=lambda: self._switch_view("connect")).pack(pady=10)

        self.update_status(f"Error loading {view_name} view.", "red")

    def _handle_view_switch_error(self, view_name: str, error: Exception):
        """
        Handle errors that occur during view switching.

        Args:
            view_name: Name of the view that failed to load
            error: The exception that occurred
        """
        error_msg = f"Failed to switch to {view_name} view: {str(error)}"
        logger.error("View switch error: %s", error_msg)
        logger.debug("View switch traceback: %s", traceback.format_exc())

        self.update_status(f"Error switching to {view_name} view.", "red")
        show_message("error", "View Error", error_msg)

        # Try to return to a safe view
        if self.current_view_name != "connect":
            try:
                self._switch_view("connect")
            except Exception as fallback_error:
                logger.critical("Failed to switch to fallback connect view: %s", str(fallback_error))

    # --- Application Lifecycle ---

    def sign_out(self):
        """Sign out from all services and reset the application state."""
        try:
            # Clear backend state
            self.backend.azure_auth.sign_out()
            if hasattr(self.backend.ml, 'ml_client'):
                self.backend.ml.ml_client = None

            if hasattr(self.backend.github, 'logout'):
                self.backend.github.logout()

            # Reset UI state
            self.nav_panel.set_azure_buttons_state("disabled")

            # Switch to connect view
            self._switch_view("connect")

            self.update_status("Signed out successfully.")
            logger.info("User signed out successfully")

        except Exception as signout_error:
            logger.error("Sign out error: %s", str(signout_error))
            self.update_status("Sign out completed with warnings.", "orange")

    def _on_window_close(self):
        """Handle application window close event."""
        try:
            logger.info("Application shutdown initiated")
            # Perform cleanup
            self._cleanup_resources()

            # Close the application
            self.root.quit()
            self.root.destroy()

        except Exception as shutdown_error:
            logger.error("Error during shutdown: %s", str(shutdown_error))
            # Force close if cleanup fails
            self.root.destroy()

    def _cleanup_resources(self):
        """Clean up resources before application shutdown."""
        try:
            # Stop any background threads
            # Clean up temporary files
            # Save application state if needed

            # Sign out cleanly
            self.sign_out()
            logger.info("Resource cleanup completed")

        except Exception as cleanup_error:
            logger.error("Cleanup error: %s", str(cleanup_error))

    def _handle_initialization_error(self, error: Exception):
        """
        Handle critical errors during application initialization.

        Args:
            error: The exception that occurred during initialization
        """
        error_msg = f"Application initialization failed: {str(error)}"
        logger.critical("Initialization error: %s", error_msg)
        logger.debug("Initialization traceback: %s", traceback.format_exc())

        # Try to show error dialog
        try:
            show_message("error", "Initialization Error",
                         f"The application failed to initialize properly:\n\n{error_msg}")
        except Exception as dialog_error:
            # If UI isn't available, print to console
            logger.critical("Could not show error dialog: %s", str(dialog_error))
            print("CRITICAL ERROR: Could not initialize application")
            print(error_msg)

        # Exit the application
        sys.exit(1)

    # --- Helper Methods ---

    def run_in_thread(self, target_func, callback=None):
        """
        Run a function in a background thread with optional callback.

        Args:
            target_func: Function to run in background
            callback: Optional callback function for results
        """
        run_in_thread(self.root, target_func, callback)

    def update_status(self, text: str, color: str = "black"):
        """
        Update the status bar text and color.

        Args:
            text: Status message to display
            color: Text color (black, red, green, blue, orange)
        """
        if hasattr(self, 'status_bar'):
            self.status_bar.set_status(text, color)

    def show_error(self, message: str, title: str = "Error"):
        """
        Show an error message dialog.

        Args:
            message: Error message to display
            title: Dialog title
        """
        show_message('error', title, message, parent=self.root)

    def show_info(self, message: str, title: str = "Information"):
        """
        Show an information message dialog.

        Args:
            message: Information message to display
            title: Dialog title
        """
        show_message('info', title, message, parent=self.root)

    def get_app_info(self) -> dict:
        """
        Get application information and status.

        Returns:
            dict: Application information
        """
        return {
            **self.app_info,
            "current_view": self.current_view_name,
            "initialization_complete": self.initialization_complete,
            "available_features": self._get_available_features(),
            "dependency_status": dict(DEPENDENCY_STATUS)
        }


def main():
    """Main application entry point."""
    print("Starting Cloud Development Tools...")
    logger.info("Application startup initiated")

    try:
        # Step 1: Run dependency checks
        print("Checking dependencies...")
        logger.info("Running dependency checks")
        run_startup_checks()

        # Step 2: Create main window
        print("Creating main window...")
        logger.info("Creating main Tkinter window")
        main_window = tk.Tk()

        # Step 3: Initialize application
        print("Initializing application...")
        logger.info("Initializing CloudToolsApp")
        app = CloudToolsApp(main_window)

        # Step 4: Show dependency report in console
        print("\nDependency Status:")
        report = get_dependency_report()
        for dep_name, dep_info in report.items():
            status = "AVAILABLE" if dep_info["status"] else "MISSING"
            print(f"  {dep_name}: {status}")
            logger.info("Dependency %s: %s", dep_name, status)

        print(f"\nApplication initialized successfully!")
        print(f"Available features: {', '.join(CloudToolsApp._get_available_features())}")
        print("Starting main event loop...\n")
        logger.info("Starting Tkinter main event loop")

        # Step 5: Start the main event loop
        main_window.mainloop()

    except KeyboardInterrupt:
        print("\nApplication interrupted by user.")
        logger.info("Application interrupted by user (KeyboardInterrupt)")
        sys.exit(0)

    except Exception as startup_error:
        error_msg = f"CRITICAL ERROR: {str(startup_error)}"
        print(f"\n{error_msg}")
        print(f"Traceback: {traceback.format_exc()}")
        logger.critical("Application startup failed: %s", str(startup_error))
        logger.debug("Startup error traceback: %s", traceback.format_exc())

        # Try to show error dialog if possible
        try:
            import tkinter as tkinter_module
            from tkinter import messagebox
            error_window = tkinter_module.Tk()
            error_window.withdraw()
            messagebox.showerror("Critical Error",
                                 f"Application startup failed:\n\n{str(startup_error)}\n\n"
                                 "Please check the console for detailed error information.")
            error_window.destroy()
        except Exception as dialog_error:
            logger.error("Failed to show error dialog: %s", str(dialog_error))

        sys.exit(1)


if __name__ == "__main__":
    main()
