#!/usr/bin/env bash
# ── Multimodal Jailbreak Fuzzer — quick-run script ────────────────────────────
#
# 사용법:
#   ./run.sh text attacks
#   ./run.sh text harmbench
#   ./run.sh text packet [burp_packet.txt] [https://target.ngrok.app/api/chat]
#   ./run.sh text all
#   ./run.sh image [--strategies ...] [--payloads ...]
#   ./run.sh all
#
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHONUTF8=1 "$DIR/venv/bin/python3" "$DIR/main.py" "$@"
