#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
RUN_ID="${RUN_ID:-$(date +%s)}"
USER_ID="${USER_ID:-smoke-user-${RUN_ID}}"
SESSION_PREFIX="${SESSION_PREFIX:-smoke-${RUN_ID}}"

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
    print(json.dumps(payload, indent=2), file=sys.stderr)
    raise SystemExit(1)
PY
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

print_pass() {
  local message="$1"

  echo "PASS: ${message}"
}

wait_for_health() {
  echo "Waiting for ${BASE_URL}/health ..."
  for _ in $(seq 1 60); do
    if response="$(request_json GET /health 2>/dev/null)"; then
      assert_json_contains "$response" '"status": "ok"'
      assert_json_contains "$response" '"database": "ok"'
      print_json "GET /health response" "$response"
      print_pass "health endpoint returned status=ok and database=ok"
      return
    fi
    sleep 1
  done

  echo "Service did not become healthy" >&2
  exit 1
}

require_command curl
require_command python3

echo "Smoke test target: ${BASE_URL}"
echo "Smoke test user: ${USER_ID}"

wait_for_health

echo "Creating first turn: Berlin, NYC, Stripe, Biscuit"
turn_response="$(request_json POST /turns "{
  \"session_id\": \"${SESSION_PREFIX}-berlin-1\",
  \"user_id\": \"${USER_ID}\",
  \"messages\": [
    {
      \"role\": \"user\",
      \"content\": \"I just moved to Berlin from NYC. I work at Stripe. My dog Biscuit is adjusting.\"
    },
    {
      \"role\": \"assistant\",
      \"content\": \"Berlin sounds like a great move.\"
    }
  ],
  \"timestamp\": \"2026-05-07T10:00:00Z\",
  \"metadata\": {
    \"source\": \"smoke-test\"
  }
}")"
print_json "POST /turns first response" "$turn_response"
assert_json_contains "$turn_response" '"id"'
print_pass "first turn was created"

echo "Inspecting user memories"
memories_response="$(request_json GET "/users/${USER_ID}/memories")"
print_json "GET /users/${USER_ID}/memories response" "$memories_response"
assert_json_contains "$memories_response" "location.current_city"
assert_json_contains "$memories_response" "Berlin"
assert_json_contains "$memories_response" "employment.current_company"
assert_json_contains "$memories_response" "Stripe"
assert_json_contains "$memories_response" "pet.dog.name"
assert_json_contains "$memories_response" "Biscuit"
print_pass "memories include Berlin, NYC, Stripe, and Biscuit"

echo "Recalling location and pet"
recall_response="$(request_json POST /recall "{
  \"query\": \"Where does the user live and what is the dog's name?\",
  \"session_id\": \"${SESSION_PREFIX}-berlin-2\",
  \"user_id\": \"${USER_ID}\",
  \"max_tokens\": 512
}")"
print_json "POST /recall location and pet response" "$recall_response"
assert_json_contains "$recall_response" "Berlin"
assert_json_contains "$recall_response" "Biscuit"
print_pass "recall context includes Berlin and Biscuit"

echo "Searching for Biscuit"
search_response="$(request_json POST /search "{
  \"query\": \"dog Biscuit\",
  \"session_id\": \"${SESSION_PREFIX}-berlin-2\",
  \"user_id\": \"${USER_ID}\",
  \"limit\": 10
}")"
print_json "POST /search dog Biscuit response" "$search_response"
assert_json_contains "$search_response" "pet.dog.name"
assert_json_contains "$search_response" "Biscuit"
print_pass "search results include pet.dog.name = Biscuit"

echo "Creating second turn: Stripe -> Notion"
second_turn_response="$(request_json POST /turns "{
  \"session_id\": \"${SESSION_PREFIX}-work-2\",
  \"user_id\": \"${USER_ID}\",
  \"messages\": [
    {
      \"role\": \"user\",
      \"content\": \"I just joined Notion.\"
    }
  ],
  \"timestamp\": \"2026-05-07T11:00:00Z\",
  \"metadata\": {
    \"source\": \"smoke-test\"
  }
}")"
print_json "POST /turns second response" "$second_turn_response"
assert_json_contains "$second_turn_response" '"id"'
print_pass "second turn was created"

echo "Checking supersession in recall"
work_recall_response="$(request_json POST /recall "{
  \"query\": \"Where does the user work?\",
  \"session_id\": \"${SESSION_PREFIX}-work-3\",
  \"user_id\": \"${USER_ID}\",
  \"max_tokens\": 512
}")"
print_json "POST /recall work supersession response" "$work_recall_response"
assert_json_contains "$work_recall_response" "employment.current_company"
assert_json_contains "$work_recall_response" "Notion"
assert_json_contains "$work_recall_response" "previously Stripe"
print_pass "recall shows Notion and previous Stripe history"

echo "Deleting smoke user"
request_json DELETE "/users/${USER_ID}" >/dev/null
print_pass "DELETE /users/${USER_ID} returned success"

echo "Verifying cleanup"
cleanup_response="$(request_json GET "/users/${USER_ID}/memories")"
print_json "GET /users/${USER_ID}/memories cleanup response" "$cleanup_response"
assert_json_contains "$cleanup_response" '"memories": []'
print_pass "cleanup removed smoke user memories"

echo "Smoke test passed"
