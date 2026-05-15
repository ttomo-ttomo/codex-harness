---
description: architect が設計し、Codex に実装委譲、triage で審査する（段階 3）
argument-hint: <機能の説明>
---

# /feature — 段階 3: Orchestrate

**適用範囲**: 新機能、アーキテクチャ変更、複数コンポーネントに跨る変更

この段階でのみ **Codex が実装者に反転**する。CC は設計・審査・統合に専念する。

## 手順

### Phase 1: 設計（architect サブエージェント）

1. **architect サブエージェントを起動**
   - 入力: `$ARGUMENTS` + 関連 ADR + 既存アーキテクチャ文書
   - 出力: 以下 3 ファイルを `.claude/work/<task-id>/` に生成
     - `REQUIREMENTS.md` — 機能要件・非機能要件・受け入れ条件
     - `TEST.md` — テスト戦略・テストケース一覧
     - `AGENT_TASKS.md` — Codex に渡すタスク分解（1 タスク = 1 PR レベル）

2. **ADR 起票判断**
   - 新しいアーキテクチャ決定を含む場合、`docs/adr/` に ADR ドラフトも作成

### Phase 1.5: Critic レビュー（承認ゲート前の自己批評）

1. **critic サブエージェントを起動**
   - 入力: architect が出した全成果物（REQUIREMENTS.md / TEST.md / AGENT_TASKS.md / ADR ドラフト）+ フォールバック発動の有無や `CODEX_HARNESS_FALLBACK` 設定など、Codex 利用可否の前提
   - 出力: Must / Should / Could の 3 分類で批評
2. **critic の判定別の対応**
   - **承認推奨**: Phase 2 へ
   - **条件付き承認**: architect を再起動して Must のみ修正 → critic 再実行
   - **差し戻し**: ユーザーに状況を報告し、根本方針から相談し直す
3. **最大 2 サイクル**。それでも収束しない場合はユーザー判断に委ねる

### Phase 2: 承認ゲート（人間必須）

1. architect の成果物と critic の批評を **セットで** ユーザーに提示
2. 以下を明示的に確認：
   - 要件は合っているか
   - タスク分解は妥当か（粒度・順序・並列可否）
   - ADR ドラフトは方向性として正しいか
   - critic の Must / Should を承認 / 却下 / 保留
3. **ユーザーの明示承認なしに Phase 3 には進まない**
4. 修正指示があれば architect を再度呼び出して更新

### Phase 3: タスク委譲ループ

#### Phase 3 着手前: Codex 検出（必須）

```bash
python3 -c "
from core.codex_detect import detect_codex, should_fallback

detection = detect_codex()
fallback, strategy = should_fallback()

if not detection.available:
    print('STOP')
else:
    print('OK')
"
```

- `OK` の場合は通常どおり `mcp__codex__implement` を使ってタスク委譲ループに進む
- `STOP` の場合は採用案 D により実装委譲を停止し、ユーザーに以下 3 択を提示して止まる
  1. **自分で実装する**: CC が手を動かす形に切り替える
  2. **Codex を入れる**: `codex` CLI をインストールして `/feature` を再実行する
  3. **`/task` に降格する**: 実装委譲は諦め、軽量レビュー中心のフローに切り替える
- `CODEX_HARNESS_FALLBACK=off` の場合も `/feature` では同様に停止する。メッセージだけ「フォールバック無効のため停止」と明示する
- `agents/codex-fallback-reviewer.md` は `/feature` Phase 3 では使わない。reviewer 専用であり、implement 用には作成しない

`AGENT_TASKS.md` の各タスクについて、順次以下を実行：

1. **Codex MCP に実装依頼**
   - `mcp__codex__implement` を呼び出し
   - 入力: 当該タスクの定義 + REQUIREMENTS.md の関連部分 + AGENTS.md
   - Codex は差分を返す（直接コミットはさせない）

2. **triage サブエージェントで審査（4 視点モード）**
   - 入力: Codex の差分 + タスク定義 + TEST.md
   - **モード指定**: 4 視点モード（Security / Performance / Quality / Accessibility）
   - 出力: 採用 / 差し戻し / 部分採用 の判定 + 4 視点レビュー

3. **差し戻し判定の場合**
   - Codex に差し戻し理由を添えて再依頼（最大 2 回）
   - 2 回で解決しなければユーザーに判断を仰ぐ

4. **採用判定の場合**
   - CC が差分を適用し、lint + typecheck + test を実行
   - 失敗したら修正して再実行（CC が手を動かす）

5. **進捗を `AGENT_TASKS.md` に記録**
   - 各タスクに `status: done/failed/skipped` を追記

### Phase 4: 統合

1. 全タスク完了後、全体差分をユーザーに提示
2. PR 本文を生成（REQUIREMENTS.md と AGENT_TASKS.md から逆算）
3. ADR を最終化（ドラフト → 正式版）
4. **`Plans.md` を更新**
   - 「進行中の機能」から「完了済み」セクションへ移動
   - 成果物 URL、アーティファクトパス、次回への学びを記録
5. ユーザー承認後にコミット＋ PR 作成

## 中断条件

以下の場合は処理を止めてユーザーに判断を仰ぐ：

- architect が出した計画に矛盾がある
- Codex が 2 回差し戻しても改善しない
- テストが落ち続ける（3 回以上）
- 事前に想定していない破壊的変更が必要になった
- Codex 不在で `/feature` の実装委譲が停止された（採用案 D）
- `CODEX_HARNESS_FALLBACK=off` でフォールバック自体が無効化されている
