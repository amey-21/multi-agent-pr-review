import tempfile

def strip_diff_markers(code_patch: str) -> str:
    """Removes +/-/@@ diff markers, returns clean code as a string."""
    clean_lines = []
    for line in code_patch.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            clean_lines.append(line[1:])
        elif line.startswith('-') and not line.startswith('---'):
            pass
        elif not line.startswith('@@'):
            clean_lines.append(line)
    return '\n'.join(clean_lines)


def write_to_temp_file(clean_code: str, suffix: str = '.py') -> str:
    """Writes already-clean code to a temp file, returns the path."""
    with tempfile.NamedTemporaryFile(
        mode='w', suffix=suffix, delete=False, encoding='utf-8'
    ) as tmp:
        tmp.write(clean_code)
        return tmp.name