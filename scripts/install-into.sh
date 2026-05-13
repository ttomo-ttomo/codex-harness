#!/usr/bin/env bash
# codex-harness を別プロジェクトに複製するスクリプト。
#
# 使い方:
#   scripts/install-into.sh <target-project-dir>
#
# 動作:
#   - AGENTS.md / CLAUDE.md / Plans.md / .mcp.json / .claude/ 一式は実体コピー
#     （プロジェクトごとに育てる前提）
#   - core/ はマスター（このリポジトリ）へのシンボリックリンク
#     （ガードレールエンジンの更新を全プロジェクトに伝播させる）
#   - 既存ファイルは上書きしない（衝突したらスキップして警告）
#   - ディレクトリが既に存在する場合は中身単位でマージ
#     （まだ無いファイルだけ補充。既存ファイルは温存）

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <target-project-dir>" >&2
  exit 2
fi

TARGET="$1"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -d "$TARGET" ]]; then
  echo "error: target dir does not exist: $TARGET" >&2
  exit 1
fi

if [[ "$(cd "$TARGET" && pwd)" == "$SRC" ]]; then
  echo "error: target is the harness master itself" >&2
  exit 1
fi

COPIED=()

copy_entity() {
  local rel="$1"
  local src_path="$SRC/$rel"
  local dst_path="$TARGET/$rel"

  if [[ ! -e "$src_path" ]]; then
    echo "skip (missing in master): $rel"
    return
  fi

  # ディレクトリで、かつ宛先にも既にディレクトリがある場合は中身単位でマージ。
  # それ以外（新規 or ファイル）は従来どおり「既存ならスキップ、無ければコピー」。
  if [[ -d "$src_path" && ! -L "$src_path" && -d "$dst_path" && ! -L "$dst_path" ]]; then
    merge_directory "$rel"
    return
  fi

  if [[ -e "$dst_path" || -L "$dst_path" ]]; then
    echo "skip (already exists): $rel"
    return
  fi
  mkdir -p "$(dirname "$dst_path")"
  cp -R "$src_path" "$dst_path"
  echo "copied: $rel"
  COPIED+=("$rel")
}

# 既存ディレクトリへ中身を補充するマージ。
# - find -type f でマスター側の全ファイルを走査
# - 宛先に同じ相対パスが無い場合のみコピー
# - 既存ファイルは触らない（上書きも警告もしない、ログに skip として残す）
# 注: マージは「宛先ディレクトリが既存」という前提で呼ばれるため、
#     .gitignore への自動追記対象（COPIED）には積まない。
merge_directory() {
  local rel="$1"
  local src_root="$SRC/$rel"
  local dst_root="$TARGET/$rel"
  local added=0
  local skipped=0

  while IFS= read -r -d '' src_file; do
    local sub="${src_file#"$src_root"/}"
    local dst_file="$dst_root/$sub"
    if [[ -e "$dst_file" || -L "$dst_file" ]]; then
      echo "  skip (already exists): $rel/$sub"
      skipped=$((skipped + 1))
      continue
    fi
    mkdir -p "$(dirname "$dst_file")"
    cp "$src_file" "$dst_file"
    echo "  merged: $rel/$sub"
    added=$((added + 1))
  done < <(find "$src_root" -type f -print0)

  echo "merge: $rel/ (added=$added, skipped=$skipped)"
}

append_to_gitignore() {
  if [[ ${#COPIED[@]} -eq 0 ]]; then
    return
  fi
  local gitignore="$TARGET/.gitignore"
  local to_add=()
  for entry in "${COPIED[@]}"; do
    if [[ -f "$gitignore" ]] && grep -Fxq "$entry" "$gitignore"; then
      continue
    fi
    to_add+=("$entry")
  done
  if [[ ${#to_add[@]} -eq 0 ]]; then
    return
  fi
  {
    if [[ -s "$gitignore" && -n "$(tail -c1 "$gitignore" 2>/dev/null)" ]]; then
      printf '\n'
    fi
    if [[ -s "$gitignore" ]]; then
      printf '\n'
    fi
    printf '# codex-harness (added by scripts/install-into.sh)\n'
    printf '%s\n' "${to_add[@]}"
  } >> "$gitignore"
  echo "appended to .gitignore: ${to_add[*]}"
}

link_core() {
  local dst_path="$TARGET/core"
  if [[ -e "$dst_path" || -L "$dst_path" ]]; then
    echo "skip (already exists): core"
    return
  fi
  ln -s "$SRC/core" "$dst_path"
  echo "linked: core -> $SRC/core"
  COPIED+=("core")
}

for entity in AGENTS.md CLAUDE.md Plans.md .mcp.json .claude docs; do
  copy_entity "$entity"
done

link_core

append_to_gitignore

cat <<EOF

done. next steps in $TARGET:
  1. AGENTS.md / Plans.md をプロジェクトに合わせて編集
  2. core/ がマスター ($SRC/core) を指していることを確認
  3. python3 >= 3.10 が PATH に通っていることを確認（ビルド不要）
EOF
