"""Fix ALL UUID type mismatches across entire backend codebase"""
import os
import re

BASE_DIR = r'C:\Users\maani\instantrisk-v2\backend-merged\app'

# Directories to scan
DIRS = ['core', 'middleware', 'models', 'schemas', 'services', 'routers']

def fix_file(filepath):
    """Fix user_id: int -> str and assessment_id: int -> str"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Fix user_id: int -> user_id: str
    content = re.sub(r'user_id:\s*int\b', 'user_id: str', content)
    content = re.sub(r'user_id:\s*Optional\[int\]', 'user_id: Optional[str]', content)

    # Fix assessment_id: int -> assessment_id: str (in Pydantic schemas and function params)
    content = re.sub(r'assessment_id:\s*int\b', 'assessment_id: str', content)
    content = re.sub(r'assessment_id:\s*Optional\[int\]', 'assessment_id: Optional[str]', content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

print("="*60)
print("COMPREHENSIVE UUID TYPE FIX")
print("Fixing: user_id: int -> str, assessment_id: int -> str")
print("="*60)

fixed_count = 0

for dir_name in DIRS:
    dir_path = os.path.join(BASE_DIR, dir_name)
    if not os.path.exists(dir_path):
        continue

    print(f"\n--- {dir_name.upper()} ---")
    for filename in os.listdir(dir_path):
        if filename.endswith('.py'):
            filepath = os.path.join(dir_path, filename)
            if fix_file(filepath):
                print(f"[FIXED] {dir_name}/{filename}")
                fixed_count += 1

print()
print(f"Total fixed: {fixed_count} files")
print("="*60)
