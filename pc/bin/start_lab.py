#!/usr/bin/env python3
import docker, sqlite3, time, uuid, os
DB="db/audit.db"
client = docker.from_env()

def ensure_db():
    os.makedirs("db", exist_ok=True)
    conn=sqlite3.connect(DB)
    c=conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS audit(id TEXT,ts TEXT,user TEXT,action TEXT,meta TEXT)")
    conn.commit()
    conn.close()

def audit(user, action, meta=""):
    conn=sqlite3.connect(DB)
    c=conn.cursor()
    c.execute("INSERT INTO audit VALUES(?,?,?, ?, ?)", (str(uuid.uuid4()), time.ctime(), user, action, meta))
    conn.commit()
    conn.close()

def start_juice_shop():
    net_name = "lab_juice_net"
    try:
        client.networks.get(net_name)
    except docker.errors.NotFound:
        client.networks.create(net_name, internal=True)
    cont = client.containers.run(
        "bkimminich/juice-shop:latest",
        name="lab_juice",
        detach=True,
        network=net_name,
        mem_limit="1g",
        cpu_period=100000, cpu_quota=50000,
        remove=True
    )
    audit("labadmin","start_juice", f"container:{cont.id}")
    print("Started lab_juice:", cont.id)

if __name__=="__main__":
    ensure_db()
    start_juice_shop()
