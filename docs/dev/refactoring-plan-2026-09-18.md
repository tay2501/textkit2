# リファクタリング計画 — press (textkit2) 2026-09-18

**対象**: `build/deps-refresh-2026-08-13` commit `1df2550`
**方針**: 前回計画 [refactoring-plan-2026-08-04.md](refactoring-plan-2026-08-04.md) 実施後に残った
**同一事実の重複**と、**Python 3.15 GA（2026-10-01）で顕在化する非互換**を、公式情報で裏取りしたうえで潰す。
過去にスコープ外と判定済みの項目（`clipboard.py` 分割、pystray 移行、`from __future__` 除去）は再提案しない。

**ベースライン（変更前・実測）**: `ruff 0.16.2 format --check` 97 files formatted /
`ruff check` All checks passed / `mypy --strict`（win32 + `--platform linux`）ともに 50 files 問題なし /
`pytest` **1038 passed, 2 skipped** / coverage **86.05%**（ゲート 74%、Windows レーン）。

> **実施状況（2026-09-18）**: **R1〜R6 をすべて実施済み ✅**
>
> - **検証**: `ruff 0.16.8` format/check green / `mypy 2.3.1 --strict`（win32 + `--platform linux`）
>   ともに 51 files 問題なし / **1043 passed, 2 skipped**（+5 は R1 の新規テスト）/
>   coverage **86.07%**（ゲート 76%）。
> - **計画からの逸脱 1 点**: R3 で既存テスト 2 件（`test_chain.TestDispatcherPipelines`）が
>   旧文言を pin していたため更新した。計画時の grep が `press/` のみを対象にしていた漏れ。

---

## 0. 最新公式情報の調査結果（2026-09-18 時点）

| 調査対象 | 公式の最新状況 | 本プロジェクトへの結論 |
|---|---|---|
| **ruff** | **0.16.8**（2026-09-16）。0.16.3 で `RET504` の finally 変数 false positive 修正、0.16.5 で category selectors 導入（**preview 限定**）、0.16.6 で `DTZ901`/`ISC003`/`B031` 修正、0.16.8 で `SIM117`/`SIM109`/`UP040` 修正 | 修正対象は **RET/DTZ/ISC/B/SIM/UP すべて select 済み**。floor を 0.16.8 へ（**R5**）。0.16.8 で `format --check` 97 files formatted・`check` green を事前実測し、整形差分ゼロを確認 |
| **ruff category selectors** | `select = ["correctness", …]` は **preview 必須**。公式ドキュメントは「`lint.select` を明示的に」「`ALL` は慎重に」「小さく始めて 1 グループずつ追加」を推奨 | 現行の明示 `select` が公式推奨そのもの。**変更不要**（採用は preview 卒業後に再評価） |
| **mypy** | **2.3.1**。2.3 系は mypyc/free-threading 中心で strict 既定の変更なし | floor を 2.3.1 へ（**R5**）。実測で新規エラーなし |
| **Python 3.15** | PEP 790: rc1 = 2026-08-04、rc2 = 2026-09-01、**GA = 2026-10-01** | allow-failure レーンの binding 化は GA 後（**R7**、本計画では未実施） |
| **Python 3.15 / importlib.metadata** | METADATA 欠落時に **`MetadataNotFound`（`FileNotFoundError` 派生。`PackageNotFoundError` の派生では**ない**）** を送出するよう変更 | **現行コードが未捕捉 → 実バグ（R1）** |
| **Python 3.15 / argparse** | `suggest_on_error` の既定が `False`→`True`。パラメータ自体は **3.14 追加** | 3.13 レーンで `TypeError` になるため明示指定は**不採用** |
| **Python 3.15 / PEP 810 lazy imports** | `lazy import json` 構文が追加 | press の起動コスト設計（関数内 import / PEP 562）と正面から一致するが、`requires-python>=3.13` では構文エラー。**採用不可**。floor が 3.15 に上がった時点で再評価 |
| **Python 3.15 / PEP 686** | UTF-8 が既定エンコーディングに | `press` はテキストを開く箇所がなく（`config.py` は `"rb"`、他は `encoding=` 明示）、`main()` も明示的に `reconfigure(encoding="utf-8")` する。**影響なし** |
| **charset-normalizer / pytest / pynput / pystray / uv** | 3.5.1 / 9.1.1 / 1.8.2 / 0.19.5 / 0.12.15 | いずれも現行 pin の範囲内または据え置き。**変更不要** |

