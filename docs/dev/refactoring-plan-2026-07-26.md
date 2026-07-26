# リファクタリング計画 — press (textkit2) 2026-07-26

**対象**: `feat/type-keystroke-paste` ブランチ commit `7f8a404`
（`type` コマンド / typed sequence / undo を追加した一連の変更以降）
**方針**: 最新の公式情報で前提を裏取りしたうえで、**同じ事実が複数箇所に書かれている**
箇所だけを潰す。挙動は保存する。
**前提**: [refactoring-review-2026-07-21.md](refactoring-review-2026-07-21.md) の R1〜R3 は
実施済み。同レビューが「負債ではない」と判定した項目、および過去に不採用と決定した項目は
再提案しない。

**ベースライン（変更前）**: `ruff format --check` 91 files formatted /
`ruff check` All checks passed / `mypy --strict` 49 files 問題なし /
`pytest` **963 passed, 2 skipped**。

> **実施状況（2026-07-26 更新）**: **R1〜R5 をすべて実施済み ✅**
>
> - **検証**: ruff 0.16 format/check green / `mypy --strict` (win32 + `--platform linux`)
>   ともに 49 files 問題なし / **969 passed, 2 skipped**（+6 は新規テスト）/
>   カバレッジ 85.70%（ゲート 74%、`config.py` 99%・変更した transforms は 100%）。
> - **計画からの逸脱が 3 点**あり、いずれも実装中の実測で判明した事実に基づく。
>   下記各節に *実施メモ* として記録した:
>   1. **R3 の統合方向が逆になった** — 正典側 (`lineending`) の regex 実装が
>      `.replace()` チェーンより **6.5〜7.5 倍遅い**ことを実測。速い実装を正典に昇格させた。
>   2. **R1 で既存バグを 1 件修正** — `_config_to_toml` に TOML エスケープが無く、
>      `quote_char = '"'` や Windows パスで**読み戻せないファイル**を書いていた。
>   3. **R4 で ruff 0.16 の新デフォルト挙動に対処** — Markdown 内の Python コードブロックが
>      整形対象になったため、`docs/dev/code-style.md` の意図的な「Bad」例を守るべく
>      `[tool.ruff.format] exclude = ["*.md"]` を追加した。

---

## 0. 最新技術の調査結果

コードに手を入れる前に、本プロジェクトの前提（Python 3.13〜3.15、argparse 継続、
import budget 最優先、pystray/pynput 依存）が 2026-07 時点でも妥当かを公式情報で確認した。

| 調査対象 | 最新状況（2026-07-26 時点） | 本プロジェクトへの結論 |
|---|---|---|
| **ruff** | **0.16.0**（2026-07-23）。デフォルト規則が 59 → 413 に大幅拡大 | 本プロジェクトは明示 `select` を持つため**デフォルト拡大の影響を受けない**。ただし astral 自身が「明示 select のユーザーも新規則を見直せ」と案内しており、後述 §R4 で棚卸しする |
| **mypy** | **2.3.0**。2.0（2026-05-06）で `--local-partial-types` / `--strict-bytes` がデフォルト化、`-nN` 並列型検査を導入 | 現在 2.1.0。CLAUDE.md が既に `--num-workers 4` を採用済み。floor を 2.3 に更新して追随する |
| **PEP 649 / 749**（遅延アノテーション） | 3.14 でデフォルト化。`from __future__ import annotations` は「非推奨扱いだが動作は不変」、CPython は **3.13 EOL（2029-10）まで維持を確約** | **現状維持**。`requires-python = ">=3.13"` が 3.13 を含む限り、`TYPE_CHECKING` ブロックの前方参照に future import は必要。ruff の除去提案（issue #20739）も `target-version >= 3.14` 限定であり、本プロジェクトには適用されない |
| **tomllib の書き込み対応** | 3.15 でも**未実装**。公式ドキュメントは tomli-w / tomlkit を案内 | `config._config_to_toml` の自作維持が妥当。依存追加は import コスト（= EDR ファイルオープン）に直結するため不採用 |
| **pystray / pynput** | pystray 0.19.5 のまま inactive、pynput 1.8.2（2026-05-12） | [pystray-exit-strategy-2026-07-15.md](pystray-exit-strategy-2026-07-15.md) の方針を継続。今回のスコープ外 |

> **重要**: 上の 3 行目は「新しい書き方があるから使う」を**否定**した結論である。
> PEP 649 は魅力的だが、`from __future__ import annotations` を外せるのは
> `requires-python` の下限が 3.14 に上がった後であり、それまで外すと 3.13 レーンの
> CI が `TYPE_CHECKING` 由来の `NameError` で落ちる。

