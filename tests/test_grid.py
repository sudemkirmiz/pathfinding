import unittest

from core.grid import Cell, Grid, line_cells

ROWS, COLS = 20, 50
START, TARGET = Cell(10, 10), Cell(10, 39)


class GridTests(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = Grid(ROWS, COLS, START, TARGET)

    def test_rejects_invalid_construction(self) -> None:
        with self.assertRaises(ValueError):
            Grid(0, COLS, START, TARGET)
        with self.assertRaises(ValueError):
            Grid(ROWS, COLS, START, START)
        with self.assertRaises(ValueError):
            Grid(ROWS, COLS, Cell(-1, 0), TARGET)
        with self.assertRaises(ValueError):
            Grid(ROWS, COLS, START, Cell(ROWS, 0))

    def test_in_bounds(self) -> None:
        self.assertTrue(self.grid.in_bounds(Cell(0, 0)))
        self.assertTrue(self.grid.in_bounds(Cell(ROWS - 1, COLS - 1)))
        for cell in (Cell(-1, 0), Cell(0, -1), Cell(ROWS, 0), Cell(0, COLS)):
            self.assertFalse(self.grid.in_bounds(cell))

    def test_add_and_remove_wall(self) -> None:
        cell = Cell(3, 4)
        self.assertTrue(self.grid.add_wall(cell))
        self.assertFalse(self.grid.add_wall(cell), "adding twice is not a change")
        self.assertTrue(self.grid.is_wall(cell))
        self.assertFalse(self.grid.is_walkable(cell))
        self.assertEqual(self.grid.wall_count, 1)

        self.assertTrue(self.grid.remove_wall(cell))
        self.assertFalse(self.grid.remove_wall(cell))
        self.assertTrue(self.grid.is_walkable(cell))
        self.assertEqual(self.grid.wall_count, 0)

    def test_cannot_wall_endpoints_or_outside(self) -> None:
        self.assertFalse(self.grid.add_wall(START))
        self.assertFalse(self.grid.add_wall(TARGET))
        self.assertFalse(self.grid.add_wall(Cell(-1, 5)))
        self.assertFalse(self.grid.add_wall(Cell(5, COLS)))
        self.assertEqual(self.grid.wall_count, 0)

    def test_move_endpoints(self) -> None:
        self.assertTrue(self.grid.move_start(Cell(0, 0)))
        self.assertEqual(self.grid.start, Cell(0, 0))
        self.assertTrue(self.grid.move_target(Cell(ROWS - 1, COLS - 1)))
        self.assertEqual(self.grid.target, Cell(ROWS - 1, COLS - 1))

    def test_endpoints_cannot_overlap_walls_or_each_other(self) -> None:
        wall = Cell(2, 2)
        self.grid.add_wall(wall)
        self.assertFalse(self.grid.move_start(wall))
        self.assertFalse(self.grid.move_start(TARGET))
        self.assertFalse(self.grid.move_target(START))
        self.assertFalse(self.grid.move_target(Cell(ROWS, COLS)))
        self.assertEqual((self.grid.start, self.grid.target), (START, TARGET))

    def test_clear_and_reset(self) -> None:
        self.grid.add_wall(Cell(1, 1))
        self.grid.move_start(Cell(0, 0))
        self.grid.clear_walls()
        self.assertEqual(self.grid.wall_count, 0)
        self.assertEqual(self.grid.start, Cell(0, 0))

        self.grid.add_wall(Cell(1, 1))
        self.grid.reset()
        self.assertEqual(self.grid.wall_count, 0)
        self.assertEqual((self.grid.start, self.grid.target), (START, TARGET))

    def test_neighbors_order_and_filtering(self) -> None:
        self.assertEqual(
            list(self.grid.neighbors(Cell(5, 5))),
            [Cell(4, 5), Cell(6, 5), Cell(5, 4), Cell(5, 6)],  # up, down, left, right
        )
        self.assertEqual(list(self.grid.neighbors(Cell(0, 0))), [Cell(1, 0), Cell(0, 1)])
        self.grid.add_wall(Cell(6, 5))
        self.assertNotIn(Cell(6, 5), list(self.grid.neighbors(Cell(5, 5))))

    def test_revision_changes_only_on_real_changes(self) -> None:
        revision = self.grid.revision
        self.grid.add_wall(START)
        self.grid.remove_wall(Cell(1, 1))
        self.grid.move_start(START)
        self.grid.move_target(START)
        self.assertEqual(self.grid.revision, revision, "rejected or no-op edits keep the revision")

        for edit in (
            lambda: self.grid.add_wall(Cell(1, 1)),
            lambda: self.grid.remove_wall(Cell(1, 1)),
            lambda: self.grid.move_start(Cell(0, 0)),
            lambda: self.grid.move_target(Cell(0, 1)),
            self.grid.clear_walls,
            self.grid.reset,
        ):
            edit()
            self.assertGreater(self.grid.revision, revision)
            revision = self.grid.revision

    def test_copy_is_independent_snapshot(self) -> None:
        self.grid.add_wall(Cell(1, 1))
        self.grid.move_start(Cell(0, 0))
        snapshot = self.grid.copy()
        self.assertEqual(
            (snapshot.start, snapshot.target, snapshot.wall_count, snapshot.revision),
            (self.grid.start, self.grid.target, 1, self.grid.revision),
        )
        self.grid.add_wall(Cell(2, 2))
        self.grid.move_target(Cell(3, 3))
        self.assertFalse(snapshot.is_wall(Cell(2, 2)))
        self.assertEqual(snapshot.target, TARGET)
        snapshot.reset()
        self.assertEqual(snapshot.start, START, "copy keeps the original reset endpoints")
        self.assertTrue(self.grid.is_wall(Cell(1, 1)))


class LineCellsTests(unittest.TestCase):
    def test_single_cell(self) -> None:
        self.assertEqual(line_cells(Cell(2, 3), Cell(2, 3)), [Cell(2, 3)])

    def test_horizontal_and_reverse(self) -> None:
        self.assertEqual(line_cells(Cell(0, 0), Cell(0, 3)), [Cell(0, c) for c in range(4)])
        self.assertEqual(line_cells(Cell(0, 3), Cell(0, 0)), [Cell(0, c) for c in range(3, -1, -1)])

    def test_line_is_continuous(self) -> None:
        cells = line_cells(Cell(1, 2), Cell(9, 30))
        self.assertEqual((cells[0], cells[-1]), (Cell(1, 2), Cell(9, 30)))
        for previous, current in zip(cells, cells[1:]):
            self.assertLessEqual(abs(current.row - previous.row), 1)
            self.assertLessEqual(abs(current.col - previous.col), 1)


if __name__ == "__main__":
    unittest.main()
