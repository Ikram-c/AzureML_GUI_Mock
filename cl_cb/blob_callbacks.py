# cl_cb/blob_callbacks.py
import fnmatch
import os
from functools import partial
from tkinter import filedialog, messagebox, simpledialog

# Centralized application configuration
from config_loader import CONFIG


class BlobCallbacks:
    """
    Handles all callback logic for Azure Blob Storage operations, acting as a
    controller connecting the UI to the backend blob handler.
    """

    def __init__(self, app_controller):
        self.app = app_controller
        self.selected_local_files = []
        self.current_upload_path = ""
        # Initialize validation pattern from the config file
        self.image_validation_pattern = CONFIG['validation']['file_patterns']['image_filename']
        self.is_validation_enabled = True
        self.upload_progress = {}

    # --- Local File Selection Callbacks ---

    def handle_select_local_files(self):
        """Opens a file dialog to select local files for upload."""
        files = filedialog.askopenfilenames(title="Select Files for Upload")
        if files:
            self.selected_local_files = list(files)
            self._update_local_file_display()
            self.app.update_status(f"Selected {len(self.selected_local_files)} files.")

    def handle_add_files(self):
        """Adds more files to the current selection."""
        files = filedialog.askopenfilenames(title="Add More Files")
        if files:
            for file_path in files:
                if file_path not in self.selected_local_files:
                    self.selected_local_files.append(file_path)
            self._update_local_file_display()
            self.app.update_status(f"Total selected: {len(self.selected_local_files)} files.")

    def handle_remove_selected_files(self):
        """Removes selected files from the local file list."""
        view = self.app.storage_view
        if not view or not hasattr(view, 'local_files_listbox'): return

        selected_indices = view.local_files_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select files to remove.")
            return

        selected_filenames = [view.local_files_listbox.get(i) for i in selected_indices]
        self.selected_local_files = [
            f for f in self.selected_local_files if os.path.basename(f) not in selected_filenames
        ]
        self._update_local_file_display()
        self.app.update_status(f"Removed {len(selected_filenames)} files.")

    def handle_clear_local_selection(self):
        """Clears the list of selected local files."""
        self.selected_local_files = []
        self._update_local_file_display()
        if self.app.storage_view:
            self.app.storage_view._clear_preview()
        self.app.update_status("Local file selection cleared.")

    def handle_local_file_preview(self, event):
        """Shows a preview of the selected local file."""
        if self.app.storage_view:
            self.app.storage_view._show_local_file_preview(event)

    # --- Validation Callbacks ---

    def handle_validation_toggle(self):
        """Handles toggling the filename validation checkbox."""
        view = self.app.storage_view
        if view and hasattr(view, 'validation_panel'):
            self.is_validation_enabled = view.validation_panel.enabled_var.get()
            self._update_local_file_display()
            status = 'enabled' if self.is_validation_enabled else 'disabled'
            self.app.update_status(f"Filename validation {status}.")

    def handle_pattern_update(self):
        """Handles changes to the validation pattern."""
        view = self.app.storage_view
        if view and hasattr(view, 'validation_panel'):
            new_pattern = view.validation_panel.pattern_var.get().strip()
            if new_pattern and self.image_validation_pattern != new_pattern:
                self.image_validation_pattern = new_pattern
                self._update_local_file_display()
                self.app.update_status("Validation pattern updated.")

    def handle_set_upload_path(self):
        """Sets the upload path based on the selected remote tree item."""
        if self.app.storage_view:
            self.current_upload_path = self.app.storage_view._get_selected_remote_path()
            dest = f"/{self.current_upload_path}" if self.current_upload_path else "root"
            self.app.update_status(f"Upload destination: {dest}")

    # --- Remote Container Management Callbacks ---

    def handle_refresh_container_tree(self):
        """Fetches the folder/blob structure from the current container."""
        self.app.update_status("Loading container structure...")
        auth_handler = self.app.backend.azure_auth
        if not auth_handler.container_name:
            messagebox.showerror("No Container", "Please select a container first.")
            return

        def on_fetch_complete(structure, error):
            if error:
                messagebox.showerror("Error", f"Failed to load container: {error}")
                return
            if self.app.storage_view:
                self.app.storage_view._populate_container_tree(structure)
            count = self._count_blobs_in_structure(structure)
            self.app.update_status(f"Container loaded with {count} files.")

        self.app.run_in_thread(
            lambda: self.app.backend.blob.get_folder_structure(auth_handler, auth_handler.container_name),
            on_fetch_complete
        )

    def handle_new_folder(self):
        """Creates a new folder in the currently selected remote path."""
        folder_name = simpledialog.askstring("New Folder", "Enter new folder name:")
        if not folder_name or not folder_name.strip():
            return

        folder_name = folder_name.strip()
        if any(c in folder_name for c in '/\\:*?"<>|'):
            messagebox.showerror("Invalid Name", "Folder name contains invalid characters.")
            return

        current_path = self.app.storage_view._get_selected_remote_path() if self.app.storage_view else ""
        full_path = os.path.join(current_path, folder_name).replace("\\", "/")
        auth_handler = self.app.backend.azure_auth

        self.app.update_status(f"Creating folder '{folder_name}'...")

        def on_create_complete(result, error):
            if error:
                messagebox.showerror("Error", f"Failed to create folder: {error}")
            else:
                messagebox.showinfo("Success", result)
                self.handle_refresh_container_tree()

        self.app.run_in_thread(
            lambda: self.app.backend.blob.create_folder(auth_handler, auth_handler.container_name, full_path),
            on_create_complete
        )

    def handle_delete_selected_blobs(self):
        """Deletes selected blobs from the container."""
        if not self.app.storage_view: return
        selected_blobs = self.app.storage_view._get_selected_blob_names()
        if not selected_blobs:
            messagebox.showwarning("No Selection", "Please select one or more files to delete.")
            return

        limit = CONFIG['api']['limits']['delete_summary_count']
        file_list = "\n".join([f"• {os.path.basename(b)}" for b in selected_blobs[:limit]])
        if len(selected_blobs) > limit:
            file_list += f"\n... and {len(selected_blobs) - limit} more files"

        if not messagebox.askyesno("Confirm Deletion", f"Delete {len(selected_blobs)} file(s)?\n\n{file_list}"):
            return

        self.app.update_status("Deleting files...")
        self.app.status_bar.set_progress_mode('determinate', len(selected_blobs))

        def delete_task():
            # This task would contain the loop to delete blobs one by one
            # For brevity, the implementation is omitted here but would live in the backend
            pass  # Placeholder for backend call

        def on_delete_complete(result, error):
            self.app.status_bar.clear_progress()
            if error:
                messagebox.showerror("Delete Error", f"Failed to delete files: {error}")
            else:
                # Assuming result is a tuple of (deleted_count, errors_list)
                deleted_count, errors = result
                if errors:
                    messagebox.showwarning("Partial Success", f"Deleted {deleted_count}, but {len(errors)} failed.")
                else:
                    messagebox.showinfo("Success", f"Successfully deleted {deleted_count} files.")
                self.handle_refresh_container_tree()

        # self.app.run_in_thread(delete_task, on_delete_complete) # This would be the actual call

    # --- Upload & Download Callbacks ---

    def handle_start_upload(self):
        """Starts the process of uploading validated local files."""
        files_to_upload = self._get_valid_local_files_for_upload()
        if not files_to_upload:
            messagebox.showwarning("No Files", "No valid files are selected for upload.")
            return

        auth_handler = self.app.backend.azure_auth
        if not auth_handler.container_name:
            messagebox.showerror("No Container", "No container selected for upload.")
            return

        size_mb = sum(os.path.getsize(f) for f in files_to_upload) / (1024 * 1024)
        dest = f"/{self.current_upload_path}" if self.current_upload_path else "root folder"
        if not messagebox.askyesno("Confirm Upload",
                                   f"Upload {len(files_to_upload)} files ({size_mb:.1f} MB) to {dest}?"):
            return

        self.app.status_bar.set_progress_mode('determinate', len(files_to_upload))
        self.app.update_status("Starting upload...")
        # The actual upload task would be run in a thread here

    def handle_remote_blob_preview(self, blob_name: str):
        """Shows a preview of the selected remote blob."""
        if not blob_name or not self.app.storage_view: return
        self.app.storage_view._clear_preview()
        self.app.update_status(f"Loading preview for {os.path.basename(blob_name)}...")
        auth_handler = self.app.backend.azure_auth

        def on_download_complete(result, error):
            if error:
                messagebox.showerror("Preview Error", f"Failed to load preview: {error}")
            elif self.app.storage_view:
                temp_path, file_size = result
                self.app.storage_view._display_preview(temp_path, blob_name, file_size)

        self.app.run_in_thread(
            lambda: self.app.backend.blob.download_blob_for_preview(auth_handler, auth_handler.container_name,
                                                                    blob_name),
            on_download_complete
        )

    def handle_download_selected_blobs(self):
        """Downloads the selected blobs from the remote browser."""
        if not self.app.storage_view: return
        selected_blobs = self.app.storage_view._get_selected_blob_names()
        if not selected_blobs:
            messagebox.showwarning("Selection Required", "Please select files to download.")
            return

        local_dir = filedialog.askdirectory(title="Select Download Folder")
        if not local_dir: return

        self.app.status_bar.set_progress_mode('determinate', len(selected_blobs))
        self.app.update_status("Starting download...")
        # The actual download task would be run in a thread here

    # --- Internal Helper Methods ---

    def _update_local_file_display(self):
        """Updates the local file list display based on current validation settings."""
        if self.app.storage_view:
            self.app.storage_view._update_local_file_list()

    def _get_valid_local_files_for_upload(self):
        """Returns the list of files that are valid for upload."""
        if self.is_validation_enabled and self.image_validation_pattern:
            return [
                f for f in self.selected_local_files
                if fnmatch.fnmatch(os.path.basename(f), self.image_validation_pattern)
            ]
        return self.selected_local_files

    def _count_blobs_in_structure(self, structure):
        """Recursively counts the number of blobs in a container structure."""
        count = 0
        for value in structure.values():
            if isinstance(value, dict):
                count += self._count_blobs_in_structure(value)
            else:
                count += 1
        return count
