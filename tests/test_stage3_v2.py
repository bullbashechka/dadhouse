import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from geometry_stage3_v2 import connected_paths, segment_clear, make_candidate

class RevisionTwoTests(unittest.TestCase):
    def test_both_entries_must_connect(self):
        r=connected_paths([[2000,0,3000,5300]],{'D06':(1000,2750),'D05':(4000,4800)}, {'terrace':(4550,700)})
        self.assertFalse(r['ok'])
        self.assertFalse(r['access']['D06:terrace'])
        self.assertTrue(r['access']['D05:terrace'])
    def test_corridor_900_boundary(self):
        for width,expected in [(900,True),(899,False)]:
            r=connected_paths([[0,0,2000,5300],[2000+width,0,5000,5300]],{'a':(2450,1000)}, {'b':(2450,4000)})
            self.assertEqual(r['ok'],expected)
    def test_media_zone_not_a_shortcut(self):
        r=connected_paths([],{'a':(1000,1000)},{'b':(4000,1000)},[[2000,0,3000,5300]])
        self.assertFalse(r['ok'])
    def test_sight_ray_three_dimensions(self):
        ray=((0,1000,1650),(5000,1000,1650))
        self.assertTrue(segment_clear(*ray,[[2000,500,0,3000,1500,850]]))
        self.assertFalse(segment_clear(*ray,[[2000,500,0,3000,1500,2700]]))
        self.assertTrue(segment_clear(*ray,[[2000,500,2700,3000,1500,3100]]))
    def test_guest_mode_is_real_six_seats(self):
        c=make_candidate()
        self.assertEqual(len(c['ground']['daily']['chairs']),4)
        self.assertEqual(len(c['ground']['guests']['chairs']),6)
        self.assertNotEqual(c['ground']['daily']['table'],c['ground']['guests']['table'])
        self.assertEqual(c['sleepers'],2)
    def test_side_stair_and_actual_floor(self):
        c=make_candidate()
        self.assertLessEqual(c['stair']['footprint'][2],2100)
        self.assertEqual(c['floor_z'],3100)
        self.assertEqual(c['floor_thickness'],400)
        self.assertTrue(c['holes'])

class DoorApproachRegression(unittest.TestCase):
    def test_open_door_must_not_be_ignored_at_stair_foot(self):
        # Source D06 fully-open swept extrema for the recorded dimension range.
        obstacles=[[-180,3005,657,3245],[40,0,2060,2090]]
        blocked=connected_paths(obstacles,{'entry':(1200,2750)},{'stair':(550,2750)})
        clear=connected_paths(obstacles,{'entry':(1200,2750)},{'stair':(550,2550)})
        self.assertFalse(blocked['ok'])
        self.assertTrue(clear['ok'])

class ApplianceAccessRegression(unittest.TestCase):
    def test_fridge_has_a_separate_access_target_from_both_entries(self):
        from geometry_stage3_v2 import check_candidate
        c=check_candidate(make_candidate())
        for mode in ('daily','guests'):
            for door in ('D06','D05'):
                self.assertTrue(c['ground'][mode]['circulation']['access'].get(door+':fridge',False))
