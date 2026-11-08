import ast
import io
import tokenize
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class AssetTests(unittest.TestCase):
    def test_all_python_parses_without_comments(self):
        for folder in ('src', 'tools', 'tests'):
            for path in (ROOT / folder).rglob('*.py'):
                with self.subTest(path=path):
                    text = path.read_text()
                    ast.parse(text)
                    self.assertFalse([t for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type == tokenize.COMMENT])

    def test_robot_joint_tree_and_plugins(self):
        robot = ET.parse(ROOT / 'src/maze_control/urdf/burger.urdf').getroot()
        links = {link.attrib['name'] for link in robot.findall('link')}
        joints = {joint.attrib['name'] for joint in robot.findall('joint')}
        for joint in robot.findall('joint'):
            self.assertIn(joint.find('parent').attrib['link'], links)
            self.assertIn(joint.find('child').attrib['link'], links)
        drive = robot.find('./gazebo/plugin[@name="differential_drive"]')
        self.assertIn(drive.findtext('left_joint'), joints)
        self.assertIn(drive.findtext('right_joint'), joints)
        self.assertEqual(drive.findtext('robot_base_frame'), 'base_footprint')

    def test_all_maze_walls_have_matching_collisions(self):
        world = ET.parse(ROOT / 'src/maze_control/worlds/maze.world').getroot()
        count = 0
        for model in world.findall('world/model'):
            box = model.find('link/visual/geometry/box/size')
            if box is not None:
                self.assertEqual(box.text, model.findtext('link/collision/geometry/box/size'))
                self.assertEqual(model.findtext('static'), 'true')
                count += 1
        self.assertEqual(count, 7)

    def test_maze_rviz_exposes_goal_and_reset_controls(self):
        config = yaml.safe_load((ROOT / 'src/maze_control/config/maze.rviz').read_text())
        tools = config['Visualization Manager']['Tools']
        displays = config['Visualization Manager']['Displays']
        self.assertTrue(any(tool.get('Class') == 'rviz_default_plugins/SetGoal' and tool.get('Topic') == '/goal_pose' for tool in tools))
        self.assertTrue(any(display.get('Class') == 'rviz_default_plugins/InteractiveMarkers' and display.get('Interactive Markers Namespace') == '/maze_reset' for display in displays))
