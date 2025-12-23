import platform

import psutil


def get_cpu():
    return {
        "model": platform.processor(),
        "logical_core_count": psutil.cpu_count(logical=True),
        "physical_core_count": psutil.cpu_count(logical=False),
        "freq_mhz": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
    }

def get_cpu_usage():
    return psutil.cpu_percent(interval=1)