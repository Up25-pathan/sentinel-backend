# monitor/monitor.py
import time, subprocess, json
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
import psutil
import docker

client = docker.from_env()

def get_host_metrics():
    return {
        "cpu": psutil.cpu_percent(interval=0.1),
        "mem": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent,
    }

def list_lab_containers():
    out=[]
    for c in client.containers.list(all=True):
        # only show containers whose name starts with lab_
        if c.name.startswith("lab_") or c.name.startswith("juice") or c.name.startswith("dvwa"):
            info = client.api.inspect_container(c.id)
            out.append({
                "name": c.name,
                "status": c.status,
                "uptime": info['State'].get('StartedAt',''),
            })
    return out

def render():
    host = get_host_metrics()
    tbl = Table(title="Host Health")
    tbl.add_column("CPU%"); tbl.add_column("Mem%"); tbl.add_column("Disk%")
    tbl.add_row(str(host["cpu"]), str(host["mem"]), str(host["disk"]))

    cont_table = Table(title="Lab Containers")
    cont_table.add_column("Name"); cont_table.add_column("Status"); cont_table.add_column("Uptime")
    for c in list_lab_containers():
        cont_table.add_row(c["name"], c["status"], c["uptime"][:19])

    return Panel(tbl) , Panel(cont_table)

if __name__ == "__main__":
    with Live(refresh_per_second=1) as live:
        while True:
            left, right = render()
            live.update(left)
            time.sleep(0.5)
            live.update(right)
            time.sleep(1)
