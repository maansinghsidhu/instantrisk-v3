"""Fix ALL user_id type from int to str (UUID) across entire codebase"""
import os
import re

ROUTERS_DIR = r'C:\Users\maani\instantrisk-v2\backend-merged\app\routers'
SERVICES_DIR = r'C:\Users\maani\instantrisk-v2\backend-merged\app\services'

def fix_file(filepath):
    """Fix user_id: int -> user_id: str in a file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Replace user_id: int with user_id: str in function signatures and type hints
    # Handles: user_id: int, user_id: int =, user_id: int), etc.
    content = re.sub(r'user_id:\s*int\b', 'user_id: str', content)

    # Also fix Optional[int] for user_id
    content = re.sub(r'user_id:\s*Optional\[int\]', 'user_id: Optional[str]', content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

print("="*60)
print("Fixing ALL user_id type: int -> str (UUID)")
print("="*60)

fixed_count = 0

# Fix routers
print("\n--- ROUTERS ---")
for filename in os.listdir(ROUTERS_DIR):
    if filename.endswith('.py'):
        filepath = os.path.join(ROUTERS_DIR, filename)
        if fix_file(filepath):
            print(f"[FIXED] routers/{filename}")
            fixed_count += 1

# Fix services
print("\n--- SERVICES ---")
for filename in os.listdir(SERVICES_DIR):
    if filename.endswith('.py'):
        filepath = os.path.join(SERVICES_DIR, filename)
        if fix_file(filepath):
            print(f"[FIXED] services/{filename}")
            fixed_count += 1

print()
print(f"Total fixed: {fixed_count} files")
print("="*60)
