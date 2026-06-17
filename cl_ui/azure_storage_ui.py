# cl_ui/azure_storage_ui.py
import fnmatch
import os
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import Image, ImageTk

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Centralized application configuration
from config_loader import CONFIG


class ValidationPanel:
    """Container for validation panel tkinter variables."""

    def __init__(self, initial_pattern=""):
        self.enabled_var = tk.BooleanVar(value=True)
        self.pattern_var = tk.StringVar(value=initial_pattern)


class AzureStorageView(ttk.Frame):
    """
    A comprehensive UI view for managing Azure Blob Storage operations.
    """

    def __init__(self, parent, app_controller):
        super().__init__(parent, padding=10)
        self.pack(fill="both", expand=True)
        self.app = app_controller
        self.cb = self.app.blob_callbacks
        self.current_preview_path = None
        self.preview_temp_files = []

        self._setup_main_layout()
        self.cb.handle_refresh_container_tree()

    def _setup_main_layout(self):
        """Sets up the main layout with file management and preview panels."""
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)
        self._build_preview_panel()
        main_paned.add(self.preview_panel, weight=2)

        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill="both", expand=True)
        upload_tab = ttk.Frame(self.notebook)
        browse_tab = ttk.Frame(self.notebook)
        self.notebook.add(upload_tab, text="Upload")
        self.notebook.add(browse_tab, text="Browse")

        self._build_upload_tab(upload_tab)
        self._build_browse_tab(browse_tab)

    def _build_upload_tab(self, parent):
        """Builds the upload tab with local file selection and remote destination."""
        upload_paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        upload_paned.pack(fill="both", expand=True, pady=5)

        local_frame = ttk.LabelFrame(upload_paned, text="Local Files", padding=5)
        upload_paned.add(local_frame, weight=1)
        self._build_local_file_panel(local_frame)

        remote_frame = ttk.LabelFrame(upload_paned, text="Upload Destination", padding=5)
        upload_paned.add(remote_frame, weight=1)
        self._build_remote_explorer_panel(remote_frame, is_for_upload=True)

        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill="x", pady=5)
        self._build_upload_controls(controls_frame)

    def _build_browse_tab(self, parent):
        """Builds the browse tab for viewing and downloading files."""
        browser_frame = ttk.LabelFrame(parent, text="Container Contents", padding=5)
        browser_frame.pack(fill="both", expand=True, pady=5)
        self._build_remote_explorer_panel(browser_frame, is_for_upload=False)

        download_frame = ttk.Frame(parent)
        download_frame.pack(fill="x", pady=5)
        self._build_download_controls(download_frame)

    def _build_local_file_panel(self, parent):
        """Builds the panel for local file selection and management."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", pady=5)
        ttk.Button(button_frame, text="Select Files", command=self.cb.handle_select_local_files).pack(side="left",
                                                                                                      padx=2)
        ttk.Button(button_frame, text="Add More", command=self.cb.handle_add_files).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Remove", command=self.cb.handle_remove_selected_files).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Clear All", command=self.cb.handle_clear_local_selection).pack(side="left",
                                                                                                      padx=2)

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill="both", expand=True, pady=5)

        columns = ("Name", "Size", "Type", "Status")
        self.local_files_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        for col in columns: self.local_files_tree.heading(col, text=col)

        col_configs = CONFIG['ui']['treeview_columns']['local_files']
        self.local_files_tree.column("Name", width=col_configs['name_width'], anchor="w")
        self.local_files_tree.column("Size", width=col_configs['size_width'], anchor="e")
        self.local_files_tree.column("Type", width=col_configs['type_width'], anchor="center")
        self.local_files_tree.column("Status", width=col_configs['status_width'], anchor="center")

        v_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.local_files_tree.yview)
        self.local_files_tree.configure(yscrollcommand=v_scrollbar.set)
        self.local_files_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.local_files_tree.bind("<<TreeviewSelect>>", self.cb.handle_local_file_preview)
        self.local_files_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED)  # For compatibility
        self.local_summary_label = ttk.Label(parent, text="No files selected", foreground="gray")
        self.local_summary_label.pack(pady=2)

    def _build_remote_explorer_panel(self, parent, is_for_upload: bool):
        """Builds the panel for exploring remote blob container contents."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=5)
        ttk.Button(toolbar, text="Refresh", command=self.cb.handle_refresh_container_tree).pack(side="left", padx=2)
        if is_for_upload:
            ttk.Button(toolbar, text="New Folder", command=self.cb.handle_new_folder).pack(side="left", padx=2)
            self.upload_path_label = ttk.Label(toolbar, text="Upload to: /", foreground="blue")
            self.upload_path_label.pack(side="right", padx=5)

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, pady=5)

        tree = ttk.Treeview(tree_frame, selectmode="extended" if not is_for_upload else "browse")
        if is_for_upload:
            self.upload_remote_tree = tree
        else:
            self.browse_remote_tree = tree

        tree.heading("#0", text="Container Structure", anchor="w")
        v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=v_scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        if is_for_upload:
            tree.bind('<<TreeviewSelect>>', lambda e: self._on_upload_tree_select())
        else:
            tree.bind('<<TreeviewSelect>>', lambda e: self._on_browse_tree_select())

    def _build_upload_controls(self, parent):
        """Builds the upload control panel."""
        validation_frame = ttk.LabelFrame(parent, text="File Validation", padding=5)
        validation_frame.pack(fill="x", pady=2)
        self.validation_panel = ValidationPanel(self.cb.image_validation_pattern)

        val_control_frame = ttk.Frame(validation_frame)
        val_control_frame.pack(fill="x")
        val_control_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(val_control_frame, text="Enable filename validation",
                        variable=self.validation_panel.enabled_var,
                        command=self.cb.handle_validation_toggle).grid(row=0, column=0, sticky="w")
        pattern_entry = ttk.Entry(val_control_frame, textvariable=self.validation_panel.pattern_var)
        pattern_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5)
        pattern_entry.bind("<KeyRelease>", lambda e: self.cb.handle_pattern_update())

        upload_button_frame = ttk.Frame(parent)
        upload_button_frame.pack(fill="x", pady=5)
        self.upload_button = ttk.Button(upload_button_frame, text="Upload Files", command=self.cb.handle_start_upload)
        self.upload_button.pack(side="left", padx=5)
        self.upload_summary_label = ttk.Label(parent, text="", justify="left")
        self.upload_summary_label.pack(fill="x", pady=2)

    def _build_download_controls(self, parent):
        """Builds the download control panel."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x")
        self.download_button = ttk.Button(button_frame, text="Download Selected",
                                          command=self.cb.handle_download_selected_blobs)
        self.download_button.pack(side="left", padx=5)
        ttk.Button(button_frame, text="Preview Selected", command=self._preview_selected).pack(side="left", padx=5)
        self.selection_info_label = ttk.Label(parent, text="No files selected", foreground="gray")
        self.selection_info_label.pack(pady=2)

    def _build_preview_panel(self):
        """Builds the preview panel for displaying file previews."""
        self.preview_panel = ttk.LabelFrame(self, text="Preview", padding=5)
        self.preview_panel.columnconfigure(0, weight=1)
        self.preview_panel.rowconfigure(0, weight=1)
        self.preview_label = ttk.Label(self.preview_panel, anchor="center", text="Select a file to preview")
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        self.preview_info_label = ttk.Label(self.preview_panel, text="", justify="center", foreground="gray")
        self.preview_info_label.grid(row=1, column=0, sticky="ew")

    def _on_upload_tree_select(self):
        self.cb.handle_set_upload_path()
        path = self.cb.current_upload_path
        display_path = f"Upload to: /{path}" if path else "Upload to: / (root)"
        self.upload_path_label.config(text=display_path)

    def _on_browse_tree_select(self):
        selected_blob = self._get_selected_remote_blob_name()
        if selected_blob:
            self.cb.handle_remote_blob_preview(selected_blob)
        self._update_selection_info()

    def _get_selected_remote_blob_name(self):
        """Gets the full path of the selected blob in the browse tree."""
        tree = self.browse_remote_tree
        selection = tree.selection()
        if not selection: return None
        item = tree.item(selection[0])
        if 'file' not in item['tags']: return None

        path_parts = [item['text'].split(' ')[0]]
        parent_id = tree.parent(selection[0])
        while parent_id:
            parent_item = tree.item(parent_id)
            path_parts.insert(0, parent_item['text'].replace('[Folder] ', ''))
            parent_id = tree.parent(parent_id)
        return "/".join(path_parts)

    def _get_selected_remote_path(self):
        """Gets the path of the selected folder for uploads."""
        tree = self.upload_remote_tree
        selection = tree.selection()
        if not selection: return ""

        path_parts = []
        item_id = selection[0]
        while item_id:
            item = tree.item(item_id)
            path_parts.insert(0, item['text'].replace('[Folder] ', ''))
            item_id = tree.parent(item_id)
        return "/".join(path_parts)

    def _update_local_file_list(self):
        """Updates the local file list display."""
        self.local_files_tree.delete(*self.local_files_tree.get_children())
        self.local_files_listbox.delete(0, tk.END)

        valid_files = self.cb._get_valid_local_files_for_upload()
        total_size = 0
        for file_path in self.cb.selected_local_files:
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            total_size += file_size
            status = "Valid" if file_path in valid_files else "Invalid"
            size_str = self._format_file_size(file_size)
            self.local_files_tree.insert("", "end", values=(filename, size_str, "File", status))
            self.local_files_listbox.insert(tk.END, filename)

        summary = f"{len(self.cb.selected_local_files)} files selected, {len(valid_files)} valid"
        self.local_summary_label.config(text=summary)

    def _populate_container_tree(self, structure: dict):
        """Populates the container tree views with the given structure."""

        def _populate(tree):
            tree.delete(*tree.get_children())

            def _add_nodes(parent, substructure):
                for key, value in sorted(substructure.items()):
                    if isinstance(value, dict):
                        node = tree.insert(parent, "end", text=f"[Folder] {key}", open=False, tags=('folder',))
                        _add_nodes(node, value)
                    else:
                        tree.insert(parent, "end", text=f"{key} ({self._format_file_size(value)})", tags=('file',))

            _add_nodes("", structure)

        if hasattr(self, 'upload_remote_tree'): _populate(self.upload_remote_tree)
        if hasattr(self, 'browse_remote_tree'): _populate(self.browse_remote_tree)

    def _display_preview(self, path: str, name_for_text: str, file_size: int):
        """Displays a preview of the given file."""
        self.current_preview_path = path
        filename = os.path.basename(name_for_text)
        self.preview_info_label.config(text=f"{filename} ({self._format_file_size(file_size)})")

        if PIL_AVAILABLE and self._is_image_file(path):
            self._display_image_preview(path)
            return

        preview_text = f"No preview available for {filename}."
        max_bytes = CONFIG['api']['limits']['text_preview_bytes']
        if self._is_text_file(path) and file_size < max_bytes:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(CONFIG['api']['limits']['text_preview_chars'])
                    preview_text = f"Preview:\n\n{content}"
                    if len(content) < file_size:
                        preview_text += "\n\n... (truncated)"
            except Exception:
                pass
        self.preview_label.config(image="", text=preview_text)

    def _display_image_preview(self, path):
        """Displays an image preview using PIL."""
        try:
            with Image.open(path) as img:
                self.preview_panel.update_idletasks()
                w, h = self.preview_panel.winfo_width(), self.preview_panel.winfo_height()
                if w > 1 and h > 1:
                    img.thumbnail((w, h), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.preview_label.config(image=photo, text="")
                    self.preview_label.image = photo
        except Exception as e:
            self.preview_label.config(image="", text=f"Image Preview Error:\n{e}")

    def _clear_preview(self):
        self.preview_label.config(image="", text="Select a file to preview")
        self.preview_info_label.config(text="")
        self.current_preview_path = None

    def _format_file_size(self, size_bytes):
        if size_bytes < 1024: return f"{size_bytes} B"
        if size_bytes < 1024 ** 2: return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024 ** 3: return f"{size_bytes / 1024 ** 2:.1f} MB"
        return f"{size_bytes / 1024 ** 3:.1f} GB"

    def _is_image_file(self, path):
        return os.path.splitext(path)[1].lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']

    def _is_text_file(self, path):
        return os.path.splitext(path)[1].lower() in ['.txt', '.csv', '.json', '.xml', '.log']

    def _preview_selected(self):
        """Previews the first selected file in the browse tab."""
        selected = self._get_selected_blob_names()
        if selected:
            self.cb.handle_remote_blob_preview(selected[0])

    def __del__(self):
        """Cleans up temporary files when the view is destroyed."""
        for temp_file in self.preview_temp_files:
            try:
                if os.path.exists(temp_file): os.remove(temp_file)
            except Exception:
                pass
