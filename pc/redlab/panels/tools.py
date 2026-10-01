"""A dedicated REDLAB panel for each offensive tool.

Every tool existed only as a button inside the Red Ops tab, so the navigation
rail showed OPS/SCAN/CAMP/ASST and none of the actual tooling. Each panel here
runs the same job script through the same code path as the OPS button, so there
is one implementation per tool rather than two that can drift apart.
"""
import os
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QInputDialog, QFrame,
)

from redlab.utils.workers import JobRunner
from utils import audit
import sys

# Resolved against this file so the path holds from source, a bundle or an
# install, not from whatever the working directory happens to be.
REDLAB_BIN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")


class ToolPanel(QWidget):
    """One tool: a RUN button, a description, and a live output console."""

    def __init__(self, key, name, title, prompt_label, script_name, accent, blurb,
                 value_flag="--target"):
        super().__init__()
        self.setObjectName("ToolPanel")
        self.key = key
        self.name = name
        self.script_name = script_name
        # The flag each job script expects. Guessing this per tool in run()
        # is what made WEB pass --target to a script that only accepts --url.
        self.value_flag = value_flag
        self.accent = accent
        self._runners = {}
        self._counter = 0
        self._setup_ui(title, prompt_label, blurb)

    def _setup_ui(self, title, prompt_label, blurb):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        header.addWidget(label)
        header.addStretch(1)

        self.run_btn = QPushButton(f"RUN {self.name}")
        self.run_btn.setMinimumWidth(120)
        self.run_btn.setStyleSheet(
            f"QPushButton {{ border-color: {self.accent}; color: {self.accent}; "
            f"font-weight:700; letter-spacing:1px; }} "
            f"QPushButton:hover {{ background-color: {self.accent}; color: #080a0e; }} "
            f"QPushButton:disabled {{ color: #475569; border-color: #1a1e2e; }}")
        self.run_btn.clicked.connect(self.run)
        header.addWidget(self.run_btn)
        layout.addLayout(header)

        desc = QLabel(blurb)
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#64748b; font-size:8pt;")
        layout.addWidget(desc)

        prompt = QLabel(f"Input: {prompt_label}")
        prompt.setStyleSheet("color:#475569; font-size:7pt; letter-spacing:1px;")
        layout.addWidget(prompt)

        self.status = QLabel("IDLE — NO RUN YET")
        self.status.setStyleSheet(
            f"color:{self.accent}; font-size:7pt; font-weight:600; letter-spacing:1px;")
        layout.addWidget(self.status)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet(
            "font-family: 'Fira Code', 'Consolas', monospace; font-size:9pt;")
        layout.addWidget(self.output, 1)

    # ── running ─────────────────────────────────────────────────────
    def run(self):
        value, ok = QInputDialog.getText(self, f"{self.name} Target", "Enter target:")
        if not ok or not value.strip():
            self.status.setText("CANCELLED")
            return
        value = value.strip()

        args = [self.value_flag, value]
        if self.key == "exploit":
            ports, ok2 = QInputDialog.getText(
                self, "Port Range", "Comma-separated ports (blank = default set):")
            if not ok2:
                self.status.setText("CANCELLED")
                return
            if ports.strip():
                args += ["--scan", ports.strip()]

        self._launch(args)

    def _launch(self, args):
        script_path = os.path.join(REDLAB_BIN_DIR, self.script_name)
        if not os.path.exists(script_path):
            self.output.append(
                f"[ERROR] job script missing: {script_path}\n"
                f"         {self.name} was not started and no result is shown.\n")
            self.status.setText("SCRIPT MISSING")
            return

        self._counter += 1
        tag = f"{self.key}_{self._counter}"
        now = datetime.now().strftime("%H:%M:%S")
        audit.log_action("JOB_START", f"{self.name} {' '.join(args)}")
        self.output.append(f"\n{'=' * 55}")
        self.output.append(f"  [{now}] START: {self.name} {' '.join(args)}")
        self.output.append(f"{'=' * 55}\n")

        runner = JobRunner(sys.executable, [script_path] + args)
        runner.outputReady.connect(lambda text: self.output.append(f"  {text}"))
        runner.finished.connect(lambda code: self._on_done(code))
        self._runners[tag] = runner
        self.status.setText(f"RUNNING — {now}")
        self.run_btn.setEnabled(False)
        runner.run()

    def _on_done(self, returncode):
        self.run_btn.setEnabled(True)
        if returncode == 0:
            self.status.setText("COMPLETE — EXIT 0")
        else:
            self.status.setText(f"FAILED — EXIT {returncode}")
        self.output.append(f"\n  [DONE] exit {returncode}")

    def refresh(self):
        """Navigation hook. Panels keep their output; nothing is re-run."""
        return None