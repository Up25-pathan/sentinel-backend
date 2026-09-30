# utils/background.py

"""Run slow work off the GUI thread.

Every panel used to do its slow work inline: parsing the 45.7 MB ATT&CK dataset,
probing the Docker socket, shelling out to VBoxManage. All of it ran on the GUI
thread inside __init__, before the window was ever shown, so the app looked dead
at launch.

run_in_background(fn, on_done, on_error) pushes `fn` onto the global thread
pool. `fn` runs on a worker thread; because on_done is a bound method of a widget
living in the GUI thread, Qt delivers the result back on the GUI thread, so
callbacks may touch widgets directly.

Keep `fn` free of any widget access.
"""

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal


class _Signals(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    progressed = pyqtSignal(object)


class _Task(QRunnable):
    def __init__(self, fn, wants_progress=False):
        super().__init__()
        self._fn = fn
        self._wants_progress = wants_progress
        self.signals = _Signals()

    def run(self):
        try:
            if self._wants_progress:
                # fn receives `progress` so it can report long steps (e.g. an
                # ATT&CK download) back to the GUI thread.
                result = self._fn(progress=self.signals.progressed.emit)
            else:
                result = self._fn()
        except Exception as exc:  # noqa: BLE001 - report anything the worker raises
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.signals.done.emit(result)


def run_in_background(fn, on_done=None, on_error=None, on_progress=None):
    """Execute fn() on a worker thread.

    Returns the QRunnable so a caller can hold a reference; drop it otherwise,
    the pool keeps the task alive until it finishes.

    When on_progress is given, fn is called as fn(progress=cb); cb may be invoked
    any number of times from the worker thread and is delivered on the GUI thread.
    """
    task = _Task(fn, wants_progress=on_progress is not None)
    if on_done is not None:
        task.signals.done.connect(on_done)
    if on_error is not None:
        task.signals.failed.connect(on_error)
    if on_progress is not None:
        task.signals.progressed.connect(on_progress)
    QThreadPool.globalInstance().start(task)
    return task
