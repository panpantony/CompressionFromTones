import os
import sys
import subprocess
import threading
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext

# ----------------- Configuration -----------------

# Config file paths (stored in the user's home directory)
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".pdf_compressor_config.json")
CACHE_FILE = os.path.join(os.path.expanduser("~"), ".pdf_compressor_cache.json")

#REMOVE COMMAND APPEARING
if sys.platform == "darwin":
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
def load_config():
    """Loads settings from the config file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    # Default settings
    return {
        "default_folder": "",
        "auto_monitoring": False,
        "minimize_on_startup": False,
        "quality": "Low Quality"  # Default quality setting
    }


def save_config(config):
    """Saves settings to the config file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)


def load_cache():
    """Loads processed files from cache to prevent duplicate processing."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """Saves processed files cache."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


# Load configuration and cache
config = load_config()
default_folder = config.get("default_folder", "")
auto_monitoring = config.get("auto_monitoring", False)
minimize_on_startup = config.get("minimize_on_startup", False)
default_quality = config.get("quality", "Low Quality")
processed_files = load_cache()  # Tracks processed files

# Globals for monitoring thread
monitoring_thread = None
monitor_stop_event = None  # threading.Event used to signal monitoring thread to stop

# ----------------- Autostart Functionality -----------------

APP_LABEL = "MyPDFCompressor"  # Change this to your application's name


