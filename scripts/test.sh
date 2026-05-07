#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
RUN_ID="${RUN_ID:-$(date +%s)}"
USER_ID="${USER_ID:-api-test-user-${RUN_ID}}"
SESSION_PREFIX="${SESSION_PREFIX:-api-test-${RUN_ID}}"

if [[ -n "${MEMORY_AUTH_TOKEN:-}" ]]; then
  AUTH_ARGS=(-H "Authorization: Bearer ${MEMORY_AUTH_TOKEN}")
else
  AUTH_ARGS=()
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

request_json() {
  local method="$1"
  local path="$2"
  local body="${3:-}"

  if [[ -n "$body" ]]; then
    curl -fsS \
      -X "$method" \
      "${BASE_URL}${path}" \
      -H "Content-Type: application/json" \
      "${AUTH_ARGS[@]}" \
      -d "$body"
  else
    curl -fsS \
      -X "$method" \
      "${BASE_URL}${path}" \
      "${AUTH_ARGS[@]}"
  fi
}

request_status() {
  local method="$1"
  local path="$2"
  local body="${3:-}"

  if [[ -n "$body" ]]; then
    curl -sS \
      -o /tmp/memory-service-test-response.json \
      -w "%{http_code}" \
      -X "$method" \
      "${BASE_URL}${path}" \
      -H "Content-Type: application/json" \
      "${AUTH_ARGS[@]}" \
      -d "$body"
  else
    curl -sS \
      -o /tmp/memory-service-test-response.json \
      -w "%{http_code}" \
      -X "$method" \
      "${BASE_URL}${path}" \
      "${AUTH_ARGS[@]}"
  fi
}

assert_json_contains() {
  local json="$1"
  local expected="$2"

  RESPONSE_JSON="$json" python3 - "$expected" <<'PY'
import json
import os
import sys

expected = sys.argv[1]
payload = json.loads(os.environ["RESPONSE_JSON"])
text = json.dumps(payload, sort_keys=True)
if expected not in text:
    print(f"Expected to find {expected!r} in response:", file=sys.stderr)
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    raise SystemExit(1)
PY
}

assert_status() {
  local actual="$1"
  local expected="$2"
  local label="$3"

  if [[ "$actual" != "$expected" ]]; then
    echo "FAIL: ${label} expected HTTP ${expected}, got ${actual}" >&2
    if [[ -f /tmp/memory-service-test-response.json ]]; then
      cat /tmp/memory-service-test-response.json >&2
      echo >&2
    fi
    exit 1
  fi
}

print_json() {
  local title="$1"
  local json="$2"

  echo
  echo "=== ${title} ==="
  RESPONSE_JSON="$json" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["RESPONSE_JSON"])
print(json.dumps(payload, indent=2, sort_keys=True))
PY
}

pass() {
  echo "PASS: $1"
}

require_command curl
require_command python3

echo "Live endpoint test target: ${BASE_URL}"
echo "This script does not start Docker. Start the stack first:"
echo "  docker compose up --build"
echo

health="$(request_json GET /health)"
print_json "GET /health" "$health"
assert_json_contains "$health" '"status": "ok"'
assert_json_contains "$health" '"database": "ok"'
pass "health returned ok"

echo
echo "Running full memory smoke flow..."
bash scripts/smoke.sh
pass "smoke flow passed"

cold_user="${USER_ID}-cold"
cold_recall="$(request_json POST /recall "{
  \"query\": \"What do we know about this user?\",
  \"session_id\": \"${SESSION_PREFIX}-cold\",
  \"user_id\": \"${cold_user}\",
  \"max_tokens\": 256
}")"
print_json "POST /recall cold user" "$cold_recall"
assert_json_contains "$cold_recall" '"context"'
assert_json_contains "$cold_recall" '"citations": []'
pass "cold recall returns a valid empty response"

bad_turn_status="$(request_status POST /turns "{
  \"session_id\": \"${SESSION_PREFIX}-bad\",
  \"user_id\": \"${USER_ID}\",
  \"messages\": [],
  \"timestamp\": \"2026-05-07T10:00:00Z\",
  \"metadata\": {}
}")"
assert_status "$bad_turn_status" "422" "POST /turns empty messages"
pass "POST /turns rejects empty messages with 422"

bad_recall_status="$(request_status POST /recall "{
  \"query\": \"\",
  \"session_id\": \"${SESSION_PREFIX}-bad\",
  \"user_id\": \"${USER_ID}\",
  \"max_tokens\": 512
}")"
assert_status "$bad_recall_status" "422" "POST /recall empty query"
pass "POST /recall rejects empty query with 422"

bad_search_status="$(request_status POST /search "{
  \"query\": \"dog\",
  \"session_id\": \"${SESSION_PREFIX}-bad\",
  \"user_id\": \"${USER_ID}\",
  \"limit\": 0
}")"
assert_status "$bad_search_status" "422" "POST /search limit=0"
pass "POST /search rejects invalid limit with 422"

session_user="${USER_ID}-session-delete"
request_json POST /turns "{
  \"session_id\": \"${SESSION_PREFIX}-delete-session\",
  \"user_id\": \"${session_user}\",
  \"messages\": [
    {
      \"role\": \"user\",
      \"content\": \"I work at Stripe.\"
    }
  ],
  \"timestamp\": \"2026-05-07T10:30:00Z\",
  \"metadata\": {
    \"source\": \"live-endpoint-test\"
  }
}" >/dev/null
delete_session_status="$(request_status DELETE "/sessions/${SESSION_PREFIX}-delete-session")"
assert_status "$delete_session_status" "204" "DELETE /sessions"
pass "DELETE /sessions/{session_id} returns 204"

memories_after_session_delete="$(request_json GET "/users/${session_user}/memories")"
print_json "GET /users/${session_user}/memories after session delete" "$memories_after_session_delete"
assert_json_contains "$memories_after_session_delete" '"memories": []'
pass "session delete removed turn memories"

echo
echo "Live endpoint tests passed"
