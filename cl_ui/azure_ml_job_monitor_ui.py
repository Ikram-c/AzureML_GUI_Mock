# cl_ui/azure_ml_job_monitor_ui.py
import os
import tkinter as tk
from tkinter import ttk, scrolledtext

from PIL import Image, ImageTk

# Centralized application configuration
from config_loader import CONFIG


class JobMonitorView(ttk.Frame):
    """
    A UI view for listing Azure ML jobs and viewing their details, outputs, and logs.
    """

    def __init__(self, parent, app_controller):
        super().__init__(parent, padding=10)
        self.pack(fill="both", expand=True)
        self.app = app_controller
        cb = self.app.job_monitor_callbacks

        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.LabelFrame(main_pane, text="Recent Jobs", padding=10)
        main_pane.add(list_frame, weight=1)
        self._build_job_list_panel(list_frame, cb)

        notebook_frame = ttk.Frame(main_pane)
        main_pane.add(notebook_frame, weight=3)
        self._build_details_notebook(notebook_frame, cb)

        cb.handle_load_job_list()

    def _build_job_list_panel(self, parent, cb):
        """Builds the panel for listing and filtering jobs."""
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        columns = ("Name", "Status", "Created")
        self.job_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        self.job_tree.heading("Name", text="Name")
        self.job_tree.heading("Status", text="Status")
        self.job_tree.heading("Created", text="Created")

        # Use column widths from config
        column_configs = CONFIG['ui']['treeview_columns']['job_monitor']
        self.job_tree.column("Name", width=column_configs['name_width'], anchor="w")
        self.job_tree.column("Status", width=column_configs['status_width'], anchor="w")
        self.job_tree.column("Created", width=column_configs['created_width'], anchor="w")

        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.job_tree.yview)
        self.job_tree.configure(yscrollcommand=scrollbar.set)
        self.job_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.job_tree.bind("<<TreeviewSelect>>", cb.handle_job_selection)

        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        controls_frame.columnconfigure(1, weight=1)

        self.filter_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            controls_frame, text="Show only my jobs", variable=self.filter_var,
            command=cb.handle_load_job_list
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            controls_frame, text="Refresh List", command=cb.handle_load_job_list
        ).grid(row=0, column=1, sticky="e")

    def _build_details_notebook(self, parent, cb):
        """Builds the tabbed interface for job details, logs, and outputs."""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True, padx=(10, 0))

        details_tab = ttk.Frame(notebook, padding=10)
        outputs_tab = ttk.Frame(notebook, padding=10)
        logs_tab = ttk.Frame(notebook, padding=10)

        notebook.add(details_tab, text="Details")
        notebook.add(outputs_tab, text="Outputs & Preview")
        notebook.add(logs_tab, text="Logs")

        self.details_text = tk.Text(details_tab, wrap=tk.WORD, state=tk.DISABLED)
        self.details_text.pack(fill=tk.BOTH, expand=True)

        self.logs_text = scrolledtext.ScrolledText(
            logs_tab, wrap=tk.WORD, state=tk.DISABLED, background="#2d2d2d", foreground="#cccccc"
        )
        self.logs_text.pack(fill=tk.BOTH, expand=True)

        self._build_outputs_panel(outputs_tab, cb)

    def _build_outputs_panel(self, parent, cb):
        """Builds the panel for viewing job outputs and their previews."""
        output_pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        output_pane.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.LabelFrame(output_pane, text="Output Files", padding=5)
        output_pane.add(list_frame, weight=1)

        preview_frame = ttk.LabelFrame(output_pane, text="Preview", padding=5)
        output_pane.add(preview_frame, weight=2)

        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.outputs_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE)
        self.outputs_listbox.grid(row=0, column=0, sticky="nsew")
        output_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.outputs_listbox.yview)
        output_scrollbar.grid(row=0, column=1, sticky="ns")
        self.outputs_listbox.config(yscrollcommand=output_scrollbar.set)
        self.outputs_listbox.bind("<<ListboxSelect>>", cb.handle_output_selection)

        self.preview_label = ttk.Label(preview_frame, anchor="center")
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        self.open_in_browser_button = ttk.Button(
            preview_frame, text="Open in Browser", state=tk.DISABLED, command=cb.handle_open_in_browser
        )
        self.open_in_browser_button.pack(pady=5)

    def _clear_job_tree(self):
        self.job_tree.delete(*self.job_tree.get_children())

    def _populate_job_tree(self, jobs):
        if not jobs:
            self.job_tree.insert("", "end", values=("No jobs found.", "", ""))
            return
        sorted_jobs = sorted(jobs, key=lambda j: j.creation_context.created_at, reverse=True)
        for job in sorted_jobs:
            self.job_tree.insert("", "end", values=(
                job.name,
                job.status,
                job.creation_context.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ))

    def _get_selected_job_name(self):
        selection = self.job_tree.selection()
        return self.job_tree.item(selection[0], "values")[0] if selection else None

    def _clear_all_details(self):
        """Clears all detail panels when a new job is selected."""
        self._display_details("")
        self._display_logs("")
        self.outputs_listbox.delete(0, tk.END)
        self._clear_output_preview()

    def _display_details(self, details):
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        if isinstance(details, str):
            self.details_text.insert(tk.END, details)
        else:
            detail_str = (
                f"Name: {details.name}\n"
                f"Status: {details.status}\n"
                f"Compute: {details.compute}\n"
                f"Experiment: {details.experiment_name}\n"
                f"Created: {details.creation_context.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.details_text.insert(tk.END, detail_str)
        self.details_text.config(state=tk.DISABLED)

    def _display_logs(self, logs):
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.delete(1.0, tk.END)
        self.logs_text.insert(tk.END, logs)
        self.logs_text.config(state=tk.DISABLED)

    def _populate_outputs_list(self, output_files):
        if not output_files:
            self.outputs_listbox.insert(tk.END, "No output files found.")
        else:
            for file_path in sorted(output_files):
                self.outputs_listbox.insert(tk.END, file_path)

    def _get_selected_output_file(self):
        selection = self.outputs_listbox.curselection()
        return self.outputs_listbox.get(selection[0]) if selection else None

    def _clear_output_preview(self):
        self.preview_label.config(image='', text="")
        self.preview_label.image = None
        self.open_in_browser_button.config(state=tk.DISABLED)

    def _display_output_preview(self, full_path, error_message=None):
        self._clear_output_preview()
        if error_message:
            self.preview_label.config(text=error_message)
            return

        _, extension = os.path.splitext(full_path)
        delay = CONFIG['ui']['timings']['image_render_delay_ms']

        if extension.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
            self.after(delay, lambda: self._render_image_preview(full_path))
        elif extension.lower() == '.html':
            self.preview_label.config(text=f"HTML File:\n{os.path.basename(full_path)}\n\nClick button to open.")
            self.open_in_browser_button.config(state=tk.NORMAL)
        else:
            self.preview_label.config(text="No preview available for this file type.")

    def _render_image_preview(self, path):
        """Renders an image, ensuring the panel is visible first."""
        try:
            with Image.open(path) as img:
                ph = self.preview_label.winfo_height()
                pw = self.preview_label.winfo_width()
                padding = CONFIG['ui']['dimensions']['image_preview_padding']
                delay = CONFIG['ui']['timings']['image_render_delay_ms']

                if pw > padding and ph > padding:
                    img.thumbnail((pw - padding, ph - padding), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.preview_label.config(image=photo)
                    self.preview_label.image = photo
                else:
                    self.after(delay, lambda: self._render_image_preview(path))
        except Exception as e:
            self.preview_label.config(text=f"Error rendering image:\n{e}")
