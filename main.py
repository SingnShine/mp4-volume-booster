from cProfile import label
import sys
import json
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from PIL import Image, ImageTk
import tempfile
import urllib.request
import shutil
import threading

# ---------------- CONFIG ----------------
batch_running = False
preview_proc = None
preview_after_id = None


# ---------------- APP INFO ----------------
APP_NAME = "MP4 Volume Booster"
APP_VERSION = "1.0.0"
UPDATE_URL = "https://singnshine.github.io/mp4-volume-booster-updates/latest.json"
ENGINE_UPDATE_URL = (
    "https://singnshine.github.io/mp4-volume-booster-updates/engine_update.json"
)


def app_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def resource_path(relative_path):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path


def ffmpeg_path():
    p = app_base_dir() / "tools" / "ffmpeg.exe"
    if p.exists():
        return p
    return (
        Path(sys._MEIPASS) / "tools" / "ffmpeg.exe" if hasattr(sys, "_MEIPASS") else p
    )


def ffplay_path():
    p = app_base_dir() / "tools" / "ffplay.exe"
    if p.exists():
        return p
    return (
        Path(sys._MEIPASS) / "tools" / "ffplay.exe" if hasattr(sys, "_MEIPASS") else p
    )


TOOLS_DIR = app_base_dir() / "tools"
ENGINE_VERSION_FILE = TOOLS_DIR / "engine_version.txt"
BTN_BORDER = "#274C6B"  # muted pale blue
BTN_PAD = 1  # creates a subtle border effect without needing a separate widget

PRESETS = [
    "Music (Singing)",
    "Speech",
    "Speech (Mono)",
    "Speech (Stereo)",
]
NOISE_OPTIONS = ["Off", "Light", "Medium", "Strong"]


def is_newer_version(remote, local):
    def parse(v):
        return tuple(map(int, v.split(".")))

    return parse(remote) > parse(local)


def check_for_updates():
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        remote_version = data.get("version")
        download_url = data.get("download_url")
        notes = data.get("notes", "")

        if is_newer_version(remote_version, APP_VERSION):
            msg = (
                f"A new version is available!\n\n"
                f"Current: {APP_VERSION}\n"
                f"Latest : {remote_version}\n\n"
                f"{notes}\n\n"
                "Would you like to download it?"
            )
            if messagebox.askyesno("Update Available", msg):
                import webbrowser

                webbrowser.open(download_url)
        else:
            messagebox.showinfo(
                "Up to Date", f"You are using the latest version ({APP_VERSION})."
            )

    except Exception as e:
        messagebox.showerror(
            "Update Check Failed",
            "Unable to check for updates.\nPlease try again later.",
        )


def read_local_engine_version():
    try:
        return ENGINE_VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


def parse_version(v):
    return tuple(map(int, v.split(".")))


def download_with_progress(url, dest, on_progress):
    with urllib.request.urlopen(url) as r:
        total = int(r.headers.get("Content-Length", 0))
        downloaded = 0
        chunk = 8192

        with open(dest, "wb") as f:
            while True:
                data = r.read(chunk)
                if not data:
                    break
                f.write(data)
                downloaded += len(data)

                if total:
                    percent = (downloaded / total) * 100
                    on_progress(percent)


def show_progress_window(title):
    win = tk.Toplevel(app)
    win.title(title)
    win.geometry("380x160")
    win.resizable(False, False)
    win.transient(app)
    win.grab_set()

    lbl = tk.Label(win, text="Starting download...", font=("Segoe UI", 10))
    lbl.pack(pady=8)

    bar = ttk.Progressbar(win, length=320, mode="determinate")
    bar.pack(pady=6)

    return win, lbl, bar, None


