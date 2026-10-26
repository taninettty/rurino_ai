from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory import MAX_NOTE, MAX_NOTES, Memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'nested' / 'memory.json'

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_file_loads_empty(self):
        memory = Memory(self.path)
        self.assertEqual((memory.name, memory.notes), ('', []))
        self.assertEqual(memory.prompt_suffix(), '')
        self.assertFalse(memory)

    def test_round_trip(self):
        Memory(self.path).update('小明', ['喜欢猫', '讨厌香菜']).save()
        loaded = Memory(self.path)
        self.assertEqual(loaded.name, '小明')
        self.assertEqual(loaded.notes, ['喜欢猫', '讨厌香菜'])
        self.assertTrue(self.path.is_file())

    def test_saved_file_is_readable_json(self):
        Memory(self.path).update('小明', ['喜欢猫']).save()
        data = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(data, {'name': '小明', 'notes': ['喜欢猫']})

    def test_corrupt_file_falls_back_instead_of_raising(self):
        self.path.parent.mkdir(parents=True)
        for content in ('{not json', '[]', '{"name": 5, "notes": "x"}', '\xff\xfe'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding='utf-8', errors='surrogateescape')
                memory = Memory(self.path)
                self.assertEqual((memory.name, memory.notes), ('', []))

    def test_notes_are_cleaned_bounded_and_deduplicated(self):
        notes = ['  空白\t换行  ', '空白 换行', '', '   ', 'x' * (MAX_NOTE + 50)]
        notes += [f'note-{index}' for index in range(MAX_NOTES * 2)]
        memory = Memory(self.path).update('名字' * 50, notes)
        self.assertEqual(memory.notes[0], '空白 换行')
        self.assertEqual(memory.notes[1], 'x' * MAX_NOTE)
        self.assertEqual(len(memory.notes), MAX_NOTES)
        self.assertEqual(len(set(memory.notes)), MAX_NOTES, '重复备注必须去掉')
        self.assertEqual(len(memory.name), 40)

    def test_save_is_atomic_and_leaves_no_temp_files(self):
        memory = Memory(self.path).update('小明', ['喜欢猫'])
        memory.save()
        memory.update('小明', ['喜欢狗']).save()
        leftovers = [item.name for item in self.path.parent.iterdir() if item.name != 'memory.json']
        self.assertEqual(leftovers, [])
        self.assertEqual(Memory(self.path).notes, ['喜欢狗'])

    def test_prompt_suffix_only_when_something_is_saved(self):
        memory = Memory(self.path)
        self.assertEqual(memory.prompt_suffix(), '')
        memory.update('小明', [])
        self.assertIn('小明', memory.prompt_suffix())
        memory.update('', ['喜欢猫'])
        suffix = memory.prompt_suffix()
        self.assertIn('- 喜欢猫', suffix)
        self.assertNotIn('称呼', suffix)

    def test_load_is_repeatable(self):
        Memory(self.path).update('小明', ['喜欢猫']).save()
        memory = Memory(self.path)
        self.assertIs(memory.load(), memory)
        self.assertEqual((memory.name, memory.notes), ('小明', ['喜欢猫']))


if __name__ == '__main__':
    unittest.main()
