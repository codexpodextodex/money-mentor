#!/usr/bin/env bash
# A few plain requests to the model server on this machine, to tell a healthy model from a
# broken one before the app is pointed at it. Prints only the first part of each answer.
set -uo pipefail
APP_DIR="${APP_DIR:-/root/money-mentor}"
KEY=$(grep '^LLM_API_KEY=' "$APP_DIR/.env" | cut -d= -f2)
URL="http://127.0.0.1:8001/v1"

ask() {  # name, json body
  local started=$(date +%s.%N)
  curl -s -m 120 "$URL/chat/completions" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "$2" |
    python3 -c "
import sys, json, time
try:
    d = json.load(sys.stdin)
    m = d['choices'][0]['message']
    text = (m.get('content') or '').replace('\n', ' ')[:160]
    calls = [c['function']['name'] + ' ' + c['function']['arguments'][:80] for c in (m.get('tool_calls') or [])]
    print('  answer:', repr(text), '| tools:', calls, '| tokens:', d.get('usage', {}).get('completion_tokens'))
except Exception as exc:
    print('  FAILED:', type(exc).__name__, str(exc)[:120])
"
  echo "  ($1, $(python3 -c "import time; print(round(time.time() - $started, 1))") s)"
}

OFF='"chat_template_kwargs": {"enable_thinking": false}'
ask "greedy" '{"model": "nemotron-3.5-super-vl", "temperature": 0, "max_tokens": 24, '"$OFF"', "messages": [{"role": "user", "content": "What is the capital of Finland? One word."}]}'
ask "temperature 0.2" '{"model": "nemotron-3.5-super-vl", "temperature": 0.2, "max_tokens": 40, '"$OFF"', "messages": [{"role": "user", "content": "Name three Finnish cities, comma separated."}]}'
ask "tool call" '{"model": "nemotron-3.5-super-vl", "temperature": 0.2, "max_tokens": 200, '"$OFF"', "messages": [{"role": "user", "content": "How much did I spend on taxis last month?"}], "tool_choice": "auto", "tools": [{"type": "function", "function": {"name": "get_spending", "description": "Total spending in a period, optionally by kind of place.", "parameters": {"type": "object", "properties": {"period": {"type": "string"}, "subcategory": {"type": "string"}}}}}]}'
docker ps -a --format "  server: {{.Names}} {{.Status}}"
