import customtkinter as ctk
from tkinter import filedialog, messagebox
import webbrowser
import hashlib
import pandas as pd
import os
import time
import requests
import threading

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


def select_file():
    """Open a file dialog to select a .txt file and display the path."""
    file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
    if file_path:
        selected_file.set(file_path)
        file_line_count.set("Total lines: 0")
        domain_status_textbox.delete(1.0, ctk.END)


def update_timer(start_time):
    """Update the window title with elapsed time."""
    while processing_flag.is_set():
        elapsed_time = int(time.time() - start_time)
        hours, remainder = divmod(elapsed_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        root.title(
            f"P$ych1c Parser v1 | Elapsed time: [{hours:02}:{minutes:02}:{seconds:02}]"
        )
        time.sleep(1)
    root.title("P$ych1c Parser Beta")


def process_file_thread():
    """Run the file processing in a separate thread."""
    try:
        process_file()
    finally:
        processing_flag.clear()


def process_file():
    """Process the selected file and generate the output Excel file."""
    file_path = selected_file.get()
    delimiter = delimiter_var.get()
    ping_parse = ping_parse_var.get()
    filter_keywords = filter_keywords_var.get().split(",")

    if not file_path:
        messagebox.showerror("Error", "Please select a .txt file to process.")
        return

    if not delimiter:
        messagebox.showerror("Error", "Please select a delimiter")
        return

    try:
        start_time = time.time()
        processing_flag.set()
        threading.Thread(target=update_timer, args=(start_time,), daemon=True).start()

        InTxtFile = file_path
        OutFile = os.path.join(os.path.dirname(file_path), "output.xlsx")

        with open(InTxtFile, "r", encoding="utf8") as infile:
            all_lines = infile.readlines()
            total_lines = len(all_lines)

        file_line_count.set(f"Total lines: {total_lines}")

        rows = []
        processed_lines = set()
        domain_status_cache = {}
        valid_lines = []

        def update_gui_cache():
            """Helper function to update the GUI with the current domain status cache."""
            cache_text = "\n".join(
                [
                    f"{domain}: {status}"
                    for domain, status in domain_status_cache.items()
                ]
            )
            domain_status_textbox.delete(1.0, ctk.END)
            domain_status_textbox.insert(ctk.END, cache_text)

        for idx, line in enumerate(all_lines):
            line = line.strip()

            if filter_keywords and not any(
                keyword.strip() in line
                for keyword in filter_keywords
                if keyword.strip()
            ):
                continue

            if line in processed_lines:
                continue
            processed_lines.add(line)

            update_current_line(idx + 1)

            try:
                if line.startswith("http://") or line.startswith("https://"):
                    parts = line.split(delimiter)
                    if len(parts) > 3:
                        url = ":".join(line.split(":")[0:2])
                        valid_lines.append([parts[2], parts[3], url])
                elif delimiter in line:
                    parts = line.split(delimiter, 2)
                    if len(parts) >= 2:
                        valid_lines.append(parts)
            except IndexError:
                print(f"Skipping line {idx + 1} due to insufficient parts: {line}")
                continue

        rows = valid_lines

        if ping_parse == "Yes":
            print("\nStarting website pinging...\n")
            for idx, row in enumerate(rows):
                if len(row) > 2:
                    url = row[2].strip()
                    if url.startswith("http") and not (
                        url.startswith("http://") or url.startswith("https://")
                    ):
                        url = "http://" + url
                        row[2] = url

                    if url.startswith("http://") or url.startswith("https://"):
                        domain = url.split("/", 3)[2]
                        if domain in domain_status_cache:
                            status = domain_status_cache[domain]
                            print(f"Reusing cached status for {url}... [{status}]")
                        else:
                            try:
                                headers = {
                                    "User-Agent": (
                                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                                    )
                                }
                                print(f"Pinging {url}...", end=" ")
                                update_pinging_line(idx + 1)
                                response = requests.get(url, headers=headers, timeout=5)
                                if response.status_code == 200:
                                    status = "Up"
                                else:
                                    status = "Down"
                            except requests.RequestException:
                                status = "Down"

                            domain_status_cache[domain] = status
                            print(f"[{status}]")

                        row.insert(0, status)
                        update_gui_cache()
                    else:
                        print(f"Skipping invalid or missing URL: {url}")
                        row.insert(0, "Invalid URL")
                else:
                    print(f"Skipping row with insufficient data: {row}")
                    row.insert(0, "Invalid URL")
            print("\nWebsite pinging completed.\n")
        else:
            for row in rows:
                row.insert(0, "Skipped")

        down_rows = [row for row in rows if row[0] == "Down"]
        if down_rows:
            delete_prompt = messagebox.askyesno(
                "Delete Non-Responsive Hosts",
                f"{len(down_rows)} hosts did not respond to pings. Do you want to delete these rows?",
            )
            if delete_prompt:
                rows = [row for row in rows if row[0] != "Down"]

        df = pd.DataFrame(rows)
        df.to_excel(OutFile, index=False, header=False)

        end_time = time.time()
        elapsed_time = end_time - start_time
        hours, remainder = divmod(int(elapsed_time), 3600)
        minutes, seconds = divmod(remainder, 60)

        messagebox.showinfo(
            "Success",
            f"Processing complete in {hours:02}:{minutes:02}:{seconds:02}.\nOutput saved to:\n{OutFile}",
        )
        os.startfile(OutFile)

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")


def set_placeholder(entry, placeholder_text):
    """Set placeholder text for a CTkEntry widget."""
    if not entry.get():
        entry.insert(0, placeholder_text)
        entry.configure(text_color="gray")

    def on_focus_in(event):
        if entry.get() == placeholder_text:
            entry.delete(0, "end")
            entry.configure(text_color="white")

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, placeholder_text)
            entry.configure(text_color="gray")

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)