---

## 1. R1【最優先・バグ】パッケージバージョン取得の 3.15 非互換と二重実装

### 事実（実測）

`fake-1.0.dist-info`（METADATA なし）を `sys.path` に置き `importlib.metadata.version("fake")` を呼んだ結果:

| Python | 結果 |
|---|---|
| 3.13.14 / 3.14.6 | **`None` を返す** → `press --version` は `press None` と表示（`_version()` の戻り型は `str` 宣言） |
| 3.15.0b3 | **`MetadataNotFound` を送出**（`PackageNotFoundError` では捕捉不可、`FileNotFoundError` 派生）→ `press --version` がトレースバックで異常終了 |

同じ取得が **2 箇所に別実装**で存在していた:

- `press/__main__.py` — `except PackageNotFoundError` のみ（3.15 で未捕捉）
- `press/daemon/_service.py` — `contextlib.suppress(Exception)`（広すぎる except、かつ `None` を status ファイルへ書きうる）

### 実施内容

`press/_version.py` に正典 `press_version() -> str` を新設し、両所から呼ぶ。
`importlib.metadata` は関数内 import のままで **CLI の import budget は不変**（`--version` 時のみ支払う）。
`except (PackageNotFoundError, OSError)` と `or "unknown"` で 2 つの失敗形を 1 箇所に吸収した。

**検証**: `test/unit/test_version.py` に 5 ケース（正常・`PackageNotFoundError`・`None` 返却（3.13/3.14 相当）・
`FileNotFoundError` 送出（3.15 相当）・空文字）を追加。`FileNotFoundError` で書くことで、
`MetadataNotFound` が存在しない 3.13/3.14 レーンでも同じ契約を検証できる。
**リスク**: 低（正常インストール時の出力は不変）。

---

## 2. R2 undo 抑止ポリシーの二重実装を正典化

`_cli_helpers._snapshot_clipboard_for_undo`（CLI・ファイル）と
`_dispatch._remember_for_undo`（daemon・メモリ）が、同じ 3 条件
（`PRESS_NO_UNDO=1` / sensitive マーク付き / マーク判定そのものが失敗）を各自で実装していた。
CLAUDE.md が「クリップボードを上書きする経路は必ずこのどちらかを呼べ」と規定している以上、
**規則の本体は 1 箇所**にあるべきである。

`press/transforms/undo.py` に `snapshot_allowed() -> bool` を追加し、両者をその上に載せ替えた。
分岐順序も含め挙動は不変（`undo_disabled()` → マーク判定 → 記録）。CLAUDE.md の当該 gotcha も更新した。

---

## 3. R3 pipeline「レジストリ限定」エラー文言の統一

同一の設定ミスに 2 つの文言があった:

| 場所 | 変更前 |
|---|---|
| `commands.validate_pipelines` | `pipeline 'x': unknown step 'y'` |
| `daemon/_dispatch._run_pipeline` | `pipeline 'x': step 'y' is not a transform command` |

`press config validate` と daemon 実行時で説明が変わる状態だったため、
`commands.unknown_step_error(name, step)` を新設して両者を寄せた
（`_cli_chain` の文言は `[pipelines]` 名も候補に含む別の事実を述べているので維持）。
旧文言を pin していた `test_chain.TestDispatcherPipelines` の 2 件を更新した。

---

## 4. R4 例外の具体化とエラー出力の集約（**唯一、挙動変更を含む**）

`__main__.py` の 3 ハンドラのうち `_undo` だけが `except (OSError, RuntimeError)` で、
`_cl` / `_hold` は `except Exception` だった。呼び先を確認した結果、
`clipboard.py` は `OSError`/`RuntimeError` のみ、`_dpapi.py` も `RuntimeError`/`OSError` のみを送出し、
広く捕まえる根拠はない（CLAUDE.md rule 7）。両者を `_undo` と同じ具体例外へ揃えた。

