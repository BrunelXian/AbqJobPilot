"""Display-only resources and user preferences. Never imports Runtime or Store."""
import json
import os
from pathlib import Path
from functools import lru_cache

LANGUAGES = {'en': 'English', 'zh-CN': '简体中文', 'fr-FR': 'Français (Preview)', 'de-DE': 'Deutsch (Preview)'}


@lru_cache(maxsize=4)
def catalog(locale):
    if locale not in LANGUAGES: locale = 'en'
    try:
        value = json.loads((Path(__file__).parent / 'locales' / (locale + '.json')).read_text(encoding='utf-8'))
        if not isinstance(value, dict): raise ValueError('Invalid display catalog')
        return {key: text for key, text in value.items() if isinstance(text, str)}
    except (OSError, ValueError):
        if locale == 'en': raise
        return catalog('en')


def translate(locale, key, **values):
    locale = 'zh-CN' if locale == 'zh' else locale
    if locale not in LANGUAGES: locale = 'en'
    message = catalog(locale).get(key, catalog('en').get(key))
    if message is None:
        message = catalog(locale).get('error.generic', catalog('en')['error.generic'])
        values = {'code': 'DISPLAY_MESSAGE_UNAVAILABLE'}
    try: return message.format_map(values)
    except (KeyError, ValueError): return catalog('en')['error.generic'].format(code='DISPLAY_PARAMETER_MISSING')


class DisplayPreferences:
    """Bounded user display preferences, no credential or Project mutation."""
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get('ABQJOBPILOT_UI_PREFS') or
                         Path.home() / '.abqjobpilot' / 'display.json')
        self.data = {}
        try:
            with self.path.open('rb') as f: raw = f.read(65537)
            if len(raw) <= 65536:
                value = json.loads(raw)
                if isinstance(value, dict): self.data = value
        except (OSError, ValueError): pass
        if self.data.get('language') not in LANGUAGES: self.data['language'] = 'en'
        if not isinstance(self.data.get('recent',[]),list):self.data['recent']=[]
        if not isinstance(self.data.get('dividers',{}),dict):self.data['dividers']={}

    def save(self, **values):
        for key, value in values.items():
            if key in {'language', 'geometry', 'dividers', 'recent'}: self.data[key] = value
        raw = json.dumps({k: v for k, v in self.data.items() if k in
                         {'language','geometry','dividers','recent'}}, ensure_ascii=False, indent=2)
        if len(raw.encode('utf-8')) > 65536: raise ValueError('Display preference limit')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Per-process staging; preferences do not control execution and last save wins.
        stage = self.path.with_suffix('.' + str(os.getpid()) + '.tmp')
        stage.write_text(raw, encoding='utf-8'); stage.replace(self.path)

    def remember(self, path):
        recent = self.data.get('recent', [])
        if not isinstance(recent, list): recent = []
        self.save(recent=[str(path)] + [v for v in recent if isinstance(v,str) and v != str(path)][:9])
