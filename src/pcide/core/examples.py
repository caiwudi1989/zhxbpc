"""Validated offline examples; double-click creates an editable project copy."""
from __future__ import annotations

from pathlib import Path

from .development import TEMPLATE_MAP
from .paths import read_json
from .project import Project, valid_file_name

def load_catalog(paths):
    root = paths.resources / 'examples' if (paths.resources / 'examples/catalog.json').is_file() else paths.root / 'examples'
    raw = read_json(root / 'catalog.json', {})
    if not isinstance(raw, dict) or raw.get('version') != 1 or not isinstance(raw.get('examples'), list) or len(raw['examples']) > 500:
        raise ValueError('示例目录无效或尚未生成')
    used = set()
    for item in raw['examples']:
        if not isinstance(item, dict) or not valid_file_name(item.get('id', '')) or item['id'] in used or item.get('template') not in TEMPLATE_MAP:
            raise ValueError('示例ID重复或模板无效')
        used.add(item['id'])
        relative = item.get('path', '')
        path = Path(relative)
        target = root / path
        if not relative or path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative or not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
            raise ValueError('示例路径越界')
        if not (target / '.pcide/project.json').is_file() or not (target / 'README.md').is_file():
            raise ValueError('示例缺少完整工程或说明')
        for field in ('title', 'category', 'description', 'expected', 'requires'):
            if not isinstance(item.get(field), str) or len(item[field]) > 4000:
                raise ValueError('示例说明字段无效')
    return root, raw['examples']

def instantiate_example(paths, item):
    root, catalog = load_catalog(paths)
    record = next((value for value in catalog if value['id'] == item['id']), None)
    if record is None:
        raise ValueError('找不到这个示例')
    name = 'Example_' + record['id']
    target = paths.project(name)
    number = 2
    while target.exists():
        target = paths.project(name + '_' + str(number))
        number += 1
    project = Project.copy_to(root / record['path'], target)
    project.manifest['name'] = target.name
    project.save_manifest()
    return project
