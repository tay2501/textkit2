# セキュリティレビュー — press (textkit2) 2026-08-06

**実施日**: 2026-08-06
**対象**: commit `a9c3e5e` — `feat(daemon): add press trace on/off/status diagnostic logging`
（マージコミット `1c3ded9`、ブランチ `feat/trace-logging`）
**レビュー方針**: `/security-review` の基準に従い、**この変更が新規に導入した**攻撃面のみを
検証する。既存の懸念・ハードニング不足・DoS・ディスク上の機密保存は対象外
（それぞれ [adversarial-review-2026-07-15.md](adversarial-review-2026-07-15.md) と
既存の除外規定でカバー済み）。信頼度 80% 未満の推測は報告しない。

---

## 1. 結論

**HIGH / MEDIUM の指摘: 0 件。**

trace 機能は「診断スイッチ」という性質上ログ出力と信頼境界に触れるが、
設計時点で機微データの扱いと既定ログレベルの両方が正しく処理されている。
むしろ既定ログレベルが DEBUG → INFO に**下がった**ため、露出は変更前より減少している。

唯一の残余リスクは脆弱性ではなく**将来の改変事故**であり、§4 で対処した。

---

## 2. スコープの経緯

`/security-review` は「現ブランチの未マージ差分」を対象とするが、実行時点で
`main` は `origin/main` と一致し差分が 0 件だった。空レビューには意味がないため、
**直近の機能コミット `a9c3e5e` を対象と仮定**して実施した。

**レビュー対象ファイル（テストを除く 10 件）**:

| ファイル | 変更内容 |
|----------|----------|
| `press/_cli_trace.py` | 新規。`trace on/off/status` の登録とハンドラ |
| `press/_paths.py` | `trace_path()` 追加 |
| `press/_pipe.py` | `trace_marker_path()` 追加（pathlib 回避の twin） |
| `press/__main__.py` | trace 有効時の stderr タイミング出力 |
| `press/_cli_helpers.py` | `_run_transform` に `trace` キーワード引数 |
| `press/daemon/_logs.py` | `refresh_level()` / `timed()` 追加 |
| `press/daemon/_dispatch.py` | `refresh_level()` 呼び出し + `timed()` 計装 3 箇所 |
| `press/daemon/_hotkeys.py` | `timed()` 計装 1 箇所 |
| `press/daemon/_pipe.py` | `timed()` 計装 2 箇所 |
| `press/daemon/_service.py` | 起動時 `timed()` 計装 4 箇所 |

---

## 3. 検証観点と根拠

### 3.1 機微データのログ出力 — ✅ 問題なし

`timed()` は本変更で唯一の DEBUG 出力元である。全 `_log.*` 呼び出しを走査して確認した：

```
press/daemon/_logs.py:74      _log.debug(message)          ← timed() 内部。唯一の DEBUG
press/daemon/_service.py:76   _log.info("daemon started pid=%d version=%s", ...)
press/daemon/_service.py:121  _log.info("daemon stopped")
press/daemon/_service.py:137  _log.warning("pipe server not started: %s", exc)
press/daemon/_service.py:139  _log.info("pipe server listening")
press/daemon/_pipe.py:180     _log.warning("pipe: owner-only DACL unavailable; ...")
press/daemon/_pipe.py:202     _log.error(...)
press/daemon/_pipe.py:208     _log.warning("pipe: CreateNamedPipeW failed (%d)", err)
press/daemon/_pipe.py:235     _log.warning("pipe: request failed: %s", exc)
```

`timed()` の呼び出しは 11 箇所（`_service.py` 4 / `_dispatch.py` 4 / `_pipe.py` 2 /
`_hotkeys.py` 1）あるが、`**fields` を渡すのは **2 箇所のみ**で、
いずれも**件数とコマンド名だけ**：

| 呼び出し元 | fields |
|-----------|--------|
| `_dispatch.py:105` `transform()` | `cmd=command, chars=len(text)` |
| `_dispatch.py:207` `_type_clipboard()` | `chars=len(text)` |
| 他 9 箇所 | なし |

クリップボード本文・辞書エントリ内容がログに落ちる経路は存在しない。

### 3.2 ログレベル変更による情報露出 — ✅ 露出は減少

| | 変更前 | 変更後 |
|---|--------|--------|
| 既定レベル | `logging.DEBUG`（無条件） | `logging.INFO` |
| DEBUG 化条件 | なし（常時） | `%APPDATA%\press\trace` の存在時のみ |

`_setup_logging()` は従来 `_log.setLevel(logging.DEBUG)` を無条件で実行していた。
変更後は `refresh_level()` 経由となり、マーカー不在時は INFO。
**新たな露出はなく、既定状態の露出はむしろ減っている。**

### 3.3 パストラバーサル — ✅ 問題なし

新規パス生成は 2 箇所。いずれもパス要素が全てハードコード定数で、
ユーザー入力の連結が存在しない：

```python
# press/_paths.py
def trace_path() -> Path:
    return press_dir() / "trace"

# press/_pipe.py（pathlib 回避の twin）
def trace_marker_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "press", "trace")
```

基点の `%APPDATA%` は環境変数だが、除外規定 PRECEDENTS #3
（環境変数と CLI フラグは信頼値）により攻撃経路として扱わない。

