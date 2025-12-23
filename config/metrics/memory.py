import psutil


def get_memory():
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
    }

def get_memory_usage():
    mem = psutil.virtual_memory()
    return {
        "used": mem.used,
        "available": mem.available,
        "percent": mem.percent,
    }