---

## 1. R1【最優先】`config.py` — セクション定義の三重化

### 事実

1 つの設定セクションを追加すると、**同じセクション名を 5 箇所**に書く必要がある。
直近の `[type]` セクション追加（commit `7f8a404`）が実際にそうなった:

| # | 場所 | 書く内容 |
|---|------|---------|
| 1 | `TypeConfig` dataclass | フィールド定義 |
| 2 | `_parse_type()` | TOML dict → dataclass |
| 3 | `PressConfig.type` フィールド | 保持先 |
| 4 | `load_config()` L254 | `_parse_type(raw.get("type", {}))` の 1 行 |
| 5 | `_config_to_toml()` L373-377 | `[type]` ヘッダと 4 行の手書き `f"..."` |
| 6 | `config_reset()` の `match` L427-428 | `case "type": replace(existing, type=TypeConfig())` |

`_config_to_toml` は 40 行すべてが「dataclass のフィールドを 1 つずつ f-string で
書き下す」だけであり、`config_reset` の `match` 9 分岐は
`replace(existing, <名前>=<デフォルトクラス>())` の機械的な繰り返しである。
**セクション名・dataclass・パーサの対応表は 1 つしかないのに、その対応が 3 つの
制御構造に分散している。**

### なぜ問題か

- 追加漏れが静的解析で検出できない。`_config_to_toml` に書き忘れると
  `press config reset` が黙ってそのセクションを消す（既定値に戻すのではなく、
  ファイルから消える）。テストは roundtrip しか見ていないので、
  **書き忘れたセクションは roundtrip でも既定値に一致してしまい素通りする**。
- これは本プロジェクト自身が `SIMPLE_COMMANDS` / `SPECIAL_COMMANDS` で確立した
  「1 エントリ追加で全経路対応」というレジストリ駆動の設計思想と矛盾している。

### 提案

セクション表を 1 つ置き、`load_config` / `config_reset` / `_config_to_toml` の
3 経路をそこから導出する。

```python
@dataclass(frozen=True, slots=True)
class _Section:
    key: str                                  # TOML テーブル名 = PressConfig のフィールド名
    parse: Callable[[dict[str, Any]], Any]    # 既存の _parse_* をそのまま使う
    default: Callable[[], Any]                # 既定値ファクトリ

_SECTIONS: tuple[_Section, ...] = (
    _Section("hotkeys", _parse_hotkeys, HotkeysConfig),
    ...
)
```

- `load_config` → `{s.key: s.parse(raw.get(s.key, {})) for s in _SECTIONS}` を
  `PressConfig(**...)` に渡す。
- `config_reset` → `replace(existing, **{key: section.default()})`。`match` 9 分岐が消える。
- `_config_to_toml` → dataclass の `fields()` を走査して型ごとに TOML リテラル化する
  汎用シリアライザ。ネストテーブルを持つ `hotkeys` と `pipelines` のみ専用ハンドラ。

**維持する点（過去の不採用判断との整合）**: 2026-05 の調査で
「`_parse_*` の DRY 化」は**カスタムロジックが各関数に必要**という理由で不採用とした。
本提案は `_parse_*` の**中身には一切触れない** — 統合するのは *dispatch* だけである。
`_parse_type` のフォールバック、`_parse_ui` の allow-list、`_parse_hotkeys` の
デフォルトマージはそのまま残る。

**効果**: セクション追加が 6 箇所 → **2 箇所**（dataclass + 表に 1 行）。
**リスク**: 低。TOML 出力のバイト一致を検証ゲートに置く。
**検証**: 変更前後で `_config_to_toml(PressConfig())` と
`_config_to_toml(<全セクション非デフォルト>)` の出力が**バイト一致**すること。

### 実施メモ 1 — バイト一致検証で既存バグを発見

上記の検証を実行したところ、**既定値の出力は完全にバイト一致**した一方、
非デフォルト構成で 1 行だけ差分が出た:

```diff
 [sql_in]
-quote_char = """
+quote_char = "\""
```

旧実装は文字列値を `f'"{value}"'` でそのまま埋め込んでおり、TOML のエスケープを
一切行っていなかった。`quote_char = '"'`（`press sql-in --quote-char '"'` に対応する
正当な設定）を書き出すと `"""` となり、これは TOML では複数行文字列の開始と
解釈されるため、**書いた本人が読み戻せないファイル**になっていた:

```
tomllib.TOMLDecodeError: Unterminated string (at end of document)
```

