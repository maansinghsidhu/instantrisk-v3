import os, zipfile, shutil

# Copy buildspec.yml to backend-merged
src = r'C:\Users\maani\instantrisk-v2\backend\buildspec.yml'
dst = r'C:\Users\maani\instantrisk-v2\backend-merged\buildspec.yml'
shutil.copy2(src, dst)
print(f'Copied buildspec.yml to backend-merged/')

# Recreate zip with buildspec.yml included
merged_dir = r'C:\Users\maani\instantrisk-v2\backend-merged'
zip_path = r'C:\Users\maani\instantrisk-v2\backend-source.zip'

include_items = ['Dockerfile', 'buildspec.yml', 'app', 'alembic', 'alembic.ini', 'requirements.txt']

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for item in include_items:
        full_path = os.path.join(merged_dir, item)
        if os.path.isfile(full_path):
            arcname = item.replace(os.sep, '/')
            zf.write(full_path, arcname)
            print(f'  Added file: {arcname}')
        elif os.path.isdir(full_path):
            for root, dirs, files in os.walk(full_path):
                dirs[:] = [d for d in dirs if d != '__pycache__']
                for f in files:
                    if f.endswith('.pyc'):
                        continue
                    file_path = os.path.join(root, f)
                    arcname = os.path.relpath(file_path, merged_dir).replace(os.sep, '/')
                    zf.write(file_path, arcname)
            dir_count = sum(1 for name in zf.namelist() if name.startswith(item + '/'))
            print(f'  Added directory: {item}/ ({dir_count} files)')
        else:
            print(f'  WARNING: {item} not found!')

print(f'Zip recreated: {zip_path}')
with zipfile.ZipFile(zip_path, 'r') as zf:
    top_level = sorted(set(n.split('/')[0] for n in zf.namelist()))
    print(f'Top-level entries: {top_level}')
    print(f'Total entries: {len(zf.namelist())}')
