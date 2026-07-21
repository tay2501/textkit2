# 敵対的リファクタリングレビュー — press (textkit2)

**実施日**: 2026-07-21
**対象**: main ブランチ commit 2901bdd（`612bcea` 以降に追加された chain / pipelines /
9 変換コマンド群を主眼）
**レビュー方針**: [adversarial-review-2026-07-15.md](adversarial-review-2026-07-15.md)
（セキュリティ・EDR 耐性・Win32 正確性が中心）の後、**構造・保守性の観点**で追加監査する。
「動いているから良い」を認めず、将来のメンテナ視点で重複・責務漏れ・仕様乖離を探す。
前回レビューで指摘済みの項目、および計画で**意図的に棚上げ済み**の項目は再提案しない。

> **重要な前置き（誠実性の担保）**: 本レビューが「バグ」ではなく「意図的トレードオフ」と
> 判定した項目を §5 に分離した。`feature-pipelines-2026-07-16.md` の R2 / Non-goals で
> 明文化された設計判断（パラメトリック step のデフォルト実行、chain の非委譲）は
> **仕様どおり**であり、欠陥ではない。§1〜§3 のみが「新規の技術的負債」である。

> **実施状況（2026-07-21 更新）**: 推奨順どおり **R1〜R3 + D をすべて実施済み ✅**。
> - **R1** `commands.py` に `resolve_spec` / `run_command` を新設し、CLI（`__main__`）・
>   `chain`（`resolve_transform`）・daemon（`_dispatch.transform`）の 3 経路・
>   5 dispatch を 1 本へ収斂。パラメトリック引数の優先順位
>   （cli_kwargs > config.daemon_kwargs > 関数デフォルト）を `run_command` に集約。
> - **R2** pipeline の述語・展開・検証を `commands.py`
>   （`is_registry_command` / `expand_pipeline_steps` / `validate_pipelines`）へ集約。
>   nesting メッセージは `_nesting_error` の 1 箇所に。`config.pipeline_errors` /
>   `_cli_chain._expand_steps` / `_dispatch._run_pipeline` は薄いラッパ化。
> - **R3** `bounded_int` / `write_clipboard_or_warn` を `_cli_helpers.py` に抽出し
>   `_positive_int` 二重定義と genpass/uuid のクリップボード warning 重複を解消。
> - **D** `docs/user/config.md` に「同じ pipeline が CLI と hotkey で挙動が変わる」注記を追加。
> - **検証**: `--help` 全サブコマンドでバイト一致 ✅ / エラー文言（`length/seconds/count
>   must be >= N`）保存 ✅ / ruff・mypy(strict) green / **714 passed, 91 skipped** /
>   `_pipe.py` import budget テスト維持（`importlib` は関数内 lazy import のまま）。
> - `import_budget` を崩さないため `commands.py` トップに重い import は追加していない。

---

## 0. 総合評価

| 領域 | 評価 | 一言 |
|------|------|------|
| レジストリ駆動のコマンド追加 | ★★★★★ | 1 エントリで CLI/daemon/pipe/lazy-load 全対応。模範的 |
| 変換関数の純粋性・テスト容易性 | ★★★★★ | `fn(text, **kw) -> str` 規律が全新規モジュールで貫徹 |
| **コマンド解決・実行ロジックの単一化** | ★★☆☆☆ | **同じ「名前→callable→実行」が 3 モジュールに散在**（§1）|
| **パイプライン検証・実行の単一化** | ★★☆☆☆ | **検証が 3 箇所、実行が 2 箇所に重複**。エラー文言もベタ書き重複（§2）|
| CLI ハンドラ内の小重複 | ★★★☆☆ | `_positive_int` 二重定義、`-q/-C` 手書き（§3）|

**結論**: 新機能（chain / pipelines / 9 コマンド）は純関数レイヤは非常に綺麗だが、
**「コマンド名を callable に解決して実行する」中核ロジックが CLI・chain・daemon の
3 経路それぞれに独立実装されており、パラメトリック引数の扱いが経路ごとに微妙に異なる**。
現時点では仕様（§5）で正当化されているが、実装が 3 本ある限り「片方だけ直して片方が
腐る」事故の温床であり、次の機能追加の前に 1 本へ収斂させる価値が最も高い。

---

