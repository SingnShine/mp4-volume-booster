import sys
import time
import subprocess
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import shutil

# ---------------- CONFIG ----------------

MAIN_APP_CMD = [sys.executable, "main.py"]  # change to main.exe after build

BASE_DIR = Path(__file__).parent
TOOLS_DIR = BASE_DIR / "tools"
TEMP_DIR = Path(tempfile.gettempdir()) / "mp4_volume_booster_engine_update"

ENGINE_VERSION_FILE = TOOLS_DIR / "engine_version.txt"
CLOSE_SIGNAL = Path(tempfile.gettempdir()) / "mp4_vol_booster_close.signal"
# ---------------------------------------


def try_apply_update(status_var, root):
    """
    Try replacing engine files.
    If main app is still running, Windows will block replace().
    We retry until it succeeds.
    """
    status_var.set("Waiting for main application to close…")
    root.update()

    while True:
        try:
            TOOLS_DIR.mkdir(parents=True, exist_ok=True)

            shutil.move(TEMP_DIR / "ffmpeg.exe", TOOLS_DIR / "ffmpeg.exe")
            shutil.move(TEMP_DIR / "ffplay.exe", TOOLS_DIR / "ffplay.exe")
            shutil.move(TEMP_DIR / "engine_version.txt", ENGINE_VERSION_FILE)

            return True

        except PermissionError:
            # App still running → wait and retry
            time.sleep(0.5)
        except Exception as e:
            messagebox.showerror("Update Failed", str(e))
            return False


def reopen_main_app():
    subprocess.Popen(MAIN_APP_CMD)


# ---------------- UI ----------------

root = tk.Tk()
root.title("Finish FFmpeg Engine Update")
root.geometry("420x200")
root.resizable(False, False)

status_text = tk.StringVar(
    value=(
        "FFmpeg engine update is ready.\n\n"
        "Please close the main application\n"
        "and click “Finish Update”."
    )
)

tk.Label(
    root,
    textvariable=status_text,
    font=("Segoe UI", 10),
    wraplength=380,
    justify="center",
    pady=15,
).pack()

button_frame = tk.Frame(root)
button_frame.pack(pady=10)


def on_finish_update():
    # Disable buttons immediately
    finish_btn.config(state="disabled")
    cancel_btn.config(state="disabled")

    # 1️⃣ Force main app to close (NO QUESTION)
    CLOSE_SIGNAL.write_text("close")

    status_text.set("Closing application…")
    root.update()

    # Give main app time to exit and release locks
    time.sleep(1.5)

    # 2️⃣ Apply update ONCE (no loops)
    ok = try_apply_update(status_text, root)
    if not ok:
        messagebox.showerror(
            "Update Failed",
            "Failed to apply the update.\n"
            "Please restart the application and try again.",
        )
        root.destroy()
        sys.exit(1)

    # 3️⃣ Success state
    status_text.set("✅ Update completed successfully")
    root.update()

    reopen_btn.config(state="normal")
    close_btn.config(state="normal")


finish_btn = tk.Button(
    button_frame, text="Close App & Update", width=16, command=on_finish_update
)
finish_btn.grid(row=0, column=0, padx=6)

cancel_btn = tk.Button(
    button_frame,
    text="Cancel",
    width=16,
    command=lambda: root.destroy(),
)
cancel_btn.grid(row=0, column=1, padx=6)

reopen_btn = tk.Button(
    button_frame,
    text="Reopen App",
    width=16,
    state="disabled",
    command=lambda: (reopen_main_app(), root.destroy()),
)
reopen_btn.grid(row=1, column=0, padx=6, pady=6)

close_btn = tk.Button(
    button_frame,
    text="Close",
    width=16,
    state="disabled",
    command=lambda: root.destroy(),
)
close_btn.grid(row=1, column=1, padx=6, pady=6)

root.mainloop()
