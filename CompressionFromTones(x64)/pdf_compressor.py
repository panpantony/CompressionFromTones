import os
import sys
import subprocess
import threading
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext
import shutil  # For checking ghostscript existence

# ----------------- Prompt for Admin Privileges (Windows Only) -----------------
if sys.platform.startswith("win"):
    import ctypes
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False
    if not is_admin:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit(0)

# ----------------- Single Instance Check & Activate Existing Instance (Windows Only) -----------------
if sys.platform.startswith("win"):
    import ctypes
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, True, "Global\\MyPDFCompressorMutex")
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        hwnd = ctypes.windll.user32.FindWindowW(None, "PDF File Compressor")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        sys.exit(0)

# ----------------- Additional Imports for Tray Icon -----------------
import pystray
from PIL import Image

# ----------------- Configuration -----------------
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".pdf_compressor_config.json")
CACHE_FILE = os.path.join(os.path.expanduser("~"), ".pdf_compressor_cache.json")

# REMOVE COMMAND APPEARING on macOS
if sys.platform == "darwin":
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "default_folder": "",
        "auto_monitoring": False,
        "minimize_on_startup": False,
        "quality": "Low Quality"
    }

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

config = load_config()
default_folder = config.get("default_folder", "")
auto_monitoring = config.get("auto_monitoring", False)
minimize_on_startup = config.get("minimize_on_startup", False)
default_quality = config.get("quality", "Low Quality")
processed_files = load_cache()

monitoring_thread = None
monitor_stop_event = None  # For folder-monitoring thread
tray_icon = None

# ----------------- Autostart Functionality -----------------
APP_LABEL = "MyPDFCompressor"

def add_to_startup():
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
            shortcut.IconLocation = exe_path
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
            subprocess.run(["launchctl", "load", plist_path], check=True)
            log_message("LaunchAgent loaded successfully.")
        except Exception as e:
            log_message(f"Error creating or loading the LaunchAgent plist: {e}")
    else:
        log_message("Autostart is not implemented for this platform.")

# ----------------- Ghostscript Executable Helper -----------------
def get_ghostscript_executable():
    if getattr(sys, 'frozen', False):
        gs = os.path.join(sys._MEIPASS, "gswin64c.exe")
        if not os.path.exists(gs):
            log_message("Bundled Ghostscript not found!")
        return gs
    else:
        if sys.platform.startswith("win"):
            local_gs = os.path.join(os.path.dirname(__file__), "ghostscript", "gswin64c.exe")
            if os.path.exists(local_gs):
                return local_gs
            else:
                gs_path = shutil.which("gswin64c.exe") or shutil.which("gs")
                if gs_path is None:
                    log_message("Ghostscript not found in PATH!")
                    return None
                return gs_path
        else:
            gs_path = shutil.which("gs")
            if gs_path is None:
                log_message("Ghostscript not found in PATH!")
                return None
            return gs_path

# ----------------- Tray Icon Functions -----------------
def get_icon_image():
    try:
        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(sys._MEIPASS, "icon.ico")
        else:
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        return Image.open(icon_path)
    except Exception as e:
        print("Error loading tray icon:", e)
        return None

def on_tray_show(icon, item):
    root.after(0, root.deiconify)
    icon.stop()
    global tray_icon
    tray_icon = None

def on_tray_exit(icon, item):
    icon.stop()
    root.after(0, root.destroy)

def start_tray_icon():
    global tray_icon
    if tray_icon is None:
        image = get_icon_image()
        tray_icon = pystray.Icon("pdf_compressor", image, "PDF Compressor",
                                  menu=pystray.Menu(
                                      pystray.MenuItem("Show", on_tray_show),
                                      pystray.MenuItem("Exit", on_tray_exit)
                                  ))
        t = threading.Thread(target=tray_icon.run, daemon=True)
        t.start()

def on_closing():
    root.withdraw()
    start_tray_icon()

# ----------------- PDF Compression Functions -----------------
def get_file_size(file_path):
    return os.path.getsize(file_path) / (1024 * 1024)

def log_message(message):
    log_text.configure(state="normal")
    log_text.insert("end", message + "\n")
    log_text.configure(state="disabled")
    log_text.yview("end")

