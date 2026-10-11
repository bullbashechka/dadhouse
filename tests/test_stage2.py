import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from geometry_stage2 import boundary_mesh, solid_cells, within_tolerance, door_pose


class SolidGeometryTests(unittest.TestCase):
    def test_door_hinge_and_direction_from_plan(self):
        # North entrance hinges on its east jamb and opens north-west.
        self.assertEqual(door_pose('x',6955,7745,9800,'high',-1,30),((7745,9800),150))
        # Terrace entrance hinges on the south jamb and opens north-east.
        self.assertEqual(door_pose('y',680,1470,11800,'low',-1,30),((11800,680),60))

    def test_door_void_and_lintel(self):
        # 400-mm wall, 900 x 2100-mm doorway, 2900-mm total height.
        axes, cells = solid_cells([[0, 0, 0, 5000, 400, 2900]],
                                 [[1500, -10, -10, 2400, 410, 2100]])
        volume = sum((axes[0][i + 1] - axes[0][i]) *
                     (axes[1][j + 1] - axes[1][j]) *
                     (axes[2][k + 1] - axes[2][k]) for i, j, k in cells)
        self.assertEqual(volume, 5044000000)
        def contains(x, y, z):
            return any(axes[0][i] < x < axes[0][i + 1] and
                       axes[1][j] < y < axes[1][j + 1] and
                       axes[2][k] < z < axes[2][k + 1] for i, j, k in cells)
        self.assertFalse(contains(1900, 200, 1000))
        self.assertTrue(contains(1900, 200, 2500))

    def test_union_does_not_double_count_corner(self):
        axes, cells = solid_cells([[0, 0, 0, 2000, 400, 1000],
                                  [0, 0, 0, 400, 2000, 1000]])
        volume = sum((axes[0][i + 1] - axes[0][i]) *
                     (axes[1][j + 1] - axes[1][j]) *
                     (axes[2][k + 1] - axes[2][k]) for i, j, k in cells)
        self.assertEqual(volume, 1440000000)

    def test_door_mesh_is_closed_without_duplicate_faces(self):
        vertices, faces = boundary_mesh([[0, 0, 0, 5000, 400, 2900]],
                                       [[1500, -10, -10, 2400, 410, 2100]])
        edges = Counter(tuple(sorted((f[i], f[(i + 1) % len(f)])))
                        for f in faces for i in range(len(f)))
        self.assertTrue(vertices and faces)
        self.assertTrue(all(n == 2 for n in edges.values()))
        self.assertEqual(len(faces), len({tuple(sorted(f)) for f in faces}))

    def test_tolerance_boundary_and_invalid_numbers(self):
        self.assertTrue(within_tolerance(5001, 5000))
        self.assertTrue(within_tolerance(4999, 5000))
        self.assertFalse(within_tolerance(5001.01, 5000))
        self.assertFalse(within_tolerance(float('nan'), 5000))
        self.assertFalse(within_tolerance(float('inf'), 5000))


if __name__ == '__main__':
    unittest.main()
