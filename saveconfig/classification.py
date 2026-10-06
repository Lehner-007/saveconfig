from pathlib import Path

FILTER_DEFAULTS = dict(program=True, system_desktop=False, cache=False, unknown=True, backup_file=False)
CATEGORIES = {'program', 'system_desktop', 'cache', 'backup_file', 'profile', 'program_data', 'sensitive', 'unknown', 'ignored'}


def category_for(path, kind, known=False, program=''):
    if Path(path).name.lower().endswith(('~', '.bak', '.backup', '.old', '.orig')):
        return 'backup_file'
    if kind == 'cache' or path == '~/.cache' or path.startswith('~/.cache/'):
        return 'cache'
    if program == 'Cinnamon' or kind == 'system':
        return 'system_desktop'
    if not known:
        return 'unknown'
    return {'profile': 'profile', 'data': 'program_data', 'key': 'sensitive'}.get(kind, 'program')


def visible(entry, filters):
    group = 'program' if entry.category in ('program', 'profile', 'program_data', 'sensitive') else entry.category
    return bool(filters.get(group, False))


def is_cache(entry):
    path=entry.path if hasattr(entry,'path') else str(entry)
    return getattr(entry,'kind',None)=='cache' or getattr(entry,'category',None)=='cache' or any(part.casefold() in {'.cache','cache','caches','cache2','code cache','gpucache'} for part in Path(path).parts)


def is_codex(entry):
    path=entry.path if hasattr(entry,'path') else str(entry)
    return str(getattr(entry,'program','')).casefold()=='codex' or any(part.casefold() in {'.codex','codex','codex-app','codex-runtimes'} for part in Path(path).parts)


def excluded_backup(entry):
    return is_cache(entry) or is_codex(entry)
