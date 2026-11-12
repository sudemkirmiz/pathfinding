"""Side-by-side BFS / A* comparison on one grid snapshot, without animation.

Pygame-independent. Counts and path lengths are exact and deterministic;
timings are wall-clock medians and should be read as approximate.
"""

from dataclasses import dataclass
from statistics import median
from time import perf_counter

from algorithms.common import SearchResult, run_to_completion
from algorithms.registry import STEP_FUNCTIONS, Algorithm
from core.grid import Grid


@dataclass(frozen=True, slots=True)
class AlgorithmBenchmark:
    algorithm: Algorithm
    result: SearchResult
    median_seconds: float


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    """BFS and A* results on the same grid snapshot, in ``STEP_FUNCTIONS`` order."""

    entries: tuple[AlgorithmBenchmark, ...]
    revision: int        # Grid revision the snapshot was taken from.
    repetitions: int
    warmup_runs: int


def compare_algorithms(grid: Grid, repetitions: int, warmup_runs: int) -> ComparisonReport:
    """Run BFS and A* on one snapshot of ``grid`` and time them.

    Fairness measures:
        * All runs use the same frozen copy of the grid (same start, target,
          walls and neighbour rules); later edits to ``grid`` cannot leak in.
        * Each algorithm runs ``warmup_runs`` untimed times first.
        * Timed runs alternate between algorithms, so slow drifts in CPU speed
          affect all of them alike; the median of ``repetitions`` runs is kept.
        * Only the search itself is timed — no drawing or animation.
    """
    if repetitions < 1 or warmup_runs < 0:
        raise ValueError("repetitions must be >= 1 and warmup_runs >= 0.")
    snapshot = grid.copy()
    algorithms = tuple(STEP_FUNCTIONS)  # BFS and A*; the hybrid is not benchmarked here.

    for algorithm in algorithms:
        for _ in range(warmup_runs):
            run_to_completion(STEP_FUNCTIONS[algorithm](snapshot))

    timings: dict[Algorithm, list[float]] = {algorithm: [] for algorithm in algorithms}
    results: dict[Algorithm, SearchResult] = {}
    for _ in range(repetitions):
        for algorithm in algorithms:
            started = perf_counter()
            results[algorithm] = run_to_completion(STEP_FUNCTIONS[algorithm](snapshot))
            timings[algorithm].append(perf_counter() - started)

    entries = tuple(
        AlgorithmBenchmark(algorithm, results[algorithm], median(timings[algorithm]))
        for algorithm in algorithms
    )
    return ComparisonReport(entries, snapshot.revision, repetitions, warmup_runs)
