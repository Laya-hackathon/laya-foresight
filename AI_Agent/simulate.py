

import sys
import json
import time
import urllib.request


BASE_URL = "http://localhost:8000"


def stream_scenario(scenario_id: str, scenario_name: str):
    url = f"{BASE_URL}/api/run/{scenario_id}"
    print(f"\n{'='*60}")
    print(f"🎯 Starting: {scenario_name}")
    print(f"   Endpoint: {url}")
    print(f"{'='*60}\n")

    req = urllib.request.Request(url)
    req.add_header('Accept', 'text/event-stream')

    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            buffer = ""
            for line_bytes in response:
                line = line_bytes.decode('utf-8').strip()
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    print_event(data)
                    if data['type'] in ('done', 'complete'):
                        if data['type'] == 'done':
                            break
    except Exception as e:
        print(f"❌ Error: {e}")


def print_event(event):
    t = event['type']
    d = event['data']

    if t == 'status':
        print(f"  📡 {d['message']}")
    elif t == 'api_call':
        print(f"  ⏳ {d['message']}")
    elif t == 'reasoning':
        print(f"\n  🧠 Claude (Step {d['step']}):")
        # Word-wrap the reasoning text
        text = d['text']
        for i in range(0, len(text), 80):
            print(f"     {text[i:i+80]}")
        print()
    elif t == 'tool_call':
        print(f"  🔧 Calling: {d['tool_name']}({json.dumps(d['tool_input'], indent=None)})")
    elif t == 'tool_result':
        result_str = json.dumps(d['result'], indent=2)
        # Truncate if too long
        if len(result_str) > 200:
            result_str = result_str[:200] + "..."
        print(f"  📦 Result: {result_str}")
    elif t == 'error':
        print(f"  ⚠️  {d['message']}")
    elif t == 'complete':
        print(f"\n  ✅ {d['message']}")
    elif t == 'done':
        print(f"  🏁 Scenario complete.\n")


def main():
    print("\n" + "╔" + "═"*58 + "╗")
    print("║  LayaAIAgent — Simulation Runner                        ║")
    print("║  Free Tier: 5 RPM · 15s between API calls               ║")
    print("╚" + "═"*58 + "╝\n")

    # Check health
    try:
        health = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/health").read())
        if not health.get('api_key_configured'):
            print("⚠️  WARNING: ANTHROPIC_API_KEY not configured in .env!")
            print("   Set it before running scenarios.\n")
            return
        print("✅ Server is healthy. API key configured.\n")
    except Exception as e:
        print(f"❌ Server not running at {BASE_URL}")
        print(f"   Start it with: python server.py")
        print(f"   Error: {e}\n")
        return

    # Get scenarios
    try:
        data = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/scenarios").read())
        scenarios = data['scenarios']
    except Exception as e:
        print(f"❌ Failed to fetch scenarios: {e}")
        return

    print(f"📋 Found {len(scenarios)} scenarios:\n")
    for i, s in enumerate(scenarios, 1):
        print(f"   {i}. [{s['risk_band']}] {s['name']}")
        print(f"      €{s['amount_eur']:,.0f} · {s['claim_type']} · {s['customer_name']}")
    print()

    # Check for specific scenario argument
    if len(sys.argv) > 1:
        scenario_id = sys.argv[1]
        scenario = next((s for s in scenarios if s['id'] == scenario_id), None)
        if scenario:
            stream_scenario(scenario_id, scenario['name'])
        else:
            print(f"❌ Unknown scenario: {scenario_id}")
            print(f"   Available: {', '.join(s['id'] for s in scenarios)}")
        return

    # Run all scenarios
    print("🚀 Running all scenarios sequentially...")
    print(f"   Estimated time: ~{len(scenarios) * 60}s ({len(scenarios)} scenarios × ~60s each)\n")

    start_time = time.time()

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'─'*60}")
        print(f"  Scenario {i}/{len(scenarios)}")
        print(f"{'─'*60}")

        stream_scenario(scenario['id'], scenario['name'])

        # Wait between scenarios (extra safety margin)
        if i < len(scenarios):
            wait = 5
            print(f"  ⏱️  Waiting {wait}s before next scenario...")
            time.sleep(wait)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"🏁 All {len(scenarios)} scenarios complete!")
    print(f"   Total time: {elapsed:.0f}s ({elapsed/60:.1f} minutes)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
