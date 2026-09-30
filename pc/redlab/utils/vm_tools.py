# utils/vm_tools.py

import re
import subprocess
import time

# Every call below blocks the calling thread. RedOpsPanel used to invoke these
# from __init__ and again on every navigation, with no timeout, so a wedged
# VirtualBox install froze the GUI indefinitely.
COMMAND_TIMEOUT = 10


def _run_command(args):
    """Run a VBoxManage command. Returns (ok, output)."""
    command = ["VBoxManage"] + args
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=COMMAND_TIMEOUT,
        )
        return True, result.stdout.strip()
    except FileNotFoundError:
        return False, "VBoxManage not found. Is VirtualBox installed and in your PATH?"
    except subprocess.TimeoutExpired:
        return False, f"VBoxManage {args[0] if args else '?'} timed out after {COMMAND_TIMEOUT}s"
    except subprocess.CalledProcessError as e:
        return False, (e.stderr or "").strip() or f"exit code {e.returncode}"

def list_vms():
    """Lists all available VirtualBox VMs."""
    success, output = _run_command(["list", "vms"])
    if not success:
        return []

    # The output format is "VM Name" {uuid}
    # We use regex to extract just the name inside the quotes
    return re.findall(r'"(.+?)"', output)

def get_vm_status(vm_name: str):
    """Checks if a VM is currently running."""
    success, output = _run_command(["showvminfo", vm_name, "--machinereadable"])
    if not success:
        return "error"
    
    # The output contains a line like: VMState="running" or VMState="poweroff"
    match = re.search(r'VMState="(\w+)"', output)
    return match.group(1) if match else "unknown"

def start_vm(vm_name: str):
    """Starts a VM in headless mode."""
    return _run_command(["startvm", vm_name, "--type", "headless"])

def stop_vm(vm_name: str):
    """Stops a VM gracefully using ACPI power button."""
    return _run_command(["controlvm", vm_name, "acpipowerbutton"])

def reset_vm(vm_name: str, snapshot_name: str):
    """Restores a VM to a given snapshot."""
    # First, power off the machine if it's running, as snapshots can only be restored when off.
    status = get_vm_status(vm_name)
    if status == "running":
        print(f"VM '{vm_name}' is running. Powering it off before restoring snapshot.")
        # We use 'poweroff' for a quick stop, as the state is being discarded anyway.
        _run_command(["controlvm", vm_name, "poweroff"])
        # Wait a moment for the VM to power down
        time.sleep(3)

    return _run_command(["snapshot", vm_name, "restore", snapshot_name])