# Codex × Claude Code Harness

Claude Code を主、Codex を副とする 3 段階ハーネス。
現状の「Codex レビュー → CC 評価 → CC 実装」フローを、タスクの複雑度に応じて 3 段階に昇華させる。

## 段階

| 段階 | コマンド | CC の動き | Codex の役割 |
|---|---|---|---|
| 1. Quick | `/fix` | 即実装、事後に軽レビュー | skill 経由の一発レビュー |
| 2. Harness | `/task` | task-note 起草 → 実装 → MCP 経由レビュー → triage | MCP 経由の多ターンレビュー |
| 3. Orchestrate | `/feature` | architect 起草 → critic 批評 → 承認ゲート → タスク委譲 → 4 視点 triage → 統合 | MCP 経由の **実装エンジン**（役割反転） |

段階 3 でのみ Codex が実装者に反転する。段階 1-2 は Codex=レビュアーのまま。

## コンポーネント

### ガードレールエンジン（`core/`）

Python 製（標準ライブラリのみ）。PreToolUse/PostToolUse フックで動作。R01-R11 + POST-01/02 のルールで危険操作を阻止し、全ツール呼び出しを Agent Trace に記録する。

### サブエージェント（`agents/`）

- **architect** — 要件・計画・タスク分解を起草
- **critic** — architect の成果物を批評（承認ゲート前）
- **triage** — Codex 出力を必須/推奨/ノイズで分類。段階 3 では 4 視点モード

### SSOT（`Plans.md`）

プロジェクト全体の索引。進行中・完了済みタスクが全てここから辿れる。

## セットアップ

Claude Code プラグイン（marketplace）として配布する。

1. Claude Code 内で marketplace を追加:

   ```
   /plugin marketplace add ttomo-ttomo/codex-harness
   /plugin install codex-harness@codex-harness
   ```

2. `python3 >= 3.10` が PATH に通っていることを確認（ガードレールエンジン用、ビルド不要）
3. Codex CLI が PATH に通っていることを確認（`codex mcp-server` を MCP 経由で起動するため）
4. プラグインを有効化したいプロジェクトの `AGENTS.md` をプロジェクト用に編集（テンプレが必要なら `templates/` を参照）
5. 動作確認：`/fix` / `/task` / `/feature` が補完候補に出るか

## Codex 不在時のフォールバック

Codex CLI が PATH に無い環境でも、採用案 D により `/fix` と `/task` は `agents/codex-fallback-reviewer.md` へ縮退できる一方、`/feature` の実装委譲は品質劣化リスクを避けるため停止する。設定は `export CODEX_HARNESS_FALLBACK=auto` のように行い、`auto` では利用可能なら Codex を使い、不在ならフォールバックする。`off` は Codex 不在時に停止、`claude-subagent` はレビュー系経路を強制フォールバックする。発動時のマーカーは `[harness-core] FALLBACK MODE: Codex unavailable (<reason>). Strategy: <strategy>. Quality may degrade.` で、`core/codex_detect.py` の `format_fallback_marker()` が唯一の生成箇所である。詳細は `docs/adr/0001-codex-fallback-strategy.md` を参照。

## 設計思想

- **AGENTS.md = エージェント向け ADR の軽量版**。両ツールが同じ憲法を読む
- **triage サブエージェントが「累積型指摘」を除去し「創造型指摘」を残す**
- **architect → critic → ユーザー承認の 3 段フィルタ** で計画品質を担保
- **ガードレールは実行時に強制**（指示ベースの守りに頼らない）
- **Plans.md を SSOT に**。状態が 1 箇所にある

## 他実装との関係

- OpenAI `harness engineering` の 4 本柱（AGENTS.md / MCP / Skills / Subagents）に準拠

## ディレクトリ

公式プラグインレイアウトに従う。`/plugin install` 後、commands/agents/skills/hooks は自動検出される。

```
.
├── .claude-plugin/
│   ├── plugin.json              プラグインマニフェスト
│   └── marketplace.json         marketplace マニフェスト
├── AGENTS.md                    両ツール共有の憲法（~100 行のマップ）
├── CLAUDE.md                    @AGENTS.md を参照、CC 固有のみ追記
├── Plans.md                     プロジェクト SSOT
├── .mcp.json                    Codex MCP サーバー登録
├── commands/                    スラッシュコマンド（/fix /task /feature）
├── agents/                      architect / critic / triage
├── skills/                      段階 1-2 で使う軽量 skill
├── templates/                   起草用テンプレ（task-note 等）
├── hooks/
│   └── hooks.json               フック登録（${CLAUDE_PLUGIN_ROOT}/core/hooks.py を呼ぶ）
├── core/                        ガードレールエンジン（Python・標準ライブラリのみ）
│   ├── hooks.py                 エントリポイント（pre/post/stop サブコマンド）
│   ├── domain.py                ToolCall + 宣言的ルールファクトリ
│   ├── engine.py                評価エンジン + Agent Trace
│   ├── rules.py                 ルール定義（R01-R11 + POST-01/02）
│   └── test_harness.py          unittest
└── docs/adr/                    ADR 置き場（既存資産と接続）
```

ランタイム成果物（`.claude/work/<task-id>/`、`.claude/state/agent-trace.jsonl`）はプラグインを実行したプロジェクトの cwd 配下に書き出される（gitignore 対象）。
