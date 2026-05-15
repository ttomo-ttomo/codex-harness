# core/ — Guardrail Engine

Claude Code フック経由で動作する Python 製ガードレール。標準ライブラリのみで動く。

## 役割

| 責務 | 実装 |
|---|---|
| 危険コマンドの事前阻止 | R01-R04, R10, R11（PreToolUse） |
| 文脈依存の警告 | R05-R09（PreToolUse） |
| テスト改ざん検知 | POST-01（PostToolUse） |
| ガバナンス文書変更の警告 | POST-02（PostToolUse） |
| Agent Trace 記録 | 全フック共通 |
| セッション終了サマリ | Stop フック |

## ファイル

```
core/
├── hooks.py        # CLI エントリ。`python3 core/hooks.py {pre|post|stop}`
├── domain.py       # ToolCall + Rule + 宣言的ファクトリ
├── engine.py       # evaluate() + write_trace()
├── rules.py        # R01-R11 + POST-01/02
├── test_harness.py # unittest
└── README.md
```

## アーキテクチャ

3 層構成で疎結合に保つ：

```
hooks.py (CLI)
  └─> parse_event(raw_dict) -> ToolCall   ← Claude Code プロトコルとの唯一の接点
       └─> evaluate(rules, call) -> Result ← ルールはToolCallだけを見る
            └─> Rule.check(call) -> Decision
```

- **`domain.py`**: `ToolCall`（正規化済みイベント）、`Rule`、宣言的ファクトリ（`bash_pattern_rule` / `path_pattern_rule`）。生 dict は `parse_event` だけが触る
- **`rules.py`**: 単純な regex マッチはファクトリで宣言。分岐ロジック（R09, POST-01）は独自 `check` 関数
- **`engine.py`**: ルールを順に評価し、最初の deny で短絡。warn は積算
- **`hooks.py`**: stdin → parse → evaluate → trace → exit code

## セットアップ

ビルド不要。`python3 >= 3.10` が PATH に通っていればそのまま動く。
フック登録はプラグイン直下の `hooks/hooks.json` に済んでいる（`${CLAUDE_PLUGIN_ROOT}/core/hooks.py` を呼び出す）。

## テスト

```bash
python3 -m unittest discover -s core -p 'test_*.py'
```

## ルールの追加

### パターンマッチで済む場合（推奨）

```python
# rules.py
R20_MY_RULE = bash_pattern_rule(
    id="R20",
    description="Deny dangerous foo invocation",
    action="deny",
    patterns=[r"\bfoo\s+--bar\b"],
    message="R20: foo --bar is not allowed.",
)
# その後 UNIVERSAL_RULES か MODE_SPECIFIC_RULES に追加
```

ファイルパス系なら `path_pattern_rule` を使う。`message` は `str` か `lambda call, pat: ...` 形式。

### 分岐ロジックが必要な場合

```python
def _r21_check(call: ToolCall) -> Decision:
    if call.command is None:
        return ALLOW
    if "specific-thing" in call.command:
        return Decision("warn", "R21: ...")
    return ALLOW

R21_MY_RULE = Rule("R21", "...", ("PreToolUse",), _r21_check)
```

最後にレジストリに登録 + `test_harness.py` にテストを追加。

## 設計方針

- **Fail open**: ハーネス自身のバグで agent loop を止めない
- **ルールは ToolCall だけを見る**: 生 hook 形状から独立
- **ID は不変**: R01 は永久に R01。ADR やコミットメッセージから引用可能
- **段階的厳格化**: `allow` → `warn` → `deny` の 3 段階で、運用しながら `warn` を `deny` に昇格

## ADR との接続

各ルールは `docs/adr/` から引用される。例：

> ADR-0004: sudo コマンドは原則禁止する（R01 で強制）

この対応関係が保たれている限り、ルール ID を検索すれば根拠 ADR に辿り着ける。
