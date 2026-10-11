import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from review_geometry import (door_model, polygon_at, sweep, intersects,
                             first_collision, pair_collision, require_scene,
                             obstacle_from_mesh, hits_obstacle)
from geometry_stage2 import boundary_mesh


def door(length=800, pivot=(0, 0), angle=0, sign=1):
    return dict(pivot=pivot, closed_angle=angle, sign=sign,
                local_polygon=[(0, 0), (length, 0), (length, -40), (0, -40)])


class ReviewGeometryTests(unittest.TestCase):
    def test_motion_collision_between_clear_endpoints(self):
        leaf = door()
        obstacle = [(440, 440), (460, 440), (460, 460), (440, 460)]
        self.assertFalse(intersects(polygon_at(leaf, 0), obstacle))
        self.assertFalse(intersects(polygon_at(leaf, 90), obstacle))
        result = first_collision(leaf, obstacle)
        self.assertEqual(result['status'], 'collision')
        self.assertGreater(result['angle_deg'], 20)
        self.assertLess(result['angle_deg'], 60)

    def test_free_sweep(self):
        obstacle = [(1000, 1000), (1100, 1000), (1100, 1100), (1000, 1100)]
        self.assertEqual(first_collision(door(), obstacle)['status'], 'clear')

    def test_containment_is_collision(self):
        self.assertTrue(intersects([(0, 0), (20, 0), (20, 20), (0, 20)],
                                   [(-10, -10), (30, -10), (30, 30), (-10, 30)]))

    def test_contact_is_not_penetration(self):
        self.assertFalse(intersects([(0, 0), (20, 0), (20, 20), (0, 20)],
                                    [(20, 0), (40, 0), (40, 20), (20, 20)]))

    def test_frame_and_leaf_reduce_clear_width(self):
        opening = dict(axis='x', interval_mm=[0, 900], hinge='low', swing_sign=1)
        model = door_model(opening, dict(rect_mm=[-400, -200, 2000, 200]))
        self.assertEqual(model['frame_clear_mm'], 790)
        p = polygon_at(model, 90)
        self.assertAlmostEqual(max(x for x, y in p) - min(x for x, y in p), 40)
        self.assertAlmostEqual(model['frame_clear_mm'] - 40, 750)

    def test_width_range_changes_result(self):
        obstacle = [(780, 100), (800, 100), (800, 120), (780, 120)]
        self.assertEqual(first_collision(door(740), obstacle)['status'], 'clear')
        self.assertEqual(first_collision(door(840), obstacle)['status'], 'collision')

    def test_independent_door_angles(self):
        a, b = door(800), door(800, (600, 600), sign=-1)
        self.assertTrue(all(not intersects(polygon_at(a, t/10), polygon_at(b, t/10)) for t in range(901)))
        result = pair_collision(a, b)
        self.assertEqual(result['status'], 'collision')
        self.assertNotEqual(*result['angles_deg'])
        self.assertTrue(intersects(polygon_at(a, result['angles_deg'][0]),
                                   polygon_at(b, result['angles_deg'][1])))

    def test_sweep_encloses_rotation_with_sub_mm_error(self):
        pieces = sweep(door(900), error=.25)
        self.assertGreater(len(pieces), 10)
        self.assertTrue(all(p['error_mm'] <= .25 + 1e-8 for p in pieces))
        # Independent points on the physical circular path, between arbitrary samples.
        for angle in (1.117, 13.271, 44.913, 88.143):
            x=899.999*math.cos(math.radians(angle))
            y=899.999*math.sin(math.radians(angle))
            self.assertTrue(any(intersects(p['polygon'], [(x,y)]) for p in pieces))
        radius=math.hypot(900,40)
        self.assertTrue(all(math.hypot(*v)<=radius+.25+1e-8 for p in pieces for v in p['polygon']))

    def test_real_mesh_containment_and_door_hole(self):
        v,f=boundary_mesh([[-100,-100,-20,100,100,2100]])
        obstacle=obstacle_from_mesh('enclosing solid',v,f)
        self.assertTrue(hits_obstacle([(-20,-20),(20,-20),(20,20),(-20,20)],obstacle))
        v,f=boundary_mesh([[0,0,0,2000,400,2900]],[[500,-1,0,1400,401,2100]])
        wall=obstacle_from_mesh('wall with doorway',v,f)
        self.assertFalse(hits_obstacle([(600,50),(1300,50),(1300,350),(600,350)],wall))
        self.assertTrue(hits_obstacle([(1350,50),(1500,50),(1500,350),(1350,350)],wall))

    def test_above_door_lintel_is_excluded_from_collision(self):
        v,f=boundary_mesh([[0,0,2200,2000,400,2900]])
        self.assertIsNone(obstacle_from_mesh('high beam',v,f))

    def test_wrong_scene_rejected(self):
        with self.assertRaises(ValueError):
            require_scene('/tmp/original.blend', '/tmp/review.blend')
        require_scene('/tmp/review.blend', '/tmp/review.blend')


if __name__ == '__main__':
    unittest.main()
