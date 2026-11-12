"""Grid model: map dimensions, walls and the start/target endpoints.

This module is pure Python and has no dependency on Pygame, so it can be used
by the search algorithms and unit tests without a display.
"""

from collections.abc import Iterator
from typing import NamedTuple


class Cell(NamedTuple):
    """Zero-based grid coordinate."""

    row: int
    col: int


# Four-directional movement in a fixed order: up, down, left, right.
# Search algorithms inherit this order, which makes their results deterministic.
NEIGHBOR_OFFSETS: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))


class Grid:
    """Rectangular map of walkable cells and walls with two distinct endpoints.

    Invariants:
        * ``start`` and ``target`` are inside the grid and never equal.
        * ``start`` and ``target`` are never walls.

    ``revision`` increases on every change, so observers (e.g. a running search)
    can detect that their view of the grid is outdated.
    """

    def __init__(self, rows: int, cols: int, start: Cell, target: Cell) -> None:
        if rows <= 0 or cols <= 0:
            raise ValueError(f"Grid size must be positive, got {rows}x{cols}.")
        self._rows = rows
        self._cols = cols
        for name, cell in (("start", start), ("target", target)):
            if not self.in_bounds(cell):
                raise ValueError(f"{name} {cell} is outside the {rows}x{cols} grid.")
        if start == target:
            raise ValueError("start and target must be different cells.")

        self._initial_start = start
        self._initial_target = target
        self._start = start
        self._target = target
        self._walls: set[Cell] = set()
        self._revision = 0

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def start(self) -> Cell:
        return self._start

    @property
    def target(self) -> Cell:
        return self._target

    @property
    def wall_count(self) -> int:
        return len(self._walls)

    @property
    def walls(self) -> frozenset[Cell]:
        """Read-only copy of the wall cells."""
        return frozenset(self._walls)

    @property
    def revision(self) -> int:
        return self._revision

    def in_bounds(self, cell: Cell) -> bool:
        return 0 <= cell.row < self._rows and 0 <= cell.col < self._cols

    def is_wall(self, cell: Cell) -> bool:
        return cell in self._walls

    def is_walkable(self, cell: Cell) -> bool:
        return self.in_bounds(cell) and cell not in self._walls

    def neighbors(self, cell: Cell) -> Iterator[Cell]:
        """Yield the walkable 4-neighbours of ``cell`` in ``NEIGHBOR_OFFSETS`` order."""
        for row_offset, col_offset in NEIGHBOR_OFFSETS:
            neighbor = Cell(cell.row + row_offset, cell.col + col_offset)
            if self.is_walkable(neighbor):
                yield neighbor

    def add_wall(self, cell: Cell) -> bool:
        """Turn ``cell`` into a wall. Returns True if the grid changed."""
        if not self.in_bounds(cell) or cell in (self._start, self._target):
            return False
        if cell in self._walls:
            return False
        self._walls.add(cell)
        self._revision += 1
        return True

    def remove_wall(self, cell: Cell) -> bool:
        """Make ``cell`` walkable again. Returns True if the grid changed."""
        if cell not in self._walls:
            return False
        self._walls.remove(cell)
        self._revision += 1
        return True

    def move_start(self, cell: Cell) -> bool:
        """Move the start to ``cell`` if it is a free, non-target cell.

        Returns True if the start actually moved.
        """
        if cell == self._start or not self._can_place_endpoint(cell, other=self._target):
            return False
        self._start = cell
        self._revision += 1
        return True

    def move_target(self, cell: Cell) -> bool:
        """Move the target to ``cell`` if it is a free, non-start cell.

        Returns True if the target actually moved.
        """
        if cell == self._target or not self._can_place_endpoint(cell, other=self._start):
            return False
        self._target = cell
        self._revision += 1
        return True

    def clear_walls(self) -> None:
        self._walls.clear()
        self._revision += 1

    def reset(self) -> None:
        """Remove all walls and restore the initial endpoints."""
        self._walls.clear()
        self._start = self._initial_start
        self._target = self._initial_target
        self._revision += 1

    def copy(self) -> "Grid":
        """Return an independent snapshot with the same walls, endpoints and revision."""
        clone = Grid(self._rows, self._cols, self._initial_start, self._initial_target)
        clone._start = self._start
        clone._target = self._target
        clone._walls = set(self._walls)
        clone._revision = self._revision
        return clone

    def _can_place_endpoint(self, cell: Cell, other: Cell) -> bool:
        return self.is_walkable(cell) and cell != other


def line_cells(begin: Cell, end: Cell) -> list[Cell]:
    """Return the cells on the straight line from ``begin`` to ``end`` (inclusive).

    Uses Bresenham's line algorithm. Fast mouse movement can skip cells between
    two motion events; drawing along this line keeps wall strokes continuous.
    """
    cells: list[Cell] = []
    row, col = begin
    delta_row = abs(end.row - row)
    delta_col = abs(end.col - col)
    step_row = 1 if end.row > row else -1
    step_col = 1 if end.col > col else -1
    error = delta_col - delta_row

    while True:
        cells.append(Cell(row, col))
        if row == end.row and col == end.col:
            return cells
        doubled_error = 2 * error
        if doubled_error > -delta_row:
            error -= delta_row
            col += step_col
        if doubled_error < delta_col:
            error += delta_col
            row += step_row