同じ問題は `[dictionary] files` に Windows パス（`C:\Users\...`）を書いた場合にも起きる
（`\U` などが不正なエスケープ扱いになる）。`config reset --key <section>` は
**ファイル全体をパース済み config から書き直す**仕様のため、1 セクションの部分リセットで
全セクションを巻き添えに壊しうる経路だった。

新しい汎用シリアライザでは `_toml_string()`（TOML 1.0 basic string 準拠:
`\` `"` および C0 制御文字をエスケープ）を通すよう修正し、
回帰テスト（`TestSectionRegistry.test_serialized_output_is_always_valid_toml` ほか）を追加した。
**上記 1 行を除き、出力は変更前とバイト一致している。**

### 実施メモ 2 — セクション名の重複はもう 1 箇所あった

調査時点では 6 箇所と数えたが、`_cli_config.py:35` の argparse
`choices=[...]` とその直後の help 文にも同じ 8 セクション名が並んでいた（計 7〜8 箇所）。

ただしここを `SECTION_NAMES` から導出することは**採らなかった**:
`_register_config_commands()` は `make_parser()` から**毎回の press 起動時**に呼ばれるため、
`press.config` を import すると `tomllib` と `pathlib`（CLAUDE.md 実測で 20 file opens）が
全コマンドの起動パスに乗る。これは daemon 委譲がわざわざ削っているコストそのものである。

代わりに **`SECTION_NAMES` を公開し、テストで両者を固定**した
（`TestSectionRegistry.test_matches_the_reset_choices_offered_by_the_cli`）。
起動コストを払わずに追加漏れを CI で検出できる。

---

## 2. R2 `CommandDispatcher.dispatch()` — 多分岐が `match` でない

### 事実

`daemon/_dispatch.py:54-70` は特殊コマンドを 4 連続の
`if command == "...": ...; return` で捌いている。
CLAUDE.md の Code Standards は
「**`match` statement** — 多分岐 dispatch には構造的パターンマッチを使う」と
規定しており、同じファイル内の `transform()` L104 は正しく `match` を使っている。
**同一クラス内で規約が守られている箇所と守られていない箇所が同居している。**

### 提案

`match command:` へ書き換え、`case "clear" | "hold" | "undo" | "type"` の各 case を
ハンドラ呼び出し 1 行にする。`case _:` が既存の「transform して書き戻す」経路。
分岐の網羅性が読み手に一目で分かるようになる。

**効果**: 規約準拠。行数はほぼ不変（可読性の改善が目的）。
**リスク**: 極低。`test_daemon.py` が全 4 コマンドの経路を押さえている。

---

## 3. R3 CRLF 正規化リテラルの三重化

### 事実

`text.replace("\r\n", "\n").replace("\r", "\n")` という**同一の式**が 3 箇所にある:

| 場所 | 備考 |
|------|------|
| `transforms/lineending.py:9` `_normalize_to_lf` | **正典**。`to_lf` として公開されている |
| `transforms/lines.py:14` `_normalise` | 再実装 |
| `transforms/timestamp.py:18` `_map_lines` | 再実装 |

`keystrokes.py:98` は正しく `from press.transforms.lineending import to_lf` している。
**同じ規則を知っている場所が 3 つあり、うち 1 つだけが正典を参照している。**

### なぜ問題か

行末正規化は「どの文字を行区切りと見なすか」という**仕様**であり、
仕様が 3 箇所に複製されている。将来 U+2028（LINE SEPARATOR）や単独の
U+0085 を扱うと決めたとき、`lineending` だけ直して `sort`/`dedupe`/`unix-to-date` が
取り残される。

### 提案

`lines.py` と `timestamp.py` を `from press.transforms.lineending import to_lf` に
差し替える。どちらも既に `transforms` パッケージ内であり、`_LAZY` 経由の遅延ロードは
維持される。

**リスク**: 極低。純関数であり Ubuntu CI レーンで完全に検証できる。
`test_lines.py` / `test_timestamp.py` / `test_lineending.py` が回帰網。

### 実施メモ — 統合方向を逆にした（実測に基づく計画変更）

着手時に「正典 = `lineending._normalize_to_lf`（regex 実装）」を前提にしていたが、
**どちらの実装が正しいかを決める前に測るべき**と判断して計測した結果、
正典側のほうが大幅に遅いことが判明した:

```
mixed      (CRLF 400 行) : regex 0.1165s  replace 0.0156s  → regex が 7.48x 遅い
long-lines (200 字 × 400 行): regex 0.5098s  replace 0.0782s  → regex が 6.52x 遅い
（CPython 3.13.7 / 2000 反復）
```

