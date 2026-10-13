import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from geometry_stage3 import (roof_inner, rectangle_clearance, passes_height,
                             footprint_overlap, make_layout, fit_profile, supported_route, stair_ground_obstacles)


class Stage3GeometryTests(unittest.TestCase):
    def test_normal_thickness_not_vertical(self):
        self.assertAlmostEqual(roof_inner([(0, 3000), (3000, 6000)], 1000, 450),
                               4000 - 450 * math.sqrt(2))

    def test_height_boundary_is_not_dimension_tolerance(self):
        self.assertTrue(passes_height(2050))
        self.assertFalse(passes_height(2049))
        self.assertFalse(passes_height(float('nan')))

    def test_route_edges_not_just_ridge(self):
        profile = [(0, 4000), (1000, 6500), (2000, 4000)]
        self.assertLess(rectangle_clearance(profile, 0, [500, 0, 1500, 1000], 3100, 450), 2050)
        self.assertGreater(roof_inner(profile, 1000, 450) - 3100, 2050)

    def test_overlap_and_shared_boundary(self):
        self.assertTrue(footprint_overlap([0, 0, 1000, 1000], [999, 0, 2000, 500]))
        self.assertFalse(footprint_overlap([0, 0, 1000, 1000], [1000, 0, 2000, 500]))

    def test_layouts_preserve_kitchen_and_two_sleepers(self):
        for position in ('north', 'west'):
            for stair in ('ordinary', 'compact'):
                for furniture in ('loungers', 'double_bed'):
                    layout = make_layout(position, stair, furniture)
                    self.assertEqual(layout['floor_z'], 3100)
                    self.assertEqual(layout['sleepers'], 2)
                    self.assertEqual(layout['room_mm'], [6600, 400, 11600, 5700])
                    self.assertAlmostEqual(layout['stair']['rise'] * layout['stair']['risers'], 3100)

    def test_fit_covers_entire_required_rectangle(self):
        requirement = {'rect': [2000, 2000, 3000, 3000], 'z': 3100}
        fitted = fit_profile('gable', [0, 0, 5000, 5300], [requirement])
        self.assertGreaterEqual(rectangle_clearance(fitted['profile'], fitted['axis'],
                                                  requirement['rect'], 3100, 450), 2050)

    def test_reject_outside_roof(self):
        self.assertEqual(roof_inner([(0, 3000), (1000, 4000)], -1, 350), -math.inf)

    def test_route_must_have_floor_under_whole_width(self):
        platform=[0,0,4000,3000]
        self.assertTrue(supported_route(platform,[],[[0,0,3000,1000],[2000,0,3000,3000]]))
        self.assertFalse(supported_route(platform,[[2100,500,2900,1500]],[[2000,0,3000,3000]]))
        self.assertFalse(supported_route(platform,[],[[3500,0,4500,1000]]))

    def test_narrow_turn_is_not_a_metre_wide_route(self):
        self.assertFalse(supported_route([0,0,4000,3000],[],[[0,0,2000,1000],[1500,500,2500,2500]]))

    def test_outboard_stringer_blocks_a_tread_only_clearance(self):
        layout=make_layout('north','compact','loungers')
        obstacles=stair_ground_obstacles(layout)
        self.assertTrue(any(r[0]<=8645<=r[2] and r[1]<=2670<=r[3] for r in obstacles))


if __name__ == '__main__':
    unittest.main()
