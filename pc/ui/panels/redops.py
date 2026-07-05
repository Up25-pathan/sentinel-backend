from functools import partial
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QInputDialog,
    QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from utils.workers import JobRunner
from utils import docker_tools, vm_tools, audit
import sys

class RedOpsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.job_counter = 0
        self.job_runners = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Red Team Operations")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_jobs_tab(), "\U00002694 Jobs")
        tabs.addTab(self._build_docker_tab(), "\U0001F4E6 Docker Labs")
        tabs.addTab(self._build_vm_tab(), "\U0001F5A5 VirtualBox VMs")
        layout.addWidget(tabs)

    def _build_jobs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        btn_layout = QHBoxLayout()
        recon_btn = QPushButton("\U0001F50D Reconnaissance")
        recon_btn.clicked.connect(self.start_recon_job)
        web_btn = QPushButton("\U0001F310 Web Attack")
        web_btn.clicked.connect(self.start_web_job)
        privesc_btn = QPushButton("\U0001F511 Privilege Escalation")
        privesc_btn.clicked.connect(self.start_privesc_job)
        osint_btn = QPushButton("\U0001F50E OSINT Sandbox")
        osint_btn.clicked.connect(self.start_osint_job)

        for btn in [recon_btn, web_btn, privesc_btn, osint_btn]:
            btn.setMinimumHeight(40)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

        self.job_output = QTextEdit()
        self.job_output.setReadOnly(True)
        self.job_output.setStyleSheet("font-family: 'Fira Code', 'Consolas', monospace; font-size: 9pt;")
        layout.addWidget(self.job_output, 1)

        return tab

    def _build_docker_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        self.labs_table = QTableWidget()
        self.labs_table.setColumnCount(4)
        self.labs_table.setHorizontalHeaderLabels(["Name", "Status", "Start", "Stop"])
        self.labs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.labs_table.verticalHeader().setVisible(False)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._update_labs)

        layout.addWidget(refresh_btn)
        layout.addWidget(self.labs_table, 1)

        self._update_labs()
        return tab

    def _build_vm_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        self.vm_table = QTableWidget()
        self.vm_table.setColumnCount(4)
        self.vm_table.setHorizontalHeaderLabels(["VM Name", "Status", "Actions", "Reset"])
        self.vm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.vm_table.verticalHeader().setVisible(False)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._update_vms)

        layout.addWidget(refresh_btn)
        layout.addWidget(self.vm_table, 1)

        self._update_vms()
        return tab

    def start_generic_job(self, name, script_path, args=None):
        if args is None:
            args = []
        self.job_counter += 1
        audit.log_action("JOB_START", f"Starting job '{name}' with args: {args}")
        self.job_output.append(f"\n {'='*50}")
        self.job_output.append(f"  Starting: {name}")
        self.job_output.append(f" {'='*50}\n")

        job_runner = JobRunner(sys.executable, [script_path] + args)
        job_runner.outputReady.connect(lambda text: self.job_output.append(text))
        tag = f"job_{self.job_counter}"
        self.job_runners[tag] = job_runner
        job_runner.run()

    def start_recon_job(self):
        target, ok = QInputDialog.getText(self, 'Recon Target', 'Enter Target IP:')
        if ok and target:
            self.start_generic_job("Reconnaissance", "bin/recon_job.py", ["--target", target])

    def start_web_job(self):
        url, ok = QInputDialog.getText(self, 'Web Attack Target', 'Enter Target URL:')
        if ok and url:
            self.start_generic_job("Web Attack", "bin/web_job.py", ["--url", url])

    def start_privesc_job(self):
        target, ok = QInputDialog.getText(self, 'Privesc Target', 'Enter Target IP:')
        if ok and target:
            self.start_generic_job("Privesc", "bin/privesc_job.py", ["--target", target])

    def start_osint_job(self):
        domain, ok = QInputDialog.getText(self, 'OSINT Target', 'Enter Target Domain:')
        if ok and domain:
            self.start_generic_job("OSINT", "bin/osint_job.py", ["--domain", domain])

    def _update_labs(self):
        self.labs_table.setRowCount(0)
        labs = docker_tools.list_labs()
        self.labs_table.setRowCount(len(labs))
        for row, lab in enumerate(labs):
            self.labs_table.setItem(row, 0, QTableWidgetItem(lab['name']))
            self.labs_table.setItem(row, 1, QTableWidgetItem(lab['status']))
            start_btn = QPushButton("Start")
            stop_btn = QPushButton("Stop")
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
            self.vm_table.setItem(row, 0, QTableWidgetItem(vm_name))
            self.vm_table.setItem(row, 1, QTableWidgetItem(status))
            start_btn = QPushButton("Start")
            stop_btn = QPushButton("Stop")
            start_btn.setEnabled(status != 'running')
            stop_btn.setEnabled(status == 'running')
            start_btn.clicked.connect(partial(self._control_vm, "start", vm_name))
            stop_btn.clicked.connect(partial(self._control_vm, "stop", vm_name))
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(0, 0, 0, 0)
            al.addWidget(start_btn)
            al.addWidget(stop_btn)
            self.vm_table.setCellWidget(row, 2, actions)
            reset_btn = QPushButton("Reset")
            reset_btn.clicked.connect(partial(self._reset_vm, vm_name))
            self.vm_table.setCellWidget(row, 3, reset_btn)

    def _control_lab(self, action, lab_name):
        func = docker_tools.start_lab if action == "start" else docker_tools.stop_lab
        success, msg = func(lab_name)
        audit.log_action(f"DOCKER_{action.upper()}", f"Lab '{lab_name}': {msg}")
        self.job_output.append(f"  [Docker] {action} {lab_name}: {msg}")
        self._update_labs()

    def _control_vm(self, action, vm_name):
        if action == "start":
            success, msg = vm_tools.start_vm(vm_name)
        else:
            success, msg = vm_tools.stop_vm(vm_name)
        audit.log_action(f"VM_{action.upper()}", f"VM '{vm_name}': {msg}")
        self.job_output.append(f"  [VM] {action} {vm_name}: {msg}")
        self._update_vms()

    def _reset_vm(self, vm_name):
        snapshot, ok = QInputDialog.getText(self, 'Reset Snapshot', f'Enter snapshot name for "{vm_name}":')
        if ok and snapshot:
            success, msg = vm_tools.reset_vm(vm_name, snapshot)
            audit.log_action("VM_RESET", f"Reset VM '{vm_name}' to '{snapshot}'")
            self.job_output.append(f"  [VM] Reset {vm_name} to snapshot '{snapshot}': {msg}")
            self._update_vms()
