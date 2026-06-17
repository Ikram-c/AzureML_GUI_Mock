# cl_ui/azure_ml_ui.py
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from config_loader import CONFIG


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
        self.entry_script_entry.insert(0, f"python {CONFIG['project_details']['Project_Execution_Command']}")

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