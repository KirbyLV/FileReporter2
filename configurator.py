"""
FileReporter2 Configurator - CustomTkinter Version
Modern, dark-themed configurator with native file dialogs
"""

import os
import sys
import subprocess
import json
import webbrowser
import threading
import time
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Set appearance mode and default color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")  # We'll override with custom colors

# --- Subprocess helpers ---
def _win_si():
    if os.name != "nt":
        return None, 0
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    flags = subprocess.CREATE_NO_WINDOW
    return si, flags

def run_quiet(cmd, cwd=None):
    si, flags = _win_si()
    return subprocess.run(
        cmd, cwd=cwd,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        text=True,
        startupinfo=si, creationflags=flags
    ).returncode

def run_capture(cmd, cwd=None):
    si, flags = _win_si()
    p = subprocess.run(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
        startupinfo=si, creationflags=flags
    )
    return p.returncode, p.stdout

def run_stream_quiet(cmd, cwd=None, on_line=None):
    si, flags = _win_si()
    p = subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
        startupinfo=si, creationflags=flags
    )
    def pump():
        for line in p.stdout:
            if on_line: on_line(line.rstrip("\n"))
        p.wait()
        if on_line: on_line(f"[process exited {p.returncode}]")
    t = threading.Thread(target=pump, daemon=True)
    t.start()
    return p

# Docker compose templates
APP_SERVICE_NAME = "media"
DEFAULT_SHEET_NAME = "Media Repo Inventory"

COMPOSE_IMAGE = """services:
  media:
    image: {image_ref}
    ports:
      - "8008:8008"
    environment:
      REPO_DIR: /repo
      SHOW_MEDIA_DIR: /repo_show
      QUARANTINE_DIR: /repo_quarantine
      CONFIG_DIR: /config
      GOOGLE_SERVICE_ACCOUNT_JSON: /config/google-service-account.json
      GOOGLE_SHEET_NAME: {sheet_name}
    volumes:
      - "{repo_host}:/repo:rw"
      - "{show_host}:/repo_show:rw"
      - "{quarantine_host}:/repo_quarantine:rw"
      - "./config:/config:rw"
"""

COMPOSE_BUILD = """services:
  media:
    build: .
    ports:
      - "8008:8008"
    environment:
      REPO_DIR: /repo
      SHOW_MEDIA_DIR: /repo_show
      QUARANTINE_DIR: /repo_quarantine
      CONFIG_DIR: /config
      GOOGLE_SERVICE_ACCOUNT_JSON: /config/google-service-account.json
      GOOGLE_SHEET_NAME: {sheet_name}
    volumes:
      - "{repo_host}:/repo:rw"
      - "{show_host}:/repo_show:rw"
      - "{quarantine_host}:/repo_quarantine:rw"
      - "./config:/config:rw"
"""

def which(cmd):
    from shutil import which as w
    return w(cmd)

def docker_compose_cmd():
    if which("docker") and "compose" in subprocess.getoutput("docker --help"):
        return ["docker", "compose"]
    if which("docker-compose"):
        return ["docker-compose"]
    return None


