from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlDeviceGetUtilizationRates, nvmlDeviceGetName, nvmlDeviceGetClockInfo, NVML_CLOCK_GRAPHICS, \
    nvmlShutdown


def get_gpu():
    gpu_info = None
    try:
        nvmlInit()
        handle = nvmlDeviceGetHandleByIndex(0)

        mem_info = nvmlDeviceGetMemoryInfo(handle)

        gpu_info = {
            "name": nvmlDeviceGetName(handle).decode("utf-8"),
            "memory": {
                "total": mem_info.total,
            },
            "clock_mhz": nvmlDeviceGetClockInfo(
                handle, NVML_CLOCK_GRAPHICS
            ),
        }
    except Exception as e:
        gpu_info = {"error": str(e)}
    finally:
        try:
            nvmlShutdown()
        except:
            pass
    return gpu_info


def get_gpu_usage():
    gpu_info = None
    try:
        nvmlInit()
        handle = nvmlDeviceGetHandleByIndex(0)

        mem_info = nvmlDeviceGetMemoryInfo(handle)
        util = nvmlDeviceGetUtilizationRates(handle)

        gpu_info = {
            "memory": {
                "used": mem_info.used,
                "free": mem_info.free,
            },
            "utilization": {
                "gpu": util.gpu,
                "memory": util.memory,
            },
        }
    except Exception as e:
        gpu_info = {"error": str(e)}
    finally:
        try:
            nvmlShutdown()
        except:
            pass
    return gpu_info
