# タスク分解: <機能名>

- **feature-id**: YYYYMMDD-<slug>
- **関連**: `REQUIREMENTS.md`, `TEST.md`
- **status**: draft | approved | in-progress | done

## 依存グラフ

```
T1 ─┬─→ T2 ─→ T4
    └─→ T3 ─→ T4
T5 (T1-T4 と並列可)
```

## 実行順序

- Phase 1: T1, T5 (並列)
- Phase 2: T2, T3 (並列、T1 完了後)
- Phase 3: T4 (T2, T3 完了後)
- Phase 4: T6 (最終統合)

## タスク一覧

### T1: <タスク名>
- **目的**: <このタスクで何を達成するか>
- **変更ファイル**:
  - `path/to/file.ts` (new)
  - `path/to/existing.ts` (edit)
- **完了条件**:
  - [ ] <具体的な実装項目>
  - [ ] TC-1, TC-2 が通る
  - [ ] 既存テストが退行しない
- **関連要件**: FR-1
- **関連テスト**: TC-1, TC-2
- **推定規模**: <小/中/大> (目安: ファイル数・行数)
- **Codex への指示の要点**:
  - <既存の類似実装 `<path>` を参考にする>
  - <このエラーハンドリングパターンを踏襲する>
  - <ここは絶対に触らない>
- **status**: todo | in-progress | review | done | failed | skipped
- **担当**: codex
- **実行ログ**:
  - [YYYY-MM-DD HH:MM] 依頼送信
  - [YYYY-MM-DD HH:MM] Codex 応答受信
  - [YYYY-MM-DD HH:MM] triage 判定: 採用 / 差し戻し / 部分採用
  - [YYYY-MM-DD HH:MM] コミット: <hash>

### T2: ...

<以下、タスクごとに繰り返し>

## 統合タスク

### T-merge: 全体統合と PR 作成
- 全タスク完了後、差分を統合
- PR 本文を REQUIREMENTS.md から生成
- ADR を正式版に昇格
- **担当**: claude code (human approval required)

## メトリクス記録

| タスク | Codex 往復回数 | triage 結果 | 所要時間 |
|---|---|---|---|
| T1 | 1 | 採用 | - |
| T2 | 2 | 部分採用 | - |

## 差し戻しログ

### T2 差し戻し 1 回目
- 日時: ...
- 理由: <triage が指摘した内容>
- Codex への再指示: ...
- 結果: <改善 / 未改善>
