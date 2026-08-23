#!/usr/bin/env python3
"""Desktop audio player and converter for local or authorized media files."""

from __future__ import annotations

import shutil
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


AUDIO_EXTENSIONS = (
    ".aac",
    ".aiff",
    ".alac",
    ".flac",
    ".m4a",
    ".mka",
    ".mp3",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
)

MEDIA_EXTENSIONS = AUDIO_EXTENSIONS + (
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".webm",
)

CONVERSION_PROFILES = {
    "mp3": ["-vn", "-codec:a", "libmp3lame", "-b:a", "320k"],
    "m4a": ["-vn", "-codec:a", "aac", "-b:a", "192k"],
    "wav": ["-vn", "-codec:a", "pcm_s16le"],
    "flac": ["-vn", "-codec:a", "flac"],
    "ogg": ["-vn", "-codec:a", "libvorbis", "-q:a", "5"],
}


@dataclass
class MediaTools:
    ffmpeg: str | None
    ffplay: str | None
    afplay: str | None

    @property
    def player(self) -> str | None:
        return self.ffplay or self.afplay


class AudioPlayerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Audio Player")
        self.geometry("860x560")
        self.minsize(760, 500)

        self.tools = MediaTools(
            ffmpeg=shutil.which("ffmpeg"),
            ffplay=shutil.which("ffplay"),
            afplay=shutil.which("afplay"),
        )
        self.playlist: list[Path] = []
        self.active_index = -1
        self.play_process: subprocess.Popen[str] | None = None
        self.monitor_thread: threading.Thread | None = None
        self.stop_requested = False

        self._build_ui()
        self._refresh_tool_status()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(18, 16, 18, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = ttk.Label(header, text="Audio Player", font=("TkDefaultFont", 24, "bold"))
        title.grid(row=0, column=0, sticky="w")

        self.tool_status = ttk.Label(header, text="", foreground="#5b6670")
        self.tool_status.grid(row=1, column=0, sticky="w", pady=(4, 0))

        add_button = ttk.Button(header, text="Add Files", command=self.add_files)
        add_button.grid(row=0, column=1, rowspan=2, padx=(14, 0))

        main = ttk.Frame(self, padding=(18, 8, 18, 18))
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        playlist_panel = ttk.Frame(main)
        playlist_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        playlist_panel.rowconfigure(1, weight=1)
        playlist_panel.columnconfigure(0, weight=1)

        ttk.Label(playlist_panel, text="Playlist", font=("TkDefaultFont", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        list_frame = ttk.Frame(playlist_panel)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.playlist_listbox = tk.Listbox(
            list_frame,
            activestyle="dotbox",
            borderwidth=1,
            exportselection=False,
            highlightthickness=0,
            selectmode=tk.BROWSE,
        )
        self.playlist_listbox.grid(row=0, column=0, sticky="nsew")
        self.playlist_listbox.bind("<Double-Button-1>", lambda _event: self.play_selected())

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.playlist_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.playlist_listbox.configure(yscrollcommand=scrollbar.set)

        controls = ttk.Frame(playlist_panel)
        controls.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        controls.columnconfigure((0, 1, 2, 3), weight=1)

        ttk.Button(controls, text="Previous", command=self.play_previous).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(controls, text="Play", command=self.play_selected).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(controls, text="Stop", command=self.stop_playback).grid(row=0, column=2, sticky="ew", padx=6)
        ttk.Button(controls, text="Next", command=self.play_next).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        tools_panel = ttk.Frame(main)
        tools_panel.grid(row=0, column=1, sticky="nsew")
        tools_panel.columnconfigure(0, weight=1)

        ttk.Label(tools_panel, text="Convert", font=("TkDefaultFont", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        ttk.Label(tools_panel, text="Output format").grid(row=1, column=0, sticky="w")
        self.format_var = tk.StringVar(value="mp3")
        format_picker = ttk.Combobox(
            tools_panel,
            textvariable=self.format_var,
            values=tuple(CONVERSION_PROFILES.keys()),
            state="readonly",
        )
        format_picker.grid(row=2, column=0, sticky="ew", pady=(4, 12))

        self.output_dir_var = tk.StringVar(value=str(Path.home() / "Music"))
        ttk.Label(tools_panel, text="Output folder").grid(row=3, column=0, sticky="w")

        output_row = ttk.Frame(tools_panel)
        output_row.grid(row=4, column=0, sticky="ew", pady=(4, 12))
        output_row.columnconfigure(0, weight=1)
        ttk.Entry(output_row, textvariable=self.output_dir_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(output_row, text="Choose", command=self.choose_output_dir).grid(row=0, column=1, padx=(8, 0))

        ttk.Button(tools_panel, text="Convert Selected", command=self.convert_selected).grid(
            row=5, column=0, sticky="ew", pady=(0, 8)
        )
        ttk.Button(tools_panel, text="Convert All", command=self.convert_all).grid(row=6, column=0, sticky="ew")

        ttk.Separator(tools_panel).grid(row=7, column=0, sticky="ew", pady=18)

        ttk.Label(tools_panel, text="Project Rule", font=("TkDefaultFont", 12, "bold")).grid(row=8, column=0, sticky="w")
        rule = (
            "Use local files or media you are allowed to convert. "
            "This app does not remove ads or bypass another service's player."
        )
        ttk.Label(tools_panel, text=rule, wraplength=290, foreground="#5b6670").grid(row=9, column=0, sticky="w", pady=(6, 0))

        self.status_var = tk.StringVar(value="Ready.")
        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(18, 0, 18, 14))
        status.grid(row=2, column=0, sticky="ew")

    def _refresh_tool_status(self) -> None:
        playback = "FFplay" if self.tools.ffplay else "afplay" if self.tools.afplay else "missing"
        conversion = "FFmpeg ready" if self.tools.ffmpeg else "FFmpeg missing"
        self.tool_status.configure(text=f"Playback: {playback} / Conversion: {conversion}")

        if not self.tools.ffmpeg:
            self.status_var.set("Install FFmpeg to convert broad media formats. Playback can use macOS afplay.")

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Choose audio or video files",
            filetypes=[
                ("Media files", " ".join(f"*{extension}" for extension in MEDIA_EXTENSIONS)),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return

        new_paths = [Path(path) for path in paths]
        self.playlist.extend(new_paths)
        self._render_playlist()
        self.status_var.set(f"Added {len(new_paths)} file(s).")

        if self.active_index == -1:
            self.active_index = 0
            self.playlist_listbox.selection_set(0)

    def choose_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Choose output folder", initialdir=self.output_dir_var.get())
        if path:
            self.output_dir_var.set(path)

    def play_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Choose a file", "Add a media file, then select it to play.")
            return
        self._play_index(index)

    def play_previous(self) -> None:
        if not self.playlist:
            return
        next_index = (self.active_index - 1) % len(self.playlist)
        self._play_index(next_index)

    def play_next(self) -> None:
        if not self.playlist:
            return
        next_index = (self.active_index + 1) % len(self.playlist)
        self._play_index(next_index)

    def stop_playback(self) -> None:
        self.stop_requested = True
        if self.play_process and self.play_process.poll() is None:
            self.play_process.terminate()
        self.play_process = None
        self.status_var.set("Stopped.")

    def convert_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Choose a file", "Select a media file to convert.")
            return
        self._start_conversion([self.playlist[index]])

    def convert_all(self) -> None:
        if not self.playlist:
            messagebox.showinfo("Add files", "Add media files before converting.")
            return
        self._start_conversion(self.playlist[:])

    def _play_index(self, index: int) -> None:
        player = self.tools.player
        if not player:
            messagebox.showerror("Playback unavailable", "Install FFplay or use macOS afplay to enable playback.")
            return

        path = self.playlist[index]
        if not path.exists():
            messagebox.showerror("File missing", f"{path} no longer exists.")
            return

        self.stop_playback()
        self.stop_requested = False
        self.active_index = index
        self.playlist_listbox.selection_clear(0, tk.END)
        self.playlist_listbox.selection_set(index)
        self.playlist_listbox.see(index)

        command = self._play_command(player, path)
        try:
            self.play_process = subprocess.Popen(command, text=True)
        except OSError as error:
            messagebox.showerror("Playback failed", str(error))
            return

        self.status_var.set(f"Playing {path.name}")
        self.monitor_thread = threading.Thread(target=self._monitor_playback, args=(path,), daemon=True)
        self.monitor_thread.start()

    def _monitor_playback(self, path: Path) -> None:
        process = self.play_process
        if not process:
            return

        process.wait()
        if not self.stop_requested:
            self.after(0, lambda: self.status_var.set(f"Finished {path.name}"))

    def _play_command(self, player: str, path: Path) -> list[str]:
        if Path(player).name == "ffplay":
            return [player, "-nodisp", "-autoexit", "-loglevel", "error", str(path)]
        return [player, str(path)]

    def _start_conversion(self, paths: list[Path]) -> None:
        if not self.tools.ffmpeg:
            messagebox.showerror(
                "FFmpeg required",
                "Install FFmpeg to convert media files. On macOS with Homebrew: brew install ffmpeg",
            )
            return

        output_dir = Path(self.output_dir_var.get()).expanduser()
        output_format = self.format_var.get()
        output_dir.mkdir(parents=True, exist_ok=True)

        thread = threading.Thread(
            target=self._convert_paths,
            args=(paths, output_dir, output_format),
            daemon=True,
        )
        thread.start()

    def _convert_paths(self, paths: list[Path], output_dir: Path, output_format: str) -> None:
        failures: list[str] = []
        profile = CONVERSION_PROFILES[output_format]

        for position, source in enumerate(paths, start=1):
            self.after(0, lambda source=source, position=position: self.status_var.set(
                f"Converting {position}/{len(paths)}: {source.name}"
            ))

            target = self._unique_output_path(output_dir, source.stem, output_format)
            command = [
                self.tools.ffmpeg or "ffmpeg",
                "-y",
                "-i",
                str(source),
                *profile,
                "-map_metadata",
                "0",
                str(target),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                failures.append(f"{source.name}: {result.stderr.strip() or 'conversion failed'}")

        if failures:
            self.after(0, lambda: self._show_conversion_failures(failures))
        else:
            self.after(0, lambda: self.status_var.set(f"Converted {len(paths)} file(s) to {output_format}."))

    def _show_conversion_failures(self, failures: list[str]) -> None:
        self.status_var.set(f"Converted with {len(failures)} failure(s).")
        messagebox.showerror("Conversion failures", "\n\n".join(failures[:3]))

    def _unique_output_path(self, output_dir: Path, stem: str, extension: str) -> Path:
        candidate = output_dir / f"{stem}.{extension}"
        counter = 2
        while candidate.exists():
            candidate = output_dir / f"{stem} {counter}.{extension}"
            counter += 1
        return candidate

    def _selected_index(self) -> int | None:
        selection = self.playlist_listbox.curselection()
        if selection:
            return int(selection[0])
        if self.active_index != -1:
            return self.active_index
        return None

    def _render_playlist(self) -> None:
        self.playlist_listbox.delete(0, tk.END)
        for path in self.playlist:
            self.playlist_listbox.insert(tk.END, path.name)

    def _close(self) -> None:
        self.stop_playback()
        self.destroy()


if __name__ == "__main__":
    app = AudioPlayerApp()
    app.mainloop()
