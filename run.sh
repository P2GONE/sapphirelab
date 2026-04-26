#!/usr/bin/env bash
# ── Multimodal Jailbreak Fuzzer — quick-run script ────────────────────────────
#
# 사용법:
#   ./run.sh text attacks
#   ./run.sh text harmbench
#   ./run.sh text packet [burp_packet.txt] [https://target.ngrok.app/api/chat] [--limit N]
#   ./run.sh text resume [session_TIMESTAMP.json] [https://target.ngrok.app/api/chat] [--limit N]
#   ./run.sh text all
#   ./run.sh audio --packet burp_audio_packet.txt --target https://target/api/chat [--limit N]
#   ./run.sh image-packet --packet burp_image_packet.txt --target https://target/api/chat [--limit N] [--strategies ...]
#   ./run.sh image [--strategies ...] [--payloads ...]   # Gemini API 직접 테스트
#   ./run.sh all
#
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHONUTF8=1 "$DIR/venv/bin/python3" "$DIR/main.py" "$@"