`re.sub(r"\r\n|\r|\n", "\n", text)` は 1 パスで済む代わりに、マッチごとに
正規表現エンジンの記録処理が入る。対して `str.replace` は 2 パスだが完全に C 実装で、
このサイズでは後者が圧勝する。等価性も確認済み（`\r\r\n` や `\n\r` のような
隣接ケースでも両者の出力は一致する）。

したがって**統合方向を反転**し、`_normalize_to_lf` の中身を `.replace()` チェーンに
置き換えたうえで `lines.py` / `timestamp.py` をそこに寄せた。結果として
「重複解消」だけを狙った変更が、`crlf` / `lf` / `cr` を含む**全行指向コマンドの
6.5 倍高速化**を伴った。`re` の import も 1 つ消えている。

この計測は本プロジェクトの「未測定の性能変更は行わない」方針
（[project memory 2026-05](refactoring-review-2026-07-21.md) の `case.py` 1.38x 最適化と同じ手順）
に従ったものであり、逆に**測らずに正典へ寄せていれば 6.5 倍の性能劣化を入れていた**。

---

## 4. R4 lint / 型検査設定の棚卸しとツール更新

### 事実 1: 死んだ `ignore` エントリ

```toml
[tool.ruff.lint]
select = ["E4","E7","E9","F","I","UP","B","PTH","SIM","RET","TC","RUF","LOG","G","PERF","FURB","ARG","PIE","C4"]
ignore = ["TRY003", "ERA001"]
```

`TRY`（tryceratops）も `ERA`（eradicate）も **`select` に入っていない**。
明示 `select` を使う設定では選択されていない規則の `ignore` は完全な no-op であり、
この 2 行は「TRY/ERA を検討して外した」という**誤った履歴を読み手に伝える**だけの
デッドコードである。

### 事実 2: 無料で足せる規則（実測）

候補規則を `press/` 配下で実測した結果:

| 規則 | 内容 | press/ の違反数 |
|------|------|----------------|
| `DTZ` | naive datetime の使用禁止 | **0** |
| `RSE` | `raise X()` の不要な括弧 | **0** |
| `SLOT` | `str`/`tuple` 継承クラスの `__slots__` 欠落 | **0** |
| `ISC` | 暗黙の文字列連結 | **0** |

いずれも現状違反 0 のため、**追加コスト 0 で将来の回帰を止められる**。
とりわけ `DTZ` は `transforms/timestamp.py` の tz-aware 実装
（`datetime.fromtimestamp(value, tz=UTC)`）を将来にわたって固定する価値が高い。

### 事実 3: 追加しない規則と理由

大規模な規則追加は実測のうえで**明確に不採用**とする:

| 規則 | 違反数 | 不採用理由 |
|------|-------|----------|
| `PLC0415` (import-outside-top-level) | 379 | **設計と正面衝突**。関数内 lazy import は本プロジェクトの起動時間戦略そのもの（CLAUDE.md「Lazy imports in `__main__.py`」）|
| `D` (pydocstyle) | 958 | 大半が `test/` の `D102`。公開 API の docstring は既に充実しており費用対効果が低い |
| `TRY003` | 68 | 「例外に長いメッセージを書くな」。本プロジェクトはユーザー向けエラー文言を重視する方針で意図的に違反している |
| `EM101/EM102` | 68 | 同上（例外メッセージの変数化は可読性を下げる）|
| `SLF001` | 102 | ほぼ `test/` からの private アクセス。テストの意図的な設計 |
| `PLR2004` (magic value) | 42 | Win32 定数比較が大半。定数化済みのものを再度定数化する要求になる |

### 提案

1. `ignore = ["TRY003", "ERA001"]` を削除（no-op のため挙動不変）。
2. `select` に `DTZ`, `RSE`, `SLOT`, `ISC` を追加。
3. `ruff>=0.16.0` / `mypy>=2.3.0` に floor を更新し `uv lock`。
   ruff 0.16 で stable 化した `FURB192`（`sorted()[0]` → `min()`）は
   選択済み `FURB` に含まれるため、検出されれば修正する。

**リスク**: 低。CI が同じ lock ファイルを使うためローカルと CI の結果は一致する。

### 実施メモ — ruff 0.16 は Markdown も整形する

ruff 0.16 へ上げた直後、`ruff format --check` の対象が **91 → 121 ファイル**に増え、
3 ファイルが「要整形」と報告された。3 つとも `.md` である:

```
docs/dev/code-style.md
docs/dev/refactoring-plan-2026-07-26.md
docs/dev/refactoring-review-2026-07-21.md
```

