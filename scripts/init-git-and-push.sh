#!/usr/bin/env bash
# 在项目根目录：chmod +x scripts/init-git-and-push.sh && ./scripts/init-git-and-push.sh
# 已配置远程：https://github.com/cong19920207-bit/lxm
# 注意：请在本机「终端.app」中运行；Cursor 内置终端可能无法完成 git init。

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# 你提供的 GitHub 仓库（HTTPS，便于首次登录/凭据）
DEFAULT_REMOTE="https://github.com/cong19920207-bit/lxm.git"

if ! git config user.name >/dev/null 2>&1 || ! git config user.email >/dev/null 2>&1; then
  if ! git config --global user.name >/dev/null 2>&1 || ! git config --global user.email >/dev/null 2>&1; then
    echo "请先设置 Git 身份，例如："
    echo "  git config --global user.name \"你的名字\""
    echo "  git config --global user.email \"你的邮箱@example.com\""
    exit 1
  fi
fi

if [ ! -d .git ]; then
  git init
  git add -A
  git status
  if [ -n "$(git status --porcelain)" ]; then
    git commit -m "chore: 初始提交（双机通过远程仓库同步）"
  else
    echo "没有可提交的内容，已跳过 commit。"
  fi
else
  echo "已存在 .git，跳过 init；将暂存变更并尽量提交后推送。"
  git add -A
  if [ -n "$(git status --porcelain)" ]; then
    git commit -m "chore: 同步本地修改" || true
  fi
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$DEFAULT_REMOTE"
else
  git remote add origin "$DEFAULT_REMOTE"
fi

git branch -M main
echo ""
echo "正在推送到: $DEFAULT_REMOTE"
git push -u origin main
echo "完成。另一台电脑可执行: git clone $DEFAULT_REMOTE"
