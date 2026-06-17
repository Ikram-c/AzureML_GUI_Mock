# cl_cb/azure_ml_job_monitor_callbacks.py
import os
import tkinter as tk
import webbrowser
from tkinter import messagebox


class JobMonitorCallbacks:
    """
    Handles callback logic for the JobMonitorView, acting as a controller
    that connects the UI to the backend AzureMLHandler for monitoring jobs.
    """

    def __init__(self, app_controller):
        """
        Initializes the callbacks handler.

        Args:
            app_controller: The main application instance.
        """
        self.app = app_controller
        self.output_temp_dir = None
        self.selected_output_file_path = None

    # --- Job List Callbacks ---

    def handle_load_job_list(self):
        """
        Fetches the list of recent jobs and populates the treeview,
        respecting the user filter.
        """
        view = self.app.job_monitor_view
        if not view: return

        self.app.update_status("Fetching recent jobs...")
        view._clear_job_tree()
        view._insert_loading_message_in_tree("Loading jobs...")

        should_filter = view.filter_var.get()

        def on_fetch_complete(jobs, error):
            view._clear_tree(view.job_tree)
            if error:
                messagebox.showerror("Azure Error", f"Failed to list jobs: {error}")
                view._insert_error_in_tree(str(error))
            else:
                view._populate_job_tree(jobs)
            self.app.update_status("Job list updated.")

        self.app.run_in_thread(
            lambda: self.app.backend.ml.list_jobs(filter_by_user=should_filter),
            on_fetch_complete
        )

    def handle_job_selection(self, event=None):
        """
        Fetches and displays details for a selected job. This is the primary
        orchestrator when a user clicks a job in the list.
        """
        view = self.app.job_monitor_view
        job_name = view._get_selected_job_name()

        if not job_name:
            return

        # Clear all detail panels
        view._clear_all_details()

        # --- Fetch Details, Logs, and Outputs Concurrently ---
        self._fetch_job_details(job_name)
        self._fetch_job_logs(job_name)
        self._fetch_job_outputs(job_name)

    # --- Job Detail Fetching Methods ---

    def _fetch_job_details(self, job_name: str):
        """Fetches and displays the main properties of a job."""
        view = self.app.job_monitor_view
        self.app.update_status(f"Fetching details for {job_name}...")
        view._display_details("Loading details...")

        def on_fetch_complete(details, error):
            if error:
                view._display_details(f"Error fetching details: {error}")
            else:
                view._display_details(details)
            self.app.update_status("Details loaded.")

        self.app.run_in_thread(
            lambda: self.app.backend.ml.get_job_details(job_name),
            on_fetch_complete
        )

    def _fetch_job_logs(self, job_name: str):
        """Fetches and displays the std_log.txt for a job."""
        view = self.app.job_monitor_view
        self.app.update_status(f"Fetching logs for {job_name}...")
        view._display_logs("Loading logs...")

        def on_fetch_complete(logs, error):
            if error:
                view._display_logs(f"Error fetching logs: {error}")
            else:
                view._display_logs(logs)
            self.app.update_status("Logs loaded.")

        self.app.run_in_thread(
            lambda: self.app.backend.ml.get_job_logs(job_name),
            on_fetch_complete
        )

    def _fetch_job_outputs(self, job_name: str):
        """Downloads and lists the output files for the selected job."""
        view = self.app.job_monitor_view
        self.app.update_status(f"Fetching outputs for {job_name}...")
        view._clear_outputs_list()
        view.outputs_listbox.insert(tk.END, "Loading outputs...")

        def on_download_complete(result, error):
            view._clear_outputs_list()
            if error:
                messagebox.showerror("Output Error", f"Failed to get job outputs: {error}")
                view.outputs_listbox.insert(tk.END, "Error loading outputs.")
                return

            output_files, temp_dir = result
            self.output_temp_dir = temp_dir  # Store temp dir for previewing
            view._populate_outputs_list(output_files)

        self.app.run_in_thread(
            lambda: self.app.backend.ml.download_job_outputs(job_name),
            on_download_complete
        )

    # --- Output Preview Callback ---

    def handle_output_selection(self, event=None):
        """
        Displays a preview of the selected output file.
        """
        view = self.app.job_monitor_view
        selected_file_rel_path = view._get_selected_output_file()

        if not selected_file_rel_path or not self.output_temp_dir:
            return

        # Construct the full local path to the temporary file
        full_path = os.path.join(self.output_temp_dir, selected_file_rel_path)
        self.selected_output_file_path = full_path

        if not os.path.exists(full_path):
            view._display_output_preview(None, "Output file not found locally.")
            return

        view._display_output_preview(full_path)

    def handle_open_in_browser(self):
        """Opens the selected HTML output file in the default web browser."""
        if self.selected_output_file_path and self.selected_output_file_path.lower().endswith('.html'):
            # Use os.path.realpath to get the canonical path
            webbrowser.open(f"file://{os.path.realpath(self.selected_output_file_path)}")
        else:
            messagebox.showwarning("No File", "No HTML file is selected for preview.")
