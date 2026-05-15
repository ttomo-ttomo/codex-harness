---
name: codex-review
description: Codex CLI を使ってコード差分の軽量レビューを実行する。段階 1 (/fix) で一発レビューとして使用。多ターン対話が必要な場合は MCP 経由（段階 2 /task）を使うこと。
---

# Codex Review Skill

Codex CLI の `codex exec` を使って、差分に対する一発レビューを実行する軽量 skill。

## 使用タイミング

- **段階 1 (/fix)** の最終チェックとして
- 小さな差分（~100 行以内）の確認
- 多ターン対話が不要な場面

## 使用しないタイミング

- 段階 2 以降 → MCP 経由の `mcp__codex__review` を使う
- 差分が 300 行を超える → タスクを分割するか段階 2 へ
- 質問・相談ベースの対話 → CC 内で完結させる

## 実行手順

### 1. 差分の準備

```bash
# ステージング前の変更を対象にする
git diff > /tmp/review-diff.patch

# または特定コミット範囲
git diff <base>..<head> > /tmp/review-diff.patch
```

### 2. Codex 呼び出し

```bash
codex exec \
  --skip-git-repo-check \
  --output-last-message /tmp/codex-review.md \
  "以下の差分をレビューしてください。

重要な制約:
- 指摘は必須/推奨/ノイズの 3 分類で出力
- スタイルの揚げ足取りより、設計・セキュリティ・パフォーマンスを優先
- 最大 10 件まで。それ以上は重要な 10 件に絞る
- AGENTS.md の規約に基づいて判定

差分:
$(cat /tmp/review-diff.patch)"
```

### 3. 出力の triage へ引き渡し

Codex の出力ファイル `/tmp/codex-review.md` を読み、
`triage` サブエージェントに渡して最終分類する。

## 失敗時のフォールバック

- Codex が応答しない / エラー → 一度リトライ、それでも失敗なら CC 単独レビューに切り替え、ユーザーに報告
- 差分が大きすぎてトークン超過 → ファイル単位で分割して複数回実行

## 注意

- **Codex の出力をそのまま適用しない**。必ず triage を経由する
- **破壊的コマンドの実行は禁止**（`exec` はレビューのみで使い、修正コマンドを実行させない）
- **レビュー結果は task-note.md または作業ログに保存**（将来の参照用）
