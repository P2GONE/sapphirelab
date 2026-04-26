"""
Multimodal Jailbreak Fuzzer
쇼핑몰 멀티모달 챗봇 안전 정책 우회 테스트 — 텍스트/이미지 통합 퍼저

사용법:
  python main.py text attacks                       # .atk 공격 파일 실행
  python main.py text harmbench                     # HarmBench 데이터셋 실행
  python main.py text packet [file] [target_url]    # Burp Suite 패킷 리플레이
  python main.py text all                           # attacks + harmbench

  python main.py audio                               # 오디오 퍼징 (Burp 패킷 기반)
  python main.py audio --packet burp_packet.txt --target https://target/api/chat

  python main.py image                              # 모든 페이로드 × 모든 전략
  python main.py image --strategies text_overlay_visible steganography_lsb
  python main.py image --payloads DO-001 SE-001
  python main.py image --image samples/product.jpg
  python main.py image --dry-run                    # API 호출 없이 이미지만 생성

  python main.py all                                # harmbench + 이미지 전체 실행
"""
import os
import sys
import argparse
import asyncio

import pyfiglet
from termcolor import colored
from rich.console import Console

console = Console(highlight=False, emoji=False)


def print_motd():
    if os.name == 'nt':
        os.system('color')
    print('Welcome to')
    print(colored(
        pyfiglet.figlet_format("MM Fuzzer", font='starwars', justify='left', width=180),
        'green',
    ))
    print(colored('### Warning: Use this fuzzer only on your own integrations!', 'red'))
    print(colored('### Do not attempt to harm or scan external systems!', 'red'))
    print()


# ── Text fuzzer ──────────────────────────────────────────────────────────────

def run_text(args):
    from fuzzer.text.engine import LLMfuzzer
    fuzzer = LLMfuzzer("fuzzer.cfg")

    mode = getattr(args, 'text_mode', None) or 'attacks'

    if mode == 'packet':
        packet_file = getattr(args, 'packet_file', None) or 'burp_packet.txt'
        target_url  = getattr(args, 'target_url', None)
        fuzzer.runFromPacket(packet_file, target_url=target_url)
    else:
        fuzzer.checkConnection()
        if mode == 'harmbench':
            fuzzer.runHarmBench()
        elif mode == 'all':
            fuzzer.runAttacks()
            fuzzer.runHarmBench()
        else:
            fuzzer.runAttacks()


# ── Image fuzzer ─────────────────────────────────────────────────────────────

async def run_image(args):
    from fuzzer.image.image_fuzzer import ImageFuzzer, MutationStrategy, ALL_STRATEGIES
    from payloads.injection_payloads import PAYLOADS, PAYLOAD_MAP
    from runner.image_runner import TestRunner
    from reporter.report import save_results, print_image_summary
    from config import OUTPUT_DIR, RESULTS_DIR, settings

    # Strategy selection
    strategies = None
    if getattr(args, 'strategies', None):
        try:
            strategies = [MutationStrategy(s) for s in args.strategies]
        except ValueError as e:
            console.print(f"[red]Unknown strategy: {e}[/red]")
            console.print(f"Available: {[s.value for s in MutationStrategy]}")
            return

    # Payload selection
    if getattr(args, 'payloads', None):
        payloads = [PAYLOAD_MAP[pid] for pid in args.payloads if pid in PAYLOAD_MAP]
        missing  = [pid for pid in args.payloads if pid not in PAYLOAD_MAP]
        if missing:
            console.print(f"[yellow]Unknown payload IDs: {missing}[/yellow]")
    else:
        payloads = PAYLOADS

    base_image  = getattr(args, 'image', None)
    no_save     = getattr(args, 'no_save', False)
    dry_run     = getattr(args, 'dry_run', False)
    user_prompt = getattr(args, 'prompt', '이 제품 이미지를 분석하고 설명해주세요.')

    console.rule("[bold red]Image Fuzzer[/bold red]")
    console.print(f"Payloads   : {len(payloads)}")
    console.print(f"Strategies : {len(strategies) if strategies else len(ALL_STRATEGIES)}")
    console.print(f"Base image : {base_image or '(synthetic)'}")
    console.print(f"Model      : [cyan]{settings.gemini_model}[/cyan]")
    console.print()

    console.print("[bold]Step 1: Generating mutated images...[/bold]")
    fuzzer = ImageFuzzer(
        base_image_path=base_image,
        output_dir=OUTPUT_DIR,
        save_images=not no_save,
    )
    mutated_images = fuzzer.fuzz_all_payloads(payloads, strategies)

    ok  = sum(1 for m in mutated_images if not m.error)
    err = sum(1 for m in mutated_images if m.error)
    console.print(f"  Generated: [green]{ok}[/green] ok, [yellow]{err}[/yellow] errors\n")

    if dry_run:
        console.print("[yellow]Dry run — skipping API calls.[/yellow]")
        if not no_save:
            console.print(f"Images saved to: {OUTPUT_DIR}")
        return

    console.print("[bold]Step 2: Testing against Gemini...[/bold]")
    runner  = TestRunner()
    results = await runner.run_batch(
        [m for m in mutated_images if not m.error],
        payload_map=PAYLOAD_MAP,
        user_prompt=user_prompt,
    )

    result_path = save_results(results, RESULTS_DIR)
    console.print(f"\nResults saved: [cyan]{result_path}[/cyan]")
    print_image_summary(results)


