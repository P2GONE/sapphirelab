import sys
import llmfuzzer

# Print MOTD
llmfuzzer.printMotd()

# Create llmfuzzer instance
fuzzer = llmfuzzer.LLMfuzzer("llmfuzzer.cfg")

# -------------------------------------------------------------------
# Usage:
#   python main.py                          -> run .atk attacks
#   python main.py harmbench               -> HarmBench via config API
#   python main.py packet [packet.txt]     -> HarmBench via raw packet
#   python main.py all                     -> attacks + HarmBench
# -------------------------------------------------------------------
mode = sys.argv[1] if len(sys.argv) > 1 else 'attacks'

if mode == 'packet':
    # Target comes from the packet file — skip config connection check
    packet_file = sys.argv[2] if len(sys.argv) > 2 else 'packet.txt'
    target_url  = sys.argv[3] if len(sys.argv) > 3 else None
    fuzzer.runFromPacket(packet_file, target_url=target_url)

else:
    # All other modes use the configured API endpoint
    fuzzer.checkConnection()

    if mode == 'harmbench':
        fuzzer.runHarmBench()
    elif mode == 'all':
        fuzzer.runAttacks()
        fuzzer.runHarmBench()
    else:
        fuzzer.runAttacks()
