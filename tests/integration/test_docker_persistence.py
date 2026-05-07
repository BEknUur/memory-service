#python imports
import json
import os
import subprocess
import time
import urllib.request

#third-party imports
import pytest

#project imports

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1",
    reason="Docker persistence test is opt-in; set RUN_DOCKER_TESTS=1",
)


def _local_env_has_openai_key() -> bool:
    env_path = ".env"
    if not os.path.exists(env_path):
        return False
    with open(env_path) as env_file:
        for line in env_file:
            if line.startswith("OPENAI_API_KEY=") and line.strip() != "OPENAI_API_KEY=":
                return True
    return False


def _request_json(path: str, payload: dict | None = None) -> dict:
    url = f"http://localhost:8080{path}"
    if payload is None:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())

    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def test_docker_restart_persists_recall_data():
    if _local_env_has_openai_key():
        pytest.skip("Docker persistence smoke skips local .env files with OPENAI_API_KEY set")

    subprocess.run(["docker", "compose", "up", "-d", "--build"], check=True)
    for _ in range(30):
        try:
            if _request_json("/health") == {"status": "ok", "database": "ok"}:
                break
        except Exception:
            time.sleep(1)
    else:
        raise AssertionError("service did not become healthy")

    _request_json(
        "/turns",
        {
            "session_id": "docker-persist-1",
            "user_id": "docker-user",
            "messages": [{"role": "user", "content": "I just moved to Berlin from NYC."}],
            "timestamp": "2025-03-15T10:30:00Z",
            "metadata": {},
        },
    )

    subprocess.run(["docker", "compose", "restart", "api"], check=True)
    time.sleep(3)

    response = _request_json(
        "/recall",
        {
            "query": "Where does the user live?",
            "session_id": "docker-persist-2",
            "user_id": "docker-user",
            "max_tokens": 512,
        },
    )

    assert "Berlin" in response["context"]
