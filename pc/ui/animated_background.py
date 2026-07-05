# ui/animated_background.py

import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont

class AnimatedBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)
        
        # --- Animation Parameters ---
        self.char_font = QFont("Fira Code", 10)
        self.font_size = 15
        self.char_color = QColor(0, 230, 118, 150) # Neon green, semi-transparent
        self.background_color = QColor("#010409")
        self.drops = []
        # Katakana characters often used for this effect
        self.charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()[]"

    def resizeEvent(self, event):
        """Re-initialize the animation when the window is resized."""
        super().resizeEvent(event)
        self._initialize_drops()
        if not self.timer.isActive():
            self.timer.start(50) # Update roughly 20 times per second

    def _initialize_drops(self):
        """Create the initial set of 'rain drops' based on widget width."""
        self.drops = []
        num_columns = self.width() // self.font_size
        for i in range(num_columns):
            # Each drop starts at a random y position off-screen
            self.drops.append({
                "x": i * self.font_size,
                "y": random.randint(-self.height(), 0),
                "speed": random.randint(2, 6),
                "char": random.choice(self.charset)
            })

    def paintEvent(self, event):
        """The main drawing loop, called every time the widget updates."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background_color)
        
        painter.setFont(self.char_font)
        painter.setPen(self.char_color)

        for drop in self.drops:
            # Draw the character for the current drop
            painter.drawText(drop["x"], drop["y"], drop["char"])

    def _update_animation(self):
        """Update the position of each drop for the next frame."""
        for drop in self.drops:
            drop["y"] += drop["speed"]
            # If the drop goes off-screen, reset it to the top
            if drop["y"] > self.height():
                drop["y"] = random.randint(-100, 0)
                drop["x"] = drop["x"] # Keep it in the same column
                drop["speed"] = random.randint(2, 6)
                drop["char"] = random.choice(self.charset) # Change character
        
        self.update() # Schedule a repaint