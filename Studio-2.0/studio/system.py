"""Local hardware facts; unavailable measurements are never guessed."""
import ctypes
import os
import platform
import shutil
import sys


def memory_bytes():
    if os.name == 'nt':
        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.total, status.available
    elif sys.platform.startswith('linux'):
        try:
            with open('/proc/meminfo') as file:
                values = {line.split(':')[0]: int(line.split()[1]) * 1024 for line in file}
            return values.get('MemTotal'), values.get('MemAvailable')
        except (OSError, ValueError):
            pass
    return None, None


def report(root, model_root):
    total, available = memory_bytes()
    disk = shutil.disk_usage(root)
    result = dict(os=platform.system(), os_version=platform.release(), python=platform.python_version(),
                  architecture=platform.machine(), cpu=platform.processor() or None,
                  logical_cpus=os.cpu_count(), ram_total_bytes=total, ram_available_bytes=available,
                  data_path=str(root.resolve()), model_path=str(model_root.resolve()),
                  disk_free_bytes=disk.free, cuda=False, gpu=None, vram=None)
    try:
        import torch
        result['cuda'] = torch.cuda.is_available()
        if result['cuda']:
            free, capacity = torch.cuda.mem_get_info()
            result.update(gpu=torch.cuda.get_device_name(0), vram=dict(
                total_bytes=capacity, free_bytes=free, allocated_bytes=torch.cuda.memory_allocated(),
                reserved_bytes=torch.cuda.memory_reserved(), peak_allocated_bytes=torch.cuda.max_memory_allocated()))
    except (ImportError, RuntimeError) as exc:
        result['gpu_check_error'] = type(exc).__name__
    return result
