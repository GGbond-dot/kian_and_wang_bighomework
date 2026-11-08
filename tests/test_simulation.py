import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from offline_sim import laser, point_experiment, read_walls, simulate
from maze_control.control import Pose, WallFollower


class SimulationTests(unittest.TestCase):
    def test_waypoint_sequence_converges(self):
        self.assertLess(point_experiment(), 0.05)

    def test_wall_following_exits_without_collision(self):
        for adaptive in (False, True):
            with self.subTest(adaptive=adaptive):
                with tempfile.TemporaryDirectory() as directory:
                    result = simulate(adaptive, directory)
                self.assertTrue(result['reached_exit'], result)
                self.assertGreater(result['minimum_body_clearance_m'], 0.02, result)

    def test_turn_stops_with_odometry_across_wrap(self):
        follower = WallFollower()
        pose = Pose(0.5, 0.5, 3.1)
        follower.turn(math.pi / 2, pose, 0)
        pose.yaw = follower.turn_goal
        v, w = follower.step(pose, laser(pose, read_walls()), 2)
        self.assertEqual((v, w), (0, 0))
        self.assertEqual(follower.state, 'CLEAR')

    def test_stuck_turn_latches_fault(self):
        pose = Pose(0.5, 0.5, math.pi / 2)
        follower = WallFollower()
        follower.turn(math.pi / 2, pose, 0)
        self.assertEqual(follower.step(pose, laser(pose, read_walls()), 16), (0, 0))
        self.assertEqual(follower.state, 'FAULT')