## 1. 【最優先】コマンド解決・実行ロジックの三重化

### 事実

「レジストリの `SimpleCommand`/`ParametricCommand` を `importlib.import_module` +
`getattr` で callable にして実行する」処理が、**3 モジュール・5 箇所**に独立して存在する:

| # | 場所 | パラメトリック引数の出所 | 委譲 |
|---|------|------------------------|------|
| A | `__main__.py:_register_transform_command._apply` (L89-99) | CLI フラグ（`extras`）| ✅ `try_delegate` |
| B | `commands.py:resolve_transform` (L417-443) | **関数デフォルトのみ** | ❌ |
| C | `daemon/_dispatch.py:CommandDispatcher.transform` (L82-114) | **config 由来 `daemon_kwargs`** or 委譲引数 | ❌（サーバ側）|

`feature-pipelines-2026-07-16.md` §3.1 は `resolve_transform` を
**「Single source of truth reused by `_cli_chain.py`」**と謳うが、実態は
**chain からしか使われていない**。CLI（A）と daemon（C）はそれぞれ独自に
`importlib.import_module(spec.module)` を書き直しており、SSOT の主張は半分しか
実現していない。

```
$ grep -rn "importlib.import_module" press/ | grep -v transforms/__init__
press/commands.py:431      ← B (simple)
press/commands.py:436      ← B (parametric)
press/__main__.py:98       ← A
press/daemon/_dispatch.py:99   ← C (simple)
press/daemon/_dispatch.py:108  ← C (parametric)
```

### なぜ問題か（敵対的視点）

- **引数解決の三様式**が同居する: A=CLIフラグ / B=デフォルト / C=config。新しい
  パラメトリックコマンドを足すたび、3 経路すべてで正しく配線されているかを人手で
  確認する必要がある。レジストリ駆動の「1 エントリで全対応」という美点を、この
  分岐が実行時側で相殺している。
- **エイリアス解決の非対称**: C は `PARAMETRIC_ALIASES.get(...)` を明示的に噛ませるが、
  B は `PARAMETRIC_COMMAND_INDEX`（エイリアス込み index）に直接引く。結果は一致するが
  導出経路が違い、将来 index の作り方を変えると片方だけ壊れる。
- **§5 の仕様乖離（B と C の差）が実装の別物性から生じている**: 同じ名前付き
  パイプラインが `press chain cleanup`（B 経由＝デフォルト）と daemon ホットキー
  （C 経由＝config）で挙動が変わる。現状は仕様（R2）だが、**1 本の実行関数に統合すれば
  「引数の出所」だけをパラメータ化でき、仕様変更も 1 箇所で完結する**。

### 提案

`commands.py` に唯一の実行 API を置き、A/B/C をその薄いラッパにする:

```python
# commands.py  — 唯一の resolve+run。importlib は関数内 lazy import のまま（import budget 不変）
def resolve_spec(command: str) -> SimpleCommand | ParametricCommand | None:
    """名前/エイリアス → レジストリ spec（両 index を一本化して引く）。"""

def run_command(
    command: str,
    text: str,
    *,
    cli_kwargs: dict[str, Any] | None = None,
    config: PressConfig | None = None,
) -> str:
    """spec を解決し、引数を「cli_kwargs > config.daemon_kwargs > 関数デフォルト」の
    優先順で決めて実行する。未知コマンドは ValueError。"""
```

- A（CLI）: `run_command(name, text, cli_kwargs=extras)`（委譲成功時は従来どおり早期 return）
- B（chain）: `resolve_transform` を `partial(run_command, config=None)` で再実装 →
  デフォルト実行という現仕様を維持しつつ実体は共有
- C（daemon）: `run_command(cmd, text, cli_kwargs=kwargs, config=self._config)`

**効果**: dispatch 実装が 5 → 1。引数優先順位が 1 関数に集約。§5 のトレードオフを
将来見直す際、変更点が `run_command` の 1 行になる。
**工数**: 〜1 日（挙動保存リファクタ）。
**リスク**: 低。既存テスト（chain / daemon / pipe 委譲の互換テスト）が回帰網。
**制約遵守**: `importlib` は現行どおり関数内 lazy import に留め、`commands.py` の
モジュールトップに重い import を増やさない（`TestImportBudget` の思想を尊重）。

---

