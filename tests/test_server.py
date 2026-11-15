import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "frontend"))

import server as web
from planner_service import PlannerError


@pytest.fixture
def start():
    started = []

    def _start(planner):
        srv = web.make_server("127.0.0.1", 0, planner=planner)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        started.append(srv)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    yield _start
    for srv in started:
        srv.shutdown()
        srv.server_close()


def post(base, fields, path="/user_submission"):
    data = urllib.parse.urlencode(fields).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, data=data)) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def echo(**kwargs):
    return {"plan": {"courses": [], "assumptions": [], "unresolved_questions": []},
            "validation": {"passed": True, "issues": [], "limitations": []}, "got": kwargs}


def test_serves_the_three_frontend_files(start):
    base = start(echo)
    for path, kind in [("/", "text/html"), ("/style.css", "text/css"), ("/script.js", "javascript")]:
        with urllib.request.urlopen(base + path) as resp:
            assert resp.status == 200 and kind in resp.headers["Content-Type"]
            assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_other_files_are_not_served(start):
    base = start(echo)
    for path in ["/server.py", "/../main.py", "/%2e%2e/main.py", "/data/sac_state_students.csv"]:
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(base + path)
        assert err.value.code == 404


def test_valid_submission_passes_clean_values_to_planner(start):
    base = start(echo)
    status, body = post(base, {"sid": " SYNTHETIC_001 ", "school": "csus", "major": "CS",
                               "min_unit_load": "12", "max_unit_load": "15"})
    assert status == 200
    assert body["got"] == {"student_id": "SYNTHETIC_001", "min_units": 12, "max_units": 15}


def test_blank_units_become_none(start):
    base = start(echo)
    status, body = post(base, {"sid": "S1", "min_unit_load": "", "max_unit_load": ""})
    assert status == 200 and body["got"]["min_units"] is None and body["got"]["max_units"] is None


@pytest.mark.parametrize("fields,fragment", [
    ({"sid": "   "}, "student ID"),
    ({"sid": "x" * 65}, "too long"),
    ({"sid": "S1", "school": "csuc"}, "Sacramento"),
    ({"sid": "S1", "min_unit_load": "abc"}, "Minimum units"),
    ({"sid": "S1", "max_unit_load": "31"}, "Maximum units"),
    ({"sid": "S1", "min_unit_load": "-1"}, "Minimum units"),
    ({"sid": "S1", "min_unit_load": "١٢"}, "Minimum units"),
    ({"sid": "S1", "min_unit_load": "16", "max_unit_load": "12"}, "cannot be greater"),
])
def test_bad_input_is_400_and_planner_never_runs(start, fields, fragment):
    called = []
    base = start(lambda **kw: called.append(kw))
    status, body = post(base, fields)
    assert status == 400 and fragment in body["error"] and called == []


def test_planner_error_status_and_message_reach_the_page(start):
    def boom(**kw):
        raise PlannerError(404, "Student ID 'X' not found.")
    status, body = post(start(boom), {"sid": "X"})
    assert (status, body) == (404, {"error": "Student ID 'X' not found."})


def test_unexpected_error_does_not_leak_details(start):
    def boom(**kw):
        raise RuntimeError("secret path /home/me/key")
    status, body = post(start(boom), {"sid": "S1"})
    assert status == 500 and "secret" not in body["error"]


def test_second_request_while_busy_gets_429(start):
    started, release = threading.Event(), threading.Event()

    def slow(**kw):
        started.set()
        release.wait(5)
        return echo(**kw)

    base = start(slow)
    first = {}
    t = threading.Thread(target=lambda: first.update(zip(("s", "b"), post(base, {"sid": "S1"}))))
    t.start()
    assert started.wait(5)
    status, body = post(base, {"sid": "S2"})
    release.set()
    t.join(5)
    assert status == 429 and "already being created" in body["error"]
    assert first["s"] == 200


def test_lock_released_after_failure(start):
    def boom(**kw):
        raise PlannerError(502, "down")
    base = start(boom)
    assert post(base, {"sid": "S1"})[0] == 502
    assert post(base, {"sid": "S1"})[0] == 502  # not 429


def test_oversized_and_empty_bodies(start):
    base = start(echo)
    assert post(base, {"sid": "S1", "major": "x" * 20000})[0] == 413
    req = urllib.request.Request(base + "/user_submission", data=b"", method="POST")
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req)
    assert err.value.code == 400


def test_wrong_post_path_is_404(start):
    assert post(start(echo), {"sid": "S1"}, path="/other")[0] == 404