def compress_pdf(file_path, quality=None):
    gs_executable = get_ghostscript_executable()
    if gs_executable is None:
        messagebox.showerror("Error", "Ghostscript is not installed.")
        log_message("❌ Ghostscript is not installed.")
        return False
    if quality is None:
        quality = quality_var.get()
    try:
        file_size = os.path.getsize(file_path)
        if file_path in processed_files and processed_files[file_path] == file_size:
            return False
        try:
            subprocess.run([gs_executable, "--version"], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except Exception as e:
            messagebox.showerror("Error", "Ghostscript error: " + str(e))
            log_message("❌ Ghostscript error processing (version check): " + str(e))
            return False
        base, ext = os.path.splitext(file_path)
        output_file = base + "_compressed" + ext
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
        if sys.platform.startswith("win"):
            creationflags = subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            creationflags = 0
            startupinfo = None
        result = subprocess.run(gs_command, check=True, creationflags=creationflags, startupinfo=startupinfo,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.stdout:
            log_message("Ghostscript stdout: " + result.stdout)
        if result.stderr:
            log_message("Ghostscript stderr: " + result.stderr)
        original_size = os.path.getsize(file_path) / (1024 * 1024)
        new_size = os.path.getsize(output_file) / (1024 * 1024)
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
    except subprocess.CalledProcessError as e:
        log_message(f"❌ Ghostscript error processing: {file_path} (Exit Code: {e.returncode})")
        log_message("Ghostscript stderr: " + e.stderr)
        messagebox.showerror("Error", "Ghostscript failed to compress the file.\n" + e.stderr)
        return False
    except Exception as e:
        log_message(f"❌ Error compressing {file_path}: {e}")
        return False

def select_and_compress():
    file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
    if file_path:
        compress_pdf(file_path)

def select_folder():
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
    global monitoring_thread, monitor_stop_event
    if monitoring_thread and monitoring_thread.is_alive():
        return
    monitor_stop_event = threading.Event()
    watcher = Watcher(folder, monitor_stop_event)
    monitoring_thread = threading.Thread(target=watcher.run, daemon=True)
    monitoring_thread.start()
    log_message(f"🔄 Monitoring started for: {folder}")

def stop_monitoring():
    global monitoring_thread, monitor_stop_event
    if monitor_stop_event:
        monitor_stop_event.set()
    if monitoring_thread:
        monitoring_thread.join(timeout=2)
    monitoring_thread = None
    monitor_stop_event = None

class Watcher:
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
            if self.stop_event.wait(10):
                break

def toggle_auto_monitoring():
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
    global minimize_on_startup
    minimize_on_startup = not minimize_on_startup
    config["minimize_on_startup"] = minimize_on_startup
    save_config(config)
    if minimize_on_startup:
        add_to_startup()
        log_message("✅ Will start on startup and minimize automatically.")
    else:
        log_message("❌ Will not start on startup and minimize automatically.")
        root.deiconify()

def update_quality(new_quality):
    config["quality"] = new_quality
    save_config(config)
    log_message(f"🎚️ Default PDF quality set to: {new_quality}")

# ----------------- Create the GUI -----------------
root = ctk.CTk()
root.configure(fg_color="#23272D")
root.title("PDF File Compressor")
root.geometry("500x450")
root.protocol("WM_DELETE_WINDOW", on_closing)

# Set the application icon for the main window
try:
    if getattr(sys, 'frozen', False):
        icon_path = os.path.join(sys._MEIPASS, "icon.ico")
    else:
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
    root.iconbitmap(icon_path)
except Exception as e:
    print("Failed to set window icon:", e)

choose_pdf = ctk.CTkButton(root, text="Choose PDF", command=select_and_compress)
choose_pdf.pack(pady=10)
autocompress_folder = ctk.CTkButton(root, text="Set Auto-Compress Folder", command=select_folder)
autocompress_folder.pack(pady=10)
quality_var = ctk.StringVar(value=default_quality)
quality_label = ctk.CTkLabel(root, text="Select PDF Quality:")
quality_label.pack(pady=(10, 0))
quality_options = ["Low Quality", "Balanced Quality", "High Quality", "Very High Quality"]
quality_menu = ctk.CTkOptionMenu(root, variable=quality_var, values=quality_options, command=update_quality)
quality_menu.pack(pady=(0, 0))
quality_description = ctk.CTkLabel(root,
    text=("• Low Quality: Highest Compression\n"
          "• Balanced Quality: Balanced Compression\n"
          "• High Quality: Low Compression\n"
          "• Very High Quality: Very Low Compression"),
    text_color="gray", font=("Arial", 12))
quality_description.pack(pady=(0, 10))
auto_monitoring_switch = ctk.CTkSwitch(root, text="Enable Auto-Compression", command=toggle_auto_monitoring)
auto_monitoring_switch.pack(pady=10)
if auto_monitoring:
    auto_monitoring_switch.select()
else:
    auto_monitoring_switch.deselect()
minimize_switch = ctk.CTkSwitch(root, text="Start on Startup & Minimize Automatically", command=toggle_minimize_on_startup)
minimize_switch.pack(pady=10)
if minimize_on_startup:
    minimize_switch.select()
else:
    minimize_switch.deselect()
log_text = scrolledtext.ScrolledText(root, height=10, wrap="word", state="disabled",
                                       bg="#1E1E1E", fg="white", font=("Arial", 10))
log_text.pack(fill="both", padx=10, pady=10, expand=True)

root.deiconify()
if default_folder and auto_monitoring:
    start_monitoring(default_folder)

root.mainloop()
