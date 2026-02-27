"""
加载 specs/bench/scenarios/*.yaml 场景文件
"""
from __future__ import annotations
import os
import yaml

def _scenarios_dir() -> str:
    explicit = os.environ.get("SCENARIOS_DIR", "")
    if explicit:
        return explicit
    default = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "..", "specs", "bench", "scenarios",
    )
    return os.path.realpath(default)


def load_scenario(scenario_id: str) -> dict:
    SCENARIOS_DIR = _scenarios_dir()
    path = os.path.join(SCENARIOS_DIR, f"{scenario_id.replace('-', '_')}.yaml")
    if not os.path.exists(path):
        # fallback: try kebab-case filename directly
        path2 = os.path.join(SCENARIOS_DIR, f"{scenario_id}.yaml")
        if not os.path.exists(path2):
            raise FileNotFoundError(
                f"场景文件未找到: {scenario_id}（搜索路径: {SCENARIOS_DIR}）"
            )
        path = path2

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_scenario_ids() -> list[str]:
    SCENARIOS_DIR = _scenarios_dir()
    if not os.path.isdir(SCENARIOS_DIR):
        return []
    ids = []
    for fname in os.listdir(SCENARIOS_DIR):
        if fname.endswith(".yaml"):
            ids.append(fname[:-5].replace("_", "-"))
    return ids
