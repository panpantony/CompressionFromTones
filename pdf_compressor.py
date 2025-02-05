#DEBUG
import tkinter as tk
from tkinter import filedialog, messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

import os
import subprocess

def compress_pdf(file_path, quality="screen"):
    """
    Compress a PDF using Ghostscript.
    Quality options: "screen", "ebook", "printer", "prepress".
    """
    try:
        output_file = file_path.replace(".pdf", "_compressed.pdf")

        # Ghostscript command to compress the PDF
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

        # Run the command
        subprocess.run(gs_command, check=True)

        # Replace original file with the compressed version
        os.replace(output_file, file_path)

        print(f"✅ Compressed PDF saved: {file_path}")
        return True
    except Exception as e:
        print(f"❌ Error compressing {file_path}: {e}")
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