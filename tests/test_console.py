from fastapi.testclient import TestClient

from workflow_hub.api import create_app

LINEAR = """
name: linear
version: 1
nodes:
  - id: start
    type: start
  - id: mark
    type: script
    config: {action: set, key: message, value: hello}
  - id: end
    type: end
edges:
  - {from: start, to: mark}
  - {from: mark, to: end}
"""


def test_console_lists_a_local_run():
    client = TestClient(create_app())
    page = client.get("/")
    assert page.status_code == 200
    assert 'data-shell="studio"' in page.text
    started = client.post("/api/runs", json={"yaml": LINEAR, "inputs": {}})
    assert started.status_code == 200
    listed = client.get("/api/runs")
    assert listed.json()[0]["id"] == started.json()["id"]
    assert listed.json()[0]["shell_executed"] is False
    loaded = client.get("/api/runs/" + started.json()["id"])
    assert loaded.json()["result"]["shell_executed"] is False
