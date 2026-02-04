#!/usr/bin/env python3
"""
Invoice Generator - Cross-Platform Desktop Application
Works on Windows, Mac, and Linux.
Upload a PO screenshot and generate a PDF invoice with one click.
"""

import os
import sys
import platform
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_invoice import extract_po_data

# Import pdf_filler
import importlib.util
spec = importlib.util.spec_from_file_location('pdf_filler',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils', 'pdf_filler.py'))
pdf_filler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdf_filler)


def open_file(filepath):
    """Open a file with the default system application."""
    system = platform.system()
    if system == 'Windows':
        os.startfile(filepath)
    elif system == 'Darwin':  # macOS
        subprocess.run(['open', filepath])
    else:  # Linux
        subprocess.run(['xdg-open', filepath])


def get_desktop_path():
    """Get the user's desktop path cross-platform."""
    if platform.system() == 'Windows':
        return os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')
    else:
        return os.path.expanduser("~/Desktop")


class InvoiceGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Invoice Generator")
        self.root.geometry("500x400")
        self.root.resizable(False, False)

        # Set app style
        self.root.configure(bg="#f0f0f0")

        # Variables
        self.selected_file = tk.StringVar()
        self.status_text = tk.StringVar(value="Select a PO screenshot to get started")

        self.create_widgets()

    def create_widgets(self):
        # Main container
        main_frame = tk.Frame(self.root, bg="#f0f0f0", padx=30, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            main_frame,
            text="Invoice Generator",
            font=("Helvetica", 24, "bold"),
            bg="#f0f0f0",
            fg="#2c3e50"
        )
        title_label.pack(pady=(0, 5))

        # Subtitle
        subtitle_label = tk.Label(
            main_frame,
            text="Convert PO screenshots to PDF invoices",
            font=("Helvetica", 12),
            bg="#f0f0f0",
            fg="#7f8c8d"
        )
        subtitle_label.pack(pady=(0, 30))

        # File selection frame
        file_frame = tk.Frame(main_frame, bg="#f0f0f0")
        file_frame.pack(fill=tk.X, pady=10)

        # File entry
        self.file_entry = tk.Entry(
            file_frame,
            textvariable=self.selected_file,
            font=("Helvetica", 11),
            state="readonly",
            width=35
        )
        self.file_entry.pack(side=tk.LEFT, padx=(0, 10))

        # Browse button
        browse_btn = tk.Button(
            file_frame,
            text="Browse...",
            command=self.browse_file,
            font=("Helvetica", 11),
            bg="#3498db",
            fg="white",
            padx=15,
            pady=5,
            cursor="hand2"
        )
        browse_btn.pack(side=tk.LEFT)

        # Preview frame (shows selected filename)
        self.preview_frame = tk.Frame(main_frame, bg="#ecf0f1", padx=15, pady=15)
        self.preview_frame.pack(fill=tk.X, pady=20)

        self.preview_label = tk.Label(
            self.preview_frame,
            text="No file selected",
            font=("Helvetica", 10),
            bg="#ecf0f1",
            fg="#7f8c8d"
        )
        self.preview_label.pack()

        # Generate button
        self.generate_btn = tk.Button(
            main_frame,
            text="Generate Invoice",
            command=self.generate_invoice,
            font=("Helvetica", 14, "bold"),
            bg="#27ae60",
            fg="white",
            padx=30,
            pady=12,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.generate_btn.pack(pady=20)

        # Status label
        self.status_label = tk.Label(
            main_frame,
            textvariable=self.status_text,
            font=("Helvetica", 10),
            bg="#f0f0f0",
            fg="#7f8c8d",
            wraplength=400
        )
        self.status_label.pack(pady=10)

        # Progress bar (hidden by default)
        self.progress = ttk.Progressbar(
            main_frame,
            mode='indeterminate',
            length=300
        )

    def browse_file(self):
        filetypes = [
            ("Image files", "*.png *.jpg *.jpeg *.PNG *.JPG *.JPEG"),
            ("All files", "*.*")
        ]

        filename = filedialog.askopenfilename(
            title="Select PO Screenshot",
            filetypes=filetypes,
            initialdir=get_desktop_path()
        )

        if filename:
            self.selected_file.set(filename)
            self.preview_label.config(
                text=f"Selected: {Path(filename).name}",
                fg="#2c3e50"
            )
            self.generate_btn.config(state=tk.NORMAL)
            self.status_text.set("Ready to generate invoice")

    def generate_invoice(self):
        if not self.selected_file.get():
            messagebox.showwarning("No File", "Please select a PO screenshot first.")
            return

        # Update UI
        self.generate_btn.config(state=tk.DISABLED)
        self.status_text.set("Processing image with OCR...")
        self.progress.pack(pady=10)
        self.progress.start(10)
        self.root.update()

        try:
            image_path = self.selected_file.get()

            # Extract data from screenshot
            self.status_text.set("Extracting data from screenshot...")
            self.root.update()
            payload = extract_po_data(image_path)

            # Generate output path
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
            os.makedirs(output_dir, exist_ok=True)

            stem = Path(image_path).stem
            output_path = os.path.join(output_dir, f"{stem}_invoice.pdf")

            # Get template path
            template_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'templates',
                'blank template.pdf'
            )

            # Generate PDF
            self.status_text.set("Generating PDF invoice...")
            self.root.update()

            invoice_number = pdf_filler.fill_invoice_template(
                payload,
                template_path,
                output_path
            )

            # Stop progress
            self.progress.stop()
            self.progress.pack_forget()

            # Success
            self.status_text.set(f"Invoice generated: {invoice_number}")
            self.status_label.config(fg="#27ae60")

            # Ask to open
            if messagebox.askyesno("Success",
                f"Invoice {invoice_number} generated successfully!\n\n"
                f"Saved to: {output_path}\n\n"
                "Would you like to open it?"):
                open_file(output_path)

        except Exception as e:
            self.progress.stop()
            self.progress.pack_forget()
            self.status_text.set(f"Error: {str(e)}")
            self.status_label.config(fg="#e74c3c")
            messagebox.showerror("Error", f"Failed to generate invoice:\n\n{str(e)}")

        finally:
            self.generate_btn.config(state=tk.NORMAL)


def main():
    root = tk.Tk()

    # Center window on screen
    root.update_idletasks()
    width = 500
    height = 400
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

    app = InvoiceGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