def add_to_startup():
    """
    Adds this executable to the system startup.
    - On Windows, creates a shortcut in the Startup folder.
    - On macOS, creates and loads a LaunchAgent plist.
    """
    exe_path = os.path.abspath(sys.argv[0])

    if sys.platform.startswith("win"):
        try:
            from win32com.client import Dispatch
        except ImportError:
            log_message("pywin32 is required on Windows for autostart. Please install it.")
            return

        startup_dir = os.path.join(os.getenv("APPDATA"), r"Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_dir, f"{APP_LABEL}.lnk")

        try:
            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = exe_path
            shortcut.WorkingDirectory = os.path.dirname(exe_path)
            shortcut.IconLocation = exe_path  # Use the executable's icon
            shortcut.save()
            log_message(f"Shortcut created in Startup folder: {shortcut_path}")
        except Exception as e:
            log_message(f"Error creating startup shortcut: {e}")

    elif sys.platform == "darwin":
        plist_dir = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents")
        if not os.path.exists(plist_dir):
            os.makedirs(plist_dir)
        plist_path = os.path.join(plist_dir, f"com.{APP_LABEL.lower()}.startup.plist")
        plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.{APP_LABEL.lower()}.startup</string>
    <key>ProgramArguments</key>
    <array>
      <string>{exe_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
  </dict>
</plist>
'''
        try:
            with open(plist_path, "w") as f:
                f.write(plist_content)
            log_message(f"LaunchAgent plist created: {plist_path}")

            # Load the LaunchAgent immediately
            subprocess.run(["launchctl", "load", plist_path], check=True)
            log_message("LaunchAgent loaded successfully.")
        except Exception as e:
            log_message(f"Error creating or loading the LaunchAgent plist: {e}")

    else:
        log_message("Autostart is not implemented for this platform.")


# ----------------- PDF Compression Functions -----------------

def get_file_size(file_path):
    """Returns file size in MB."""
    return os.path.getsize(file_path) / (1024 * 1024)


def log_message(message):
    """Updates the log display in the GUI."""
    log_text.configure(state="normal")
    log_text.insert("end", message + "\n")
    log_text.configure(state="disabled")
    log_text.yview("end")


def compress_pdf(file_path, quality=None):
    """
    Compresses a PDF file using Ghostscript.
    Uses the selected quality (or default from the quality option menu) and logs the results.
    """
    if quality is None:
        quality = quality_var.get()

    try:
        file_size = os.path.getsize(file_path)
        # Skip if the file has already been processed and not changed
        if file_path in processed_files and processed_files[file_path] == file_size:
            return False

        gs_executable = "gs"
        try:
            subprocess.run([gs_executable, "--version"], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            messagebox.showerror("Error", "Ghostscript is not installed or not found in PATH.")
            log_message("❌ Ghostscript not found.")
            return False

        base, ext = os.path.splitext(file_path)
        output_file = base + "_compressed" + ext

        # Map user-friendly quality names to Ghostscript PDFSETTINGS
        quality_map = {
            "Low Quality": "screen",
            "Balanced Quality": "ebook",
            "High Quality": "printer",
            "Very High Quality": "prepress"
        }
        gs_quality = quality_map.get(quality, "screen")
        gs_command = [
            gs_executable,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{gs_quality}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_file}",
            file_path
        ]
        # On Windows, prevent a console window from appearing during the subprocess call
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
        subprocess.run(gs_command, check=True, creationflags=creationflags)

        original_size = get_file_size(file_path)
        new_size = get_file_size(output_file)

        if new_size < original_size:
            os.replace(output_file, file_path)
            log_message(f"✅ Compressed: {file_path} (New Size: {new_size:.2f}MB)")
            processed_files[file_path] = os.path.getsize(file_path)
            save_cache(processed_files)
            return True
        else:
            os.remove(output_file)
            log_message(f"⚠️ No size reduction for: {file_path}")
            processed_files[file_path] = file_size
            save_cache(processed_files)
            return False

    except subprocess.CalledProcessError:
        messagebox.showerror("Error", "Ghostscript failed to compress the file.")
        log_message(f"❌ Ghostscript error processing: {file_path}")
        return False
    except Exception as e:
        log_message(f"❌ Error compressing {file_path}: {e}")
        return False


def select_and_compress():
    file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
    if file_path:
        compress_pdf(file_path)

def select_folder():
    """Allows user to set a default folder for automatic compression."""
    global default_folder
    folder_path = filedialog.askdirectory()
    if folder_path:
        config["default_folder"] = folder_path
        save_config(config)
        default_folder = folder_path
        messagebox.showinfo("Folder Selected", f"Monitoring folder:\n{folder_path}")
        log_message(f"📂 Monitoring folder: {folder_path}")
        if auto_monitoring:
            start_monitoring(default_folder)


# ----------------- Folder Monitoring -----------------

def start_monitoring(folder):
    """Starts monitoring a folder (and subfolders) for PDFs."""
    global monitoring_thread, monitor_stop_event
    if monitoring_thread and monitoring_thread.is_alive():
        return

    monitor_stop_event = threading.Event()
    watcher = Watcher(folder, monitor_stop_event)
    monitoring_thread = threading.Thread(target=watcher.run, daemon=True)
    monitoring_thread.start()
    log_message(f"🔄 Monitoring started for: {folder}")


def stop_monitoring():
    """Stops the folder monitoring."""
    global monitoring_thread, monitor_stop_event
    if monitor_stop_event:
        monitor_stop_event.set()
    if monitoring_thread:
        monitoring_thread.join(timeout=2)
    monitoring_thread = None
    monitor_stop_event = None


class Watcher:
    """Watches a folder (including subfolders) for PDF files and compresses them."""

    def __init__(self, folder, stop_event):
        self.folder = folder
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            for root_dir, _, files in os.walk(self.folder):
                for file in files:
                    if file.lower().endswith(".pdf") and not file.lower().endswith("_compressed.pdf"):
                        file_path = os.path.join(root_dir, file)
                        compress_pdf(file_path)
                        if self.stop_event.is_set():
                            break
                if self.stop_event.is_set():
                    break
            # Wait up to 10 seconds (exits early if stop signaled)
            if self.stop_event.wait(10):
                break


def toggle_auto_monitoring():
    """Toggles automatic folder monitoring on/off."""
    global auto_monitoring
    auto_monitoring = not auto_monitoring
    config["auto_monitoring"] = auto_monitoring
    save_config(config)
    if auto_monitoring:
        log_message("✅ Auto-monitoring enabled.")
        if default_folder:
            start_monitoring(default_folder)
    else:
        log_message("❌ Auto-monitoring disabled.")
        stop_monitoring()


def toggle_minimize_on_startup():
    """Toggles 'Start on Startup & Minimize Automatically' option."""
    global minimize_on_startup
    minimize_on_startup = not minimize_on_startup
    config["minimize_on_startup"] = minimize_on_startup
    save_config(config)
    if minimize_on_startup:
        add_to_startup()
        log_message("✅ Will start on startup and minimize automatically.")
        root.iconify()
    else:
        log_message("❌ Will not start on startup and minimize automatically.")
        root.deiconify()


def update_quality(new_quality):
    """Updates the default PDF quality setting."""
    config["quality"] = new_quality
    save_config(config)
    log_message(f"🎚️ Default PDF quality set to: {new_quality}")


# ----------------- Create the GUI -----------------

root = ctk.CTk()
root.configure(fg_color="#23272D")
root.title("PDF File Compressor")
root.geometry("500x450")
root.withdraw()  # Hide window during setup

# 1. Choose PDF Button
choose_pdf = ctk.CTkButton(root, text="Choose PDF", command=select_and_compress)
choose_pdf.pack(pady=10)

# 2. Set Auto-Compress Folder Button
autocompress_folder = ctk.CTkButton(root, text="Set Auto-Compress Folder", command=select_folder)
autocompress_folder.pack(pady=10)

# 3. PDF Quality Option Menu
quality_var = ctk.StringVar(value=default_quality)
quality_label = ctk.CTkLabel(root, text="Select PDF Quality:")
quality_label.pack(pady=(10, 0))
quality_options = ["Low Quality", "Balanced Quality", "High Quality", "Very High Quality"]
quality_menu = ctk.CTkOptionMenu(root, variable=quality_var, values=quality_options, command=update_quality)
quality_menu.pack(pady=(0, 0))

# Small descriptive text under the quality menu
quality_description = ctk.CTkLabel(
    root,
    text=(
        "• Low Quality: Highest Compression\n"
        "• Balanced Quality: Balanced Compression\n"
        "• High Quality: Low Compression\n"
        "• Very High Quality: Very Low Compression"
    ),
    text_color="gray",
    font=("Arial", 12)
)
quality_description.pack(pady=(0, 10))

# 4. Auto-Compression Switch
auto_monitoring_switch = ctk.CTkSwitch(root, text="Enable Auto-Compression", command=toggle_auto_monitoring)
auto_monitoring_switch.pack(pady=10)
if auto_monitoring:
    auto_monitoring_switch.select()
else:
    auto_monitoring_switch.deselect()

# 5. Minimize on Startup Switch
minimize_switch = ctk.CTkSwitch(root, text_color="gray", text="Start on Startup & Minimize Automatically",
                                command=toggle_minimize_on_startup)
minimize_switch.pack(pady=10)
if minimize_on_startup:
    minimize_switch.select()
else:
    minimize_switch.deselect()

# 6. Log Window
log_text = scrolledtext.ScrolledText(root, height=10, wrap="word", state="disabled",
                                     bg="#1E1E1E", fg="white", font=("Arial", 10))
log_text.pack(fill="both", padx=10, pady=10, expand=True)

# Show the main window (minimized if configured)
if minimize_on_startup:
    root.iconify()
else:
    root.deiconify()

# If auto-monitoring was enabled, start monitoring the default folder
if default_folder and auto_monitoring:
    start_monitoring(default_folder)

root.mainloop()