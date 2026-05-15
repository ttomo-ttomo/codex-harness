# ADR-0001: Codex 未インストール時のフォールバック戦略

- **日付**: 2026-05-15
- **ステータス**: accepted
- **起票**: architect subagent
- **関連 feature**: 20260515-codex-fallback (`Plans.md` 参照)

## コンテキスト

本リポジトリは「Codex CLI を Claude Code から呼び出すハーネス（プラグイン）」であり、
プラグインの主要機能 `/fix` `/task` `/feature` はいずれも Codex に依存している：

- `skills/codex-review/SKILL.md` が `codex exec` を直接呼ぶ（段階 1 / `/fix`）
- `mcp__codex__review` が `.mcp.json` 経由で `codex mcp-server` に接続（段階 2 / `/task`）
- `mcp__codex__implement` が同上で実装委譲（段階 3 / `/feature`）

`codex` バイナリが PATH 上に存在しない環境では、これらが全て失敗する。
特に初回ユーザー（プラグインを試そうとしてインストールしただけ）にとって、
**何が起きたか・どう直せばいいかが伝わらない** ため、UX 上の致命傷になる。

加えて、ガードレール（`agents/triage.md` の 3 分類 / 4 視点モード、`agents/critic.md` の自己批評）は
Codex 出力ありきで設計されており、代替経路を用意しない場合は体験全体が破綻する。

本 ADR は、Codex 未導入時の挙動を **どの方針で吸収するか** を決定する。

## 決定

論点 2「フォールバック先の選定」= **(D) ハイブリッド** + 論点 7「検出ヘルパー呼び出し主体」= **(b) skill / コマンド内 `python3` 直接呼び出し方式** を採用する。

### 経路別の挙動（採用案 D）

- `/fix` (skill `codex exec`): **(A) Claude サブエージェント `codex-fallback-reviewer` に委譲**
- `/task` (`mcp__codex__review`): **(A) 縮退 — 同じく `codex-fallback-reviewer` に委譲（多ターン上限 2 往復）**
- `/feature` (`mcp__codex__implement`): **(C) 停止 — ユーザーに 3 択（自分で書く / Codex を入れる / `/task` に降格）を提示して停止**

### 副次的決定

1. **検出方式**: ハイブリッド（セッション初回のみ `codex --version` を 2 秒タイムアウトで実行、結果をモジュール内キャッシュ）
2. **設定方式**: 環境変数 `CODEX_HARNESS_FALLBACK` 一本化、デフォルト `auto`、許容値は `auto` / `off` / `claude-subagent`。設定ファイル化は将来 ADR で検討
3. **可観測性 / フォールバック発動メッセージ書式**:
   - 書式: `[harness-core] FALLBACK MODE: Codex unavailable (<reason>). Strategy: <strategy>. Quality may degrade.`
   - **生成は `core/codex_detect.py` の `format_fallback_marker(reason: str, strategy: str) -> str` ヘルパーに一元化**。
   - skill / commands 側はこのヘルパーの戻り値を `stderr` または出力先頭に出すだけにする（書式の散在を防ぐ）
4. **検出ヘルパー呼び出し主体**: skill / コマンド内 `python3 -c "from core.codex_detect import ..."` 直接呼び出し方式。`core/hooks.py` および `hooks/hooks.json` への変更は **発生しない**
5. **triage / critic の維持**: フォールバック経路でも 3 分類 / 4 視点モード / critic 自己批評は退化なしで適用
6. **ガードレール**: 既存ルール R01-R11 / POST-01-02 はフォールバック実装にも従来通り適用される

## 根拠

### 検討した選択肢（フォールバック先 = 論点 2）

#### 選択肢 A: Claude Code サブエージェント委譲
- メリット:
  - 同一プロセス内で完結、再帰呼び出しなし
  - 既存の `architect` / `critic` / `triage` パターンと同形で実装可能
  - ガードレール（`hooks/hooks.json` の matcher）が自然にカバーされる
  - subagent の YAML frontmatter 定義のみで成立し、新規 Python コードはほぼ不要