公式リリースノートによれば、ruff 0.16 は **Markdown 中の
` ```python ` / `py` / `pyi` / `pycon` フェンスをデフォルトで整形する**ようになった。
Python ソースは 1 ファイルも変わっていない。

これを**受け入れなかった**理由: `docs/dev/code-style.md` は
「Bad な書き方」と「Good な書き方」を並べて対比させる教材であり、
Bad 側は**意図的に整形が崩してある**。実際に diff を見ると、フォーマッタは

```diff
-def normalize_whitespace(text: str) -> str:
-    ...
+def normalize_whitespace(text: str) -> str: ...
```

のように例を書き換えており、文書が示そうとしている差そのものを消してしまう。
公式が案内する 2 つの opt-out（`exclude` に `*.md` を足す / `fmt: off` で囲む）のうち、
散文中に `fmt: off` を撒くより設定 1 行のほうが意図が明確なので前者を採った:

```toml
[tool.ruff.format]
exclude = ["*.md"]
```

`ruff check`（lint）側は Markdown を対象にしないため影響を受けない。

---

## 5. R5 `daemon/_dispatch.py` の関数内 `contextlib` import

`import contextlib` が `dispatch()` / `_notify()` / `_update_icon()` の
**3 つの関数内**に書かれている。`press/_pipe.py` の import budget 規律
（`ctypes`/`threading`/`pathlib` をモジュールトップに置かない）は
**CLI の起動パス**を守るためのもので、`press.daemon._dispatch` は
デーモンプロセス側 — pystray と pynput を読み込んだ後にしか import されない。
`contextlib` を 3 回関数内 import する理由がなく、規律の**カーゴカルト適用**になっている。

モジュールトップの 1 回に集約する。

**リスク**: 極低。`test_pipe.py::TestImportBudget` は `press._pipe` のみを対象としており、
本変更はその対象外（念のため実行して確認する）。

---

## 6. 不採用（今回スコープ外）

| 候補 | 不採用理由 |
|------|----------|
| `clipboard.py`（758 行）の パッケージ分割 | Windows 専用コードで Ubuntu CI では大半が検証不能。過去の「daemon.py / clipboard.py リファクタリング」不採用判断（2026-05）を踏襲。分割の利益より、検証できない変更を入れるリスクが上回る |
| tomli-w / tomlkit の導入 | tomllib に writer が来ていない事実は確認したが、依存追加は import コスト（EDR 環境のファイルオープン）に直結。`_config_to_toml` は R1 で汎用化されるため自作維持で十分 |
| pystray からの移行 | 既存の exit strategy 文書の管轄。今回は変更しない |
| `from __future__ import annotations` の除去 | §0 のとおり `requires-python` 下限が 3.14 に上がるまで**不可** |
| `timestamp._map_lines` と `lines._normalise/_join` の統合 | 空行の扱いが微妙に異なる（`_map_lines` は空行を素通し、`_normalise` は末尾センチネルを除去）。統合は挙動変更になるため、R3 では正規化式のみを共有する |

---

## 7. 実施順序

| 段階 | 内容 | リスク |
|------|------|-------|
| R3 | CRLF 正規化の集約 | 極低 |
| R2 | `dispatch()` を `match` へ | 極低 |
| R5 | `contextlib` import 集約 | 極低 |
| R1 | `config.py` セクション表 | 低 |
| R4 | lint 設定棚卸し + ツール更新 | 低 |

低リスクから順に実施し、各段階で `ruff` / `mypy` / `pytest` を通す。
R1 の後に `_config_to_toml` の**バイト一致**を専用スクリプトで検証する。
最後に `mypy --platform linux` で Ubuntu レーン相当の検証を行う
（CLAUDE.md: mypy は Ubuntu レーンのみで走るため）。

---

## 参照

- 前回レビュー: [refactoring-review-2026-07-21.md](refactoring-review-2026-07-21.md) /
  [adversarial-review-2026-07-15.md](adversarial-review-2026-07-15.md)
- 公式ソース:
  [Ruff v0.16.0](https://astral.sh/blog/ruff-v0.16.0) /
  [Mypy 2.0 Released](https://mypy-lang.blogspot.com/2026/05/mypy-20-relased.html) /
  [PEP 649](https://peps.python.org/pep-0649/) /
  [PEP 749](https://peps.python.org/pep-0749/) /
  [What's New in Python 3.14](https://docs.python.org/3/whatsnew/3.14.html) /
  [tomllib — Parse TOML files](https://docs.python.org/3/library/tomllib.html)
