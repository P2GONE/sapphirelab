"""Parallel test-case executor and shared TestCase / RunResult dataclasses."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional


@dataclass
class TestCase:
    id: str
    modality: str
    seed_id: str
    user_message: str
    seed_instruction: str
    mutation_chain: List[str] = field(default_factory=list)
    payload_path: Optional[str] = None
    text_payload: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class RunResult:
    case: TestCase
    response: str
    status: int
    score: int
    score_label: str
    violations: List[str]
    error: Optional[str] = None

    def to_dict(self):
        return {
            "case": self.case.to_dict(),
            "response": self.response,
            "status": self.status,
            "score": self.score,
            "score_label": self.score_label,
            "violations": self.violations,
            "error": self.error,
        }


def run_parallel(cases: List[TestCase], execute_one: Callable, workers: int = 4):
    if workers <= 1:
        return [execute_one(c) for c in cases]
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(execute_one, c): c for c in cases}
        for fut in as_completed(futures):
            results.append(fut.result())
    return results
