from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel

class StatCard(QFrame):
    def __init__(self, title, value="0", color="#4f8cff", subtext=""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("StatTitle")

        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("StatValue")
        self.value_label.setStyleSheet(f"color: {color}; font-size: 28pt; font-weight: 700;")

        self.subtext_label = QLabel(subtext)
        self.subtext_label.setObjectName("StatSubtext")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtext_label)

    def set_value(self, value, subtext=""):
        self.value_label.setText(str(value))
        if subtext:
            self.subtext_label.setText(subtext)
