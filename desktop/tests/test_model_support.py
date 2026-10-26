import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_support import validate_model


class ModelValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.file = self.root / 'pet.model3.json'
        (self.root / 'pet.moc3').write_bytes(b'MOC3test-only')
        (self.root / 'texture.png').write_bytes(b'test-only')
        self.data = {'Version': 3, 'FileReferences': {'Moc': 'pet.moc3', 'Textures': ['texture.png']}}

    def tearDown(self):
        self.temp.cleanup()

    def check(self):
        self.file.write_text(json.dumps(self.data), encoding='utf-8-sig')
        return validate_model(self.file)

    def test_complete_dependency_set(self):
        self.assertEqual(self.check()[0], self.file)

    def test_missing_texture(self):
        (self.root / 'texture.png').unlink()
        with self.assertRaisesRegex(ValueError, '缺失'):
            self.check()

    def test_missing_motion_sound(self):
        (self.root / 'idle.motion3.json').write_text('{}')
        self.data['FileReferences']['Motions'] = {'Idle': [{'File': 'idle.motion3.json', 'Sound': 'absent.wav'}]}
        with self.assertRaisesRegex(ValueError, 'absent.wav'):
            self.check()

    def test_malformed_json_shapes(self):
        for refs in (None, [], {'Moc': 'pet.moc3', 'Textures': 'texture.png'}):
            with self.subTest(refs=refs):
                self.data['FileReferences'] = refs
                with self.assertRaises(ValueError):
                    self.check()

    def test_parent_absolute_windows_and_symlink_escape(self):
        (self.root / 'outside.png').symlink_to(Path(__file__).resolve())
        for name in ('../outside.png', str(Path(__file__).resolve()), 'C:/secret.png', 'C:\\secret.png', 'outside.png'):
            with self.subTest(name=name):
                self.data['FileReferences']['Textures'] = [name]
                with self.assertRaises(ValueError):
                    self.check()

    def test_renamed_psd_rejected(self):
        (self.root / 'pet.moc3').write_bytes(b'8BPSfake')
        with self.assertRaisesRegex(ValueError, 'MOC3'):
            self.check()


if __name__ == '__main__':
    unittest.main()
