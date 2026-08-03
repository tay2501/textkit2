# リファクタリング計画 — press (textkit2) 2026-08-04

**対象**: `main` commit `56aa951`（`strip-newlines` マージ以降）
**方針**: 前回計画 [refactoring-plan-2026-07-26.md](refactoring-plan-2026-07-26.md) の
R1〜R5 実施後に**残った同一事実の重複**だけを、最新の公式情報で前提を裏取りしたうえで潰す。
挙動はバイト単位で保存する。速度未測定の変更・スコープ外と判定済みの項目
（`clipboard.py` 分割、pystray 移行、`from __future__` 除去等）は再提案しない。

**ベースライン（変更前）**: `ruff 0.16.0 format --check` 91 files formatted /
`ruff check` All checks passed / `mypy --strict`（win32 + `--platform linux`）
ともに 49 files 問題なし / `pytest` **873 passed, 120 skipped**（Ubuntu レーン;
120 は `windows_only`）。

> **実施状況（2026-08-04）**: **R1・R2 を実施済み ✅**
>
> - **検証**: `ruff 0.16.1` format/check green / `mypy --strict`（win32 +
>   `--platform linux`）ともに 49 files 問題なし / **873 passed, 120 skipped**（不変）/
>   R1 対象 2 モジュールの出力が変更前と**バイト一致**（下記スクリプトで実証）。
> - **計画からの逸脱なし**。R1 は前回 R3 の**統合漏れ 2 件の回収**であり、新規の設計判断を含まない。

---

## 0. 最新技術の調査結果（2026-08-04 時点）

コードに触れる前に、本プロジェクトの前提（Python 3.13〜3.15、argparse 継続、
import budget 最優先、明示 `select` を持つ ruff 設定）が今も妥当かを公式情報で確認した。
前回調査（2026-07-26）から 9 日しか経っておらず、**前提を覆す変化は無い**。

| 調査対象 | 最新状況（2026-08-04 時点） | 本プロジェクトへの結論 |
|---|---|---|
| **ruff** | **0.16.1**（2026-07-30）。0.16.0 の 1 週間後のバグ修正リリース。`flake8-return`（RET）の *finally ブロックで読まれる変数* に対する false positive 修正、`flake8-comprehensions` のキーワード正規化修正、LSP の TOML lint 対応ほか | 本プロジェクトは **RET を select 済み**。当該 false positive 修正は直接該当するため、floor を **0.16.1** へ更新（§R2）。新規 lint 違反は 0 で挙動不変 |
| **mypy** | **2.3.0**（現行）。2.x で mypyc により 3〜5x 高速化、PEP 750 t-string 対応、`--python-version 3.9` 廃止 | 既に 2.3.0 floor。**変更不要** |
| **charset-normalizer** | **3.4.9**（2026-07-07）。本プロジェクト pin は `>=3.4.7` | 範囲内で自動追随。**明示更新は不要**（`fix-encoding` の遅延ロード依存であり floor を上げる利益が無い） |
| **jaconv** | **0.5.0**（2026-02-08、現行）。pin `>=0.5.0` | **変更不要** |
| **tomllib writer / pystray / PEP 649** | 前回調査から変化なし（tomllib は 3.15 でも writer 未実装、pystray 0.19.5 inactive、`from __future__ import annotations` は 3.14 で非推奨扱いだが 3.13 レーン維持のため除去不可） | いずれも**現状維持**。前回結論を踏襲 |

> **重要**: ruff 0.16.1 は**バグ修正のみ**で新デフォルト規則の追加は無い。0.16.0 で対処済みの
> Markdown 整形（`[tool.ruff.format] exclude = ["*.md"]`）はそのまま有効。

---

## 1. R1【最優先】行末正規化リテラルの統合漏れ 2 件

### 事実

前回 R3 は「`text.replace("\r\n", "\n").replace("\r", "\n")` という同一の式が **3 箇所**にある」
と数え、`lines.py` / `timestamp.py` を正典 `lineending.to_lf` へ寄せた。
しかし今回コードベース全体を `grep` し直したところ、**当時この式は実際には 5 箇所**にあり、
R3 は `lines` / `timestamp` の 2 つだけを回収し、残り 2 つを取り残していたことが判明した:

```
$ grep -rn 'replace("\r\n", "\n")' press/
press/transforms/lineending.py:20   ← 正典 (_normalize_to_lf)
press/transforms/sql.py:23          ← 統合漏れ ①
press/transforms/whitespace.py:16   ← 統合漏れ ②
```

| 場所 | 変更前 | 備考 |
|------|--------|------|
| `transforms/sql.py:23` | `text.replace("\r\n","\n").replace("\r","\n").split("\n")` | `to_sql_in` の行分割前処理 |
| `transforms/whitespace.py:16` | `text.replace("\r\n","\n").replace("\r","\n")` | `normalize_whitespace` の前処理 |

`lineending.py` の docstring 自身が「`lines.py`, `timestamp.py` and `keystrokes.py` all
normalise through its `to_lf`」と**コンシューマを列挙**しているが、`sql` と `whitespace`
はその一覧にも実コードにも入っていなかった。**正典の存在を宣言しておきながら、
2 つのモジュールがその宣言を裏切って規則を再実装している**状態だった。

### なぜ問題か

前回 R3 の「なぜ問題か」と同一である。行末正規化は「どの文字を行区切りと見なすか」という
**仕様**であり、U+2028 / U+0085 を将来扱うと決めたとき、`lineending` だけ直して
`sql-in` と `normalize` が取り残される。R3 がまさにその重複を潰したのに、
同じ式の別コピーが 2 つ生き残っていたのでは片手落ちである。

