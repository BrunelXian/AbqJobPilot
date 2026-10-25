"""Build review-only static HTML and four proposed resource catalogs. Standard library only."""
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
rows=list(csv.DictReader((HERE/'strings.tsv').open(encoding='utf-8'),delimiter='\t'))
locales={lang:{row['key']:row[lang] for row in rows} for lang in ('en','zh-CN','fr-FR','de-DE')}
(HERE/'locales').mkdir(exist_ok=True)
for lang,strings in locales.items():
    (HERE/'locales'/f'{lang}.json').write_text(json.dumps(strings,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
template=(HERE/'prototype.template.html').read_text(encoding='utf-8')
(HERE/'index.html').write_text(template.replace('/* RESOURCE_CATALOG */', 'const catalog = '+json.dumps(locales,ensure_ascii=False)+';'),encoding='utf-8')
print(json.dumps({'locales':list(locales),'keys_per_locale':len(rows),'output':str(HERE/'index.html')}))
