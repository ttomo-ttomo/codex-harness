---
description: 計画を立てて実装し、Codex MCP 経由の多ターンレビューを受ける（段階 2）
argument-hint: <タスクの説明>
---

# /task — 段階 2: Harness

**適用範囲**: 複数ファイルの変更、新機能の追加、既存パターンの踏襲範囲内のリファクタ

## 手順

### Phase 1: 起草

1. **task-id を採番**: `YYYYMMDD-<短い要約>` 形式
2. **作業ディレクトリ作成**: `.claude/work/<task-id>/`
3. **task-note.md を起草**
   - `${CLAUDE_PLUGIN_ROOT}/templates/task-note.md` をコピー
   - 背景・スコープ・完了条件・影響範囲・ロールバック手順を埋める
   - 関連する ADR を `docs/adr/` から検索して参照
4. **ユーザー承認を取る**
   - task-note を提示し、「この内容で実装に進んで良いですか？」と確認
   - 承認なしで Phase 2 に進まない

### Phase 2: 実装

1. AGENTS.md の規約に従い実装
2. 各ファイル変更の意図を task-note.md の「実装メモ」に追記（Codex と triage の文脈になる）
3. lint + typecheck + test が通ることを確認

### Phase 3: Codex MCP レビュー

0. **Codex 検出（フォールバック判定）**
   - `mcp__codex__review` を呼ぶ前に、Codex の有無を確認する
   - 例:

   ```bash
   python3 -c "
   from core.codex_detect import detect_codex, format_fallback_marker, should_fallback
   import sys

   detection = detect_codex()
   fallback, strategy = should_fallback()

   if fallback and strategy == 'claude-subagent':
       reason = detection.reason or 'detected unavailable'
       sys.stderr.write(format_fallback_marker(reason=reason, strategy=strategy) + '\n')
       print('FALLBACK')
   elif strategy == 'off' and not detection.available:
       sys.stderr.write(
           '[harness-core] Codex unavailable and CODEX_HARNESS_FALLBACK=off - please install codex.\n'
       )
       print('STOP')
   else:
       print('OK')
   "
   ```

   - `OK` の場合は 1 に進み、既存どおり `mcp__codex__review` を使う
   - `FALLBACK` の場合は 1.5 に進む
   - `STOP` の場合はユーザーに `codex` のインストールを案内して停止する
1. **MCP 経由で Codex に依頼（OK の場合のみ）**
   - `mcp__codex__review` ツールを呼び出す
   - 入力: task-note.md の全文 + `git diff` の出力
   - システムプロンプトで「必須/推奨/ノイズの 3 分類で指摘せよ」と明示
1.5 **フォールバック実行（FALLBACK の場合）**
   - `agents/codex-fallback-reviewer.md` を標準モードで呼び出す
   - 入力: フォールバック発動コンテキスト + task-note.md の全文 + `git diff` の出力
   - 多ターン対話は最大 2 往復まで。Codex の 3 往復より厳しくし、退化による進行ロックを抑える
   - 2 往復で結論が出ない場合は、その時点の応答を Phase 4 の triage に回す
2. **多ターン対話**
   - `OK` の場合:
     Codex から質問が返ってきたら、関連ファイルを読んで回答
   - 最大 3 往復まで。それ以上は triage に回す
   - `FALLBACK` の場合:
     `agents/codex-fallback-reviewer.md` との往復は最大 2 往復まで
3. **Phase 4 へ渡す入力の整形**
   - triage に渡す入力には、レビュー本文に加えて「Codex 不在のためフォールバック発動」または `[harness-core] FALLBACK MODE: ...` を含める
   - これにより triage がフォールバック前提のレビューであることを認識できるようにする

### Phase 4: triage

1. **triage サブエージェントを呼び出す**
   - 入力: Codex の全応答 + 差分
   - 出力: 必須 / 推奨 / ノイズ の分類結果
2. **適用判断**
   - 必須: 自動適用し、再度 lint + typecheck + test
   - 推奨: ユーザーに一覧提示して判断を仰ぐ
   - ノイズ: `task-note.md` の末尾にログとして残す（学習用）

### Phase 5: コミット

1. 最終差分と task-note.md をユーザーに提示
2. コミットメッセージ案を提案
3. ユーザー承認後にコミット
4. **`Plans.md` を更新**
   - 「進行中のタスク」から「完了済み」セクションへ移動
   - コミット hash、task-note パス、学びを記録
5. `.claude/work/<task-id>/` を残す（将来の参照用）

## エスカレーション条件

以下に該当したら段階 3 へ：

- 新規 ADR が必要
- 複数コンポーネント間の契約を変更する
- マイグレーションや破壊的変更を含む
- タスクが 5 つ以上のサブタスクに分解できる
