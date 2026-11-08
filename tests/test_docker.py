import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DockerTests(unittest.TestCase):
    def test_compose_parses_and_has_readonly_source(self):
        import yaml
        service = yaml.safe_load((ROOT / 'compose.yaml').read_text())['services']['micromouse']
        self.assertEqual(service['image'], 'micromouse:humble')
        self.assertIn('.:/workspace:ro', service['volumes'])
        self.assertIn('./results:/results:rw', service['volumes'])
        self.assertNotIn('privileged', service)

    def test_shell_scripts_parse(self):
        scripts = list((ROOT / 'tools').glob('*.sh')) + list((ROOT / 'docker').glob('*.sh'))
        self.assertGreaterEqual(len(scripts), 4)
        for script in scripts:
            with self.subTest(script=script):
                result = subprocess.run(['bash', '-n', str(script)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
