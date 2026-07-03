# REFACTORING_PLAN v2 — press (textkit2)

> 計画ドキュメント（**実施完了・記録として保存**）。
> 2026-07-03 作成（2026-06-22 版を全面改訂）。対象: 本リポジトリのみ。
> **Option A は同日中に実装完了**（コミット `045bee7`〜`00b2e4b`、全 4 項目 +
> コードレビュー指摘 6 件の修正）。棚上げ項目のトリガーは本文参照。

## 前回計画（v1, 2026-06-22）からの差分

v1 の推奨だった Option A の中核 **「ParametricCommand レジストリによる 4 点同期の解消」はコミット
`10ebcff` で実装済み**。`daemon.py::_transform` のディスパッチ、`PARAMETRIC_ALIASES`、
`transforms/__init__.py::_LAZY` はすべて `commands.py` のレジストリから導出されるようになった。

ただし **部分的な完了**である:

- ❌ `__main__.py` の parametric コマンド用 `_register_*` ボイラープレート（約 120 行、
  `__main__.py:53-167` の 6 関数）は残存。`ParametricCommand` に CLI 引数仕様のフィールドが
  ないため、**コマンド追加は依然 2 ファイル編集**（`commands.py` + `__main__.py`）。
- ❌ `requires-python` の 3.14 拡大と CI マトリクス追加は未実施（現在も `>=3.13,<3.14`、CI は 3.13 のみ）。
- ❌ src/ レイアウト移行、デーモン依存のシーム導入も未実施。

---

## 調査 — 最新公式情報（2026-07-03 時点）