def check_engine_update(startup=False):
    global batch_running

    # ✅ HARD GUARD — added safely
    if batch_running:
        choice = messagebox.askyesnocancel(
            "Batch in Progress",
            "A batch audio process is currently running.\n\n"
            "Updating the engine will stop processing.\n\n"
            "YES  → Close the app and update\n"
            "NO   → Cancel update and continue batch\n"
            "CANCEL → Do nothing",
            icon="warning",
        )

        if choice is True:
            app.destroy()
            sys.exit(0)

        # NO or CANCEL → abandon update completely
        return

    # ✅ ORIGINAL FUNCTION CONTINUES UNCHANGED
    tmp_dir = Path(tempfile.gettempdir()) / "mp4_volume_booster_engine_update"
    tmp_dir.mkdir(exist_ok=True)

    try:
        with urllib.request.urlopen(ENGINE_UPDATE_URL, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))

        remote_ver = data["engine_version"]
        ffmpeg_url = data["ffmpeg_url"]
        ffplay_url = data["ffplay_url"]
        notes = data.get("notes", "")

        local_ver = read_local_engine_version()
        if parse_version(remote_ver) <= parse_version(local_ver):
            return

        msg = (
            "A new FFmpeg engine is available.\n\n"
            f"Current: {local_ver}\n"
            f"Latest : {remote_ver}\n\n"
            f"{notes}\n\n"
            "Download and update now?"
        )

        if not messagebox.askyesno("FFmpeg Engine Update", msg):
            return

        win, label, bar, _ = show_progress_window("Updating FFmpeg Engine")

        td = Path(tempfile.gettempdir()) / "mp4_volume_booster_engine_update"
        td.mkdir(exist_ok=True)

        tmp_ffmpeg = td / "ffmpeg.exe"
        tmp_ffplay = td / "ffplay.exe"

        label.config(text="Downloading ffmpeg.exe...")
        download_with_progress(
            ffmpeg_url, tmp_ffmpeg, lambda p: bar.config(value=p) or win.update()
        )

        bar.config(value=0)
        label.config(text="Downloading ffplay.exe...")
        download_with_progress(
            ffplay_url, tmp_ffplay, lambda p: bar.config(value=p) or win.update()
        )

        win.destroy()

        (tmp_dir / "engine_version.txt").write_text(remote_ver, encoding="utf-8")

        subprocess.Popen([sys.executable, "engine_finish_update.py"])

    except Exception as e:
        if not startup:
            messagebox.showerror("Engine Update Failed", str(e))


# ---------------- (EXE SAFE) ----------------
SETTINGS_FILE = "settings.json"


def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(input_path, output_path):
    data = {
        "input_dir": input_path,
        "output_dir": output_path,
    }
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def check_close_signal():
    if CLOSE_SIGNAL.exists():
        try:
            CLOSE_SIGNAL.unlink()
        except Exception:
            pass
        app.destroy()
        sys.exit(0)
    app.after(300, check_close_signal)


def update_batch_ui(current, total):
    status_var.set(f"Processing {current} of {total} files…")
    progress = (current / total) * 100
    progress_bar["value"] = progress


def batch_done_ui(total):
    global batch_running

    hide_progress()
    status_var.set("")

    # Restore preview toggle state
    preview_toggle_btn.config(text="▶ Play")

    start_batch_btn.config(state="normal")
    batch_running = False

    save_settings(input_dir.get(), output_dir.get())
    messagebox.showinfo("Done", f"Processed {total} file(s).")


# ---------------- AUDIO PROCESSING ----------------


