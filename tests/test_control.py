import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'maze_control'))
from maze_control.control import BasicWallFollower, Pose, Scan, WallFollower, course_regions, point_control, pose_goal_control, sector_distance, wrap


class ControlTests(unittest.TestCase):
    def test_angles_wrap_at_pi(self):
        self.assertAlmostEqual(wrap(3 * math.pi), -math.pi)

    def test_scan_filters_invalid_and_handles_wrap(self):
        scan = Scan([float('nan'), -1, 0.01, float('inf'), 0.4], -math.pi, math.pi / 2, 0.12, 3.5)
        self.assertAlmostEqual(sector_distance(scan, math.pi / 2, 0.1), 3.5)
        self.assertIsNone(sector_distance(scan, 0, 0.1))
        self.assertAlmostEqual(sector_distance(scan, -math.pi, 0.1), 0.4)

    def test_point_stops_at_goal(self):
        self.assertEqual(point_control(Pose(1, 2, 0), (1, 2)), (0.0, 0.0, True))

    def test_course_point_gains_and_five_centimeter_tolerance(self):
        v, w, done = point_control(Pose(0, 0, 0), (0.5, 0))
        self.assertAlmostEqual(v, 0.15)
        self.assertFalse(done)
        self.assertFalse(point_control(Pose(0, 0, 0), (0.06, 0))[2])
        self.assertTrue(point_control(Pose(0, 0, 0), (0.04, 0))[2])

    def test_course_regions_use_forward_minimum_and_side_medians(self):
        ranges = [3.5] * 360
        for degree in range(60, 91):
            ranges[degree] = 0.6
        ranges[75] = 0.15
        for degree in range(270, 301):
            ranges[degree] = 0.9
        ranges[359] = 0.25
        front, left, right = course_regions(Scan(ranges, 0, math.pi / 180, 0.12, 3.5))
        self.assertAlmostEqual(front, 0.25)
        self.assertAlmostEqual(left, 0.6)
        self.assertAlmostEqual(right, 0.9)

    def test_course_regions_support_negative_angle_start(self):
        ranges = [3.5] * 360
        ranges[180] = 0.4
        scan = Scan(ranges, -math.pi, math.pi / 180, 0.12, 3.5)
        self.assertAlmostEqual(course_regions(scan)[0], 0.4)

    def test_basic_wall_rule_prioritizes_front_and_uses_turn_signs(self):
        controller = BasicWallFollower()
        self.assertEqual(controller.step((0.25, 1.2, 1.0)), (0.0, -0.6))
        self.assertGreater(controller.step((1.0, 0.7, 1.0))[1], 0)
        self.assertLess(controller.step((1.0, 0.2, 1.0))[1], 0)
        self.assertEqual(controller.step((1.0, 0.4, 1.0)), (0.15, 0.0))

    def test_point_turns_before_driving(self):
        v, w, done = point_control(Pose(0, 0, math.pi), (1, 0))
        self.assertEqual(v, 0)
        self.assertGreater(abs(w), 0)
        self.assertFalse(done)

    def test_pose_goal_drives_to_position_before_final_heading(self):
        v, w, done, state = pose_goal_control(Pose(0, 0, 0), Pose(1, 0, math.pi / 2))
        self.assertGreater(v, 0)
        self.assertEqual(w, 0)
        self.assertFalse(done)
        self.assertEqual(state, 'RVIZ_GOAL')

    def test_pose_goal_aligns_heading_after_reaching_position(self):
        v, w, done, state = pose_goal_control(Pose(1, 1, 0), Pose(1.01, 1, math.pi / 2))
        self.assertEqual(v, 0)
        self.assertGreater(w, 0)
        self.assertFalse(done)
        self.assertEqual(state, 'RVIZ_ALIGN')

    def test_pose_goal_finishes_with_wrapped_heading_error(self):
        v, w, done, state = pose_goal_control(Pose(1, 1, math.pi - 0.01), Pose(1, 1, -math.pi + 0.01))
        self.assertEqual((v, w), (0.0, 0.0))
        self.assertTrue(done)
        self.assertEqual(state, 'RVIZ_REACHED')

    def test_invalid_scan_stops(self):
        self.assertEqual(WallFollower().step(Pose(0, 0, 0), None, 0), (0.0, 0.0))

    def test_front_wall_starts_right_turn(self):
        ranges = [3.5] * 360
        for i in range(360):
            if min(i, 360 - i) <= 20:
                ranges[i] = 0.25
            if abs(i - 90) <= 20:
                ranges[i] = 0.38
        v, w = WallFollower().step(Pose(0, 0, 0), Scan(ranges, 0, math.pi / 180, 0.12, 3.5), 0)
        self.assertEqual(v, 0)
        self.assertLess(w, 0)

    def test_corridor_heading_rejects_corner_oversteer(self):
        follower = WallFollower()
        scan = Scan([0.38] * 360, 0, math.pi / 180, 0.12, 3.5)
        follower.step(Pose(0, 0, 0), scan, 0)
        v, w = follower.step(Pose(0, 0, 0.8), scan, 0.1)
        self.assertLess(w, 0)

    def test_turn_preserves_corridor_axis(self):
        follower = WallFollower()
        scan = Scan([0.38] * 360, 0, math.pi / 180, 0.12, 3.5)
        follower.step(Pose(0, 0, 0), scan, 0)
        follower.turn(math.pi / 2, Pose(0, 0, 0.2), 1)
        self.assertAlmostEqual(follower.turn_goal, math.pi / 2)


if __name__ == '__main__':
    unittest.main()
