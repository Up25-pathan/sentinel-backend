from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QPlainTextEdit, QComboBox, QLineEdit, QInputDialog,
    QMessageBox, QSplitter, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from utils import campaign_manager, attack_manager, audit

class CampaignsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.attack_data = attack_manager.get_attack_data()
        self._setup_ui()
        self._populate_campaigns()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Campaign Planning & MITRE ATT&CK")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)

        controls = QHBoxLayout()
        self.campaign_selector = QComboBox()
        self.campaign_selector.currentIndexChanged.connect(self._load_notes)
        new_btn = QPushButton("New")
        new_btn.clicked.connect(self._create_campaign)
        save_btn = QPushButton("Save Notes")
        save_btn.clicked.connect(self._save_notes)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_campaign)

        controls.addWidget(QLabel("Campaign:"))
        controls.addWidget(self.campaign_selector, 1)
        controls.addWidget(new_btn)
        controls.addWidget(save_btn)
        controls.addWidget(delete_btn)
        left_layout.addLayout(controls)

        self.notes_editor = QPlainTextEdit()
        self.notes_editor.setPlaceholderText("Campaign notes...")
        left_layout.addWidget(self.notes_editor, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)

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

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([500, 350])
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
        self._load_notes()

    def _load_notes(self):
        cid = self.campaign_selector.currentData()
        if cid is not None:
            self.notes_editor.setPlainText(campaign_manager.get_campaign_notes(cid))
        else:
            self.notes_editor.clear()

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
