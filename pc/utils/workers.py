# utils/workers.py

import sys
from PyQt6.QtCore import QObject, QProcess, pyqtSignal

class JobRunner(QObject):
    """
    Runs a command-line job in a separate process and emits its output.
    """
    # Signals to communicate with the main GUI thread
    outputReady = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, command, args):
        super().__init__()
        self.command = command
        self.args = args
        self.process = QProcess()

        # Connect the QProcess signals to our handler methods
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_finished)

    def handle_stdout(self):
        """Reads standard output and emits it."""
        data = self.process.readAllStandardOutput().data().decode(errors='ignore').strip()
        if data:
            self.outputReady.emit(data)

    def handle_stderr(self):
        """Reads standard error and emits it."""
        data = self.process.readAllStandardError().data().decode(errors='ignore').strip()
        if data:
            self.outputReady.emit(f"[ERROR] {data}")

    def handle_finished(self, exit_code):
        """Emits the finished signal when the process is done."""
        self.outputReady.emit(f"\n--- Process finished with exit code {exit_code} ---")
        self.finished.emit(exit_code)

    def run(self):
        """Starts the process."""
        self.outputReady.emit(f"--- Starting job: {' '.join([self.command] + self.args)} ---\n")
        self.process.start(self.command, self.args)