### 3.4 任意ファイル書き込み / 削除 — ✅ 問題なし

`_cli_trace.py` の `touch()` / `unlink()` は上記の固定パスのみを対象とする。
`unlink()` は `contextlib.suppress(FileNotFoundError)` で限定されており、
他の例外は伝播する（TOCTOU による誤削除の握り潰しがない）。
シンボリックリンクを介した任意書き込みを仮定しても、
対象がユーザー専有の `%APPDATA%` 配下かつ**空ファイル生成**のため実害がない。

### 3.5 コマンドインジェクション — ⛔ 指摘対象外（既存パターン）

`_cli_trace.py:49` の以下は一見サブプロセス起動だが、指摘しない：

```python
subprocess.run([sys.argv[0], "trace", "--help"], check=False)
```

- `shell=False` のリスト形式であり、外部入力の混入経路がない
- `_cli_daemon.py:127` / `_cli_config.py:62` に**同一パターンが既存**
  （サブコマンド省略時の help 表示）

本変更が新規に導入した攻撃面ではないため、
「既存のセキュリティ懸念はコメントしない」という方針に従い対象外とする。
なお `sys.argv[0]` の解決に関する一般論（Windows の CreateProcess 探索順）を
懸念するなら、それは既存 2 箇所を含めた別課題として扱うべきである。

### 3.6 パイプ権限モデルの後退 — ✅ 問題なし

`daemon/_pipe.py` の `_serve()` は `with timed("pipe.serve"):` で包まれただけで、
既存のハードニングは一切変更されていない：

- owner-only DACL（SDDL `D:P(A;;GA;;;OW)`）
- `FILE_FLAG_FIRST_PIPE_INSTANCE`
- クライアント側の `GetNamedPipeServerProcessId` による PID 検証
- `SECURITY_SQOS_PRESENT`（匿名偽装）

`try` / `except` / `finally` の構造とハンドル解放順序も維持されており、
`DisconnectNamedPipe` → `CloseHandle` が `finally` に残っている。

### 3.7 信頼境界の越境・権限昇格 — ✅ 問題なし

マーカーファイルはユーザー専有の `%APPDATA%` 配下にあり、
作成できるのは当該ユーザーまたは管理者に限られる。
トグルによって得られるのは**処理時間の DEBUG ログ**のみで、
低権限から高権限への情報流出も、コード実行経路も生じない。

### 3.8 デシリアライズ / 動的コード実行 — ✅ 該当なし

変更差分に `pickle` / `yaml` / `eval` / `exec` / XML パーサの新規導入はない。

---

## 4. 実施した対応 — 残余リスクの封じ込め

### 4.1 リスクの所在

`timed()` の「本文テキストを渡してはならない」という制約は **docstring にしか存在しない**。
既存テスト（`test_daemon_trace_instrumentation.py`）は
`TestDispatchClipboardTimed` / `TestTransformTimed` / `TestTypeClipboardTimed` /
`TestResetLeaderTimed` の 4 クラスで**現在の call site を個別に**検証しているが、
**将来追加される call site は 1 つも守れない**。

これは脆弱性ではないが、`daemon.log` は平文であり、
うっかり `timed("x", text=text)` と書かれた瞬間にクリップボード本文が
ローテーション付きファイルに 5 MB × 4 世代残る。実害は大きい。

### 4.2 対応

本プロジェクトの既定パターン
（`TestImportBudget` / `TestPidPathDuplication` / `TestSectionRegistry` /
`TestSpecialCommandsRegistry` = **規約はテストで固定する**）に倣い、
ソースレベルの AST ガードを追加した。

`test/unit/test_daemon_trace_instrumentation.py::TestTimedFieldsWhitelist` は
`press/` 配下の全 `.py` を AST で走査し、`timed(...)` の各キーワード引数が
以下の**許可リストのいずれか**に該当することを表明する：

| 許可する式 | 例 |
|-----------|-----|
| `len(...)` 呼び出し | `chars=len(text)` |
| 数値リテラル | `count=0` |
| 文字列リテラル | `mode="hotkey"` |
| コマンド名を指す識別子・属性 | `cmd=command` |

これ以外の式（`text=text`、`body=raw`、f-string、添字アクセス等）は
テスト失敗となり、CI で止まる。

---

## 5. 参考: 非脆弱性の設計上の観察

- **`_pipe.trace_marker_path()` の意図的な二重定義**は、CLI ホットパスの
  import 予算（pathlib = 20 file opens）を守るための既定パターンであり、
  `test_pipe.py::TestTraceMarkerPathDuplication` で `_paths.trace_path()` との
  一致がピン留めされている。セキュリティ上の問題はない。
- **`_run_transform` の `trace` キーワード引数**は既定 `None` で、
  `None` のとき `time.perf_counter()` を一切呼ばない。
  計測コードが常時パスに残る形にはなっていない。

---

## 6. 関連ドキュメント

- [adversarial-review-2026-07-15.md](adversarial-review-2026-07-15.md) — 全体の敵対的レビュー
- [refactoring-plan-2026-08-04.md](refactoring-plan-2026-08-04.md) — 直前のリファクタリング計画
- [../user/edr-environments.md](../user/edr-environments.md) — trace 機能の利用者向け説明
