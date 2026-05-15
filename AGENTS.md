# AGENTS.md

このファイルは Claude Code と Codex の両方が読む共有の憲法。
長大な仕様書ではなく、**深いドキュメントへのマップ**として機能させる。

## プロジェクト

<!-- プロジェクトごとに書き換え -->
- リポジトリ: `<repo-name>`
- 主要言語: `<language>`
- パッケージマネージャ: `<npm|pnpm|yarn|poetry|...>`
- 本番環境: `<GCP / AWS / Vercel / ...>`

## 必読ドキュメント（優先度順）

1. `Plans.md` — **プロジェクトの SSOT**。進行中・完了済みタスクの索引
2. `docs/adr/` — アーキテクチャ決定記録。**実装前に必ず該当する ADR を確認**
3. `docs/architecture.md` — 全体構成図
4. `docs/runbook.md` — 運用手順
5. `CONTRIBUTING.md` — 貢献ルール
6. `core/README.md` — ガードレールエンジンの全体像

## ADR の記録ルール

`docs/adr/` 配下の運用は次のとおり。テンプレートは `docs/adr/0000-template.md`。

- **ファイル名**: `NNNN-<kebab-slug>.md`。NNNN は `docs/adr/` 内の最大番号 +1 を 4 桁ゼロパディング（`0000-template.md` は採番から除外）
- **起票**: `/feature` の architect が `proposed` で起草 → critic レビュー → ユーザー承認で `accepted` に昇格
- **`/feature` 以外**: 手動で起票してよい。その場合も同テンプレートに従い、最低限 critic 相当のレビューを通す
- **deprecated / superseded**: 旧 ADR の「ステータス」を `superseded by ADR-NNNN` に書き換え、新 ADR の「波及範囲 → 他 ADR」に旧番号を明記して相互リンクを保つ
- **`Plans.md` との連携**: 進行中は `ADR:` フィールドにパスを記録。完了時は「完了済み」エントリの末尾に ADR パスを追記
- **採用後の改変禁止**: `accepted` 以降は本文を書き換えず、必要なら新 ADR で superseded する

## ビルド・テスト

```bash
<build command>
<test command>
<lint command>
<typecheck command>
```

**コミット前に lint + typecheck + test が通ることを必ず確認する。**

## コーディング規約

- 命名・フォーマットは既存ファイルに合わせる
- 新規ファイル作成前に、類似機能の既存ファイルを必ず検索する
- 1 関数 1 責務。早期 return を優先
- コメントは「なぜ」を書き、「何を」は書かない（コードが語る）
- マジックナンバーは定数化

## セキュリティ（ガードレール）

**Python 製ガードレールエンジン（`core/`）が PreToolUse/PostToolUse フックで強制**。
全ルールは `core/rules.py` に定義されている。

| ルール | 対象 | 動作 |
|---|---|---|
| R01 | sudo コマンド | deny |
| R02 | `.git/` `.env` シークレット | deny (write) |
| R03 | `rm -rf /` 等の破壊的操作 | deny |
| R04 | `git push --force` | deny |
| R05 | `npm install`（lockfile 未使用） | warn |
| R06 | production 環境参照 | warn |
| R07 | CI/IaC 設定の変更 | warn |
| R08 | lockfile への直接編集 | deny |
| R09 | 一括削除 | warn |
| R10 | curl/wget をシェルにパイプ | deny |
| R11 | git --no-verify / --no-gpg-sign | deny |
| POST-01 | テスト改ざん（skip 挿入等） | warn |
| POST-02 | AGENTS.md / CLAUDE.md / ADR 変更 | warn |

追加で、インストラクションベースで以下も徹底する：

- **シークレットを絶対にコードに書かない**。環境変数または Secret Manager 経由
- **コミット前に `git diff` をレビュー**し、意図しない変更を除去
- **本番 DB への直接接続禁止**。マイグレーション経由のみ
- 外部 API 呼び出しの追加時は、タイムアウトとリトライを必ず設定

## 変更プロセス

| 規模 | フロー |
|---|---|
| タイポ・1 行修正 | 直接実装 + 軽レビュー |
| 1 ファイル内の変更 | `/fix` コマンド |
| 複数ファイル・新機能 | `/task` コマンド（task-note 必須） |
| アーキテクチャ変更 | `/feature` コマンド（ADR 起票必須） |

## Codex 固有の指示

- レビュー時は **「必須」「推奨」「ノイズ」** の 3 段階で分類して出力
- スタイルの揚げ足取りより、**設計・セキュリティ・パフォーマンス**を優先
- 差分が大きいときは、重要な 5 点に絞って指摘

### Codex 不在時のフォールバック

- 設定は環境変数 `CODEX_HARNESS_FALLBACK` で行う。許容値は `auto` / `off` / `claude-subagent`、デフォルトは `auto`
- `auto`: Codex を検出できれば通常経路、検出できなければフォールバック
- `claude-subagent`: Codex の有無に関わらずレビュー系経路を強制フォールバック
- `off`: フォールバックせず、Codex 不在時は停止
- 採用案 D により、`/fix` と `/task` は `agents/codex-fallback-reviewer.md` に委譲する
- 採用案 D により、`/feature` は実装委譲をフォールバックさせず停止し、ユーザーに「自分で実装する / Codex を入れる / `/task` に降格する」の 3 択を提示する
- フォールバック発動マーカーは `[harness-core] FALLBACK MODE: Codex unavailable (<reason>). Strategy: <strategy>. Quality may degrade.` とする
- この書式の唯一の生成箇所は `core/codex_detect.py` の `format_fallback_marker()` であり、呼び出し側で独自生成しない
- 詳細な決定理由と運用方針は `docs/adr/0001-codex-fallback-strategy.md` を参照

## Claude Code 固有の指示

- サブエージェント（architect, triage）を積極的に活用
- 計画フェーズでユーザー承認を必ず取る（段階 3）
- skill は `skills/` 配下から自動ロード（プラグイン install 時）

## 参照リンク

- Codex MCP: `.mcp.json` 参照
- サブエージェント定義: `agents/`
- テンプレート: `templates/`