### 実施内容

両モジュールに `from press.transforms.lineending import to_lf` を追加し、インライン式を
`to_lf(text)` 呼び出しへ置換した（`lines.py` / `timestamp.py` と同じ top-level import 形式。
どちらも `transforms` パッケージ内なので `_LAZY` 遅延ロードの粒度は変わらない）。
`lineending.py` の docstring と `docs/dev/architecture.md` のコンシューマ一覧に
`sql.py` / `whitespace.py` を追記した。

**効果**: 正典 `to_lf` のコンシューマが 3 → 5 に増え、行末仕様の複製が**ゼロ**になった。
R3 が改善した `.replace()` チェーン（regex より 6.5〜7.5x 速い実装）を両モジュールも共有する。
**リスク**: 極低。純関数であり Ubuntu CI レーンで完全に検証できる。

### 実施メモ — バイト一致を実測で担保

`to_lf(x)` が旧インライン式と完全に等価であることを、隣接ケース（`\r\r\n`, `\n\r`,
`\r\n\r\n`, 末尾改行）を含む 13 入力で確認（`IDENTICAL`）。さらに `to_sql_in` /
`normalize_whitespace` の**下流出力**を変更前後で比較し、CRLF / 単独 CR / 全角空間混じりの
代表入力すべてで**バイト一致**することを実証した:

```python
from press.transforms.lineending import to_lf
inline = lambda t: t.replace("\r\n", "\n").replace("\r", "\n")
assert all(to_lf(c) == inline(c) for c in [
    "", "a\r\nb", "a\rb", "a\r\r\nb", "a\n\rb", "\r\n\r\n", "trailing\r\n", "研究\r\n開発\r",
])
# to_sql_in("a\r\nb\r\na")      == "'a','b'"       （変更前後で一致）
# normalize_whitespace("a  b\r\n  c \r d") == "a b\nc\nd"  （同上）
```

`test_sql.py` / `test_whitespace.py` は既に CRLF ケースを含んでおり、回帰網として機能する
（**873 passed, 120 skipped** で不変）。

---

## 2. R2 ツール floor 更新（ruff 0.16.0 → 0.16.1）

### 事実

ruff **0.16.1**（2026-07-30）は 0.16.0 の 1 週間後のバグ修正リリース。本プロジェクトに関係する
のは **RET（flake8-return）の finally ブロック false positive 修正**である
（`select` に `RET` を含むため）。新規デフォルト規則の追加は無く、Markdown 整形挙動も 0.16.0 と同じ。

### 実施内容

`pyproject.toml` の `ruff>=0.16.0` を `ruff>=0.16.1` に更新し `uv lock`
（`Updated ruff v0.16.0 -> v0.16.1`、CI と同じ lock を共有）。`ruff check` は
変更後も **All checks passed**（false positive 修正により違反が増えることはあっても消える方向のみ）。

**リスク**: 低。lock ファイル共有によりローカルと CI の結果は一致する。

---

## 3. 不採用（今回スコープ外）

| 候補 | 不採用理由 |
|------|----------|
| `case.py` の CRLF 非正規化 | `to_title` / `to_capitalize` は `text.split("\n")`（正規化なし）で、CRLF 入力時に行末 `\r` が残りうる。ただしこれは**式の複製ではなく挙動の選択**（入力の行末を保存する側）であり、`to_lf` へ寄せると出力が変わる。R1 は「同一式の重複解消」のみを目的とし、挙動変更は含めない（前回計画 §6 の `_map_lines` 非統合判断と同じ理由） |
| `charset-normalizer` の floor 引き上げ | 3.4.9 が出ているが `>=3.4.7` の範囲内で自動追随する。`fix-encoding` の遅延ロード依存であり floor を上げる利益が無い。依存追加/更新は EDR 環境の import コストに直結するため、必要が生じるまで動かさない |
| ruff 新規規則の追加 | 0.16.1 はバグ修正のみで新デフォルト規則が無い。前回 R4 で `DTZ`/`RSE`/`SLOT`/`ISC` を実測 0 違反で追加済み。今回追加する候補は無い |

---

## 4. 実施順序と検証

| 段階 | 内容 | リスク |
|------|------|-------|
| R1 | `sql.py` / `whitespace.py` を `to_lf` へ寄せ、docstring/architecture を追記 | 極低 |
| R2 | ruff floor を 0.16.1 へ + `uv lock` | 低 |

低リスクから実施し、各段階で `ruff format --check` / `ruff check` /
`mypy`（win32 + `--platform linux`）/ `pytest` を通した。R1 の後に下流出力の
**バイト一致**を専用スクリプトで検証した（§R1 実施メモ）。

---

## 参照

- 前回計画: [refactoring-plan-2026-07-26.md](refactoring-plan-2026-07-26.md)（R3 が本計画 R1 の前段）/
  [refactoring-review-2026-07-21.md](refactoring-review-2026-07-21.md)
- 公式ソース:
  [Ruff Releases](https://github.com/astral-sh/ruff/releases)（0.16.1, 2026-07-30）/
  [Mypy Changelog](https://mypy.readthedocs.io/en/stable/changelog.html) /
  [charset-normalizer on PyPI](https://pypi.org/project/charset-normalizer/) /
  [jaconv on PyPI](https://pypi.org/project/jaconv/)
</content>
