#!/bin/bash
set -e

echo "=== 清理旧构建 ==="
rm -rf dist/ build/ *.egg-info

echo "=== 构建包 ==="
python3 -m build

echo "=== 上传到 PyPI ==="
python3 -m twine upload dist/*

echo "=== 完成 ==="
