@echo off
REM Convenience launcher for the multimodal jailbreak fuzzer (Windows cmd/PowerShell).
REM Forwards every argument to mmfuzz.py.
python "%~dp0mmfuzz.py" %*
