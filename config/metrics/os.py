import platform


def get_os():
    return {
        "platform": platform.platform(),
        "os": platform.system(),
        "version": platform.version(),
        "release": platform.release(),
    }