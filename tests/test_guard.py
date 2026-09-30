"""
TEST-GUARD-1: Ensures no production code imports from tests/fixtures/
"""
import ast
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def check_imports(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError:
            return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if 'tests.fixtures' in alias.name or 'fixtures' in alias.name:
                    return False
        elif isinstance(node, ast.ImportFrom):
            if node.module and ('tests.fixtures' in node.module or 'fixtures' in node.module):
                return False
    return True

def test_no_fixture_imports_in_production():
    """Verify that no UI or services code imports from tests/fixtures."""
    directories_to_check = ['ui', 'services', 'ml', 'alerts', 'agent']
    
    violating_files = []
    
    for directory in directories_to_check:
        dir_path = BASE_DIR / directory
        if not dir_path.exists():
            continue
            
        for py_file in dir_path.rglob('*.py'):
            if not check_imports(py_file):
                violating_files.append(str(py_file.relative_to(BASE_DIR)))
                
    assert len(violating_files) == 0, f"TEST-GUARD-1 FAILED: Production files importing from fixtures: {violating_files}"
