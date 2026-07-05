# utils/system_monitor.py

import psutil

def get_cpu_usage() -> float:
    """Returns the current system-wide CPU utilization as a percentage."""
    return psutil.cpu_percent(interval=None)

def get_memory_usage() -> float:
    """Returns the current system-wide memory utilization as a percentage."""
    return psutil.virtual_memory().percent