あわせて `press <cmd>: error: {exc}` + `return 1` の定型を
`_cli_helpers.report_error(cmd, exc, *, quiet=False)` に集約し、
`clear` / `hold` / `undo` / `chain` / `config reset` の 5 箇所が同じ実装を共有する。

**挙動変更**: 想定外の例外型が出た場合、1 行のメッセージではなくトレースバックになる（終了コードは 1 で不変）。
この経路を pin しているテストは無く、CI も green。`config reset` の `except Exception` は
呼び先（`config_reset`）の例外集合の裏取りが別途必要なため**今回は文言集約のみ**とし、範囲は広げていない。

---

## 5. R5 ツール floor 更新 / R6 カバレッジゲート引き上げ

| # | 内容 | 根拠 |
|---|---|---|
| R5 | `ruff>=0.16.2` → `>=0.16.8`、`mypy>=2.3.0` → `>=2.3.1` + `uv lock` | select 済みルールの false positive / panic 修正が 5 件。0.16.8 で整形差分ゼロ・`check` green を事前実測 |
| R6 | `fail_under = 74` → `76` | `pyproject.toml` のコメント自身が「+2% ずつ ratchet せよ」と宣言。Windows は 81.65% → **86.05%**、`windows_only` を 116 件 deselect したローカル近似で **83.37%** と、binding の Ubuntu レーンに十分な余裕がある |

---

## 6. 不採用（根拠付き）

| 候補 | 不採用理由 |
|---|---|
| `clipboard.py`（758 行）の分割 | 2026-08-04 計画で「再提案しない」と決定済み |
| PEP 810 `lazy import` の採用 | 3.15 専用構文。`requires-python>=3.13` では構文エラーになる。floor が 3.15 に上がった時点で再評価 |
| `argparse(suggest_on_error=...)` の明示指定 | 3.14 追加のため 3.13 レーンで `TypeError`。3.15 で既定が `True` になる差は受け入れる |
| ruff category selectors / `ALL` への移行 | 前者は preview 限定、後者は公式が「アップグレードのたびに新規則が暗黙に有効化される」と警告 |
| `clear`/`undo`/`hold` を `_cli_clipboard.py` へ分離 | 文書化された CLI レイアウト規則には合うが、`__main__.py` は coverage omit 対象。移すと分母に約 70 文が加わりゲート割れリスク。直接テストの追加とセットでなければ不可 |
| `__main__._handler` のトレース計測の重複解消 | 可読性のみの利得に対し、CLI 最ホットパスに関数呼び出しを追加する。費用対効果が合わない |
| charset-normalizer の floor 引き上げ | 3.5.1 は現行 `>=3.5.0` の範囲内で自動追随する |

---

## 7. 積み残し（日付依存）

- **R7: Python 3.15 レーンの allow-failure 解除** — GA は **2026-10-01**。GA 後に `ci.yml` の
  `continue-on-error` を外し、`requires-python` の上限コメントを更新する。

---

## 参照

- 前回計画: [refactoring-plan-2026-08-04.md](refactoring-plan-2026-08-04.md) /
  [refactoring-plan-2026-07-26.md](refactoring-plan-2026-07-26.md)
- 公式ソース:
  [Ruff CHANGELOG](https://github.com/astral-sh/ruff/blob/main/CHANGELOG.md)（0.16.8, 2026-09-16）/
  [The Ruff Linter](https://docs.astral.sh/ruff/linter/)（category selectors は preview）/
  [mypy changelog](https://mypy.readthedocs.io/en/stable/changelog.html) /
  [PEP 790 – Python 3.15 Release Schedule](https://peps.python.org/pep-0790/) /
  [What's New In Python 3.15](https://docs.python.org/3.15/whatsnew/3.15.html) /
  [importlib.metadata (3.15)](https://docs.python.org/3.15/library/importlib.metadata.html) /
  [argparse (3.15)](https://docs.python.org/3.15/library/argparse.html)
