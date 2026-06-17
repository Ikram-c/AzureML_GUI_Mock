# cloud_utils/zoomcontroller.py
import platform
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

class ZoomController:
    """
    App-wide UI scaling with sensible monitor-based defaults.
    Uses `tk scaling`, refreshes default fonts, and adjusts common ttk paddings.
    """
    MIN_SCALE = 0.75
    MAX_SCALE = 2.0
    STEP = 0.05

    def __init__(self, root: tk.Tk):
        self.root = root
        self.style = ttk.Style(root)
        self._scale = self._detect_initial_scale()
        self._apply_scale(self._scale)

    @property
    def scale(self) -> float:
        return self._scale

    def set_scale(self, value: float):
        value = max(self.MIN_SCALE, min(self.MAX_SCALE, float(value)))
        if abs(value - self._scale) >= 1e-4:
            self._scale = value
            self._apply_scale(value)

    def zoom_in(self): self.set_scale(self._scale + self.STEP)
    def zoom_out(self): self.set_scale(self._scale - self.STEP)
    def reset(self):    self.set_scale(1.0)

    # --- internals ---
    def _detect_initial_scale(self) -> float:
        # Prefer screeninfo when available
        try:
            from screeninfo import get_monitors
            self.root.update_idletasks()
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width() or 1, self.root.winfo_height() or 1
            cx, cy = rx + rw // 2, ry + rh // 2

            def contains(m, x, y): return m.x <= x < m.x + m.width and m.y <= y < m.y + m.height
            mons = get_monitors()
            mon = next((m for m in mons if contains(m, cx, cy)), mons[0] if mons else None)
            if mon:
                width_scale = mon.width / 1920.0  # ~1080p baseline
                return max(self.MIN_SCALE, min(self.MAX_SCALE, round(min(width_scale, 1.5), 2)))
        except Exception:
            pass

        # Fallback to Tk-reported DPI (~96dpi => 1.0)
        try:
            dpi = float(self.root.winfo_fpixels('1i'))
            return max(self.MIN_SCALE, min(self.MAX_SCALE, round(dpi / 96.0, 2)))
        except Exception:
            return 1.0

    def _apply_scale(self, scale: float):
        # 1) core tk scaling
        self.root.tk.call('tk', 'scaling', scale)

        # 2) refresh default fonts
        base_font = tkfont.nametofont('TkDefaultFont')
        text_font = tkfont.nametofont('TkTextFont')
        fixed_font = tkfont.nametofont('TkFixedFont')
        heading_font = tkfont.nametofont('TkHeadingFont')
        menu_font = tkfont.nametofont('TkMenuFont')
        sm_caption = tkfont.nametofont('TkSmallCaptionFont') if 'TkSmallCaptionFont' in tkfont.names() else None

        def set_size(f, base): f.configure(size=max(8, int(round(base * scale))))
        set_size(base_font, 10)
        set_size(text_font, 10)
        set_size(fixed_font, 10)
        set_size(heading_font, 11)
        set_size(menu_font, 10)
        if sm_caption: set_size(sm_caption, 9)

        # 3) ttk paddings + row heights
        pad = max(2, int(round(6 * scale)))
        ipady = max(1, int(round(3 * scale)))
        self.style.configure('.', padding=pad)
        self.style.configure('TButton', padding=(pad, ipady))
        self.style.configure('TMenubutton', padding=(pad, ipady))
        self.style.configure('TCombobox', padding=(pad, ipady))
        self.style.configure('TEntry', padding=(pad, ipady))
        self.style.configure('Treeview', rowheight=max(18, int(round(22 * scale))))

        # 4) global spacing hints
        self.root.option_add('*padX', pad)
        self.root.option_add('*padY', int(round(pad * 0.75)))

def install_zoom_ui(
    root: tk.Tk,
    zoom: "ZoomController",
    *,
    status_setter=None,     # callable like: lambda text, color=None: ...
    place_slider=True       # False if you'll add your own slider elsewhere
):
    """
    Adds keyboard/mouse shortcuts and an optional View→Zoom menu+slider.
    """
    is_mac = platform.system() == 'Darwin'
    accel = 'Command' if is_mac else 'Control'

    def refresh_status():
        if status_setter:
            pct = int(round(zoom.scale * 100))
            status_setter(f"Zoom: {pct}%")

    # shortcuts
    root.bind_all(f'<{accel}-plus>', lambda e: (zoom.zoom_in(),  refresh_status()))
    root.bind_all(f'<{accel}-equal>', lambda e: (zoom.zoom_in(), refresh_status()))
    root.bind_all(f'<{accel}-minus>', lambda e: (zoom.zoom_out(), refresh_status()))
    root.bind_all(f'<{accel}-0>', lambda e: (zoom.reset(),       refresh_status()))
    root.bind_all('<Control-MouseWheel>', lambda e: (zoom.zoom_in(),  refresh_status()) if getattr(e, 'delta', 0) > 0 else (zoom.zoom_out(), refresh_status()))
    root.bind_all('<Control-Button-4>',  lambda e: (zoom.zoom_in(),  refresh_status()))
    root.bind_all('<Control-Button-5>',  lambda e: (zoom.zoom_out(), refresh_status()))

    # menu
    menubar = root.nametowidget(root['menu']) if root['menu'] else None
    if not menubar:
        menubar = tk.Menu(root)
        try: root.config(menu=menubar)
        except Exception: menubar = None

    if menubar:
        view_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label='View', menu=view_menu)
        view_menu.add_command(label='Zoom In',  accelerator=f'{accel} +', command=lambda: (zoom.zoom_in(),  refresh_status()))
        view_menu.add_command(label='Zoom Out', accelerator=f'{accel} -', command=lambda: (zoom.zoom_out(), refresh_status()))
        view_menu.add_command(label='Reset Zoom', accelerator=f'{accel} 0', command=lambda: (zoom.reset(), refresh_status()))

    # optional slider auto-placement (can be ignored if you embed in your StatusBar)
    slider = None
    if place_slider:
        slider = ttk.Scale(root, from_=ZoomController.MIN_SCALE, to=ZoomController.MAX_SCALE,
                           value=zoom.scale, orient='horizontal',
                           command=lambda v: (zoom.set_scale(float(v)), refresh_status()))
        try:
            slider.grid(row=1, column=1, sticky='e', padx=(4, 0))
            ttk.Label(root, text='Zoom').grid(row=1, column=1, sticky='e', padx=(0, 110))
        except Exception:
            pass

    refresh_status()
    return {'slider': slider}
