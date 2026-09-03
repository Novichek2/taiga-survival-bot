import json
import random
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"


def load_questions(module: str) -> list[dict]:
    path = DATA / "modules" / f"{module}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def get_question(module: str, difficulty: int = 1) -> dict | None:
    questions = [q for q in load_questions(module) if q.get("difficulty", 1) <= difficulty]
    return random.choice(questions) if questions else None


def calculate_score(old: float, correct: bool) -> float:
    delta = 8 if correct else -5
    return max(0, min(100, round(old + delta, 1)))


def level_for_score(score: float) -> str:
    levels = [(10, "Городской"), (20, "Турист"), (35, "Лагерь"), (50, "Таёжник"),
              (65, "Автономник"), (75, "Зимовщик"), (85, "Следопыт"), (92, "Экспедиционник"),
              (97, "Инструктор"), (101, "Руководитель")]
    return next(name for threshold, name in levels if score < threshold)


def random_scenario() -> dict:
    scenarios = json.loads((DATA / "scenarios.json").read_text(encoding="utf-8"))
    return random.choice(scenarios)
