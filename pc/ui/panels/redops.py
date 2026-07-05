from functools import partial
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QInputDialog,
    QMessageBox, QGroupBox, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from utils.workers import JobRunner
from utils import docker_tools, vm_tools, audit
import sys
from datetime import datetime

JOB_HISTORY = []

class JobCard(QFrame):
    def __init__(self, name, status, time, tag):
        super().__init__()
        self.setObjectName("JobCard")
        l = QHBoxLayout(self)
        l.setContentsMargins(8, 4, 8, 4)

        status_color = {"running": "#22d3ee", "done": "#22d3ee", "failed": "#ef4444", "cancelled": "#64748b"}.get(status, "#f59e0b")
        dot = QLabel("\u25CF")
        dot.setStyleSheet(f"color:{status_color}; font-size:10pt;")
        l.addWidget(dot)

        n = QLabel(name)
        n.setStyleSheet("color:#cbd5e1; font-size:8pt;")
        l.addWidget(n, 1)

        t = QLabel(time)
        t.setStyleSheet("color:#475569; font-size:7pt;")
        l.addWidget(t)

        s = QLabel(status.upper())
        s.setStyleSheet(f"color:{status_color}; font-size:7pt; font-weight:600; letter-spacing:1px;")
        l.addWidget(s)

class RedOpsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.job_counter = 0
        self.job_runners = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Red Team Operations")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_jobs_tab(), "JOBS")
        tabs.addTab(self._build_history_tab(), "HISTORY")
        tabs.addTab(self._build_docker_tab(), "DOCKER")
        tabs.addTab(self._build_vm_tab(), "VBOX")
        layout.addWidget(tabs)

    def _build_jobs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        jobs_def = [
            ("RECON", self.start_recon_job, "#22d3ee"),
            ("WEB", self.start_web_job, "#f59e0b"),
            ("PRIVESC", self.start_privesc_job, "#ef4444"),
            ("OSINT", self.start_osint_job, "#22d3ee"),
            ("EXPLOIT", self.start_exploit_job, "#ef4444"),
            ("WIFI", self.start_wifi_job, "#f59e0b"),
        ]
        for label, cb, color in jobs_def:
            btn = QPushButton(label)
            btn.setStyleSheet(f"QPushButton {{ border-color: {color}; color: {color}; }} QPushButton:hover {{ background-color: {color}; color: #080a0e; }}")
            btn.clicked.connect(cb)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

        self.job_output = QTextEdit()
        self.job_output.setReadOnly(True)
        self.job_output.setStyleSheet("font-family: 'Fira Code', 'Consolas', monospace; font-size: 9pt;")
        layout.addWidget(self.job_output, 1)

        return tab

    def _build_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(6)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Job", "Status", "Time", "Output"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        layout.addWidget(self.history_table, 1)

        clear_btn = QPushButton("CLEAR HISTORY")
        clear_btn.clicked.connect(self._clear_history)
        layout.addWidget(clear_btn)

        return tab

    def _build_docker_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        self.labs_table = QTableWidget()
        self.labs_table.setColumnCount(4)
        self.labs_table.setHorizontalHeaderLabels(["Name", "Status", "Start", "Stop"])
        self.labs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.labs_table.verticalHeader().setVisible(False)

        btn_bar = QHBoxLayout()
        refresh_btn = QPushButton("REFRESH")
        refresh_btn.clicked.connect(self._update_labs)
        btn_bar.addWidget(refresh_btn)
        btn_bar.addStretch()

        layout.addLayout(btn_bar)
        layout.addWidget(self.labs_table, 1)

        self._update_labs()
        return tab

    def _build_vm_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        self.vm_table = QTableWidget()
        self.vm_table.setColumnCount(4)
        self.vm_table.setHorizontalHeaderLabels(["VM Name", "Status", "Actions", "Reset"])
        self.vm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.vm_table.verticalHeader().setVisible(False)

        btn_bar = QHBoxLayout()
        refresh_btn = QPushButton("REFRESH")
        refresh_btn.clicked.connect(self._update_vms)
        btn_bar.addWidget(refresh_btn)
        btn_bar.addStretch()

        layout.addLayout(btn_bar)
        layout.addWidget(self.vm_table, 1)

        self._update_vms()
        return tab

    def start_generic_job(self, name, script_path, args=None):
        if args is None:
            args = []
        self.job_counter += 1
        tag = f"job_{self.job_counter}"
        now = datetime.now().strftime("%H:%M:%S")

        audit.log_action("JOB_START", f"Starting job '{name}' with args: {args}")
        self.job_output.append(f"\n{'='*55}")
        self.job_output.append(f"  [{now}] START: {name} {' '.join(args)}")
        self.job_output.append(f"{'='*55}\n")

        job_runner = JobRunner(sys.executable, [script_path] + args)
        job_runner.outputReady.connect(lambda text, n=name, t=tag: self._on_job_output(n, t, text))
        self.job_runners[tag] = job_runner

        JOB_HISTORY.append({"name": name, "status": "running", "time": now, "tag": tag, "output": []})
        self._update_history()

        self.job_output.append(f"  PID: {tag}\n")
        job_runner.run()

    def _on_job_output(self, name, tag, text):
        self.job_output.append(f"  [{name}] {text}")
        for h in JOB_HISTORY:
            if h["tag"] == tag:
                h["output"].append(text)
                if "error" in text.lower() or "fail" in text.lower():
                    h["status"] = "failed"
                break

    def _on_job_done(self, name, tag, returncode):
        self.job_output.append(f"\n  [DONE] {name} (exit: {returncode})")
        for h in JOB_HISTORY:
            if h["tag"] == tag:
                if h["status"] != "failed":
                    h["status"] = "done" if returncode == 0 else "failed"
                break
        self._update_history()

    def start_recon_job(self):
        target, ok = QInputDialog.getText(self, 'Recon Target', 'Enter Target IP/Domain:')
        if ok and target:
            self.start_generic_job("RECON", "bin/recon_job.py", ["--target", target])

    def start_web_job(self):
        url, ok = QInputDialog.getText(self, 'Web Attack Target', 'Enter Target URL:')
        if ok and url:
            self.start_generic_job("WEB", "bin/web_job.py", ["--url", url])

    def start_privesc_job(self):
        target, ok = QInputDialog.getText(self, 'Privesc Target', 'Enter Target IP:')
        if ok and target:
            self.start_generic_job("PRIVESC", "bin/privesc_job.py", ["--target", target])

    def start_osint_job(self):
        domain, ok = QInputDialog.getText(self, 'OSINT Target', 'Enter Target Domain:')
        if ok and domain:
            self.start_generic_job("OSINT", "bin/osint_job.py", ["--domain", domain])

    def start_exploit_job(self):
        target, ok = QInputDialog.getText(self, 'Exploit Target', 'Enter Target IP:')
        if ok and target:
            self.start_generic_job("EXPLOIT DEV", "bin/exploit_dev_job.py", ["--target", target])

    def start_wifi_job(self):
        interface, ok = QInputDialog.getText(self, 'Wi-Fi Interface', 'Enter interface name (e.g., wlan0):')
        if ok and interface:
            self.start_generic_job("WIFI", "bin/wifi_job.py", ["--interface", interface])

    def _update_history(self):
        self.history_table.setRowCount(0)
        self.history_table.setRowCount(len(JOB_HISTORY))
        for row, h in enumerate(reversed(JOB_HISTORY)):
            status_color = {"running": "#22d3ee", "done": "#22d3ee", "failed": "#ef4444", "cancelled": "#64748b"}.get(h["status"], "#f59e0b")
            items = [
                QTableWidgetItem(h["name"]),
                QTableWidgetItem(h["status"].upper()),
                QTableWidgetItem(h["time"]),
                QTableWidgetItem("; ".join(h["output"][-3:])),
            ]
            items[1].setForeground(QColor(status_color))
            for c, it in enumerate(items):
                self.history_table.setItem(row, c, it)

    def _clear_history(self):
        JOB_HISTORY.clear()
        self._update_history()

    def _update_labs(self):
        self.labs_table.setRowCount(0)
        labs = docker_tools.list_labs()
        self.labs_table.setRowCount(len(labs))
        for row, lab in enumerate(labs):
            status_color = {"running": "#22d3ee", "stopped": "#ef4444"}.get(lab['status'], "#64748b")
            self.labs_table.setItem(row, 0, QTableWidgetItem(lab['name']))
            si = QTableWidgetItem(lab['status'])
            si.setForeground(QColor(status_color))
            self.labs_table.setItem(row, 1, si)
            start_btn = QPushButton("START")
            stop_btn = QPushButton("STOP")
            start_btn.setEnabled(lab['status'] != 'running')
            stop_btn.setEnabled(lab['status'] == 'running')
            start_btn.clicked.connect(partial(self._control_lab, "start", lab['name']))
            stop_btn.clicked.connect(partial(self._control_lab, "stop", lab['name']))
            self.labs_table.setCellWidget(row, 2, start_btn)
            self.labs_table.setCellWidget(row, 3, stop_btn)

    def _update_vms(self):
        self.vm_table.setRowCount(0)
        vms = vm_tools.list_vms()
        if not vms:
            return
        self.vm_table.setRowCount(len(vms))
        for row, vm_name in enumerate(vms):
            status = vm_tools.get_vm_status(vm_name)
            status_color = {"running": "#22d3ee", "stopped": "#ef4444", "paused": "#f59e0b"}.get(status, "#64748b")
            self.vm_table.setItem(row, 0, QTableWidgetItem(vm_name))
            si = QTableWidgetItem(status)
            si.setForeground(QColor(status_color))
            self.vm_table.setItem(row, 1, si)
            start_btn = QPushButton("START")
            stop_btn = QPushButton("STOP")
            start_btn.setEnabled(status != 'running')
            stop_btn.setEnabled(status == 'running')
            start_btn.clicked.connect(partial(self._control_vm, "start", vm_name))
            stop_btn.clicked.connect(partial(self._control_vm, "stop", vm_name))
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(2, 0, 2, 0)
            al.setSpacing(4)
            al.addWidget(start_btn)
            al.addWidget(stop_btn)
            self.vm_table.setCellWidget(row, 2, actions)
            reset_btn = QPushButton("RESET")
            reset_btn.clicked.connect(partial(self._reset_vm, vm_name))
            self.vm_table.setCellWidget(row, 3, reset_btn)

    def _control_lab(self, action, lab_name):
        func = docker_tools.start_lab if action == "start" else docker_tools.stop_lab
        success, msg = func(lab_name)
        audit.log_action(f"DOCKER_{action.upper()}", f"Lab '{lab_name}': {msg}")
        self.job_output.append(f"  [DOCKER] {action.upper()} {lab_name}: {msg}")
        self._update_labs()

    def _control_vm(self, action, vm_name):
        if action == "start":
            success, msg = vm_tools.start_vm(vm_name)
        else:
            success, msg = vm_tools.stop_vm(vm_name)
        audit.log_action(f"VM_{action.upper()}", f"VM '{vm_name}': {msg}")
        self.job_output.append(f"  [VM] {action.upper()} {vm_name}: {msg}")
        self._update_vms()

    def _reset_vm(self, vm_name):
        snapshot, ok = QInputDialog.getText(self, 'Reset Snapshot', f'Enter snapshot name for "{vm_name}":')
        if ok and snapshot:
            success, msg = vm_tools.reset_vm(vm_name, snapshot)
            audit.log_action("VM_RESET", f"Reset VM '{vm_name}' to '{snapshot}'")
            self.job_output.append(f"  [VM] RESET {vm_name} -> '{snapshot}': {msg}")
            self._update_vms()

    def refresh(self):
        self._update_labs()
        self._update_vms()
        self._update_history()