## 2. パイプライン検証・実行の重複とエラー文言のベタ書き重複

### 事実

「pipeline の step が正当か」を判定するロジックが **3 モジュール**にある:

| 場所 | 何を検証 | エラー文言 |
|------|---------|-----------|
| `config.py:pipeline_errors` (L272-298) | 全件（空・shadow・未知・nesting）| 独自 |
| `_cli_chain.py:_expand_steps`+`_is_registry_command` (L24-67) | nesting・登録判定 | **独自（下記重複）** |
| `daemon/_dispatch.py:_run_pipeline` (L128-145) | step が registry か | 独自 |

そして nesting 拒否メッセージが `config.py:294` と `_cli_chain.py:60-63` に
**ほぼ同一文言でベタ書き**されている:

```
config.py:294       "pipeline {name!r}: step {step!r} is a pipeline (nesting is not supported)"
_cli_chain.py:60-63 f"pipeline {step!r}: step {sub_step!r} is a pipeline (nesting is not supported)"
```

「registry コマンドか？」の述語も `config._is_command`（L282）と
`_cli_chain._is_registry_command`（L24）の 2 実装。前者は index メンバシップ直接、
後者はエイリアス解決を噛ませる — **同じ問いに 2 つの答え方**。

### なぜ問題か

- pipeline のルール（step は registry のみ・nesting 禁止・空禁止・shadow 禁止）は
  **1 つの仕様**なのに 3 箇所に散る。ルールを 1 つ足す（例: step 数上限）と
  3 箇所を触ることになる。
- 検証（`config.pipeline_errors` / `config validate`）と実行（`_cli_chain` /
  `_dispatch._run_pipeline`）が別ロジックなので、**「validate は通るのに実行で
  別のエラー」あるいはその逆**が原理的に起こり得る。現状は幸い一致しているが、
  それを保証する仕組みがない。

### 提案

パイプラインの「述語・展開・検証」を 1 モジュール（`commands.py` 末尾か新規
`press/_pipelines.py`）へ集約:

```python
def is_registry_command(step: str) -> bool: ...        # §1 の resolve_spec で一本化
def expand_pipeline(steps, pipelines) -> list[str]: ... # nesting 判定込み・唯一実装
def validate_pipelines(pipelines) -> list[str]: ...     # config.pipeline_errors を移設
```

- `_cli_chain._expand_steps` と `_dispatch._run_pipeline` は `expand_pipeline` を呼ぶだけに。
- nesting メッセージは定数 1 箇所に。
- `config.pipeline_errors` は `validate_pipelines` の薄いラッパ（config import は
  現状どおり lazy 維持）。

**工数**: 〜0.5 日。**リスク**: 低（`test_config` の pipeline 検証テストが回帰網）。
**副次効果**: §1 の `resolve_spec` が入れば `is_registry_command` は自動的に一本化される
（§1→§2 の順で実施すると重複が最小）。

---

## 3. CLI ハンドラ内の小さな重複（低優先・機械的）

- **`_positive_int` の二重定義**: `__main__.py:137`（genpass）と `:217`（uuid）に同一関数。
  `_nonneg_int`（:143）と合わせ、`_cli_helpers.py` に `positive_int`/`nonneg_int` の
  argparse type ヘルパとして移すと 3 箇所 → 1 箇所。
- **`-q`/`-C` の手書き重複**: genpass / uuid / clear は `_add_io_args` を使わず
  `-q --quiet` / `-C --clip-out` を個別に `add_argument` している（入力を読まない
  ジェネレータなので `_add_io_args` 全部は不適という判断は妥当）。ただし「出力専用
  コマンド用の最小デコレータ」（`-C`/`-q` のみ付与）を切り出せば意図が明確になり
  文言のドリフトも防げる。**優先度低**（実害は文言不一致リスクのみ）。
- **clipboard 書き込み失敗の warning ハンドラ**が genpass（L200）と uuid（L254）で
  ほぼ同型。`set_clipboard_text` を包む `_try_clip_out(text, cmd, quiet, *, sensitive)`
  ヘルパに寄せられるが、これは §1 ほどの価値はない。

**工数**: まとめて 0.5 日。**リスク**: ほぼゼロ（純粋な抽出）。

---

## 4. 良い点（変更圧力がかかっても維持すべき）

