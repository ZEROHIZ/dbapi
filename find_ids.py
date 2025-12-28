import re
import os

def find_webpack_ids(filename):
    if not os.path.exists(filename):
        print(f"File {filename} not found.")
        return
        
    content = open(filename, 'r', encoding='utf-8').read()
    
    # 查找 Chunk ID: .push([["ID"]
    chunk_match = re.search(r'\.push\(\[\["(\d+)"\]', content)
    # 查找模块 ID: ID: function
    module_matches = re.findall(r'(\d+): function', content)
    
    print(f"Analysis for {filename}:")
    print(f"  Detected Chunk ID: {chunk_match.group(1) if chunk_match else 'Not Found'}")
    print(f"  Total Modules found: {len(module_matches)}")
    if module_matches:
        print(f"  First 5 Module IDs: {module_matches[:5]}")
    print("-" * 20)

find_webpack_ids("acrawler.js")
find_webpack_ids("bdms.js")
