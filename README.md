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

### サブエージェント（`.claude/agents/`）

- **architect** — 要件・計画・タスク分解を起草
- **critic** — architect の成果物を批評（承認ゲート前）
- **triage** — Codex 出力を必須/推奨/ノイズで分類。段階 3 では 4 視点モード

### SSOT（`Plans.md`）

プロジェクト全体の索引。進行中・完了済みタスクが全てここから辿れる。

## セットアップ

1. このディレクトリをプロジェクトルートに配置（または既存リポジトリにマージ）
2. `python3 >= 3.10` が PATH に通っていることを確認（ビルド不要）
3. `AGENTS.md` をプロジェクトに合わせて編集
4. Codex MCP サーバーを有効化：`codex mcp-server` が PATH に通っていることを確認
5. Claude Code を起動。`.claude/settings.json` のフックが自動登録される
6. 動作確認：`/fix` / `/task` / `/feature` が補完候補に出るか

## 複製運用のコツ

ユーザースコープには載せず、各プロジェクトに本ディレクトリ一式を配置する運用を想定。

1. **`core/` はシンボリックリンクで共有**。マスターを 1 箇所に置いて、各プロジェクトからリンクする:

   ```bash
   # マスター（編集の正本）
   /path/to/codex-harness/core/

   # 各プロジェクトに配置
   ln -s /path/to/codex-harness/core <project>/core
   ```

   `.claude/settings.json` のフックは相対パスのまま動く。ビルド不要なのでマスター更新が即時反映される。
2. **`AGENTS.md` / `Plans.md` は実体ファイル**。プロジェクトごとに中身が違うのでリンクにしない。
3. **`.claude/agents/` `.claude/commands/` `.claude/skills/` `.claude/templates/`** は用途で選ぶ:
   - 全プロジェクトに更新を伝播させたい → シンボリックリンク
   - プロジェクトごとに育てたい → 実体コピー
   - 迷ったら実体コピーで開始し、共通化したい要素だけ後からリンク化
4. **新規プロジェクト導入は `scripts/install-into.sh` を使う**。`AGENTS.md` `CLAUDE.md` `Plans.md` `.mcp.json` `.claude/` 一式は実体コピー、`core/` はマスターへのシンボリックリンクとして配置する:

   ```bash
   # マスター（このリポジトリ）から実行
   scripts/install-into.sh /path/to/<new-project>
   ```

   既存ファイルは上書きせずスキップするので、何度流しても安全。配置後は `AGENTS.md` / `Plans.md` をプロジェクトに合わせて編集する。

## 設計思想

- **AGENTS.md = エージェント向け ADR の軽量版**。両ツールが同じ憲法を読む
- **triage サブエージェントが「累積型指摘」を除去し「創造型指摘」を残す**
- **architect → critic → ユーザー承認の 3 段フィルタ** で計画品質を担保
- **ガードレールは実行時に強制**（指示ベースの守りに頼らない）
- **Plans.md を SSOT に**。状態が 1 箇所にある

## 他実装との関係

- OpenAI `harness engineering` の 4 本柱（AGENTS.md / MCP / Skills / Subagents）に準拠

## ディレクトリ

```
.
├── AGENTS.md                    両ツール共有の憲法（~100 行のマップ）
├── CLAUDE.md                    @AGENTS.md を参照、CC 固有のみ追記
├── Plans.md                     プロジェクト SSOT
├── .mcp.json                    Codex MCP サーバー登録
├── .claude/
│   ├── settings.json            フック登録（core/ を呼び出す）
│   ├── commands/                スラッシュコマンド（3 段階）
│   ├── agents/                  architect / critic / triage
│   ├── skills/                  段階 1-2 で使う軽量 skill
│   └── templates/               起草用テンプレ
├── core/                        ガードレールエンジン（Python・標準ライブラリのみ）
│   ├── hooks.py                 エントリポイント（pre/post/stop サブコマンド）
│   ├── domain.py                ToolCall + 宣言的ルールファクトリ
│   ├── engine.py                評価エンジン + Agent Trace
│   ├── rules.py                 ルール定義（R01-R11 + POST-01/02）
│   └── test_harness.py          unittest
├── scripts/
│   └── install-into.sh          新規プロジェクトへの複製スクリプト
└── docs/adr/                    ADR 置き場（既存資産と接続）
```
