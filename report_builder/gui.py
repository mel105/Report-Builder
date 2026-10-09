"""Tkinter window: pick the input, see which profiles find data, build the report."""
import json
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, ttk

from . import __version__
from .core.build import build_report, scan
from .profiles import load_all

SETTINGS = Path.home() / ".report_builder.json"
FIELDS = ("input", "template", "out", "author", "status", "profile")


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _open(path: Path) -> None:
    """Open a file or folder with the system's default application."""
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606 - user's own file
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class App(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, padding=12)
        self.root = root
        self.profiles = load_all()
        self.result = None
        self.jobs: queue.Queue = queue.Queue()
        saved = _load_settings()
        self.var = {name: tk.StringVar(value=saved.get(name, "")) for name in FIELDS}
        if not self.var["status"].get():
            self.var["status"].set("Draft")
        if not self.var["out"].get():
            self.var["out"].set(str(Path.home() / "report_out"))
        self._layout()
        self.var["input"].trace_add("write", lambda *_: self._schedule_scan())
        self._scan_job = None
        self._scan()
        root.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll)

    # ------------------------------------------------------------------ layout
    def _layout(self) -> None:
        self.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        def path_row(row, label, key, folder=False, file=False, filetypes=None):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(self, textvariable=self.var[key]).grid(row=row, column=1, sticky="ew", padx=6)
            buttons = ttk.Frame(self)
            buttons.grid(row=row, column=2, sticky="e")
            if folder:
                ttk.Button(buttons, text="Folder…", width=9,
                           command=lambda: self._pick_folder(key)).pack(side="left")
            if file:
                ttk.Button(buttons, text="File…", width=9,
                           command=lambda: self._pick_file(key, filetypes)).pack(side="left", padx=(4, 0))

        path_row(0, "Input", "input", folder=True, file=True,
                 filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        ttk.Label(self, text="Campaign folder (contains TXT/) or a *_protocol.json of anomaly_mapper",
                  foreground="#666").grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(self, text="Report type").grid(row=2, column=0, sticky="nw", pady=(10, 3))
        self.tree = ttk.Treeview(self, columns=("data", "desc"), show="tree headings", height=4,
                                 selectmode="browse")
        self.tree.heading("#0", text="Profile")
        self.tree.heading("data", text="Data")
        self.tree.heading("desc", text="Description")
        self.tree.column("#0", width=170, stretch=False)
        self.tree.column("data", width=90, stretch=False, anchor="center")
        self.tree.column("desc", width=460)
        self.tree.tag_configure("missing", foreground="#999")
        self.tree.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=(10, 3))
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_buttons())

        path_row(3, "Template", "template", file=True,
                 filetypes=[("Word template", "*.docx"), ("All files", "*.*")])
        path_row(4, "Output folder", "out", folder=True)

        ttk.Label(self, text="Author").grid(row=5, column=0, sticky="w", pady=3)
        meta = ttk.Frame(self)
        meta.grid(row=5, column=1, columnspan=2, sticky="ew", padx=6)
        meta.columnconfigure(0, weight=1)
        ttk.Entry(meta, textvariable=self.var["author"]).grid(row=0, column=0, sticky="ew")
        ttk.Label(meta, text="Status").grid(row=0, column=1, padx=(12, 6))
        ttk.Combobox(meta, textvariable=self.var["status"], values=("Draft", "Final"), width=8,
                     state="readonly").grid(row=0, column=2)

        actions = ttk.Frame(self)
        actions.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(12, 6))
        self.btn_build = ttk.Button(actions, text="Build report", command=self._build)
        self.btn_build.pack(side="left")
        self.btn_open = ttk.Button(actions, text="Open report", command=lambda: _open(self.result.report),
                                   state="disabled")
        self.btn_open.pack(side="left", padx=6)
        self.btn_folder = ttk.Button(actions, text="Open output folder",
                                     command=lambda: _open(self.result.out_dir), state="disabled")
        self.btn_folder.pack(side="left")
        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=140)
        self.progress.pack(side="right")

        self.log = tk.Text(self, height=12, wrap="word", state="disabled", relief="solid", borderwidth=1)
        self.log.grid(row=7, column=0, columnspan=3, sticky="nsew")
        self.log.tag_configure("warn", foreground="#a15c00")
        self.log.tag_configure("error", foreground="#b3261e")
        self.log.tag_configure("ok", foreground="#1b6e3c")
        self.rowconfigure(7, weight=1)

    # ------------------------------------------------------------------ actions
    def _pick_folder(self, key: str) -> None:
        start = self.var[key].get() or str(Path.home())
        chosen = filedialog.askdirectory(initialdir=start if Path(start).exists() else str(Path.home()))
        if chosen:
            self.var[key].set(chosen)

    def _pick_file(self, key: str, filetypes) -> None:
        current = Path(self.var[key].get()) if self.var[key].get() else Path.home()
        start = current if current.is_dir() else current.parent
        chosen = filedialog.askopenfilename(initialdir=str(start) if start.exists() else str(Path.home()),
                                            filetypes=filetypes)
        if chosen:
            self.var[key].set(chosen)

    def _schedule_scan(self) -> None:
        if self._scan_job:
            self.after_cancel(self._scan_job)
        self._scan_job = self.after(400, self._scan)   # wait until typing stops

    def _scan(self) -> None:
        self._scan_job = None
        text = self.var["input"].get().strip()
        path = Path(text) if text else None
        found = scan(self.profiles, path if path and path.exists() else None)
        wanted = self.tree.selection()[0] if self.tree.selection() else self.var["profile"].get()
        self.tree.delete(*self.tree.get_children())
        for name, prof in self.profiles.items():
            self.tree.insert("", "end", iid=name, text=name,
                             values=("found" if found[name] else "–", prof.DESCRIPTION),
                             tags=() if found[name] else ("missing",))
        available = [n for n, ok in found.items() if ok]
        pick = wanted if wanted in available else (available[0] if available else None)
        if pick:
            self.tree.selection_set(pick)
        self._update_buttons()

    def _selected(self):
        sel = self.tree.selection()
        if not sel or "missing" in self.tree.item(sel[0], "tags"):
            return None
        return sel[0]

    def _update_buttons(self) -> None:
        self.btn_build.configure(state="normal" if self._selected() else "disabled")

    def _say(self, text: str, tag: str = "") -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _build(self) -> None:
        name = self._selected()
        if not name:
            return
        self._save_settings()
        args = dict(prof=self.profiles[name], input_path=Path(self.var["input"].get().strip()),
                    out_root=Path(self.var["out"].get().strip() or "report_out"),
                    template=Path(self.var["template"].get().strip()) if self.var["template"].get().strip() else None,
                    author=self.var["author"].get().strip(), status=self.var["status"].get())
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._say(f"Building '{name}' …")
        if args["template"] is None:
            self._say("No template selected: the report gets no title page or company header.", "warn")
        self.btn_build.configure(state="disabled")
        self.progress.start(12)

        def work():
            try:
                self.jobs.put(("done", build_report(**args)))
            except ValueError as exc:
                self.jobs.put(("error", str(exc)))
            except Exception:   # show unexpected failures instead of dying silently
                self.jobs.put(("error", traceback.format_exc()))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self) -> None:
        try:
            kind, payload = self.jobs.get_nowait()
        except queue.Empty:
            self.after(100, self._poll)
            return
        self.progress.stop()
        self._update_buttons()
        if kind == "error":
            self._say(payload, "error")
        else:
            self.result = payload
            self._say(f"Done: {payload.tables} tables, {payload.figures} figures", "ok")
            self._say(f"Report : {payload.report}")
            self._say(f"Tables : {payload.out_dir / 'tables'}")
            self._say(f"Figures: {payload.out_dir / 'figures'}")
            if payload.warnings:
                self._say(f"\n{len(payload.warnings)} data warning(s), also listed in the report:", "warn")
                for w in payload.warnings:
                    self._say(f"  • {w}", "warn")
            self.btn_open.configure(state="normal")
            self.btn_folder.configure(state="normal")
        self.after(100, self._poll)

    def _save_settings(self) -> None:
        data = {k: v.get() for k, v in self.var.items()}
        data["profile"] = self._selected() or data.get("profile", "")
        try:
            SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _close(self) -> None:
        self._save_settings()
        self.root.destroy()


def run() -> int:
    root = tk.Tk()
    root.title(f"Report Builder {__version__}")
    root.minsize(760, 520)
    try:
        ttk.Style().theme_use("clam" if sys.platform.startswith("linux") else ttk.Style().theme_use())
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
    return 0
