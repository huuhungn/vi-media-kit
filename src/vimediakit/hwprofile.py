# hwprofile.py - detect the hardware and pick a suitable speech-recognition configuration (PC with a GPU / CPU-only laptop)
"""detect() -> Hardware; recommend(hw) -> Profile.

Rules (measured on a 10-physical-core machine, small model, 56 s sample, using faster-whisper):
- NVIDIA GPU + the CUDA packages (cublas/cudnn): run on CUDA. VRAM >= 5 GB → large-v3-turbo; >= 3.5 GB → medium; otherwise small.
- No GPU / missing CUDA packages / weak GPU: run on CPU with int8, small model (base if RAM < 6 GB or < 3 cores).
  cpu_threads = number of physical cores (leave 1 core for the UI when there are >= 6 cores); ctranslate2 defaults to only 4.
  beam 3 (more accurate) with >= 6 cores, beam 1 (almost twice as fast) on weaker machines.
- Long audio (>= 25 s) is processed in batches (BatchedInferencePipeline): ~25% faster on CPU, more on GPU.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field


@dataclass
class Hardware:
    cpu_cores: int = 4          # physical cores
    cpu_threads: int = 4        # logical threads
    ram_gb: float = 8.0
    gpu_name: str = ""          # "" if there is no NVIDIA GPU
    vram_mb: int = 0
    cuda_devices: int = 0       # number of CUDA GPUs ctranslate2 can see
    cuda_libs: bool = False     # cublas64_12 + cudnn64_9 are present
    notes: list[str] = field(default_factory=list)

    @property
    def cuda_ready(self) -> bool:
        return self.cuda_devices > 0 and self.cuda_libs


@dataclass
class Profile:
    device: str            # "cuda" | "cpu"
    model: str
    beam: int
    cpu_threads: int
    batch_size: int
    ghi_chu: str


def _nvidia_smi() -> tuple[str, int]:
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0 and r.stdout.strip():
            name, _, mem = r.stdout.strip().splitlines()[0].partition(",")
            return name.strip(), int(float(mem.strip() or 0))
    except Exception:
        pass
    return "", 0


def _cuda_libs_ok() -> bool:
    """Whether cublas 12 and cudnn 9 can be loaded (Windows). On other platforms: trust ctranslate2."""
    if os.name != "nt":
        return True
    import ctypes
    try:
        for dll in ("cublas64_12.dll", "cudnn64_9.dll"):
            ctypes.WinDLL(dll)
        return True
    except OSError:
        return False


def detect(check_cuda: bool = True) -> Hardware:
    hw = Hardware()
    logical = os.cpu_count() or 4
    cores = logical
    ram = 8.0
    try:
        import psutil
        cores = psutil.cpu_count(logical=False) or logical
        logical = psutil.cpu_count(logical=True) or logical
        ram = psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        hw.notes.append("không đọc được psutil")
    hw.cpu_cores, hw.cpu_threads, hw.ram_gb = max(1, cores), max(1, logical), round(ram, 1)
    hw.gpu_name, hw.vram_mb = _nvidia_smi()
    if check_cuda and hw.gpu_name:
        try:
            import ctranslate2
            hw.cuda_devices = int(ctranslate2.get_cuda_device_count())
        except Exception as e:
            hw.notes.append(f"ctranslate2: {e}")
        if hw.cuda_devices:
            hw.cuda_libs = _cuda_libs_ok()
    return hw


def recommend(hw: Hardware | None = None) -> Profile:
    hw = hw or detect()
    if hw.cuda_ready:
        if hw.vram_mb >= 5000:
            model, batch = "large-v3-turbo", 8
        elif hw.vram_mb >= 3500:
            model, batch = "medium", 8
        else:
            model, batch = "small", 8
        return Profile("cuda", model, 3, 0, batch,
                       f"GPU {hw.gpu_name} ({hw.vram_mb // 1024} GB) — chạy CUDA, model {model}")
    # CPU (laptop without a discrete GPU, or a GPU without the CUDA packages)
    cores = hw.cpu_cores
    threads = cores if cores < 6 else min(cores - 1, 12)
    if hw.ram_gb < 6 or cores < 3:
        model, beam, batch = "base", 1, 4
    elif cores < 6:
        model, beam, batch = "small", 1, 4
    else:
        model, beam, batch = "small", 3, 8
    why = f"CPU {cores} lõi · RAM {hw.ram_gb:.0f} GB"
    if hw.gpu_name and not hw.cuda_libs:
        why += f" — có GPU {hw.gpu_name} nhưng chưa cài gói CUDA (Cài đặt → Cài gói GPU để nhanh hơn)"
    elif not hw.gpu_name:
        why += " — không có GPU NVIDIA, chạy bằng CPU"
    return Profile("cpu", model, beam, threads, batch, f"{why}; gợi ý model {model}")


_cache: dict[str, Hardware] = {}


def hardware(refresh: bool = False) -> Hardware:
    """Detect once per session (nvidia-smi takes ~0.2 s); use refresh=True after installing the GPU packages."""
    if refresh or "hw" not in _cache:
        _cache["hw"] = detect()
    return _cache["hw"]


def tom_tat(hw: Hardware, prof: Profile) -> str:
    if hw.cuda_ready:
        gpu = f"GPU {hw.gpu_name} · CUDA sẵn sàng"
    elif hw.gpu_name:
        gpu = f"GPU {hw.gpu_name} · chưa có gói CUDA"
    else:
        gpu = "không có GPU NVIDIA"
    return (f"Máy này: CPU {hw.cpu_cores} lõi/{hw.cpu_threads} luồng · RAM {hw.ram_gb:.0f} GB · {gpu}\n"
            f"Gợi ý: chạy {'GPU' if prof.device == 'cuda' else 'CPU'}, model {prof.model}")