def boost(input_mp4, output_mp4, db, noise_level):
    filters = []

    if noise_level == "Light":
        filters.append("afftdn=nf=-20")
    elif noise_level == "Medium":
        filters.append("afftdn=nf=-25")
    elif noise_level == "Strong":
        filters.append("afftdn=nf=-30")

    if normalize_loudness.get():
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    else:
        filters.append(f"volume={db}dB")

    ffmpeg_cmd = [
        str(ffmpeg_path()),  # ✅ FIXED
        "-y",
        "-i",
        str(input_mp4),
        "-map",
        "0:v",
        "-map",
        "0:a",
        "-ac",
        "1" if force_mono.get() else "0",
        "-c:v",
        "copy",
        "-filter:a",
        ",".join(filters),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output_mp4),
    ]

    subprocess.run(
        ffmpeg_cmd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def preview_audio(input_mp4, db, noise_level):
    filters = []

    if noise_level == "Light":
        filters.append("afftdn=nf=-20")
    elif noise_level == "Medium":
        filters.append("afftdn=nf=-25")
    elif noise_level == "Strong":
        filters.append("afftdn=nf=-30")

    if force_mono.get():
        filters.append("pan=mono|c0=.5*c0+.5*c1")

    if normalize_loudness.get():
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    else:
        filters.append(f"volume={db}dB")

    subprocess.run(
        [
            str(ffplay_path()),
            "-autoexit",
            "-nodisp",
            "-i",
            str(input_mp4),
            "-ss",
            "60",
            "-t",
            "30",
            "-af",
            ",".join(filters),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def detect_channels(media_file):
    try:
        cmd = [
            str(ffmpeg_path()),
            "-i",
            str(media_file),
            "-hide_banner",
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        for line in result.stderr.splitlines():
            if "Audio:" in line:
                if "mono" in line:
                    return "Mono"
                if "stereo" in line:
                    return "Stereo"
                if "5.1" in line:
                    return "5.1 Surround"
        return "Unknown"
    except Exception:
        return "Unknown"


def sync_volume_state(*_):
    state = "disabled" if normalize_loudness.get() else "normal"
    volume_spinbox.config(state=state)


# ---------------- GUI ACTIONS ----------------


def batch_worker(files, src, dst):
    total = len(files)

    for i, mp4 in enumerate(files, start=1):
        boost(mp4, dst / mp4.name, volume_db.get(), noise_level.get())

        # UI update (thread-safe)
        app.after(0, lambda i=i: update_batch_ui(i, total))

    # Done
    app.after(0, batch_done_ui, total)


def select_input():
    folder = filedialog.askdirectory()
    if folder:
        input_dir.set(folder)
        save_settings(input_dir.get(), output_dir.get())

        # ✅ Detect channel layout from first MP4
        files = list(Path(folder).glob("*.mp4"))
        if files:
            info = detect_channels(files[0])
            channel_info.set(f"Channel layout: {info}")
        else:
            channel_info.set("Channel layout: —")


def select_output():
    folder = filedialog.askdirectory()
    if folder:
        output_dir.set(folder)
        save_settings(input_dir.get(), output_dir.get())


def open_preset_dropdown(anchor_widget):
    dropdown = tk.Toplevel(app)
    dropdown.overrideredirect(True)
    dropdown.configure(bg="#081422")

    # ✅ Close when clicking outside
    dropdown.bind("<FocusOut>", lambda e: dropdown.destroy())

    def close_on_click_outside(event):
        # If click happens inside this dropdown, ignore
        if event.widget.winfo_toplevel() is dropdown:
            return
        destroy_dropdown()

    app.bind("<Button-1>", close_on_click_outside, add="+")

    def destroy_dropdown():
        app.unbind("<Button-1>", close_on_click_outside)
        dropdown.destroy()

    anchor_widget.update_idletasks()

    x = anchor_widget.winfo_rootx()
    y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
    button_width = anchor_widget.winfo_width()

    container = tk.Frame(dropdown, bg="#081422", padx=6)
    container.pack(fill="both", expand=True)

    lb = tk.Listbox(
        container,
        bg="#081422",
        fg="#E8F1FA",
        selectbackground="#0E2440",
        selectforeground="#FFFFFF",
        highlightthickness=0,
        bd=0,
        relief="flat",
        activestyle="none",
        font=FONT_BUTTON,
        justify="center",
        exportselection=False,
    )
    lb.pack(fill="both", expand=True)
    lb.config(height=min(len(PRESETS), 4))
    for item in PRESETS:
        lb.insert("end", item)

    if audio_preset.get() in PRESETS:
        idx = PRESETS.index(audio_preset.get())
        lb.selection_set(idx)
        lb.activate(idx)

    dropdown.update_idletasks()
    list_height = lb.winfo_reqheight()
    dropdown.geometry(f"{button_width}x{list_height}+{x}+{y}")

    def on_select(event=None):
        sel = lb.curselection()
        if sel:
            audio_preset.set(lb.get(sel[0]))
            apply_audio_preset()
        dropdown.destroy()

    lb.bind("<ButtonRelease-1>", on_select)
    lb.bind("<Return>", on_select)
    lb.bind("<Escape>", lambda e: dropdown.destroy())

    lb.focus_set()


def apply_audio_preset(*_):
    preset = audio_preset.get()

    if preset == "Music (Singing)":
        normalize_loudness.set(True)
        volume_db.set(2)
        noise_level.set("Off")
        force_mono.set(False)

    elif preset == "Speech":
        normalize_loudness.set(True)
        volume_db.set(4)
        noise_level.set("Light")
        force_mono.set(False)

    elif preset == "Speech (Mono)":
        normalize_loudness.set(True)
        volume_db.set(5)
        noise_level.set("Light")
        force_mono.set(True)

    elif preset == "Speech (Stereo)":
        normalize_loudness.set(True)
        volume_db.set(3)
        noise_level.set("Light")
        force_mono.set(False)


def open_noise_dropdown(anchor_widget):
    dropdown = tk.Toplevel(app)
    dropdown.overrideredirect(True)
    dropdown.configure(bg="#081422")

    # ✅ Close when clicking outside
    dropdown.bind("<FocusOut>", lambda e: dropdown.destroy())

    def close_on_click_outside(event):
        # If click happens inside this dropdown, ignore
        if event.widget.winfo_toplevel() is dropdown:
            return
        destroy_dropdown()

    app.bind("<Button-1>", close_on_click_outside, add="+")

    def destroy_dropdown():
        app.unbind("<Button-1>", close_on_click_outside)
        dropdown.destroy()

    anchor_widget.update_idletasks()

    x = anchor_widget.winfo_rootx()
    y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
    button_width = anchor_widget.winfo_width()

    container = tk.Frame(dropdown, bg="#081422", padx=6)
    container.pack(fill="both", expand=True)

    lb = tk.Listbox(
        container,
        bg="#081422",
        fg="#E8F1FA",
        selectbackground="#0E2440",
        selectforeground="#FFFFFF",
        highlightthickness=0,
        bd=0,
        relief="flat",
        activestyle="none",
        font=FONT_BUTTON,
        justify="center",
        exportselection=False,
    )
    lb.pack(fill="both", expand=True)
    lb.config(height=min(len(NOISE_OPTIONS), 4))
    for item in NOISE_OPTIONS:
        lb.insert("end", item)

    if noise_level.get() in NOISE_OPTIONS:
        idx = NOISE_OPTIONS.index(noise_level.get())
        lb.selection_set(idx)
        lb.activate(idx)

    dropdown.update_idletasks()
    list_height = lb.winfo_reqheight()
    dropdown.geometry(f"{button_width}x{list_height}+{x}+{y}")

    def on_select(event=None):
        sel = lb.curselection()
        if sel:
            noise_level.set(lb.get(sel[0]))
        dropdown.destroy()

    lb.bind("<ButtonRelease-1>", on_select)
    lb.bind("<Return>", on_select)
    lb.bind("<Escape>", lambda e: dropdown.destroy())

    lb.focus_set()


def build_preview_filters(db, noise_level):
    filters = []

    if noise_level == "Light":
        filters.append("afftdn=nf=-20")
    elif noise_level == "Medium":
        filters.append("afftdn=nf=-25")
    elif noise_level == "Strong":
        filters.append("afftdn=nf=-30")

    if force_mono.get():
        filters.append("pan=mono|c0=.5*c0+.5*c1")

    if normalize_loudness.get():
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    else:
        filters.append(f"volume={db}dB")

    return ",".join(filters)


def toggle_preview():
    global preview_proc

    if preview_proc is None:
        start_preview()
    else:
        stop_preview(manual=True)


def start_preview():
    global preview_proc

    src = Path(input_dir.get())
    if not src.exists():
        messagebox.showerror("Error", "Please select an input folder.")
        return

    files = list(src.glob("*.mp4"))
    if not files:
        messagebox.showinfo("Info", "No MP4 files found for preview.")
        return

    start_batch_btn.config(state="disabled")
    preview_toggle_btn.config(image=stop_icon)
    preview_toggle_btn.image = stop_icon

    preview_proc = subprocess.Popen(
        [
            str(ffplay_path()),
            "-autoexit",
            "-nodisp",
            "-ss",
            "60",
            "-t",
            "30",
            "-i",
            str(files[0]),
            "-af",
            build_preview_filters(volume_db.get(), noise_level.get()),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    # auto‑stop after 30s + 2s buffer
    app.after(32_000, lambda: stop_preview(manual=False))


def stop_preview(manual=False):
    global preview_proc

    if preview_proc and preview_proc.poll() is None:
        try:
            preview_proc.terminate()
        except Exception:
            pass

    preview_proc = None

    # ✅ SWITCH BACK TO PLAY ICON (NO TEXT)
    preview_toggle_btn.config(image=play_icon)
    preview_toggle_btn.image = play_icon

    start_batch_btn.config(state="normal")


def start_batch():
    global batch_running
    if batch_running:
        return

    src = Path(input_dir.get())
    dst = Path(output_dir.get())

    if not src.exists() or not dst.exists():
        messagebox.showerror("Error", "Please select valid folders.")
        return

    files = list(src.glob("*.mp4"))
    if not files:
        messagebox.showinfo("Info", "No MP4 files found in input folder.")
        return

    batch_running = True

    # --- UI busy state ---
    status_var.set("Starting batch processing…")
    progress_bar["value"] = 0
    preview_toggle_btn.config(state="disabled")
    start_batch_btn.config(state="disabled")

    # --- Run batch in background thread ---
    t = threading.Thread(
        target=batch_worker,
        args=(files, src, dst),
        daemon=True,
    )
    t.start()


def show_batch_progress():
    progress_bar.config(mode="determinate", value=0)
    progress_bar.pack(pady=(0, 10))


def hide_progress():
    progress_bar.pack_forget()
    progress_bar["value"] = 0


class ToolTip:
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwindow = None
        self.after_id = None

        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _=None):
        self.after_id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self.tipwindow or not self.text:
            return

        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.geometry(f"+{x}+{y}")

        tk.Label(
            tw,
            text=self.text,
            bg="#222222",
            fg="#E8F1FA",
            font=("Segoe UI", 9),
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=3,
        ).pack()

    def _hide(self, _=None):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


def bordered_button(parent, **kwargs):
    container = tk.Frame(parent, bg=BTN_BORDER, padx=BTN_PAD, pady=BTN_PAD)
    btn = ttk.Button(container, style="Dark.TButton", **kwargs)
    btn.pack(fill="both")
    return container, btn


# ---------------- GUI SETUP ----------------

app = tk.Tk()
app.title("MP4 Volume Booster")
app.geometry("540x510")
app.resizable(False, True)
app.configure(bg="#0B1C2D")
menubar = tk.Menu(app)

# Fonts
FONT_LABEL = ("Segoe UI", 11)
FONT_ENTRY = ("Segoe UI", 11)
FONT_BUTTON = ("Segoe UI", 11, "bold")
FONT_SPIN = ("Segoe UI", 11)

# ---------- DARK DROPDOWN MENU ----------
app.option_add("*Menu.background", "#081422")
app.option_add("*Menu.foreground", "#E8F1FA")
app.option_add("*Menu.activeBackground", "#014D93")
app.option_add("*Menu.activeForeground", "#FFFFFF")
app.option_add("*Menu.borderWidth", 0)  # ✅ remove border
app.option_add("*Menu.relief", "flat")  # ✅ no 3D edge
app.option_add("*Menu.highlightThickness", 0)  # ✅ kill white rim

# Variables
input_dir = tk.StringVar()
output_dir = tk.StringVar()
settings = load_settings()
audio_preset = tk.StringVar(value="Music (Singing)")
input_dir.set(settings.get("input_dir", ""))
output_dir.set(settings.get("output_dir", ""))
volume_db = tk.DoubleVar(value=6.0)
noise_level = tk.StringVar(value="Off")
normalize_loudness = tk.BooleanVar(value=False)
force_mono = tk.BooleanVar(value=False)

# Style
style = ttk.Style()
style.theme_use("clam")


style.configure(
    "Dark.TButton",
    background="#07233E",
    foreground="#E8F1FA",
    font=FONT_BUTTON,
    padding=(10, 6),
    borderwidth=1,
    relief="flat",
)

style.map(
    "Dark.TButton",
    background=[
        ("active", "#014D93"),
    ],
    bordercolor=[
        ("!focus", "#081422"),
        ("focus", "#081422"),
        ("active", "#0E2440"),
    ],
    relief=[("pressed", "flat"), ("!pressed", "flat")],
)

style.configure(
    "Dark.TMenubutton",
    background="#081422",  # navy / near-black
    foreground="#E8F1FA",
    font=FONT_BUTTON,
    padding=8,
    relief="flat",
    borderwidth=0,  # ✅ remove border
    focuscolor="none",  # ✅ disable focus outline
    arrowcolor="#E8F1FA",
)

style.map(
    "Dark.TMenubutton",
    background=[
        ("active", "#081422"),
        ("pressed", "#040A12"),
        ("!active", "#081422"),
    ],
    foreground=[
        ("active", "#E8F1FA"),
        ("pressed", "#E8F1FA"),
        ("!active", "#E8F1FA"),
    ],
    bordercolor=[
        ("active", "#081422"),
        ("focus", "#081422"),  # ✅ kill focus border
        ("!focus", "#081422"),
    ],
)


style.configure(
    "Active.Horizontal.TProgressbar",
    troughcolor="#081422",  # matches your dark panel
    background="#2E86C1",
)

style.configure(
    "Icon.TButton",  # ✅ REQUIRED
    background="#102A43",
    borderwidth=0,
    padding=0,
    relief="flat",
)

style.map(
    "Icon.TButton",  # ✅ REQUIRED
    background=[
        ("active", "#0E2440"),
        ("!active", "#102A43"),
    ],
)

# ---------- ICONS ----------

icon_dir = resource_path("assets/icons")

play_icon = ImageTk.PhotoImage(
    Image.open(icon_dir / "preview_play.png").resize((44, 44), Image.LANCZOS)
)
stop_icon = ImageTk.PhotoImage(
    Image.open(icon_dir / "preview_stop.png").resize((44, 44), Image.LANCZOS)
)
browse_icon = ImageTk.PhotoImage(
    Image.open(icon_dir / "browse.png").resize((90, 30), Image.LANCZOS)
)

# ---------------- CONTENT ----------------
content = tk.Frame(app, bg="#0B1C2D", padx=20, pady=20)
content.pack(side="top", fill="both", expand=True)

inputs_frame = tk.Frame(content, bg="#102A43")
inputs_frame.pack(fill="x", pady=(0, 15))

options_frame = tk.Frame(content, bg="#102A43")
options_frame.pack(fill="x", pady=(0, 20))

actions_frame = tk.Frame(content, bg="#102A43")
actions_frame.pack(fill="x")


lbl = {"bg": "#102A43", "fg": "#E8F1FA", "font": FONT_LABEL}
ent = {
    "bg": "#0B1C2D",
    "fg": "#E8F1FA",
    "font": FONT_ENTRY,
    "insertbackground": "#09141F",
}

# ---------- INPUTS ----------
channel_info = tk.StringVar(value="Channel layout: —")
tk.Label(inputs_frame, textvariable=channel_info, **lbl).pack(anchor="w", pady=(0, 8))

tk.Label(inputs_frame, text="Input Folder", **lbl).pack(anchor="w")
row = tk.Frame(inputs_frame, bg="#102A43")
row.pack(fill="x", pady=(0, 6))
# Entry (unchanged)
tk.Entry(row, textvariable=input_dir, **ent).pack(
    side="left", fill="x", expand=True, padx=(0, 8)
)

# ✅ Icon-only Browse button
browse_in_icon = ttk.Button(
    row,
    image=browse_icon,
    command=select_input,
    style="Icon.TButton",
)
browse_in_icon.pack(side="right")
browse_in_icon.image = browse_icon

tk.Label(inputs_frame, text="Output Folder", **lbl).pack(anchor="w")
row = tk.Frame(inputs_frame, bg="#102A43")
row.pack(fill="x", pady=(0, 6))

tk.Entry(row, textvariable=output_dir, **ent).pack(
    side="left", fill="x", expand=True, padx=(0, 8)
)

browse_out_icon = ttk.Button(
    row,
    image=browse_icon,
    command=select_output,
    style="Icon.TButton",
)
browse_out_icon.pack(side="right")
browse_out_icon.image = browse_icon

# ---------- OPTIONS ----------
row = tk.Frame(options_frame, bg="#102A43")
row.pack(fill="x", pady=(0, 6))

# LEFT: Volume Boost
left = tk.Frame(row, bg="#102A43")
left.pack(side="left", anchor="nw")

tk.Label(left, text="Volume Boost (dB)", **lbl).pack(anchor="w")
volume_spinbox = tk.Spinbox(
    left,
    from_=0,
    to=20,
    textvariable=volume_db,
    font=FONT_SPIN,
    width=6,
)
volume_spinbox.pack(anchor="w")
ToolTip(volume_spinbox, "Increase audio loudness in decibels (dB).")
normalize_loudness.trace_add("write", sync_volume_state)

# MIDDLE: Preset dropdown  ✅ NEW
middle = tk.Frame(row, bg="#102A43")
middle.pack(side="left", padx=20, anchor="n")

tk.Label(middle, text="Preset", **lbl).pack(anchor="w")

preset_button = ttk.Button(
    middle,
    textvariable=audio_preset,
    style="Dark.TMenubutton",
    command=lambda: open_preset_dropdown(preset_button),
)
preset_button.pack(anchor="w")

ToolTip(
    preset_button,
    "Choose a preset optimized for Music or Speech.\nYou can fine‑tune settings after selecting.",
)

# RIGHT: Noise Reduction
right = tk.Frame(row, bg="#102A43")
right.pack(side="right", anchor="ne")

tk.Label(right, text="Noise Reduction", **lbl).pack(anchor="w")
noise_button = ttk.Button(
    right,
    textvariable=noise_level,
    style="Dark.TMenubutton",
)
noise_button.pack(anchor="w")

noise_button.config(command=lambda: open_noise_dropdown(noise_button))

ToolTip(noise_button, "Reduce background noise before boosting")

# Row 2: Checkboxes side-by-side
row = tk.Frame(options_frame, bg="#102A43")
row.pack(fill="x", pady=(6, 0))

force_mono_cb = tk.Checkbutton(
    row,
    text="Force Mono Output",
    variable=force_mono,
    bg="#102A43",
    fg="#E8F1FA",
    selectcolor="#0B1C2D",
)
force_mono_cb.pack(side="left")
ToolTip(force_mono_cb, "Convert stereo audio to mono")

normalize_cb = tk.Checkbutton(
    row,
    text="Normalize Loudness (LUFS Safe)",
    variable=normalize_loudness,
    bg="#102A43",
    fg="#E8F1FA",
    selectcolor="#0B1C2D",
)
normalize_cb.pack(side="right")
ToolTip(normalize_cb, "Adjust audio loudness to a consistent level")

# ---------- ACTIONS ROW ----------
actions_row = tk.Frame(actions_frame, bg="#102A43")
actions_row.pack(fill="x", pady=(8, 12))
# Left column: Preview
preview_col = tk.Frame(actions_row, bg="#102A43")
preview_col.pack(side="left", anchor="w")

preview_label = tk.Label(
    preview_col,
    text="Preview 30s Audio",
    bg="#102A43",
    fg="#E8F1FA",
    font=FONT_LABEL,
)
preview_label.pack(side="left", padx=(0, 8))

preview_toggle_btn = ttk.Button(
    preview_col,
    image=play_icon,
    command=toggle_preview,
    style="Icon.TButton",
)
preview_toggle_btn.pack(side="left")
preview_toggle_btn.image = play_icon

ToolTip(preview_toggle_btn, "Preview starts after 1 minute of audio")

# Right column: Status + Start
right_col = tk.Frame(actions_row, bg="#102A43")
right_col.pack(side="right", anchor="e")
status_frame = tk.Frame(actions_frame, bg="#102A43")
status_frame.pack(fill="x", pady=(4, 10))

status_var = tk.StringVar(value="")

status_label = tk.Label(
    status_frame,
    textvariable=status_var,
    bg="#000000",
    fg="#2BFF00",
    font=("Segoe UI", 10),
)
status_label.pack(pady=(2, 2))

progress_bar = ttk.Progressbar(
    status_frame,
    mode="determinate",
    length=260,
)

start_wrap, start_batch_btn = bordered_button(
    right_col,
    text="Start Batch Processing",
    command=start_batch,
)
start_wrap.pack(anchor="e")

ToolTip(
    start_batch_btn,
    "Process all MP4 files in the input folder and save to output folder",
)

CLOSE_SIGNAL = Path(tempfile.gettempdir()) / "mp4_vol_booster_close.signal"
check_close_signal()

help_menu = tk.Menu(menubar, tearoff=0)
help_menu.add_command(label="Check for Updates", command=check_for_updates)
help_menu.add_separator()
help_menu.add_command(
    label="About",
    command=lambda: messagebox.showinfo(
        APP_NAME,
        f"{APP_NAME}\nVersion {APP_VERSION}\n\nBatch audio volume enhancement for MP4 files without touching the video file\nDeveloped by SingnShine (MSME)\nPowered by FFmpeg",
    ),
)

menubar.add_cascade(label="Help", menu=help_menu)
app.config(menu=menubar)

# ---------------- FOOTER ----------------


def setup_footer(parent):
    original_img = Image.open(resource_path("assets/icons/nav.png"))
    orig_w, orig_h = original_img.size

    label = tk.Label(parent, bg=parent["bg"], bd=0, highlightthickness=0)
    label.pack(side="bottom", fill="x", padx=10, pady=(0, 10), ipady=4)

    FIXED_H = 60  # small and safe

    def resize_footer(event):
        if event.width <= 1:
            return

        scale = FIXED_H / orig_h
        new_w = int(orig_w * scale)

        resized = original_img.resize((new_w, FIXED_H), Image.LANCZOS)
        photo = ImageTk.PhotoImage(resized)

        label.configure(image=photo)  # ✅ THIS WAS MISSING
        label.image = photo  # keep reference

    label.bind("<Configure>", resize_footer)

    # initial draw
    parent.update_idletasks()
    w = label.winfo_width()
    if w > 1:
        resize_footer(type("E", (), {"width": w})())


setup_footer(app)

app.after(800, lambda: check_engine_update(startup=True))
app.mainloop()