class Configurator(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Custom colors - Dark theme with red/yellow/gold
        self.colors = {
            "bg_dark": "#1a1a1a",
            "bg_medium": "#2a2a2a",
            "bg_light": "#3a3a3a",
            "gold": "#ffd700",
            "amber": "#ffaa00",
            "red": "#ff3333",
            "yellow": "#ffcc00",
            "green": "#4caf50",
            "text": "#e0e0e0",
            "muted": "#999999"
        }

        # Window setup
        self.title("FileReporter2 Configurator")
        self.geometry("1000x700")

        # Variables
        self.repo = ctk.StringVar()
        self.show = ctk.StringVar()
        self.quarantine = ctk.StringVar()
        self.config = ctk.StringVar(value=os.path.abspath("./config"))
        self.sheet = ctk.StringVar(value=DEFAULT_SHEET_NAME)
        self.sa_json = ctk.StringVar(value=os.path.join(self.config.get(), "google-service-account.json"))
        self.deploy_mode = ctk.StringVar(value="image")
        self.image_ref = ctk.StringVar(value="jspodick/filereporter2:latest")

        # Trace variables to update buttons
        for var in [self.repo, self.show, self.quarantine, self.config, self.sheet]:
            var.trace_add("write", self.update_buttons)

        self.log_proc = None

        # Build UI
        self.create_widgets()
        self.update_buttons()

        # Start status polling
        self.after(2000, self.refresh_status)
        self.after(5000, self.status_poll)

    def create_widgets(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=self.colors["bg_medium"], corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)

        title = ctk.CTkLabel(
            header,
            text="FileReporter2 Configurator",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=self.colors["gold"]
        )
        title.pack(pady=20)

        subtitle = ctk.CTkLabel(
            header,
            text="Configure and manage your FileReporter2 Docker container",
            font=ctk.CTkFont(size=14),
            text_color=self.colors["amber"]
        )
        subtitle.pack(pady=(0, 20))

        # Status bar
        status_frame = ctk.CTkFrame(self, fg_color=self.colors["bg_dark"], corner_radius=0)
        status_frame.pack(fill="x", padx=0, pady=0)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Status: Unknown",
            font=ctk.CTkFont(size=12),
            text_color=self.colors["text"]
        )
        self.status_label.pack(side="left", padx=20, pady=10)

        # Main content area with scrolling
        main_container = ctk.CTkScrollableFrame(self, fg_color=self.colors["bg_dark"])
        main_container.pack(fill="both", expand=True, padx=0, pady=0)

        # Configuration section
        config_frame = ctk.CTkFrame(main_container, fg_color=self.colors["bg_medium"])
        config_frame.pack(fill="x", padx=20, pady=(20, 10))

        section_label = ctk.CTkLabel(
            config_frame,
            text="Directory Configuration",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors["gold"]
        )
        section_label.pack(anchor="w", padx=20, pady=(15, 10))

        # Directory inputs
        self.create_dir_input(config_frame, "Repo Folder (/repo):", self.repo)
        self.create_dir_input(config_frame, "Show Folder (/repo_show):", self.show)
        self.create_dir_input(config_frame, "Quarantine Folder (/repo_quarantine):", self.quarantine)

        # Service account
        self.create_file_input(config_frame, "Service Account JSON:", self.sa_json)

        # Sheet name
        sheet_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        sheet_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            sheet_frame,
            text="Google Sheet Name:",
            font=ctk.CTkFont(size=13),
            text_color=self.colors["amber"],
            width=200,
            anchor="w"
        ).pack(side="left", padx=(0, 10))

        ctk.CTkEntry(
            sheet_frame,
            textvariable=self.sheet,
            fg_color=self.colors["bg_dark"],
            border_color=self.colors["gold"],
            text_color=self.colors["text"]
        ).pack(side="left", fill="x", expand=True)

        # Deployment mode
        deploy_frame = ctk.CTkFrame(main_container, fg_color=self.colors["bg_medium"])
        deploy_frame.pack(fill="x", padx=20, pady=10)

        section_label2 = ctk.CTkLabel(
            deploy_frame,
            text="Deployment Mode",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors["gold"]
        )
        section_label2.pack(anchor="w", padx=20, pady=(15, 10))

        radio_frame = ctk.CTkFrame(deploy_frame, fg_color="transparent")
        radio_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkRadioButton(
            radio_frame,
            text="Use Prebuilt Image",
            variable=self.deploy_mode,
            value="image",
            fg_color=self.colors["gold"],
            hover_color=self.colors["amber"],
            text_color=self.colors["text"]
        ).pack(side="left", padx=(0, 20))

        ctk.CTkRadioButton(
            radio_frame,
            text="Build Locally",
            variable=self.deploy_mode,
            value="build",
            fg_color=self.colors["gold"],
            hover_color=self.colors["amber"],
            text_color=self.colors["text"]
        ).pack(side="left")

        # Image reference
        img_frame = ctk.CTkFrame(deploy_frame, fg_color="transparent")
        img_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(
            img_frame,
            text="Image (repo:tag):",
            font=ctk.CTkFont(size=13),
            text_color=self.colors["amber"],
            width=200,
            anchor="w"
        ).pack(side="left", padx=(0, 10))

        ctk.CTkEntry(
            img_frame,
            textvariable=self.image_ref,
            fg_color=self.colors["bg_dark"],
            border_color=self.colors["gold"],
            text_color=self.colors["text"]
        ).pack(side="left", fill="x", expand=True)

        # Action buttons
        btn_frame = ctk.CTkFrame(main_container, fg_color=self.colors["bg_medium"])
        btn_frame.pack(fill="x", padx=20, pady=10)

        section_label3 = ctk.CTkLabel(
            btn_frame,
            text="Actions",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors["gold"]
        )
        section_label3.pack(anchor="w", padx=20, pady=(15, 10))

        actions1 = ctk.CTkFrame(btn_frame, fg_color="transparent")
        actions1.pack(fill="x", padx=20, pady=5)

        self.btn_copy_sa = ctk.CTkButton(
            actions1,
            text="Copy SA JSON to /config",
            command=self.copy_sa_json,
            fg_color=self.colors["bg_light"],
            hover_color=self.colors["bg_dark"],
            border_color=self.colors["amber"],
            border_width=2,
            text_color=self.colors["amber"]
        )
        self.btn_copy_sa.pack(side="left", padx=5)

        self.btn_write = ctk.CTkButton(
            actions1,
            text="Write docker-compose.yml",
            command=self.write_compose,
            fg_color=self.colors["gold"],
            hover_color=self.colors["amber"],
            text_color="#000000"
        )
        self.btn_write.pack(side="left", padx=5)

        self.btn_start = ctk.CTkButton(
            actions1,
            text="Start App",
            command=self.compose_up,
            fg_color=self.colors["green"],
            hover_color="#3a8e3a",
            text_color="white"
        )
        self.btn_start.pack(side="right", padx=5)

        actions2 = ctk.CTkFrame(btn_frame, fg_color="transparent")
        actions2.pack(fill="x", padx=20, pady=5)

        self.btn_stop = ctk.CTkButton(
            actions2,
            text="Stop App",
            command=self.compose_down,
            fg_color=self.colors["red"],
            hover_color="#cc0000",
            text_color="white"
        )
        self.btn_stop.pack(side="left", padx=5)

        self.btn_restart = ctk.CTkButton(
            actions2,
            text="Restart App",
            command=self.compose_restart,
            fg_color=self.colors["yellow"],
            hover_color="#cc9900",
            text_color="#000000"
        )
        self.btn_restart.pack(side="left", padx=5)

        self.btn_open = ctk.CTkButton(
            actions2,
            text="Open Web Portal",
            command=lambda: webbrowser.open("http://localhost:8008"),
            fg_color=self.colors["bg_light"],
            hover_color=self.colors["bg_dark"],
            border_color=self.colors["gold"],
            border_width=2,
            text_color=self.colors["gold"]
        )
        self.btn_open.pack(side="right", padx=5)

        actions3 = ctk.CTkFrame(btn_frame, fg_color="transparent")
        actions3.pack(fill="x", padx=20, pady=(5, 15))

        self.btn_status = ctk.CTkButton(
            actions3,
            text="Refresh Status",
            command=self.refresh_status,
            fg_color=self.colors["bg_light"],
            hover_color=self.colors["bg_dark"],
            border_color=self.colors["muted"],
            border_width=1,
            text_color=self.colors["text"]
        )
        self.btn_status.pack(side="left", padx=5)

        self.btn_logs = ctk.CTkButton(
            actions3,
            text="View Logs",
            command=self.follow_logs,
            fg_color=self.colors["bg_light"],
            hover_color=self.colors["bg_dark"],
            border_color=self.colors["muted"],
            border_width=1,
            text_color=self.colors["text"]
        )
        self.btn_logs.pack(side="left", padx=5)

        self.btn_stoplogs = ctk.CTkButton(
            actions3,
            text="Stop Logs",
            command=self.stop_logs,
            fg_color=self.colors["bg_light"],
            hover_color=self.colors["bg_dark"],
            border_color=self.colors["muted"],
            border_width=1,
            text_color=self.colors["text"],
            state="disabled"
        )
        self.btn_stoplogs.pack(side="left", padx=5)

        # Console
        console_frame = ctk.CTkFrame(main_container, fg_color=self.colors["bg_medium"])
        console_frame.pack(fill="both", expand=True, padx=20, pady=10)

        console_label = ctk.CTkLabel(
            console_frame,
            text="Console Output",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors["gold"]
        )
        console_label.pack(anchor="w", padx=20, pady=(15, 10))

        self.console = ctk.CTkTextbox(
            console_frame,
            fg_color="#0a0a0a",
            text_color=self.colors["green"],
            font=ctk.CTkFont(family="Courier", size=11),
            wrap="word"
        )
        self.console.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.log("FileReporter2 Configurator Ready")
        self.log("Tip: Ensure Docker Desktop has access to your selected folders")
        self.log("Populate all fields, write docker-compose.yml, then start the app")

    def create_dir_input(self, parent, label_text, variable):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=10)

        label = ctk.CTkLabel(
            frame,
            text=label_text,
            font=ctk.CTkFont(size=13),
            text_color=self.colors["amber"],
            width=200,
            anchor="w"
        )
        label.pack(side="left", padx=(0, 10))

        entry = ctk.CTkEntry(
            frame,
            textvariable=variable,
            fg_color=self.colors["bg_dark"],
            border_color=self.colors["gold"],
            text_color=self.colors["text"]
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        btn = ctk.CTkButton(
            frame,
            text="Browse",
            command=lambda: self.pick_dir(variable),
            width=100,
            fg_color=self.colors["bg_light"],
            hover_color=self.colors["bg_dark"],
            border_color=self.colors["gold"],
            border_width=1,
            text_color=self.colors["gold"]
        )
        btn.pack(side="left")

    def create_file_input(self, parent, label_text, variable):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=10)

        label = ctk.CTkLabel(
            frame,
            text=label_text,
            font=ctk.CTkFont(size=13),
            text_color=self.colors["amber"],
            width=200,
            anchor="w"
        )
        label.pack(side="left", padx=(0, 10))

        entry = ctk.CTkEntry(
            frame,
            textvariable=variable,
            fg_color=self.colors["bg_dark"],
            border_color=self.colors["gold"],
            text_color=self.colors["text"]
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        btn = ctk.CTkButton(
            frame,
            text="Browse",
            command=lambda: self.pick_file(variable),
            width=100,
            fg_color=self.colors["bg_light"],
            hover_color=self.colors["bg_dark"],
            border_color=self.colors["gold"],
            border_width=1,
            text_color=self.colors["gold"]
        )
        btn.pack(side="left")

    def log(self, msg):
        self.console.insert("end", msg + "\n")
        self.console.see("end")

    def pick_dir(self, var):
        d = filedialog.askdirectory()
        if d:
            var.set(d)
        self.update_buttons()

    def pick_file(self, var):
        f = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if f:
            var.set(f)
        self.update_buttons()

    def all_fields_present(self):
        return all([
            self.repo.get().strip(),
            self.show.get().strip(),
            self.quarantine.get().strip(),
            self.config.get().strip(),
            self.sheet.get().strip(),
        ])

    def update_buttons(self, *args):
        ready = self.all_fields_present()
        state = "normal" if ready else "disabled"

        for btn in [self.btn_write, self.btn_start, self.btn_restart,
                    self.btn_stop, self.btn_open, self.btn_status, self.btn_logs]:
            btn.configure(state=state)

    def validate(self):
        missing = []
        for label, path in [("Repo", self.repo.get()), ("Show", self.show.get()),
                            ("Quarantine", self.quarantine.get()), ("Config", self.config.get())]:
            if not path:
                missing.append(label)
            elif not os.path.isdir(path):
                messagebox.showerror("Invalid Path", f"{label} folder does not exist:\n{path}")
                return False
        if not self.sheet.get().strip():
            messagebox.showerror("Missing Sheet Name", "Please enter a Google Sheet name.")
            return False
        return True

    def write_compose(self):
        if not self.validate(): return
        mode = self.deploy_mode.get()
        template = COMPOSE_IMAGE if mode == "image" else COMPOSE_BUILD
        compose_text = template.format(
            image_ref=self.image_ref.get(),
            repo_host=self.repo.get(),
            show_host=self.show.get(),
            quarantine_host=self.quarantine.get(),
            config_host=self.config.get(),
            sheet_name=self.sheet.get().replace('"', '\\"')
        )
        with open("docker-compose.yml", "w", encoding="utf-8") as f:
            f.write(compose_text)
        self.log(f"✅ Wrote docker-compose.yml ({mode} mode)")

    def copy_sa_json(self):
        src = self.sa_json.get()
        if not src or not os.path.isfile(src):
            messagebox.showerror("Missing JSON", "Pick a valid Service Account JSON file.")
            return
        os.makedirs(self.config.get(), exist_ok=True)
        dst = os.path.join(self.config.get(), "google-service-account.json")
        try:
            with open(src, "rb") as s, open(dst, "wb") as d:
                d.write(s.read())
            self.log(f"✅ Copied service account to: {dst}")
        except Exception as e:
            messagebox.showerror("Copy Failed", str(e))

    def docker_cmd(self, *args):
        base = docker_compose_cmd()
        if not base:
            self.log("❌ Docker not found on PATH")
            return None
        return list(base) + list(args)

    def refresh_status(self):
        cmd = self.docker_cmd("ps", "-q")
        if not cmd: return
        code, out = run_capture(cmd, cwd=os.getcwd())
        running = bool(out.strip())
        status_text = "Status: RUNNING ✓" if running else "Status: STOPPED ○"
        self.status_label.configure(
            text=status_text,
            text_color=self.colors["green"] if running else self.colors["red"]
        )

    def status_poll(self):
        try:
            self.refresh_status()
        finally:
            self.after(5000, self.status_poll)

    def compose_up(self):
        if not os.path.isfile("docker-compose.yml"):
            self.write_compose()
        cmd_base = self.docker_cmd()
        if not cmd_base:
            messagebox.showerror("Docker not found", "Need Docker Desktop / docker compose.")
            return

        if self.deploy_mode.get() == "image":
            pull_cmd = cmd_base + ["pull"]
            self.log(f"Pulling image...")
            run_quiet(pull_cmd, cwd=os.getcwd())

        up_cmd = cmd_base + ["up", "-d"]
        if self.deploy_mode.get() == "build":
            up_cmd += ["--build"]

        self.log(f"Starting app...")
        code = run_quiet(up_cmd, cwd=os.getcwd())

        if code == 0:
            self.log("🚀 App started. Open http://localhost:8008")
        else:
            self.log("❌ docker compose up failed")

        self.refresh_status()

    def compose_down(self):
        cmd = self.docker_cmd("down")
        if not cmd: return
        self.log("Stopping app...")
        code = run_quiet(cmd, cwd=os.getcwd())
        if code == 0:
            self.log("🛑 App stopped")
        else:
            self.log("❌ docker compose down failed")
        self.refresh_status()

    def compose_restart(self):
        cmd = self.docker_cmd("restart")
        if not cmd: return
        self.log("Restarting app...")
        code = run_quiet(cmd, cwd=os.getcwd())
        if code == 0:
            self.log("🔁 App restarted")
        else:
            self.log("❌ docker compose restart failed")
        self.refresh_status()

    def follow_logs(self):
        if self.log_proc:
            self.log("Logs already following")
            return
        cmd = self.docker_cmd("logs", "-f", "--tail", "200")
        if not cmd: return
        self.log("Following logs... (click 'Stop Logs' to end)")
        self.btn_logs.configure(state="disabled")
        self.btn_stoplogs.configure(state="normal")
        def on_line(line): self.log(line)
        self.log_proc = run_stream_quiet(cmd, cwd=os.getcwd(), on_line=on_line)

    def stop_logs(self):
        if not self.log_proc: return
        try:
            self.log_proc.terminate()
        except Exception:
            pass
        self.log_proc = None
        self.btn_logs.configure(state="normal")
        self.btn_stoplogs.configure(state="disabled")
        self.log("Stopped logs")


if __name__ == "__main__":
    app = Configurator()
    app.mainloop()