1. **純関数レイヤの規律**: `lines.py` の `_normalise`/`_join` による「LF 正規化 →
   処理 → trailing 復元」の共通化は綺麗。新規 9 コマンドすべてが `fn(text, **kw)->str`
   を守っており、§1 の統合を可能にしているのはこの規律のおかげ。
2. **pipeline の非再帰を「構造で」保証**: daemon 側が step を registry 限定にすることで
   recursion を型/構造レベルで排除している（実行時ガードに頼らない）設計は正しい。
3. **config の lazy import 規律**: `pipeline_errors` が `press.commands` を関数内 import し、
   委譲 CLI パスの config ロードを軽く保つ配慮。§1/§2 の統合でもこれを崩さないこと。
4. **`CliArg.__post_init__` の import 時 fail-fast**（action と value 系フィールドの
   排他検証）は、レジストリ拡張時のミスを起動時に弾く良い防御。

---

## 5. 「負債ではない」と判定した項目（再提案しない）

敵対的に見ても、以下は `feature-pipelines-2026-07-16.md` で**明文化された意図的判断**であり、
バグでも負債でもない。将来見直す価値はあるが、本レビューの改修対象からは除外する:

| 項目 | 現状 | 根拠（仕様）|
|------|------|-----------|
| chain がパイプ委譲しない（各 step をローカル import）| 意図的 | Non-goals v1: "pipe-server delegation of whole chains"。名前付き pipeline のみ将来委譲余地あり（§1 統合後に低コスト化）|
| chain のパラメトリック step がデフォルト実行（daemon は config）| 意図的 | R2: "Parametric steps run with their function defaults ... the daemon path keeps config-driven kwargs" |
| per-step CLI フラグ非対応 | 意図的 | Non-goals v1 |
| `test/`（単数）ディレクトリ名 | 現状維持 | 前回 §3.3 で「変更コスト＞実害」と結論済み |
| argparse 継続（typer/click 非採用）| 現状維持 | import budget = EDR コスト。前回 §7 |

> **ただし 1 点だけ注意喚起**: 「同じ名前付き pipeline が chain とホットキーで挙動が
> 変わる」（R2 の帰結）は仕様だが**利用者にとって直感に反する**。§1 で実行関数を
> 一本化した上で、`docs/user/config.md` に「pipeline のパラメトリック step は既定値で
> 走る／ホットキー経由のみ config が効く」を明記することを推奨（コード変更ではなく
> ドキュメント改善）。

---

## 6. 実施順序の提案（承認待ち）

| 段階 | 内容 | 対応 § | 工数 | 破壊性 |
|------|------|-------|------|--------|
| **R1** | `commands.py` に `resolve_spec` + `run_command` を新設し A/B/C を寄せる | §1 | 〜1 日 | なし（挙動保存）|
| **R2** | pipeline 検証・展開・述語を 1 箇所へ集約（`is_registry_command` は R1 に依存）| §2 | 〜0.5 日 | なし |
| **R3** | `_positive_int`/`_nonneg_int`/`-C·-q` の抽出 | §3 | 〜0.5 日 | なし |
| **D**  | `docs/user/config.md` に pipeline パラメトリック挙動を明記 | §5 注記 | 〜0.2 日 | なし |

**推奨順序: R1 → R2 → R3 → D**（R2 は R1 の `resolve_spec` を土台にすると重複が最小化される）。
各段階で CLAUDE.md のワークフロー（TDD → pythonic → quality → git-quality）に従い、
`--help` のバイト一致・全 Python バージョンでのテスト green を確認してから push すること。
本ドキュメントは**計画のみ**であり、コード変更はユーザー承認後に着手する。

---

## 参照

- 前回レビュー: [adversarial-review-2026-07-15.md](adversarial-review-2026-07-15.md) /
  [improvement-plan-2026-07-15.md](improvement-plan-2026-07-15.md)
- 対象機能の設計根拠: [feature-pipelines-2026-07-16.md](feature-pipelines-2026-07-16.md) /
  [feature-gap-analysis-2026-07-17.md](feature-gap-analysis-2026-07-17.md)
- 監査したコード（commit 2901bdd）: `press/commands.py` / `press/__main__.py` /
  `press/_cli_chain.py` / `press/config.py` / `press/daemon/_dispatch.py`
</content>
</invoke>
