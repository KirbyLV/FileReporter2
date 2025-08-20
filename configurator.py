import os, sys, subprocess, platform, json, shlex
import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser
import threading
import time

# --- Quiet subprocess helpers (add under imports) ---
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
# --- end helpers ---


APP_SERVICE_NAME = "media"  # the service name in docker-compose
DEFAULT_SHEET_NAME = "Media Repo Inventory"

COMPOSE_TEMPLATE = """
services:
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

COMPOSE_IMAGE = """
services:
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

COMPOSE_BUILD = """
services:
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
    # Prefer "docker compose", fallback to "docker-compose"
    if which("docker") and "compose" in subprocess.getoutput("docker --help"):
        return ["docker", "compose"]
    if which("docker-compose"):
        return ["docker-compose"]
    return None

def run(cmd, cwd=None):
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = []
    for line in p.stdout:
        out.append(line)
        print(line, end="")
    p.wait()
    return p.returncode, "".join(out)

def run_stream(cmd, cwd=None, on_line=None):
    """Run a command and stream lines via callback without blocking the UI."""
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    def pump():
        for line in p.stdout:
            if on_line: on_line(line.rstrip("\n"))
        p.wait()
        if on_line: on_line(f"[process exited {p.returncode}]")
    t = threading.Thread(target=pump, daemon=True)
    t.start()
    return p

class Configurator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Reporter 2 – Configurator")
        self.geometry("920x430")
        self.resizable(True, True)

        # Defaults
        self.repo = tk.StringVar()
        self.show = tk.StringVar()
        self.quarantine = tk.StringVar()
        self.config = tk.StringVar(value=os.path.abspath("./config"))
        self.sheet = tk.StringVar(value=DEFAULT_SHEET_NAME)
        self.sa_json = tk.StringVar(value=os.path.join(self.config.get(), "google-service-account.json"))

        self.repo.trace_add("write", self.update_buttons)
        self.show.trace_add("write", self.update_buttons)
        self.quarantine.trace_add("write", self.update_buttons)
        self.config.trace_add("write", self.update_buttons)
        self.sheet.trace_add("write", self.update_buttons)

        self.deploy_mode = tk.StringVar(value="image")  # "image" or "build"
        self.image_ref = tk.StringVar(value="jspodick/filereporter2:latest")  # <-- set to your Docker Hub image

        # UI
        pad = {'padx': 10, 'pady': 6}
        def row(lbl, var, pick_dir=True):
            f = tk.Frame(self); f.pack(fill="x", **pad)
            tk.Label(f, text=lbl, width=18, anchor="w").pack(side="left")
            e = tk.Entry(f, textvariable=var); e.pack(side="left", fill="x", expand=True, padx=8)
            if pick_dir:
                tk.Button(f, text="Browse…", command=lambda: self.pick_dir(var)).pack(side="left")
            return f

        row("Repo Folder (/repo):", self.repo)
        row("Show Folder (/repo_show):", self.show)
        row("Quarantine Folder (/repo_quarantine):", self.quarantine)
        f = tk.Frame(self); f.pack(fill="x", **pad)
        tk.Label(f, text="Service Account JSON:", width=18, anchor="w").pack(side="left")
        tk.Entry(f, textvariable=self.sa_json).pack(side="left", fill="x", expand=True, padx=8)
        tk.Button(f, text="Browse…", command=lambda: self.pick_file(self.sa_json)).pack(side="left")

        f2 = tk.Frame(self); f2.pack(fill="x", **pad)
        tk.Label(f2, text="Google Sheet Name:", width=18, anchor="w").pack(side="left")
        tk.Entry(f2, textvariable=self.sheet).pack(side="left", fill="x", expand=True, padx=8)

        # Deployment mode
        modef = tk.Frame(self); modef.pack(fill="x", padx=10, pady=6)
        tk.Label(modef, text="Deployment Mode:", width=18, anchor="w").pack(side="left")

        modestrip = tk.Frame(modef); modestrip.pack(side="left", fill="x", expand=True)
        tk.Radiobutton(modestrip, text="Use prebuilt image", variable=self.deploy_mode, value="image",
                       command=self.update_buttons).pack(side="left")
        tk.Radiobutton(modestrip, text="Build locally", variable=self.deploy_mode, value="build",
                       command=self.update_buttons).pack(side="left")

        # Image ref (only used when mode=image)
        imgf = tk.Frame(self); imgf.pack(fill="x", padx=10, pady=6)
        tk.Label(imgf, text="Image (repo:tag):", width=18, anchor="w").pack(side="left")
        tk.Entry(imgf, textvariable=self.image_ref).pack(side="left", fill="x", expand=True, padx=8)

        # Buttons
        bf = tk.Frame(self); bf.pack(fill="x", pady=12, padx=10)
        tk.Button(bf, text="Copy SA JSON to /config", command=self.copy_sa_json).pack(side="left", padx=8)
        self.btn_write = tk.Button(bf, text="Write docker-compose.yml", command=self.write_compose, state="disabled")
        self.btn_write.pack(side="left")
        self.btn_start = tk.Button(bf, text="Start App (docker compose up -d)", command=self.compose_up, state="disabled")
        self.btn_start.pack(side="right")

        """ bf = tk.Frame(self); bf.pack(fill="x", pady=12, padx=10)
        tk.Button(bf, text="Write docker-compose.yml", command=self.write_compose).pack(side="left")
        tk.Button(bf, text="Copy SA JSON to /config", command=self.copy_sa_json).pack(side="left", padx=8)
        tk.Button(bf, text="Start App (docker compose up -d)", command=self.compose_up).pack(side="right") """

        # Control and status
        ctrl = tk.Frame(self); ctrl.pack(fill="x", padx=10, pady=6)

        self.btn_open = tk.Button(ctrl, text="Open Web Portal", command=lambda: webbrowser.open("http://localhost:8008"))
        self.btn_open.pack(side="left")

        self.btn_status = tk.Button(ctrl, text="Refresh Status", command=self.refresh_status)
        self.btn_status.pack(side="left", padx=8)

        self.btn_logs = tk.Button(ctrl, text="View Logs (follow)", command=self.follow_logs)
        self.btn_logs.pack(side="left", padx=8)

        self.btn_stoplogs = tk.Button(ctrl, text="Stop Logs", command=self.stop_logs, state="disabled")
        self.btn_stoplogs.pack(side="left", padx=8)

        self.btn_restart = tk.Button(ctrl, text="Restart App", command=self.compose_restart)
        self.btn_restart.pack(side="right")

        self.btn_stop = tk.Button(ctrl, text="Stop App (docker compose down)", command=self.compose_down)
        self.btn_stop.pack(side="right", padx=8)

        # Status line
        self.status_var = tk.StringVar(value="Status: unknown")
        stat = tk.Label(self, textvariable=self.status_var, anchor="w")
        stat.pack(fill="x", padx=10)


        # Console
        self.console = tk.Text(self, height=10, bg="#111", fg="#e9e", insertbackground="#fff")
        self.console.pack(fill="both", expand=True, padx=10, pady=10)
        self.log("Tip: Ensure Docker Desktop has access to the folders you select (File Sharing).")
        self.log("Directions: Populate all fields, Click on 'Write docker-compose.yml', then 'Start App'. if also pushing to Google Sheets, ensure the service account has access to the sheet and click on 'Copy SA JSON to /config'.")

        self.update_buttons()
        self.log_proc = None
        self.after(2000, self.refresh_status)   # initial status probe
        self.after(5000, self.status_poll)      # start periodic polling


    def all_fields_present(self):
        return all([
            self.repo.get().strip(),
            self.show.get().strip(),
            self.quarantine.get().strip(),
            self.config.get().strip(),
            self.sheet.get().strip(),
        ])

    def update_buttons(self, *_args):
        ready = self.all_fields_present()
        for btn in (self.btn_write, self.btn_start, self.btn_restart, self.btn_stop, self.btn_open, self.btn_status, self.btn_logs):
            try:
                btn.configure(state=("normal" if ready else "disabled"))
            except Exception:
                pass
        """ # Enable write button only if all fields have data
        self.btn_write.configure(state=("normal" if self.all_fields_present() else "disabled"))
        # Optional: also gate Start App
        self.btn_start.configure(state=("normal" if self.all_fields_present() else "disabled")) """


    def log(self, msg):
        self.console.insert("end", msg + "\n"); self.console.see("end"); self.update()

    def pick_dir(self, var):
        d = filedialog.askdirectory()
        if d: var.set(d)
        self.update_buttons()

    def pick_file(self, var):
        f = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if f: var.set(f)
        self.update_buttons()

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
        self.log("✅ Wrote docker-compose.yml (" + ("image" if mode=="image" else "build") + ")")
        self.log(compose_text)

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
            self.log("❌ Docker not found on PATH (need Docker Desktop or docker-compose).")
            return None
        return list(base) + list(args)

    def refresh_status(self):
        cmd = self.docker_cmd("ps", "-q")
        if not cmd: return
        code, out = run_capture(cmd, cwd=os.getcwd())
        running = bool(out.strip())
        self.status_var.set("Status: RUNNING" if running else "Status: STOPPED")
        self.btn_open.configure(state=("normal" if running else "disabled"))

    def status_poll(self):
        # lightweight periodic check; don’t spam logs
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

        # Pull if using prebuilt image
        if self.deploy_mode.get() == "image":
            pull_cmd = cmd_base + ["pull"]
            self.log("Running: " + " ".join(shlex.quote(x) for x in pull_cmd))
            run_quiet(pull_cmd, cwd=os.getcwd())

        up_cmd = cmd_base + ["up", "-d"]
        if self.deploy_mode.get() == "build":
            up_cmd += ["--build"]

        self.log("Running: " + " ".join(shlex.quote(x) for x in up_cmd))
        code = run_quiet(up_cmd, cwd=os.getcwd())

        if code == 0:
            self.log("🚀 App started. Open http://localhost:8008")
        else:
            self.log("❌ docker compose up failed.")

        self.refresh_status()

    def compose_down(self):
        cmd = self.docker_cmd("down")
        if not cmd: return
        self.log("Running: " + " ".join(shlex.quote(x) for x in cmd))
        code = run_quiet(cmd, cwd=os.getcwd())
        if code == 0:
            self.log("🛑 App stopped.")
        else:
            self.log("❌ docker compose down failed.")
        self.refresh_status()

    def compose_restart(self):
        cmd = self.docker_cmd("restart")
        if not cmd: return
        self.log("Running: " + " ".join(shlex.quote(x) for x in cmd))
        code = run_quiet(cmd, cwd=os.getcwd())
        if code == 0:
            self.log("🔁 App restarted.")
        else:
            self.log("❌ docker compose restart failed.")
        self.refresh_status()

    def follow_logs(self):
        if self.log_proc:
            self.log("Logs already following.")
            return
        cmd = self.docker_cmd("logs", "-f", "--tail", "200")
        if not cmd: return
        self.log("Following logs… (click 'Stop Logs' to end)")
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
        self.log("Stopped logs.")



if __name__ == "__main__":
    # macOS hint: ensure /Volumes parent shared with Docker Desktop (File Sharing)
    app = Configurator()
    app.mainloop()
