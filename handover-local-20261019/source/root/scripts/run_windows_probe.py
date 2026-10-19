"""Bound a Windows diagnostic process tree; never a benchmark runner."""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import time

GIB = 1024**3


class GpuTelemetry:
    """Allow at most two missing running samples; preflight is always strict."""

    def __init__(self) -> None:
        self.consecutive_failures = 0
        self.total_failures = 0
        self.last_error: str | None = None

    def sample(self, *, strict: bool = False) -> float | None:
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                text=True, timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            fractions = []
            for row in output.strip().splitlines():
                used, total = map(float, row.split(','))
                if not all(map(math.isfinite, (used, total))) or not 0 <= used <= total or total <= 0:
                    raise ValueError('Invalid GPU memory telemetry')
                fractions.append(used / total)
            if not fractions:
                raise ValueError('Empty GPU telemetry')
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            self.consecutive_failures += 1
            self.total_failures += 1
            self.last_error = f'{type(error).__name__}: {error}'
            logging.warning('GPU_TELEMETRY_MISSING consecutive=%d total=%d error=%s',
                            self.consecutive_failures, self.total_failures, self.last_error)
            if strict or self.consecutive_failures >= 3:
                raise RuntimeError('GPU telemetry unavailable; bounded retry limit reached or preflight failed') from error
            return None
        if self.consecutive_failures:
            logging.info('GPU_TELEMETRY_RECOVERED after=%d', self.consecutive_failures)
        self.consecutive_failures = 0
        self.last_error = None
        return max(fractions)


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64),
                ("flags", W.DWORD), ("min_ws", C.c_size_t), ("max_ws", C.c_size_t),
                ("active_limit", W.DWORD), ("affinity", C.c_size_t),
                ("priority", W.DWORD), ("scheduling", W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", C.c_uint64 * 6),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process_memory", C.c_size_t), ("peak_job_memory", C.c_size_t)]


class CpuRate(C.Structure):
    _fields_ = [("flags", W.DWORD), ("rate", W.DWORD)]


class StartupInfo(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR),
                ("title", W.LPWSTR), ("x", W.DWORD), ("y", W.DWORD),
                ("xsize", W.DWORD), ("ysize", W.DWORD), ("xchars", W.DWORD),
                ("ychars", W.DWORD), ("fill", W.DWORD), ("flags", W.DWORD),
                ("show", W.WORD), ("reserved_size", W.WORD), ("reserved_ptr", C.c_void_p),
                ("stdin", W.HANDLE), ("stdout", W.HANDLE), ("stderr", W.HANDLE)]


class ProcessInfo(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE),
                ("pid", W.DWORD), ("tid", W.DWORD)]


