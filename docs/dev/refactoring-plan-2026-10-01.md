# リファクタリング計画 — press (textkit2) 2026-10-01

**対象**: `main` commit `1159794`
**方針**: 前回計画 [refactoring-plan-2026-09-18.md](refactoring-plan-2026-09-18.md) 以降に残った
**同一事実の重複・環境依存テスト・CLI 起動コスト**を、実測で裏取りしたうえで潰す。
過去に不採用と判定済みの項目（`clipboard.py` 分割、`_handler` のトレース計測重複 等）は再提案しない。

**ベースライン（変更前・実測）**: CI（main）全レーン green（3.15 allow-failure レーン含む）/
ローカル `ruff` / `ruff format --check` / `mypy --strict`（win32 + `--platform linux`）green /
`pytest` **1077 passed, 1 failed, 2 skipped**（失敗は R1）。

> **実施状況（2026-10-01）**: **R1〜R6, R8 実施済み ✅ / R7 は前提未成立のため保留**
>
> - **検証**: `ruff format` / `ruff check` green / `mypy --strict`（win32 + `--platform linux`）51 files 問題なし /
>   **1079 passed, 2 skipped**（-1 は R3 で冗長テスト削除、+2 は R2 の新規テスト、+1 は R1 の修正）/
>   Python 3.13 でも主要テスト 200 passed。

---

## R1【テスト欠陥】起動ファイルオープン予算テストが環境依存

`test_startup.py::test_transform_run_file_open_budget` がローカルで **62 > 60** で失敗した。
`%APPDATA%\press\press.pid` が残存（daemon は停止済み）しており、CLI が委譲経路
（ctypes / threading / json / sysconfig …）に入ってからローカル実行へ戻っていた。CI には PID ファイルが無いため通る。

**実施**: 計測 subprocess に `PRESS_NO_DAEMON=1` と一時 `APPDATA` を渡し、開発機の press 状態から隔離した。
あわせて `_pipe._daemon_may_be_running()` の docstring の「stale PID は接続失敗 1 回だけ」を
「以後の毎回の CLI 実行で約 14 回のファイルオープン」へ訂正した。

**積み残し（調査項目）**: stale PID ファイルを誰がいつ消すか。`status.json` も `running` のまま残っていた。

## R2【性能】`commands.py` の dataclass → `typing.NamedTuple`

`import dataclasses` は inspect / ast / dis / tokenize を連鎖 import し **14 回**ファイルを開く。
`typing` は既にロード済みなので `NamedTuple` は **0 回**。

| Python（Windows, 隔離計測） | 変更前 | 変更後 |
|---|---|---|
| 3.13 | 43 | **32**（-26%） |
| 3.14 | 49 | 49（3.14 の argparse が `_colorize` 経由で dataclasses を自前で import するため効果なし） |

`CliArg.__post_init__` の検証は `_check_cli_args(PARAMETRIC_COMMANDS)` としてモジュール読み込み時に実行し、
fail-fast を維持した。回帰テスト 2 件（`press.commands` 単体で dataclasses を読まないこと / 検証が ValueError を出すこと）を追加。

## R3【重複】パイプサーバーの独自コマンド解決

`daemon/_pipe.handle_request` は `PARAMETRIC_ALIASES` → 2 つの INDEX を個別に引いていたが、
INDEX は既に別名キーを持つため冗長だった。`commands.resolve_spec()` に一本化し、
唯一の利用者を失った `PARAMETRIC_ALIASES` と、それを pin するだけのテストを削除した。
`commands.py` の古いコメント（`daemon.py` / `_transform()`）と CLAUDE.md の gotcha も更新。

## R4【性能】`_pipe.py` の `json` を遅延 import

daemon 不在時の CLI 実行で **53 → 49**（3.14, Windows）。`TestImportBudget` の監視対象に `json` を追加。

## R5【rule 7】広域 `except Exception` の具体化

| 箇所 | 変更 | 根拠 |
|---|---|---|
| `_cli_helpers.write_clipboard_or_warn` | `(OSError, RuntimeError)` | `clipboard.py` の送出集合（09-18 R4 と同根拠） |
| `_cli_config` の `config reset` | `OSError` | `config_reset` は TOML 読込失敗を内部で処理済み。外に出るのはバックアップ/書き込みのファイル I/O のみ |

維持: `_run_transform` / `chain` の変換関数呼び出し（任意の変換エラーを利用者向けメッセージにする）、
daemon 側（不正クライアントで daemon を落とさない）。

## R6 `_cli_config.py` の `# type: ignore[arg-type]` ×2 を除去

`dict[str, object]` の `**` 展開をやめ、`_add_file_arg(parser)` ヘルパーにした。

## R7（保留）Python 3.15 レーンの必須化

2026-10-01 時点で python.org・`actions/python-versions` とも最新は **3.15.0rc2**。正式版未公開のため保留。
公開を確認後、`ci.yml` の 3.15 行から `experimental: true` を外す。

## R8【文書と実装の不一致】辞書パス

`docs/user/config.md` は `[dictionary] files` を「優先順位付きの複数ファイル」と説明していたが、
実装は daemon が `files[0]` のみ、CLI `press dict` は config を読まず `--file` / `default_dict_path()`。
**(a) 文書を実装に合わせる**を採用（挙動変更なし）。`DictionaryConfig` の docstring にも明記した。
複数ファイル対応や CLI の config 参照は機能変更として別途判断する。

## 不採用・保留

| 候補 | 理由 |
|---|---|
| `config` サブコマンド無指定時の `subprocess.run([sys.argv[0], "config", "--help"])` | 2 つ目のプロセス起動は EDR コスト上も不利で `print_help()` で足りるが、挙動（出力経路）変更を伴うため今回スコープ外。次回候補 |
| `make_parser()` が `_cli_*` 5 モジュールを常に import（5 opens） | argparse がサブコマンド parser を事前構築する前提のため、遅延化は設計変更になる。費用対効果を別途評価 |
| 予算 `_MAX_TRANSFORM_FILE_OPENS` の引き下げ | Ubuntu レーンの実測が未取得。CI 実測後に判断 |
