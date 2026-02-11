"""Fix assessment_id type from int to str (UUID) across all routers"""
import os
import re

ROUTERS_DIR = r'C:\Users\maani\instantrisk-v2\backend-merged\app\routers'

# Files to fix
files_to_fix = [
    'assessments.py',
    'clauses.py',
    'document_generation.py',
    'contracts.py',
    'integrations.py',
    'pricing.py',
    'sanctions.py',
    'sharing.py',
    'templates.py',
    'umr.py',
    'upload_session.py',
]

def fix_file(filepath):
    """Fix assessment_id: int -> assessment_id: str in a file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Replace assessment_id: int with assessment_id: str in function signatures
    # Pattern matches: assessment_id: int, or assessment_id: int = or assessment_id: int)
    content = re.sub(r'assessment_id:\s*int\b', 'assessment_id: str', content)

    # Also fix any Assessment.id == assessment_id comparisons that might cast
    # These should work with string UUIDs

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

print("="*60)
print("Fixing assessment_id type: int -> str (UUID)")
print("="*60)

fixed_count = 0
for filename in files_to_fix:
    filepath = os.path.join(ROUTERS_DIR, filename)
    if os.path.exists(filepath):
        if fix_file(filepath):
            print(f"[FIXED] {filename}")
            fixed_count += 1
        else:
            print(f"[SKIP]  {filename} (no changes needed)")
    else:
        print(f"[MISS]  {filename} (file not found)")

print()
print(f"Fixed {fixed_count} files")
print("="*60)