class MemoryStatus(C.Structure):
    _fields_ = [("length", W.DWORD), ("load", W.DWORD),
                ("total", C.c_uint64), ("available", C.c_uint64),
                ("total_commit", C.c_uint64), ("available_commit", C.c_uint64),
                ("total_virtual", C.c_uint64), ("available_virtual", C.c_uint64),
                ("extended_virtual", C.c_uint64)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--memory-gib", type=float, default=8)
    parser.add_argument("--result-json", type=Path,
                        help="Require a diagnostic report with status=passed as well as exit 0")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if os.name != "nt" or not command or not 0 < args.memory_gib <= 14 or args.timeout <= 0:
        parser.error("Windows, a command, a positive timeout, and a memory cap <=14 GiB are required")
    import msvcrt
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args.output.mkdir(parents=True, exist_ok=False)
    kernel = C.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
        "CreateProcessW": ([W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD,
                            C.c_void_p, W.LPCWSTR, C.POINTER(StartupInfo), C.POINTER(ProcessInfo)], W.BOOL),
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
        "TerminateProcess": ([W.HANDLE, W.UINT], W.BOOL),
        "ResumeThread": ([W.HANDLE], W.DWORD),
        "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
        "GetExitCodeProcess": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
        "CloseHandle": ([W.HANDLE], W.BOOL),
        "GlobalMemoryStatusEx": ([C.POINTER(MemoryStatus)], W.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        getattr(kernel, name).argtypes = arguments
        getattr(kernel, name).restype = result

    def checked(result: int) -> int:
        if not result:
            raise C.WinError(C.get_last_error())
        return result

    telemetry = GpuTelemetry()

    def sample(*, strict: bool = False) -> dict:
        gpu_fraction = telemetry.sample(strict=strict)
        memory = MemoryStatus(length=C.sizeof(MemoryStatus))
        checked(kernel.GlobalMemoryStatusEx(C.byref(memory)))
        return {"available_gib": memory.available / GIB,
                "available_commit_gib": memory.available_commit / GIB,
                "gpu_memory_fraction": gpu_fraction,
                "gpu_telemetry_consecutive_failures": telemetry.consecutive_failures,
                "gpu_telemetry_error": telemetry.last_error}

    report = {"scope": "diagnostic_only_not_benchmark", "command": command,
              "limits": {"job_memory_gib": args.memory_gib, "cpu_percent": 60,
                         "active_processes": 32, "min_available_gib": 4, "min_available_commit_gib": 2,
                         "max_gpu_fraction": 0.8, "timeout_s": args.timeout,
                         "gpu_query_timeout_s": 8, "max_missing_gpu_samples": 2,
                         "preflight_gpu_required": True}}
    job = None
    info = ProcessInfo()
    started = time.monotonic()
    try:
        if args.result_json and args.result_json.exists():
            raise RuntimeError('Refusing a pre-existing diagnostic report')
        initial = sample(strict=True)
        report["initial"] = initial
        if (initial['available_gib'] < args.memory_gib + 4
                or initial['available_commit_gib'] < args.memory_gib + 2
                or initial['gpu_memory_fraction'] > 0.8):
            raise RuntimeError("Preflight: insufficient host reserve or GPU memory")
        job = checked(kernel.CreateJobObjectW(None, None))
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000 | 0x200 | 0x8  # kill-on-close, job-memory, active-process count
        limits.basic.active_limit = 32
        limits.job_memory = int(args.memory_gib * GIB)
        checked(kernel.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
        cpu = CpuRate(flags=1 | 4, rate=6000)  # enabled + hard cap
        checked(kernel.SetInformationJobObject(job, 15, C.byref(cpu), C.sizeof(cpu)))
        with (args.output / "stdout.log").open('wb') as log, open(os.devnull, 'rb') as null:
            os.set_inheritable(log.fileno(), True)
            os.set_inheritable(null.fileno(), True)
            startup = StartupInfo(cb=C.sizeof(StartupInfo), flags=0x100 | 1, show=0,
                                  stdin=msvcrt.get_osfhandle(null.fileno()),
                                  stdout=msvcrt.get_osfhandle(log.fileno()),
                                  stderr=msvcrt.get_osfhandle(log.fileno()))
            line = C.create_unicode_buffer(subprocess.list2cmdline(command))
            checked(kernel.CreateProcessW(None, line, None, None, True,
                                          0x4 | 0x08000000 | 0x4000, None, str(args.cwd),
                                          C.byref(startup), C.byref(info)))
            checked(kernel.AssignProcessToJobObject(job, info.process))
            if kernel.ResumeThread(info.thread) == 0xFFFFFFFF:
                raise C.WinError(C.get_last_error())
            report["pid"] = info.pid
            with (args.output / 'resources.jsonl').open('w') as samples:
                while kernel.WaitForSingleObject(info.process, 1000) == 258:
                    current = sample()
                    current['elapsed_s'] = time.monotonic() - started
                    samples.write(json.dumps(current) + '\n')
                    samples.flush()
                    if args.result_json and args.result_json.exists():
                        try:
                            interim = json.loads(args.result_json.read_text(encoding='utf-8'))
                        except (json.JSONDecodeError, FileNotFoundError):
                            interim = {}  # A producer may still be writing the report.
                        if interim.get('status') == 'failed':
                            raise RuntimeError(f"Diagnostic reported failure: {interim.get('error', '')}")
                    if current['available_gib'] < 4 or current['available_commit_gib'] < 2:
                        raise RuntimeError('Host memory reserve exhausted')
                    if current['gpu_memory_fraction'] is not None and current['gpu_memory_fraction'] > 0.8:
                        raise RuntimeError('GPU memory guard exceeded')
                    if current['elapsed_s'] > args.timeout:
                        raise RuntimeError('Diagnostic wall-clock timeout')
            exit_code = W.DWORD()
            checked(kernel.GetExitCodeProcess(info.process, C.byref(exit_code)))
            report['exit_code'] = exit_code.value
            report['status'] = 'completed' if exit_code.value == 0 else 'failed'
            if args.result_json:
                report['result_json'] = str(args.result_json)
                result = json.loads(args.result_json.read_text(encoding='utf-8'))
                report['diagnostic_status'] = result.get('status')
                if result.get('status') != 'passed':
                    report['status'] = 'failed'
    except Exception as error:
        report['status'] = 'guard_or_launch_failed'
        report['error'] = str(error)
        if job:
            kernel.TerminateJobObject(job, 137)
        if info.process:
            kernel.TerminateProcess(info.process, 137)
        logging.exception('Diagnostic stopped')
    finally:
        if job:
            peak = ExtendedLimits()
            if kernel.QueryInformationJobObject(job, 9, C.byref(peak), C.sizeof(peak), None):
                report['peak_job_commit_gib'] = peak.peak_job_memory / GIB
            kernel.CloseHandle(job)
        for handle in (info.thread, info.process):
            if handle:
                kernel.CloseHandle(handle)
        report['elapsed_s'] = round(time.monotonic() - started, 2)
        report['gpu_telemetry_failures'] = telemetry.total_failures
        report['gpu_telemetry_last_error'] = telemetry.last_error
        (args.output / 'execution.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    logging.info('%s', json.dumps(report))
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
