"""Development-only sealing utility; no external process capability. No execution approval."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / 'controller'))
from frozen import original, configuration, material_paths, PACKAGE, verify_materials
from records import stable_read, write_new, digest


def main():
    old = original()
    verify_materials(old['body']['materials'])
    body = configuration(old['body'])
    body['materials'] = []
    for path in material_paths():
        _, item = stable_read(path)
        body['materials'].append({'path':str(path), 'bytes':item['bytes'], 'sha256':item['sha256']})
    value = {'body':body, 'content_digest':digest(body)}
    write_new(PACKAGE / 'CANDIDATE_MANIFEST.json', value)
    print(value['content_digest'])


if __name__ == '__main__':
    main()