- デメリット:
  - 「Claude が Claude をレビュー / 実装」になり、独立性が低下
  - 4 視点モードの独立性が形式的になる（同一モデル内の視点切替）
  - 実装委譲フォールバック（`/feature` Phase 3）は Codex 比で品質劣化リスクが大きい
- **採用判定**: `/fix` および `/task` のレビュー系経路で採用（採用案 D の構成要素）

#### 選択肢 B: `claude` CLI 別プロセス起動
- メリット:
  - プロセス分離で形式上の独立性は保たれる
  - 出力ファイル経由の連携が `codex exec` と類似で違和感が少ない
- デメリット:
  - **再帰呼び出しの危険**（CC が CC を呼ぶ無限ループ）
  - 認証コンテキストの引き継ぎが煩雑
  - 子プロセス側でガードレールが二重に動く / 動かないの挙動が不透明
  - 深さ制限（環境変数 `CODEX_HARNESS_DEPTH` 等）の実装が必須
  - 実プロセスを起こす分、検出オーバーヘッドが大きい
- **採用判定**: 不採用（採用案 D ではいずれの経路でも使用しない）

#### 選択肢 C: 明示エラーで停止
- メリット:
  - 実装が最小（検出 + エラーメッセージのみ）
  - 品質退化なし（実行されないので退化しようがない）
  - ユーザー教育として適切（Codex を入れる動機になる）
- デメリット:
  - 初回ユーザーがプラグイン体験を完了できず離脱
  - 「まず触ってみる」段階のユーザーを失う
  - フォールバックが本当に必要な CI 等のシナリオで詰む
- **採用判定**: `/feature` の実装委譲経路で採用（採用案 D の構成要素）。実装委譲は品質依存が大きすぎるため停止に倒す

#### 選択肢 D: ハイブリッド
- メリット:
  - 経路ごとに最適化（軽レビューは A、実装委譲は C）
  - 品質と体験のバランスが取りやすい
  - 段階的にフォールバック先を強化できる
- デメリット:
  - 設計が複雑、ユーザーが挙動を予測しにくい
  - ドキュメント負荷が大きい（経路ごとの挙動説明）
  - critic / triage の運用も経路依存になる
- **採用判定**: **採用**

### 検討した選択肢（検出ヘルパーの呼び出し主体 = 論点 7）

#### 選択肢 (a): PreToolUse フック方式
- 概要: `core/hooks.py` で `Bash(codex ...)` や `mcp__codex__*` 検知時に自動検出 → ブロック / 警告
- メリット:
  - ガードレール統一・自動化、呼び出し漏れが構造的に防げる
  - 既存 R01-R11 / POST-01-02 と同じ機構に乗る
  - フォールバック発動の可観測性が hook trace に自然に乗る
- デメリット:
  - matcher 設計が必要（`Bash(rg codex)` 等の誤爆回避）
  - R01-R11 との干渉検証が追加で発生
  - hook 側の例外時挙動（"Fail open"）の保守責任が増える
- **採用判定**: 不採用。本 feature では既存 hook への副作用回避を優先

#### 選択肢 (b): skill / コマンド内 `python3` 直接呼び出し方式
- 概要: Markdown 手順に `python3 -c "from core.codex_detect import should_fallback; ..."` を直書き、skill / コマンド側が検出を駆動
- メリット:
  - 既存 hook を触らないので副作用最小
  - 呼び出しタイミングが Markdown で明示でき可読性が高い
  - skill / コマンドごとに微調整しやすい
- デメリット:
  - 呼び出しタイミングが LLM 任せで漏れリスクあり
  - 新規コマンド追加時に毎回手順に挿入が必要（仕様の散在）
  - メトリクス回収のため別途 trace 追記が必要
- **採用判定**: **採用**。AGENTS.md / README に統一スニペットを掲載することで散在リスクを緩和

#### 選択肢 (c): サブエージェント / LLM が手順書ベースで呼ぶ
- 概要: 検出ヘルパーは CLI（`python3 -m core.codex_detect`）として用意し、サブエージェントが必要時に呼ぶ
- メリット:
  - 柔軟（呼ぶタイミング・粒度をエージェントが判断）
  - コマンド側の手順肥大化を防げる
  - ヘルパーの責務が「CLI ツール」一点に絞られる
