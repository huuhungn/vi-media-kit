# hwprofile.py - dò phần cứng và chọn cấu hình nhận dạng giọng nói phù hợp (PC có GPU / laptop chỉ có CPU)
"""detect() -> Hardware; recommend(hw) -> Profile.

Quy tắc (đo trên máy 10 lõi vật lý, model small, mẫu 56 s — đo bằng faster-whisper):
- GPU NVIDIA + đủ gói CUDA (cublas/cudnn): chạy CUDA. VRAM >= 5 GB → large-v3-turbo; >= 3,5 GB → medium; còn lại small.
- Không có GPU / thiếu gói CUDA / GPU yếu: chạy CPU int8, model small (base nếu RAM < 6 GB hoặc < 3 lõi).
  cpu_threads = số lõi vật lý (chừa 1 lõi cho giao diện khi >= 6 lõi); mặc định của ctranslate2 chỉ là 4.
  beam 3 (chính xác) khi >= 6 lõi, beam 1 (nhanh gần gấp đôi) với máy yếu hơn.
- Âm thanh dài (>= 25 s) chạy theo lô (BatchedInferencePipeline): nhanh hơn ~25 % với CPU, nhiều hơn với GPU.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field


@dataclass
class Hardware:
    cpu_cores: int = 4          # lõi vật lý
    cpu_threads: int = 4        # luồng logic
    ram_gb: float = 8.0
    gpu_name: str = ""          # "" nếu không có GPU NVIDIA
    vram_mb: int = 0
    cuda_devices: int = 0       # ctranslate2 thấy bao nhiêu GPU CUDA
    cuda_libs: bool = False     # đã có cublas64_12 + cudnn64_9
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
    """Có nạp được cublas 12 và cudnn 9 (Windows) hay không. Nền tảng khác: tin vào ctranslate2."""
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
    # CPU (laptop không có GPU rời, hoặc GPU chưa có gói CUDA)
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
    """Dò một lần mỗi phiên (nvidia-smi chậm ~0,2 s); refresh=True sau khi cài gói GPU."""
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