| 領域 | リポジトリの現状 | 最新（公式） | 判定 |
|---|---|---|---|
| **Python** | `requires-python = ">=3.13,<3.14"` / CI は 3.13 のみ | 3.14.4 が保守フェーズ、**3.15 は RC 2026-07-28 / GA 2026-10 予定**（[PEP 790](https://peps.python.org/pep-0790/), [devguide](https://devguide.python.org/versions/)） | ⚠️ 3.14 ユーザーをインストール不能にしている |
| **ruff** | `>=0.15.18` | **0.15.20**（2026-06-25、[PyPI](https://pypi.org/project/ruff/)） | ✅ 最新系列 |
| **mypy** | `>=2.1.0`、CI で `--num-workers 4` 使用 | **2.1**（2026-05-11、[changelog](https://mypy.readthedocs.io/en/stable/changelog.html)）。2.0 で並列型チェック導入 | ✅ 最新・新機能も活用済み |
| **pytest** | `>=9.1.1` | **9.1.1**（2026-06-19、[PyPI](https://pypi.org/project/pytest/)） | ✅ 最新 |
| **pynput** | `>=1.8.2` | **1.8.2**（2026-05-12、[PyPI](https://pypi.org/project/pynput/)）。Snyk は「Inactive」判定だが直近 2 ヶ月内にリリースあり | ✅ 当面のリスク低 |
| **pystray** | `==0.19.5` | **0.19.5 のまま 2023-09-17 から約 2 年 10 ヶ月リリースなし**（[PyPI](https://pypi.org/project/pystray/), [Snyk: discontinued 扱い](https://snyk.io/advisor/python/pystray)） | ⚠️ **唯一の実質的な供給リスク** |
| **パッケージング** | hatchling + PEP 621 + PEP 735 groups + uv.lock | 推奨構成のまま | ✅ 現代的（レイアウトのみ下記） |
| **レイアウト** | flat `press/`（CI に `PYTHONPATH: .` ハックあり） | src/ レイアウトが公式推奨デフォルト | ⚠️ 低影響のギャップ |

## 内部スメル（今回のコード監査で確認）

1. **`__main__.py` の parametric 登録ボイラープレート**（上記のとおり、v1 積み残し）。
   trim / dedupe / sort / sql-in / fix-encoding / json-format の 6 関数は「フラグ + 型付き
   オプション」だけの定型で、宣言的な引数仕様に落とせる。genpass / clear / hold は
   クリップボード I/O が特殊なので手書き維持が正しい。
2. **`%APPDATA%` フォールバック導出が 6+ 箇所に重複し、しかも不整合。**
   `config.py:85,172`・`transforms/hold.py:18`・`daemon.py:41-43` は `Path.home()` へ
   フォールバックするが、**`dictionary.py:22` だけ `""`（カレント相対）へフォールバック**する。
   非 Windows / APPDATA 未設定環境で挙動が食い違う潜在バグ。
3. **`daemon.py` が 818 行・8 責務混在**: トレイ画像生成 / hotkey 記法変換 / logging 設定 /
   status ファイル / Win32 mutex / CommandDispatcher / Listener 2 種 + Worker /
   CLI 向け `daemon_logs`・`daemon_status`・`stop_daemon`。テストは通っているが変更コストが高い。
4. **`_DEFAULT_BINDINGS`（`config.py:34`）とレジストリの整合性テストが無い。**
   バインディング値（例 `"halfwidth"`, `"sql-in"`, `"dict"`）がディスパッチ可能コマンドで
   あることを検証するテストがなく、「4 点同期バグ」の最後の 1 点が未防御。
   （`test_daemon_helpers.py` はレジストリ内部の整合性のみ検証している。）
5. **pystray / pynput への直接依存が `daemon.py` と `clipboard.py` に散在**（抽象シームなし）。
   pystray が事実上メンテ停止のため、Python 3.14+ / 将来の Pillow 変更で壊れた場合の
   交換コストがそのまま 2 ファイルの書き換えになる。

> v1 と同じく: `argparse` 採用・ctypes 直叩きクリップボード・遅延 import による高速起動は
> **意図的な設計であり欠陥ではない**。維持する。

---

## 選択肢の比較

### Option A — 保守的: v1 積み残しの完遂 + 今回発見分の是正（推奨）

小さな独立 PR 4 本。新規依存なし、公開インターフェース不変、すべて可逆。

- **A-1. バインディング整合性テスト追加**（即効・数行）
  `_DEFAULT_BINDINGS` の全値が `SIMPLE_COMMAND_INDEX ∪ PARAMETRIC_COMMAND_INDEX ∪
  {dict, dict_reverse, hold, clear}` に含まれることを検証するユニットテスト。
- **A-2. パス導出の一元化**: `press/_paths.py` を新設し `%APPDATA%` 展開を 1 箇所に。
  `dictionary.py:22` の不整合フォールバック（`""` → `Path.home()`）を修正。
- **A-3. `ParametricCommand` に宣言的 CLI 引数仕様を追加**
  `cli_args: tuple[ArgSpec, ...]`（flag / typed option / default / help）を持たせ、
  `__main__.py` の 6 個の `_register_*` を汎用 1 関数に集約。コマンド追加が
  `commands.py` 1 ファイルで完結する（v1 のゴールの完遂）。
- **A-4. Python 3.14 対応 + CI 微修正**
  `requires-python = ">=3.13,<3.15"` に拡大、CI マトリクスに 3.14 追加。
  ついでに `--cov=.` → `--cov=press` に統一（pyproject の `source=["press"]` と一致させる）。
  3.15 は GA（2026-10 予定）後に allow-failure 枠で追加検討。

- **トレードオフ:** 価値対リスク最良。A-3 は CLI 登録という中枢を触るため、
  `--help` 出力と全 574 テストのバイト単位一致を要確認。
- **影響範囲:** `commands.py`, `__main__.py`, `dictionary.py`, `config.py`, `daemon.py`,
  `transforms/hold.py`, `pyproject.toml`, `ci.yml`, テスト追加。
- **不可逆性: なし。** すべて内部変更で容易に戻せる。

### Option B — 中庸: A + 構造強化

A に加えて:

- **B-1. `daemon.py` のパッケージ分割**: `press/daemon/` 配下に `_tray.py`（アイコン・メニュー）、
  `_hotkeys.py`（Listener 群）、`_lifecycle.py`（mutex・PID・status）、`_logs.py`、
  `_dispatch.py` を切り出し。公開 API（`run_daemon` 等 4 関数）は `__init__.py` で維持。
- **B-2. トレイ/ホットキーのバックエンド Protocol シーム**: pystray / pynput を
  `daemon/_backends.py` の Protocol 越しに使い、メンテ停止上流を 1 モジュールに隔離。
- **B-3. src/ レイアウト移行**: `press/` → `src/press/`。hatchling 設定・coverage・
  CI の `PYTHONPATH: .` ハック削除が伴う。

- **トレードオフ:** 長期保守性と供給網リスク耐性は上がるが、diff が大きく履歴が荒れる。
  B-1 はテストの import パス修正を伴う。
- **不可逆性: 部分的。** B-3 は事実上一方通行。B-1 / B-2 は可逆。

### Option C — 積極的: 依存の置換

- pystray を pywin32 / ctypes 直書きの Win32 トレイ（`Shell_NotifyIcon`）へ置換、
  pynput を `RegisterHotKey` + `WH_KEYBOARD_LL` 直書きへ置換。
- CLI のゼロ依存思想とは整合するが、Win32 メッセージループの自前管理は
  テスト困難・工数大。**pynput は 2026-05 にリリースがあり死んでいない**ため、
  現時点では過剰対応。

- **不可逆性: 高。** 唯一のサポート対象プラットフォームの実行時挙動を書き換える。

---

## 推奨

**Option A（A-1 → A-2 → A-4 → A-3 の順で小 PR 4 本）。**

根拠: ツールチェーン（ruff 0.15.20 / mypy 2.1 / pytest 9.1.1 / pynput 1.8.2）は
すでに最新に追随済みで、依存更新の作業はない。残っている具体的な欠陥は
(1) v1 ゴールの積み残しである `__main__.py` ボイラープレート、
(2) 今回発見した `dictionary.py` のフォールバック不整合、
(3) 3.14 ユーザーの排除 — の 3 点で、いずれも Option A で解消できる。

**pystray リスク（B-2）は「トリガー待ち」として棚上げを推奨**: 現に動いており、
シームを先に作っても交換先が未定なら抽象の当てずっぽうになる。トリガーは
「Python 3.14/3.15 または Pillow 更新で pystray が壊れる」または「v1.0.0 の
PyPI 公開前」のいずれか早い方。B-1（daemon 分割）と B-3（src/）は価値はあるが
急がず、v0.6.0（ベンチマーク導入）前後の落ち着いたタイミングで単独判断。

Option C は見送り（v1 と同判断）。

---

## 選択

採用オプション: **Option A**（2026-07-03 ユーザー承認「全て徹底的に実施」→ 同日実装・push 完了）