- デメリット:
  - 実行保証が弱い（エージェントが忘れる可能性）
  - 検出のメトリクス回収が困難
  - 「いつ呼ぶか」のガイドラインを別文書で管理する必要
- **採用判定**: 不採用。実行保証の弱さと、CLI エントリポイント実装が増える点が嫌気された

## 影響

### ポジティブ
- Codex 未導入環境でもプラグイン体験が破綻しない（採用案 D により `/fix` `/task` は救済、`/feature` は明確に停止して案内）
- フォールバック発動が可観測になり、品質劣化のリスクをユーザーが認識できる
- 検出ヘルパー（`core/codex_detect.py`）が将来「他 CLI ツールへのフォールバック」抽象化の足場になる
- 採用案 D + 論点 7=(b) により、`core/hooks.py` および `hooks/hooks.json` への変更が **発生しない**（既存ガードレールへの副作用ゼロ）
- フォールバックメッセージ書式が `format_fallback_marker()` に一元化され、書式の散在による不整合が構造的に防げる

### ネガティブ
- フォールバック実装の品質次第で、ユーザーが「Codex 無しでも動く」と誤解し、品質劣化に気づきにくい
- 経路ごとの挙動が増えることでドキュメント負荷が増大
- 論点 7=(b) により、新規コマンド / skill 追加時に検出スニペットの挿入忘れリスクが残る（AGENTS.md / README にコピペ可能な形で掲載することで緩和）

### 波及範囲

- コード（新規ファイル）:
  - `core/codex_detect.py` — 公開 API: `detect_codex()` / `should_fallback()` / `read_setting()` / `format_fallback_marker()`
  - `core/test_codex_detect.py` — 単体テスト 16 件
- ドキュメント（編集）:
  - `skills/codex-review/SKILL.md`
  - `commands/{task,feature}.md`
  - `AGENTS.md`
  - `README.md`
- サブエージェント（新規）:
  - `agents/codex-fallback-reviewer.md`（reviewer のみ。implementer は採用案 D で `/feature` を停止に倒すため作成しない）
- 運用: 環境変数 `CODEX_HARNESS_FALLBACK` の設定手順を README / AGENTS.md に追記

## コンプライアンス

この決定に従っていることをどう確認するか：

- **lint ルール**: 静的検査として、`core/codex_detect.py` が HTTP クライアントを import しないことを CI または手動 grep で確認（NFR セキュリティ要件）
- **コードレビューのチェック項目**:
  - 新規に Codex 呼び出しを追加する場合、必ず `core/codex_detect.py` 経由でフォールバック判定を行う
  - フォールバック発動時のマーカー出力が省略されていない（必ず `format_fallback_marker()` の戻り値を使う、独自書式禁止）
  - triage / critic への入力にフォールバック発動の事実が含まれている
- **AGENTS.md への反映**:
  - 「Codex 固有の指示」セクション付近に「Codex 不在時のフォールバック」節を新設し、本 ADR への相互リンクを張る
  - フォールバック設定の環境変数を明記
  - 検出スニペット（`python3 -c "from core.codex_detect import ..."`) をコピペ可能な形で掲載

## 再検討トリガー

以下の条件が成立した場合は本 ADR を再検討（必要なら新 ADR で superseded）：

- フォールバック品質が Codex 比で著しく劣ることが利用者ログから確認された
- Codex 以外の代替 CLI ツール（Aider, Cursor 等）への汎用フォールバック需要が顕在化した
- `claude` CLI に「再帰呼び出し公式サポート」のような機能が追加され、選択肢 B のリスクが解消された
- フォールバック発動率が極めて低く（例: 観測 100 セッションで 0 件）、本機能の維持コストが利益を上回ると判断された
- ガードレール（triage / critic）の出力品質がフォールバック経路で明確に退化していると critic レビューで繰り返し指摘された
- 環境変数のみの設定方式が運用上不便と判明し、設定ファイル化要望が複数挙がる場合（その時点で別 ADR を起票）
