import os
import subprocess
import customtkinter as ctk
import threading
import sys
import platform
import json
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# System Tray Imports
if platform.system() == "Darwin":
    import rumps  # macOS system tray
elif platform.system() == "Windows":
    import winreg  # Windows auto-start
else:
    import pystray
    from PIL import Image, ImageDraw

# Config file paths
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".pdf_compressor_config.json")
CACHE_FILE = os.path.join(os.path.expanduser("~"), ".pdf_compressor_cache.json")

def load_config():
    """Loads settings from the config file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"default_folder": "", "auto_monitoring": False, "auto_start": False}

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
    """Saves processed files to prevent reprocessing unchanged PDFs."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

# Load settings
config = load_config()
default_folder = config.get("default_folder", "")
auto_monitoring = config.get("auto_monitoring", False)
auto_start = config.get("auto_start", False)
processed_files = load_cache()

monitoring_thread = None

def get_file_size(file_path):
    """Returns file size in MB"""
    return os.path.getsize(file_path) / (1024 * 1024)

def log_message(message):
    """Updates the log display in the GUI."""
    log_text.configure(state="normal")
    log_text.insert("end", message + "\n")
    log_text.configure(state="disabled")
    log_text.yview("end")

def compress_pdf(file_path, quality="screen"):
    """Compress a PDF using Ghostscript and log the results."""
    file_size = os.path.getsize(file_path)

    if file_path in processed_files and processed_files[file_path] == file_size:
        return False

    try:
        gs_executable = "gs"
        try:
            subprocess.run([gs_executable, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            messagebox.showerror("Error", "Ghostscript is not installed or not found in PATH.")
            log_message("❌ Error: Ghostscript not found.")
            return False

        output_file = file_path.replace(".pdf", "_compressed.pdf")
        gs_command = [
            gs_executable, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{quality}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
            f"-sOutputFile={output_file}", file_path
        ]
        subprocess.run(gs_command, check=True)

        original_size = get_file_size(file_path)
        new_size = get_file_size(output_file)

        if new_size < original_size:
            os.replace(output_file, file_path)
            log_message(f"✅ Compressed: {file_path} (Size: {new_size:.2f}MB)")
            processed_files[file_path] = new_size
            save_cache(processed_files)
            return True
        else:
            os.remove(output_file)
            log_message(f"⚠️ No size reduction: {file_path}")
            processed_files[file_path] = file_size
            save_cache(processed_files)
            return False
    except subprocess.CalledProcessError:
        messagebox.showerror("Error", "Ghostscript failed to compress the file.")
        log_message(f"❌ Ghostscript error while processing: {file_path}")
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
            start_monitoring(folder_path)

def start_monitoring(folder):
    """Starts monitoring the folder for PDFs and compresses them (including subfolders)."""
    global monitoring_thread
    if monitoring_thread and monitoring_thread.is_alive():
        return

    try:
        watcher = Watcher(folder)
        monitoring_thread = threading.Thread(target=watcher.run, daemon=True)
        monitoring_thread.start()
        log_message(f"🔄 Monitoring started for: {folder}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start folder monitoring: {e}")
        log_message(f"❌ Failed to start folder monitoring: {e}")

def stop_monitoring():
    """Stops monitoring the folder (disables auto-monitoring)."""
    global monitoring_thread
    if monitoring_thread:
        monitoring_thread = None
        log_message("❌ Auto-monitoring disabled.")

# Folder Monitoring (With Subfolders)
class Watcher:
    def __init__(self, folder):
        self.folder = folder

    def run(self):
        while auto_monitoring:
            for root_dir, _, files in os.walk(self.folder):
                for file in files:
                    if file.lower().endswith(".pdf") and not file.endswith("_compressed.pdf"):
                        file_path = os.path.join(root_dir, file)
                        compress_pdf(file_path)

# Create GUI
root = ctk.CTk()
root.configure(fg_color="#23272D")
root.title("PDF File Compressor")
root.geometry("500x400")

choose_pdf = ctk.CTkButton(root, text="Choose PDF", command=select_and_compress)
choose_pdf.pack(pady=10)

autocompress_folder = ctk.CTkButton(root, text="Set Auto-Compress Folder", command=select_folder)
autocompress_folder.pack(pady=10)

auto_monitoring_switch = ctk.CTkSwitch(root, text="Enable Auto-Compression", command=lambda: toggle_auto_start())
auto_monitoring_switch.pack(pady=10)

log_text = scrolledtext.ScrolledText(root, height=6, wrap="word", state="disabled", bg="#1E1E1E", fg="white", font=("Arial", 10))
log_text.pack(fill="both", padx=10, pady=10, expand=True)

if default_folder and auto_monitoring:
    start_monitoring(default_folder)

root.mainloop()