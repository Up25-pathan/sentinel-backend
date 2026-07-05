# utils/docker_tools.py

import docker

def get_docker_client():
    """Initializes and returns a Docker client. Handles connection errors."""
    try:
        client = docker.from_env()
        client.ping() # Verify connection
        return client
    except docker.errors.DockerException:
        print("Error: Could not connect to Docker daemon. Is it running?")
        return None

def list_labs():
    """Lists all containers, adding a 'lab_name' for easier identification."""
    client = get_docker_client()
    if not client:
        return []
        
    containers = []
    for container in client.containers.list(all=True):
        lab_name = container.name
        # You could add logic here to filter for specific lab containers
        containers.append({
            "id": container.short_id,
            "name": lab_name,
            "image": container.image.tags[0] if container.image.tags else 'N/A',
            "status": container.status
        })
    return containers

def start_lab(container_name: str):
    """Starts a container by its name."""
    client = get_docker_client()
    if not client:
        return False, "Docker not connected"
        
    try:
        container = client.containers.get(container_name)
        container.start()
        return True, f"Successfully started {container_name}"
    except docker.errors.NotFound:
        return False, f"Container {container_name} not found"
    except Exception as e:
        return False, str(e)

def stop_lab(container_name: str):
    """Stops a container by its name."""
    client = get_docker_client()
    if not client:
        return False, "Docker not connected"
        
    try:
        container = client.containers.get(container_name)
        container.stop()
        return True, f"Successfully stopped {container_name}"
    except docker.errors.NotFound:
        return False, f"Container {container_name} not found"
    except Exception as e:
        return False, str(e)