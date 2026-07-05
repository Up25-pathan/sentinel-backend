from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QPlainTextEdit, QComboBox, QLineEdit, QInputDialog,
    QMessageBox, QSplitter, QHeaderView, QTableWidget, QTableWidgetItem,
    QGroupBox, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from utils import campaign_manager, attack_manager, audit

PHASE_COLORS = {
    "pending": "#64748b",
    "in_progress": "#22d3ee",
    "completed": "#22d3ee",
    "failed": "#ef4444",
}

class CampaignsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.attack_data = attack_manager.get_attack_data()
        self._current_campaign_id = None
        self._setup_ui()
        self._populate_campaigns()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Campaign Planning & MITRE ATT&CK")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(6)

        controls = QHBoxLayout()
        self.campaign_selector = QComboBox()
        self.campaign_selector.currentIndexChanged.connect(self._load_campaign)
        new_btn = QPushButton("NEW")
        new_btn.clicked.connect(self._create_campaign)
        delete_btn = QPushButton("DELETE")
        delete_btn.clicked.connect(self._delete_campaign)

        controls.addWidget(QLabel("Campaign:"))
        controls.addWidget(self.campaign_selector, 1)
        controls.addWidget(new_btn)
        controls.addWidget(delete_btn)
        left_layout.addLayout(controls)

        # Progress
        prog = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_label = QLabel("0%")
        self.progress_label.setStyleSheet("color:#475569; font-size:7pt;")
        prog.addWidget(QLabel("Progress:"))
        prog.addWidget(self.progress_bar, 1)
        prog.addWidget(self.progress_label)
        left_layout.addLayout(prog)

        # Phases table
        self.phases_table = QTableWidget()
        self.phases_table.setColumnCount(4)
        self.phases_table.setHorizontalHeaderLabels(["Phase", "Status", "TTPs", "Action"])
        self.phases_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.phases_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.phases_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.phases_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.phases_table.verticalHeader().setVisible(False)
        left_layout.addWidget(self.phases_table, 1)

        # Notes
        grp = QGroupBox("NOTES")
        grp_l = QVBoxLayout(grp)
        self.notes_editor = QPlainTextEdit()
        self.notes_editor.setPlaceholderText("Campaign notes...")
        grp_l.addWidget(self.notes_editor)
        save_btn = QPushButton("SAVE NOTES")
        save_btn.clicked.connect(self._save_notes)
        grp_l.addWidget(save_btn)
        left_layout.addWidget(grp)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 0, 0, 0)

        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search ATT&CK techniques (e.g., T1053)...")
        search_bar.textChanged.connect(self._filter_tree)
        right_layout.addWidget(search_bar)

        self.attack_tree = QTreeWidget()
        self.attack_tree.setColumnCount(2)
        self.attack_tree.setHeaderLabels(["Technique", "ID"])
        self.attack_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.attack_tree.setIndentation(16)
        self._populate_tree()
        right_layout.addWidget(self.attack_tree, 1)

        # Assign TTP button
        assign_btn = QPushButton("ASSIGN TTP TO PHASE")
        assign_btn.clicked.connect(self._assign_ttp)
        right_layout.addWidget(assign_btn)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)

    def _populate_tree(self):
        self.attack_tree.clear()
        if not self.attack_data:
            return
        for tactic_group in self.attack_data:
            tactic_item = QTreeWidgetItem(self.attack_tree)
            tactic_item.setText(0, tactic_group["tactic"])
            tactic_item.setForeground(0, QColor("#4f8cff"))
            for tech in tactic_group["techniques"]:
                tech_item = QTreeWidgetItem(tactic_item)
                tech_item.setText(0, tech["name"])
                tech_item.setText(1, tech["id"])

    def _filter_tree(self, text):
        search = text.lower()
        root = self.attack_tree.invisibleRootItem()
        for i in range(root.childCount()):
            tactic = root.child(i)
            t_match = search in tactic.text(0).lower()
            any_child = False
            for j in range(tactic.childCount()):
                tech = tactic.child(j)
                match = search in tech.text(0).lower() or search in tech.text(1).lower()
                tech.setHidden(not match)
                if match:
                    any_child = True
            tactic.setHidden(not (t_match or any_child))

    def _populate_campaigns(self):
        self.campaign_selector.blockSignals(True)
        self.campaign_selector.clear()
        campaigns = campaign_manager.get_campaigns()
        if not campaigns:
            self.campaign_selector.addItem("No campaigns")
            self.notes_editor.setDisabled(True)
        else:
            self.notes_editor.setDisabled(False)
            for cid, name in campaigns:
                self.campaign_selector.addItem(name, userData=cid)
        self.campaign_selector.blockSignals(False)
        self._load_campaign()

    def _load_campaign(self):
        cid = self.campaign_selector.currentData()
        self._current_campaign_id = cid
        if cid is None:
            self.phases_table.setRowCount(0)
            self.notes_editor.clear()
            self.progress_bar.setValue(0)
            self.progress_label.setText("0%")
            return

        details = campaign_manager.get_campaign_details(cid)
        if details:
            self.notes_editor.setPlainText(details.get("notes", ""))
            phases = details.get("phases", [])
            self.phases_table.setRowCount(len(phases))
            for row, phase in enumerate(phases):
                self.phases_table.setItem(row, 0, QTableWidgetItem(phase["phase_name"]))
                si = QTableWidgetItem(phase["status"].upper())
                si.setForeground(QColor(PHASE_COLORS.get(phase["status"], "#64748b")))
                self.phases_table.setItem(row, 1, si)
                self.phases_table.setItem(row, 2, QTableWidgetItem(phase.get("ttps", "")))

                action_w = QWidget()
                al = QHBoxLayout(action_w)
                al.setContentsMargins(2, 0, 2, 0)
                al.setSpacing(2)
                status = phase["status"]
                if status == "pending":
                    start_b = QPushButton("START")
                    start_b.setFixedWidth(50)
                    start_b.clicked.connect(lambda checked, pid=phase["id"]: self._start_phase(pid))
                    al.addWidget(start_b)
                elif status == "in_progress":
                    done_b = QPushButton("DONE")
                    done_b.setFixedWidth(50)
                    done_b.clicked.connect(lambda checked, pid=phase["id"]: self._complete_phase(pid))
                    al.addWidget(done_b)
                elif status == "completed":
                    cl = QLabel("DONE")
                    cl.setStyleSheet("color:#22d3ee; font-size:7pt; font-weight:600;")
                    al.addWidget(cl)
                self.phases_table.setCellWidget(row, 3, action_w)

            progress = campaign_manager.get_campaign_progress(cid)
            self.progress_bar.setValue(int(progress))
            self.progress_label.setText(f"{int(progress)}%")

    def _start_phase(self, phase_id):
        campaign_manager.update_phase_status(phase_id, "in_progress")
        audit.log_action("PHASE_START", f"Phase {phase_id} started")
        self._load_campaign()

    def _complete_phase(self, phase_id):
        campaign_manager.update_phase_status(phase_id, "completed")
        audit.log_action("PHASE_COMPLETE", f"Phase {phase_id} completed")
        self._load_campaign()

    def _assign_ttp(self):
        if not self._current_campaign_id:
            QMessageBox.warning(self, "Warning", "Select a campaign first")
            return

        selected = self.attack_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Select a technique from the ATT&CK tree")
            return

        tech = selected[0]
        if not tech.text(1) or tech.childCount() > 0:
            QMessageBox.warning(self, "Warning", "Select a specific technique (not a tactic)")
            return

        ttp_id = tech.text(1)
        ttp_name = tech.text(0)

        phases = campaign_manager.get_campaign_details(self._current_campaign_id).get("phases", [])
        phase_names = [p["phase_name"] for p in phases]
        phase, ok = QInputDialog.getItem(self, "Assign TTP", f"Assign {ttp_id} ({ttp_name}) to phase:", phase_names, False)
        if ok and phase:
            for p in phases:
                if p["phase_name"] == phase:
                    existing = p.get("ttps", "")
                    new_ttps = (existing + ", " + ttp_id) if existing else ttp_id
                    campaign_manager.update_phase_ttps(p["id"], new_ttps)
                    audit.log_action("TTP_ASSIGN", f"{ttp_id} -> {phase}")
                    self._load_campaign()
                    break

    def _create_campaign(self):
        name, ok = QInputDialog.getText(self, 'New Campaign', 'Campaign Name:')
        if ok and name:
            target, ok2 = QInputDialog.getText(self, 'Target', f'Target for "{name}":')
            if ok2:
                success, msg = campaign_manager.create_campaign(name, target)
                if success:
                    audit.log_action("CAMPAIGN_CREATE", f"Created: {name}")
                    self._populate_campaigns()
                else:
                    QMessageBox.warning(self, "Error", msg)

    def _save_notes(self):
        cid = self.campaign_selector.currentData()
        if cid is not None:
            campaign_manager.update_campaign_notes(cid, self.notes_editor.toPlainText())
            audit.log_action("CAMPAIGN_UPDATE", f"Notes saved for campaign ID: {cid}")

    def _delete_campaign(self):
        cid = self.campaign_selector.currentData()
        name = self.campaign_selector.currentText()
        if cid is not None:
            reply = QMessageBox.question(
                self, 'Confirm', f"Delete campaign '{name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                campaign_manager.delete_campaign(cid)
                audit.log_action("CAMPAIGN_DELETE", f"Deleted: {name}")
                self._populate_campaigns()

    def refresh(self):
        self._populate_campaigns()
