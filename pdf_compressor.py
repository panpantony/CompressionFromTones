#DEBUG
import tkinter as tk
from tkinter import filedialog, messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

import os
import subprocess

def get_file_size(file_path):
    """Returns file size in MB"""
    return os.path.getsize(file_path) / (1024 * 1024)
def compress_pdf(file_path, target_size_mb=2, max_attempts=3):
    """
    Compress a PDF until it is under the target file size.
    Uses different Ghostscript quality settings.
    """
    quality_levels = ["prepress", "printer", "ebook", "screen"]  # Highest to lowest quality
    attempt = 0

    while attempt < max_attempts:
        current_size = get_file_size(file_path)

        if current_size <= target_size_mb:
            print(f"✅ File is already under {target_size_mb}MB ({current_size:.2f}MB)")
            return True

        if attempt >= len(quality_levels):  # Prevents exceeding available settings
            print(f"❌ Could not compress below {target_size_mb}MB, best attempt: {current_size:.2f}MB")
            return False

        quality = quality_levels[attempt]
        output_file = file_path.replace(".pdf", f"_compressed_{quality}.pdf")

        print(f"🔄 Attempt {attempt+1}: Compressing with quality '{quality}' (Current size: {current_size:.2f}MB)")

        try:
            gs_command = [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS=/{quality}",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={output_file}",
                file_path
            ]

            subprocess.run(gs_command, check=True)

            new_size = get_file_size(output_file)

            if new_size < current_size:  # Only replace if it actually reduced size
                os.replace(output_file, file_path)
                print(f"✅ Compressed to {new_size:.2f}MB using '{quality}' setting")

            if new_size <= target_size_mb:
                print(f"🎯 Successfully compressed below {target_size_mb}MB!")
                return True

        except Exception as e:
            print(f"❌ Compression failed: {e}")
            return False

        attempt += 1

    print(f"❌ Could not reach {target_size_mb}MB, final size: {get_file_size(file_path):.2f}MB")
    return False
# Function to select and compress a file manually
def select_and_compress():
    file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
    if not file_path:
        return

    success = compress_pdf(file_path)
    if success:
        messagebox.showinfo("Success", f"PDF compressed successfully:\n{file_path}")
    else:
        messagebox.showerror("Error", "Failed to compress PDF.")
# Drag and Drop functionality
def drop(event):
    file_path = event.data
    file_path = file_path.replace("{", "").replace("}", "")  # Fix file path formatting

    if file_path.lower().endswith(".pdf"):
        success = compress_pdf(file_path)
        if success:
            messagebox.showinfo("Success", f"PDF compressed successfully:\n{file_path}")
        else:
            messagebox.showerror("Error", "Failed to compress PDF.")
    else:
        messagebox.showerror("Error", "Please drop a valid PDF file.")

# Folder monitoring
class Watcher:
    def __init__(self, folder):
        self.folder = folder
        self.observer = Observer()

    def run(self):
        event_handler = Handler()
        self.observer.schedule(event_handler, self.folder, recursive=False)
        self.observer.start()
        print(f"Monitoring folder: {self.folder}")
        try:
            while True:
                pass
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.lower().endswith(".pdf"):
            print(f"New PDF detected: {event.src_path}")
            compress_pdf(event.src_path)

# Function to select a folder for automatic compression
def select_folder():
    folder_path = filedialog.askdirectory()
    if folder_path:
        messagebox.showinfo("Folder Selected", f"Monitoring folder:\n{folder_path}")
        watcher = Watcher(folder_path)
        thread = threading.Thread(target=watcher.run, daemon=True)
        thread.start()
# Create GUI
def create_gui():
    root = tk.Tk()
    root.title("PDF Compressor")
    root.geometry("400x200")

    label = tk.Label(root, text="Drag & Drop or Select a PDF to Compress", font=("Arial", 12))
    label.pack(pady=10)

    btn_select = tk.Button(root, text="Choose PDF", command=select_and_compress, font=("Arial", 10))
    btn_select.pack(pady=5)

    btn_folder = tk.Button(root, text="Monitor a Folder", command=select_folder, font=("Arial", 10))
    btn_folder.pack(pady=5)

    # Enable drag & drop (only for Windows)
    try:
        root.drop_target_register(tk.DND_FILES)
        root.dnd_bind("<<Drop>>", drop)
    except:
        pass  # Drag & drop might not work on all systems

    root.mainloop()
if __name__ == "__main__":
    create_gui()