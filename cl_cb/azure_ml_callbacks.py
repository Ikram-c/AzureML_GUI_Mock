# cl_cb/azure_ml_callbacks.py
import os
from functools import partial
from tkinter import messagebox, filedialog


class AzureMLCallbacks:
    """
    Handles callback logic for the AzureMLView, acting as a controller
    that connects the UI to the backend AzureMLHandler.
    """

    def __init__(self, app_controller):
        """
        Initializes the callbacks handler.

        Args:
            app_controller: The main application instance, which holds references
                            to the UI views and backend handlers.
        """
        self.app = app_controller
        # Store fetched resources to avoid re-fetching - initialize as empty lists
        self.subscriptions = []
        self.workspaces = []

    # --- Connection Flow Callbacks ---

    def handle_load_subscriptions(self):
        """Fetches Azure subscriptions to populate the connect panel."""
        self.app.update_status("Fetching subscriptions...")

        auth_handler = self.app.backend.azure_auth
        if not auth_handler.credential:
            messagebox.showerror("Auth Error", "You must be signed in to an Azure account.")
            return

        def on_fetch_complete(subs, error):
            # Get current view reference when callback is executed
            current_view = self.app.ml_view
            if not current_view:
                # View has been cleared/changed, ignore this callback
                self.app.update_status("ML view no longer available.")
                return

            if error:
                messagebox.showerror("Azure Error", f"Failed to fetch subscriptions: {error}")
                # Clear subscriptions and populate with empty list
                self.subscriptions = []
                current_view._populate_subscriptions([])
                return

            # Validate subscription data format
            if not isinstance(subs, list):
                messagebox.showerror("Data Error", "Invalid subscription data format received from Azure.")
                self.subscriptions = []
                current_view._populate_subscriptions([])
                return

            # Store subscriptions and validate each one
            self.subscriptions = []
            valid_subs = []

            for sub in subs:
                if isinstance(sub, dict) and 'id' in sub and 'name' in sub:
                    self.subscriptions.append(sub)
                    valid_subs.append(sub)
                else:
                    print(f"Warning: Skipping invalid subscription data: {sub}")

            if not valid_subs:
                messagebox.showwarning("No Subscriptions", "No valid Azure subscriptions found.")
                current_view._populate_subscriptions([])
                self.app.update_status("No valid subscriptions available.")
            else:
                current_view._populate_subscriptions(valid_subs)
                self.app.update_status(f"Loaded {len(valid_subs)} subscription(s). Please select one.")

        self.app.run_in_thread(
            lambda: self.app.backend.ml.get_subscriptions(auth_handler.credential),
            on_fetch_complete
        )

    def handle_refresh_subscriptions(self):
        """Refresh the subscription list."""
        # Clear existing data
        self.subscriptions = []
        self.workspaces = []

        # Reload subscriptions
        self.handle_load_subscriptions()

    def handle_subscription_selected(self, event=None):
        """Fetches resource groups for the selected subscription."""
        view = self.app.ml_view
        if not view:
            self.app.update_status("ML view not available for subscription selection.")
            return

        selected_index = view.connect_panel.sub_combo.current()
        if selected_index < 0:
            return

        # Validate that we have subscription data
        if not self.subscriptions:
            self.app.show_error("No subscription data available. Please refresh subscriptions.")
            return

        if selected_index >= len(self.subscriptions):
            self.app.show_error(f"Invalid subscription selection. Please refresh subscriptions.")
            return

        # Reset dependent dropdowns
        view._reset_rg_and_ws_combos()

        try:
            subscription = self.subscriptions[selected_index]
            if not isinstance(subscription, dict) or 'id' not in subscription:
                self.app.show_error("Invalid subscription data format. Please refresh subscriptions.")
                return

            sub_id = subscription['id']
            sub_name = subscription.get('name', 'Unknown')

        except (KeyError, TypeError) as e:
            self.app.show_error(f"Error accessing subscription data: {str(e)}. Please refresh subscriptions.")
            return

        self.app.update_status(f"Fetching resource groups for '{sub_name}'...")
        auth_handler = self.app.backend.azure_auth

        def on_fetch_complete(groups, error):
            # Check if view still exists when callback is called
            current_view = self.app.ml_view
            if not current_view:
                self.app.update_status("ML view no longer available.")
                return

            if error:
                messagebox.showerror("Azure Error", f"Failed to fetch resource groups: {error}")
                return
            current_view._populate_resource_groups(groups)
            self.app.update_status("Resource groups loaded. Please select one.")

        self.app.run_in_thread(
            lambda: self.app.backend.ml.get_resource_groups(auth_handler.credential, sub_id),
            on_fetch_complete
        )

    def handle_rg_selected(self, event=None):
        """Fetches ML workspaces for the selected resource group."""
        view = self.app.ml_view
        if not view:
            self.app.update_status("ML view not available for resource group selection.")
            return

        sub_index = view.connect_panel.sub_combo.current()
        rg_name = view.connect_panel.rg_combo.get()

        if sub_index < 0 or not rg_name or "Select" in rg_name:
            return

        # Validate subscription data
        if not self.subscriptions or sub_index >= len(self.subscriptions):
            self.app.show_error("Invalid subscription selection. Please refresh subscriptions.")
            return

        view._reset_ws_combo()

        try:
            subscription = self.subscriptions[sub_index]
            if not isinstance(subscription, dict) or 'id' not in subscription:
                self.app.show_error("Invalid subscription data format. Please refresh subscriptions.")
                return

            sub_id = subscription['id']

        except (KeyError, TypeError, IndexError) as e:
            self.app.show_error(f"Error accessing subscription data: {str(e)}. Please refresh subscriptions.")
            return

        self.app.update_status(f"Fetching workspaces in '{rg_name}'...")
        auth_handler = self.app.backend.azure_auth

        def on_fetch_complete(workspaces, error):
            # Check if view still exists when callback is called
            current_view = self.app.ml_view
            if not current_view:
                self.app.update_status("ML view no longer available.")
                return

            if error:
                messagebox.showerror("Azure Error", f"Failed to fetch ML workspaces: {error}")
                return
            self.workspaces = workspaces
            current_view._populate_workspaces(workspaces)
            self.app.update_status("Workspaces loaded. Please select one to connect.")

        self.app.run_in_thread(
            lambda: self.app.backend.ml.get_workspaces(auth_handler.credential, sub_id, rg_name),
            on_fetch_complete
        )

    def handle_connect_to_workspace(self):
        """Connects the MLClient to the selected workspace."""
        view = self.app.ml_view
        if not view:
            self.app.show_error("ML view not available for workspace connection.")
            return

        # Get selections from the UI
        sub_index = view.connect_panel.sub_combo.current()
        rg_name = view.connect_panel.rg_combo.get()
        ws_name = view.connect_panel.ws_combo.get()

        if sub_index < 0 or not rg_name or "Select" in rg_name or not ws_name or "Select" in ws_name:
            messagebox.showerror("Selection Error",
                                 "Please select a valid subscription, resource group, and workspace.")
            return

        # Validate subscription data
        if not self.subscriptions or sub_index >= len(self.subscriptions):
            messagebox.showerror("Selection Error", "Invalid subscription selection. Please refresh subscriptions.")
            return

        try:
            subscription = self.subscriptions[sub_index]
            if not isinstance(subscription, dict) or 'id' not in subscription:
                messagebox.showerror("Data Error", "Invalid subscription data format. Please refresh subscriptions.")
                return

            sub_id = subscription['id']

        except (KeyError, TypeError, IndexError) as e:
            messagebox.showerror("Data Error",
                                 f"Error accessing subscription data: {str(e)}. Please refresh subscriptions.")
            return

        self.app.update_status(f"Connecting to workspace '{ws_name}'...")
        auth_handler = self.app.backend.azure_auth

        def on_connect_complete(result, error):
            # Check if view still exists when callback is called
            current_view = self.app.ml_view
            if not current_view:
                self.app.update_status("ML view no longer available.")
                return

            if error:
                messagebox.showerror("Connection Failed", str(error))
                self.app.update_status("Connection failed.", "red")
            else:
                self.app.update_status(result, "green")
                # This tells the view to reveal the operational tabs
                current_view._on_successful_connect()

        self.app.run_in_thread(
            lambda: self.app.backend.ml.connect_to_workspace(auth_handler.credential, sub_id, rg_name, ws_name),
            on_connect_complete
        )

    # --- Resource Listing Callbacks ---

    def handle_refresh_computes(self):
        """Fetches and displays compute targets from the connected workspace."""
        view = self.app.ml_view
        if not view:
            self.app.update_status("ML view not available for compute refresh.")
            return

        self.app.update_status("Fetching compute targets...")
        view._clear_tree(view.compute_tree)
        view.compute_tree.insert("", "end", values=("Loading...", "", "", ""))

        def on_fetch_complete(computes, error):
            # Check if view still exists when callback is called
            current_view = self.app.ml_view
            if not current_view:
                self.app.update_status("ML view no longer available.")
                return

            current_view._clear_tree(current_view.compute_tree)
            if error:
                messagebox.showerror("Azure Error", f"Failed to list compute targets: {error}")
                current_view.compute_tree.insert("", "end", values=("Error", str(error), "", ""))
                return
            current_view._populate_compute_tree(computes)
            self.app.update_status("Compute targets loaded.")

        self.app.run_in_thread(self.app.backend.ml.list_computes, on_fetch_complete)

    def handle_refresh_models(self):
        """Fetches and displays registered models from the connected workspace."""
        view = self.app.ml_view
        if not view:
            self.app.update_status("ML view not available for model refresh.")
            return

        self.app.update_status("Fetching registered models...")
        view._clear_tree(view.model_tree)
        view.model_tree.insert("", "end", values=("Loading...", "", ""))

        def on_fetch_complete(models, error):
            # Check if view still exists when callback is called
            current_view = self.app.ml_view
            if not current_view:
                self.app.update_status("ML view no longer available.")
                return

            current_view._clear_tree(current_view.model_tree)
            if error:
                messagebox.showerror("Azure Error", f"Failed to list models: {error}")
                current_view.model_tree.insert("", "end", values=("Error", str(error), ""))
                return
            current_view._populate_model_tree(models)
            self.app.update_status("Registered models loaded.")

        self.app.run_in_thread(self.app.backend.ml.list_models, on_fetch_complete)

    # --- Job Submission Callbacks ---

    def handle_select_code_path(self):
        """Opens a dialog to select the code directory or zip file for a job."""
        view = self.app.ml_view
        if not view:
            self.app.show_error("ML view not available for code path selection.")
            return

        code_type = view.job_panel_vars['code_type'].get()

        initial_dir = os.path.abspath("project_repo") if os.path.isdir("project_repo") else None

        path = ""
        if code_type == "directory":
            path = filedialog.askdirectory(title="Select Code Directory", initialdir=initial_dir)
        else:  # zip
            path = filedialog.askopenfilename(
                title="Select Code Archive",
                initialdir=initial_dir,
                filetypes=[("ZIP files", "*.zip")]
            )

        if path:
            view.job_panel_vars['full_code_path'] = path
            view.job_panel_vars['code_path'].set(os.path.basename(path))

    def handle_select_conda_file(self):
        """Opens a dialog to select the Conda environment file."""
        view = self.app.ml_view
        if not view:
            self.app.show_error("ML view not available for Conda file selection.")
            return

        initial_dir = view.job_panel_vars.get('full_code_path', None)
        if not initial_dir:
            initial_dir = os.path.abspath("project_repo") if os.path.isdir("project_repo") else os.path.expanduser("~")

        path = filedialog.askopenfilename(
            title="Select Conda Environment File",
            initialdir=initial_dir,
            filetypes=[("YAML files", "*.yml"), ("All files", "*.*")]
        )

        if path:
            view.job_panel_vars['conda_file_path'].set(path)

    def handle_submit_job(self):
        """Gathers job configuration from the UI and submits it to the backend."""
        view = self.app.ml_view
        if not view:
            self.app.show_error("ML view not available for job submission.")
            return

        # Gather all parameters from the UI widgets
        try:
            job_name = view.job_name_entry.get().strip()
            command = view.entry_script_entry.get().strip()
            compute = view.compute_combo.get()
            code_path = view.job_panel_vars['full_code_path']
            env_option = view.job_panel_vars['env_option'].get()

            if not all([job_name, command, code_path]) or "Select" in compute or not compute:
                raise ValueError("Please complete all fields: Job Name, Command, Compute Target, and Code Path.")

            env_details = {}
            if env_option == 'conda':
                env_details['conda_file'] = view.job_panel_vars['conda_file_path'].get().strip()
                if not env_details['conda_file']:
                    raise ValueError("Conda file path cannot be empty.")
            elif env_option == 'docker':
                env_details['docker_image'] = view.docker_image_entry.get().strip()
                if not env_details['docker_image']:
                    raise ValueError("Docker image cannot be empty.")

        except (AttributeError, ValueError) as e:
            messagebox.showerror("Input Error", str(e))
            return

        self.app.update_status(f"Submitting job '{job_name}'...")
        view._set_submit_button_state("disabled")

        # Create a partial to pass all arguments to the thread
        task = partial(
            self.app.backend.ml.submit_job,
            job_name=job_name,
            code_path=code_path,
            compute_target=compute,
            command=command,
            environment_details=env_details
        )

        def on_submit_complete(job, error):
            # Check if view still exists when callback is called
            current_view = self.app.ml_view
            if current_view:
                current_view._set_submit_button_state("normal")
            else:
                self.app.update_status("ML view no longer available.")

            if error:
                messagebox.showerror("Job Submission Failed", str(error))
                self.app.update_status("Job submission failed.", "red")
            else:
                messagebox.showinfo("Submission Successful",
                                    f"Job '{job.display_name}' submitted.\n"
                                    f"Studio URL: {job.studio_url}")
                self.app.update_status(f"Job '{job.name}' created.", "green")

        self.app.run_in_thread(task, on_submit_complete)