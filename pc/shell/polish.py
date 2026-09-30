"""Consistent widget polish applied across every panel.

Walking each panel's tree once and decorating it here is deliberate. Doing this
per-panel would mean the same tooltip written sixteen times, and the first
panel nobody touched would keep the gap.

Three things are applied:

- empty-state overlays on tables, so an unpopulated table explains itself
  instead of looking broken
- tooltips on buttons, from a label-to-meaning map
- placeholder text on input fields, from a map keyed by context

All of it is best-effort: a panel that already handles its own state is left
alone.
"""

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QLabel, QLineEdit, QTableWidget, QTreeWidget

# Buttons whose label already reads as a command need no tooltip.
SELF_DESCRIBING = {
    "REFRESH", "CLEAR HISTORY", "SEND", "NEW", "DELETE", "SAVE NOTES", "CLEAR",
}

TOOLTIPS = {
    "◀ PREV": "Previous page of results",
    "NEXT ▶": "Next page of results",
    "Previous": "Previous page of results",
    "Next": "Next page of results",
    "SEARCH": "Filter the list by text",
    "Mark Read": "Mark the selected alert as acknowledged",
    "LOAD DATA": "Load the saved export data",
    "EXPORT": "Write the current view to a file",
    "RECON": "Probe a host: resolve, ping, port scan and grab banners",
    "WEB": "Inspect a URL: status, headers, title, cookies, robots.txt",
    "PRIVESC": "Audit this machine for local privilege-escalation exposure",
    "OSINT": "Passive lookups against a domain",
    "WIFI": "Inventory local wireless adapters and nearby networks",
    "SCAN": "Start a scan against the target below",
    "ASSIGN TTP TO PHASE": "Add the selected ATT&CK technique to this phase",
    "ADD ASSET": "Register an asset you are tracking",
}

PLACEHOLDERS = {
    "SEARCH": "Filter results…",
    "target": "hostname, IPv4 or IPv6 address",
    "url": "https://example.com",
    "domain": "example.com",
    "interface": "wlan0",
}


def _item_count(view):
    """Rows for a table, top-level items for a tree."""
    if hasattr(view, "rowCount"):
        return view.rowCount()
    return view.topLevelItemCount()


class _EmptyStateOverlay(QLabel):
    """Centred message drawn over a view's viewport while it holds nothing."""

    def __init__(self, table, text):
        super().__init__(table.viewport())
        self._table = table
        self.setText(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(
            "color: #475569; font-size: 9pt; background: transparent; border: none;")

    def sync(self):
        empty = _item_count(self._table) == 0
        self.setVisible(empty)
        if empty:
            self.setGeometry(self._table.viewport().rect())


class _EmptyStateFilter(QObject):
    """Keeps an overlay in sync as content is added and removed.

    Row counts change through the model, not through a resize event, so the
    model signals are what drive visibility here. Watching only geometry would
    leave the overlay visible on top of a freshly populated table.
    """

    def __init__(self, table):
        super().__init__(table)
        self._overlay = _EmptyStateOverlay(table, "No data yet")
        self._sync_scheduled = False

        model = table.model()
        if model is not None:
            for signal_name in ("rowsInserted", "rowsRemoved", "modelReset",
                                "layoutChanged"):
                signal = getattr(model, signal_name, None)
                if signal is not None:
                    signal.connect(self._schedule_sync)
        self._overlay.sync()

    def _schedule_sync(self, *_args):
        # Coalesce a burst of row insertions into one sync on the next tick.
        if self._sync_scheduled:
            return
        self._sync_scheduled = True
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._sync_now)

    def _sync_now(self):
        self._sync_scheduled = False
        self._overlay.sync()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
            self._overlay.sync()
        return False

    def set_message(self, text):
        self._overlay.setText(text)





def attach_empty_state(table, text="No data yet"):
    """Show `text` over the table whenever it has no rows."""
    filt = _EmptyStateFilter(table)
    table.installEventFilter(filt)
    table._empty_state = filt  # noqa: SLF001 - looked up by set_empty_text
    return filt


def set_empty_text(table, text):
    """Update an existing overlay's message."""
    filt = getattr(table, "_empty_state", None)
    if filt is not None:
        filt.set_message(text)


class _GeometryFilter(QObject):
    """Re-centres the overlay when the table itself is resized."""

    def __init__(self, table):
        super().__init__(table)
        self._table = table

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            overlay = getattr(self._table, "_empty_state", None)
            if overlay is not None:
                overlay._overlay.sync()  # noqa: SLF001
        return False


def polish(root, empty_text="No data yet"):
    """Apply tooltips, placeholders and empty states throughout a panel.

    Returns the number of things changed, so a test can assert the pass ran.
    """
    changed = 0

    from PyQt6.QtWidgets import QPushButton
    for button in root.findChildren(QPushButton):
        label = button.text().strip()
        if not label or button.toolTip():
            continue
        if label.upper() in SELF_DESCRIBING:
            continue
        hint = TOOLTIPS.get(label)
        if hint:
            button.setToolTip(hint)
            changed += 1

    for field in root.findChildren(QLineEdit):
        if field.placeholderText():
            continue
        hint = PLACEHOLDERS.get(field.objectName())
        if hint is None:
            hint = _infer_placeholder(field)
        if hint:
            field.setPlaceholderText(hint)
            changed += 1

    for view in list(root.findChildren(QTableWidget)) + list(root.findChildren(QTreeWidget)):
        if hasattr(view, "_empty_state"):
            continue
        attach_empty_state(view, empty_text)
        view.installEventFilter(_GeometryFilter(view))
        changed += 1

    return changed


def _infer_placeholder(field):
    """Guess help text from a field's surroundings when no explicit hint exists."""
    for label in field.findChildren(QLabel):
        text = label.text().strip().lower()
        if text.endswith(":") and text[:-1] in ("target", "domain", "interface", "url"):
            return "Enter {} to assess".format(text[:-1])
    parent = field.parent()
    if parent is not None:
        for label in parent.findChildren(QLabel):
            text = label.text().strip().lower().rstrip(":")
            if text in PLACEHOLDERS:
                return "Enter {}…".format(text)
    return None