def update_current_line(line_number):
    """Update the current line number being processed."""
    current_line_label.set(f"Processing line: {line_number}")


def update_pinging_line(line_number):
    """Update the line number that is currently being pinged."""
    pinging_line_label.set(f"Pinging line: {line_number}")


def info():
    result = messagebox.askquestion("askquestion", "Made by P$ych1c\nOpen BF Profile?")
    if result == "yes":
        webbrowser.open("https://breachforums.st/User-P$ych1c")


root = ctk.CTk()
root.title("P$ych1c Parser Beta")
root.resizable(False, False)


processing_flag = threading.Event()

selected_file = ctk.StringVar()
delimiter_var = ctk.StringVar()
ping_parse_var = ctk.StringVar(value="No")
filter_keywords_var = ctk.StringVar()
file_line_count = ctk.StringVar(value="Total lines: 0")
current_line_label = ctk.StringVar(value="Processing line: 0")
pinging_line_label = ctk.StringVar(value="Pinging line: None")

ctk.CTkLabel(root, text="Selected File:").grid(
    row=0, column=0, padx=10, pady=5, sticky="w"
)

file_input_frame = ctk.CTkFrame(root)
file_input_frame.grid(row=0, column=1, padx=10, pady=5, sticky="w")

file_entry = ctk.CTkEntry(
    file_input_frame, textvariable=selected_file, width=300, state="readonly"
)
file_entry.pack(side="left", padx=(0, 5))

browse_button = ctk.CTkButton(
    file_input_frame, text="Browse", command=select_file, width=100
)
browse_button.pack(side="left")

ctk.CTkLabel(root, text="Delete lines except:").grid(
    row=1, column=0, padx=10, pady=5, sticky="w"
)
filter_keywords_entry = ctk.CTkEntry(root, textvariable=filter_keywords_var, width=406)
filter_keywords_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")
set_placeholder(filter_keywords_entry, "e.g., password123, wordpress, .com,")

ctk.CTkLabel(root, text="Separating character:").grid(
    row=2, column=0, padx=10, pady=5, sticky="w"
)
delimiter_entry = ctk.CTkEntry(root, textvariable=delimiter_var, width=100)
delimiter_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")
set_placeholder(delimiter_entry, "e.g., : or ,")

ctk.CTkLabel(root, text="Ping http/https websites:").grid(
    row=3, column=0, padx=10, pady=5, sticky="w"
)
checkbox_frame = ctk.CTkFrame(root)
checkbox_frame.grid(row=3, column=1, padx=10, pady=5, sticky="w")

yes_checkbox = ctk.CTkRadioButton(
    checkbox_frame, text="Yes", variable=ping_parse_var, value="Yes"
)
yes_checkbox.pack(side="left", padx=2)

no_checkbox = ctk.CTkRadioButton(
    checkbox_frame, text="No", variable=ping_parse_var, value="No"
)
no_checkbox.pack(side="left", padx=2)

button_frame = ctk.CTkFrame(root)
button_frame.grid(row=4, column=0, columnspan=2, pady=10)

ctk.CTkButton(
    button_frame,
    text="Parse Txt",
    command=lambda: threading.Thread(target=process_file_thread, daemon=True).start(),
    fg_color="red",
).pack(side="left", padx=10)
ctk.CTkButton(button_frame, text="Info", command=info).pack(side="left", padx=10)

info_frame = ctk.CTkFrame(root)
info_frame.grid(row=5, column=0, columnspan=2, pady=5)

ctk.CTkLabel(info_frame, textvariable=file_line_count).pack(side="left", padx=5)
ctk.CTkLabel(info_frame, textvariable=current_line_label).pack(side="left", padx=5)
ctk.CTkLabel(info_frame, textvariable=pinging_line_label).pack(side="left", padx=5)

ctk.CTkLabel(root, text="Ping Results:", font=("Arial", 14)).grid(
    row=6, column=0, columnspan=2, pady=5, sticky="n", padx=10
)

domain_status_textbox = ctk.CTkTextbox(root, width=600, height=200, fg_color="#333333")
domain_status_textbox.grid(row=7, column=0, columnspan=2, padx=10, pady=10)

root.mainloop()
