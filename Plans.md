# Plans.md

プロジェクト全体の **単一情報源（SSOT）**。
進行中・計画中・完了済みのタスクと機能の索引。

## 運用ルール

- **`/task` 実行時**: このファイルの「進行中のタスク」セクションに追加
- **`/feature` 実行時**: 「進行中の機能」セクションに追加
- **完了時**: 「完了済み」セクションに移動し、リンク先の成果物パスを記録
- **定期レビュー**: 週次で古い「検討中」項目を整理

## 進行中の機能 (/feature)

<!-- フォーマット
### <feature-id>: <機能名>
- **status**: architect 完了 / critic 完了 / 承認済み / 実装中 / レビュー中
- **architect 起草**: `.claude/work/<feature-id>/REQUIREMENTS.md`
- **開始日**: YYYY-MM-DD
- **想定完了**: YYYY-MM-DD
- **ADR**: `docs/adr/<番号>-<タイトル>.md`
- **メモ**: ...
-->

_（なし）_

## 進行中のタスク (/task)

<!-- フォーマット
### <task-id>: <タスク要約>
- **status**: 起草 / 実装中 / レビュー中
- **task-note**: `.claude/work/<task-id>/task-note.md`
- **開始日**: YYYY-MM-DD
- **メモ**: ...
-->

_（なし）_

## 検討中

<!-- ユーザーから依頼されたが、まだ /fix /task /feature のどれで進めるか決まっていないもの -->

_（なし）_

## 完了済み

<!-- フォーマット
### YYYY-MM-DD: <要約>
- **ID**: <task-id> or <feature-id>
- **段階**: 1 | 2 | 3
- **成果物**: <PR URL> / <コミット hash>
- **アーティファクト**: `.claude/work/<id>/`（参照用に保持）
- **ADR**: `docs/adr/<番号>-<タイトル>.md`（段階 3 で起票した場合のみ）
- **学び**: <次回に活かせるメモ>
-->

### 2026-05-15: Codex 未インストール時のフォールバック
- **ID**: 20260515-codex-fallback
- **段階**: 3 (/feature)
- **成果物**: コミット予定（PR は別途）
- **アーティファクト**: `.claude/work/20260515-codex-fallback/`（REQUIREMENTS.md / TEST.md / AGENT_TASKS.md）
- **ADR**: `docs/adr/0001-codex-fallback-strategy.md`（accepted）
- **採用方針**: 論点 2=D（ハイブリッド）+ 論点 7=(b)（skill / コマンド内 `python3` 直接呼び出し）
  - `/fix`・`/task` → `agents/codex-fallback-reviewer.md` に委譲
  - `/feature` → 実装委譲は停止、ユーザーに 3 択提示
- **新規ファイル**: `core/codex_detect.py` / `core/test_codex_detect.py` / `agents/codex-fallback-reviewer.md` / `docs/adr/0001-...`
- **テスト**: 単体 16 件追加（既存 13 件と合わせて 29 件 pass、退行なし）
- **学び**:
  - architect → critic を 2 サイクル回したことで「採用案未確定のまま T3-T6 に進む矛盾」「ADR proposed 中の決定凍結問題」が事前に解消できた
  - 副次的決定（先行確定）と運用メモ（accepted 化時に削除）のパターンは ADR のロックイン回避に有効
  - 検出ヘルパーの呼び出し主体（hook / skill 直書き / CLI）を独立論点として critic が指摘してくれたおかげで、後続タスクの曖昧さが消えた

## メトリクス

<!-- 月次で集計 -->

### YYYY-MM
- /fix 件数: -
- /task 件数: -
- /feature 件数: -
- Codex との総往復数: -
- triage ノイズ率: - %
- 平均 critic Must 件数: -
