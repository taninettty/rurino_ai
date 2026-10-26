"""Small, user-editable profile injected into the conversation prompt.

Only what the user types is stored: no transcript is written, the file is plain
JSON the user can read or delete, and a damaged file falls back to empty instead
of blocking the desktop pet.
"""
import json
import os
from pathlib import Path
import tempfile

MAX_NAME = 40
MAX_NOTES = 20
MAX_NOTE = 120


def default_path():
    base = os.environ.get('LOCALAPPDATA') or (Path.home() / '.local/share')
    return Path(base) / 'RurinoLive2D' / 'memory.json'


def clean_notes(values):
    """Strip, truncate, de-duplicate while keeping order, and bound the count."""
    if not isinstance(values, (list, tuple)):
        # A string would otherwise be taken apart character by character.
        return []
    notes, seen = [], set()
    for value in values or []:
        if not isinstance(value, str):
            continue
        note = ' '.join(value.split())[:MAX_NOTE]
        if note and note not in seen:
            seen.add(note)
            notes.append(note)
        if len(notes) >= MAX_NOTES:
            break
    return notes


class Memory:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_path()
        self.name = ''
        self.notes = []
        self.load()

    def load(self):
        self.name, self.notes = '', []
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeDecodeError):
            return self
        if not isinstance(data, dict):
            return self
        name = data.get('name')
        if isinstance(name, str):
            self.name = ' '.join(name.split())[:MAX_NAME]
        self.notes = clean_notes(data.get('notes'))
        return self

    def update(self, name='', notes=()):
        self.name = ' '.join(str(name).split())[:MAX_NAME]
        self.notes = clean_notes(notes)
        return self

    def save(self):
        data = {'name': self.name, 'notes': clean_notes(self.notes)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='memory-', suffix='.tmp')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            # Replace only once the new file is complete, so a crash cannot
            # leave a half-written profile behind.
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        self.name, self.notes = data['name'], data['notes']
        return self

    def block(self):
        lines = []
        if self.name:
            lines.append(f'用户希望你称呼他/她为「{self.name}」。')
        lines.extend(f'- {note}' for note in self.notes)
        return '\n'.join(lines)

    def prompt_suffix(self):
        body = self.block()
        if not body:
            return ''
        return ('\n\n用户主动保存的少量个人资料（只在相关时自然使用，不要逐条复述，也不要编造更多）：\n'
                + body)

    def __bool__(self):
        return bool(self.name or self.notes)