# ── CLI parser ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multimodal Jailbreak Fuzzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    # text ---------------------------------------------------------------
    text_p = sub.add_parser("text", help="텍스트 LLM 퍼징")
    text_sub = text_p.add_subparsers(dest="text_mode")
    text_sub.add_parser("attacks",   help=".atk 공격 파일 실행")
    text_sub.add_parser("harmbench", help="HarmBench 데이터셋 실행")
    text_sub.add_parser("all",       help="attacks + harmbench")
    pkt_p = text_sub.add_parser("packet", help="Burp Suite 패킷 리플레이")
    pkt_p.add_argument("packet_file", nargs="?", default="burp_packet.txt")
    pkt_p.add_argument("target_url",  nargs="?", default=None)

    # image --------------------------------------------------------------
    img_p = sub.add_parser("image", help="이미지 멀티모달 퍼징")
    img_p.add_argument("--image",      type=str,  default=None, help="베이스 이미지 경로")
    img_p.add_argument("--strategies", nargs="+", default=None, help="뮤테이션 전략 목록")
    img_p.add_argument("--payloads",   nargs="+", default=None, help="페이로드 ID 목록")
    img_p.add_argument("--prompt",     type=str,  default="이 제품 이미지를 분석하고 설명해주세요.")
    img_p.add_argument("--no-save",    action="store_true")
    img_p.add_argument("--dry-run",    action="store_true")

    # audio --------------------------------------------------------------
    aud_p = sub.add_parser("audio", help="오디오 멀티모달 퍼징")
    aud_p.add_argument("--packet",  type=str, default="burp_packet.txt", help="Burp 패킷 파일")
    aud_p.add_argument("--target",  type=str, default=None, help="타겟 URL (패킷 Host 대신 사용)")

    # all ----------------------------------------------------------------
    all_p = sub.add_parser("all", help="harmbench(텍스트) + 이미지 전체 실행")
    all_p.add_argument("--image",      type=str,  default=None)
    all_p.add_argument("--strategies", nargs="+", default=None)
    all_p.add_argument("--payloads",   nargs="+", default=None)
    all_p.add_argument("--prompt",     type=str,  default="이 제품 이미지를 분석하고 설명해주세요.")
    all_p.add_argument("--no-save",    action="store_true")

    return parser


# ── Entry point ──────────────────────────────────────────────────────────────

async def main():
    print_motd()
    args = build_parser().parse_args()

    if args.mode == "text":
        run_text(args)

    elif args.mode == "audio":
        from fuzzer.audio.engine import AudioLLMFuzzer
        fuzzer = AudioLLMFuzzer("fuzzer.cfg")
        fuzzer.runAudioPacket(args.packet, target_url=args.target)

    elif args.mode == "image":
        await run_image(args)

    elif args.mode == "all":
        class _TextArgs:
            text_mode = 'harmbench'
        run_text(_TextArgs())
        await run_image(args)


if __name__ == "__main__":
    asyncio.run(main())
