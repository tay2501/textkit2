# pystray 脱出戦略 調査メモ(改善計画 第10位)

**作成日**: 2026-07-15
**種別**: 調査のみ(コード変更なし)
**背景**: pystray 0.19.5 は 2023-09-17 を最後に更新停止。トレイは daemon の
メインループ(`run_tray_icon` がブロッキング)であり、Python 3.16 時代に
非互換が出た場合の脱出先を事前に確定しておく。

---

## 1. 現行要件(`daemon/_backends.py` の contract)

| 要件 | 現行実装 |
|------|---------|
| ブロッキング実行 + `setup(icon)` コールバック | `pystray.Icon.run(setup=)` |
| コンテキストメニュー(ラベル + 区切り + Quit) | `pystray.Menu` |
| アイコン動的差替(hold 中は赤) | `icon.icon = <PIL.Image>`(`_tray.py` が Pillow で生成) |
| 通知 `notify(message, title)` | `pystray.Icon.notify`(Shell balloon)。既定 `notify_level="off"` のためソフト要件 |
| 停止 `stop()` | `pystray.Icon.stop` |

置き換え面は `TrayIcon` Protocol + `run_tray_icon()` + `_tray.py`(画像生成)のみ。
他モジュールは Protocol 経由でしか触れない(設計通り)。

---

## 2. 候補比較(2026-07-15 時点)

### 案 A: ctypes 直実装(Shell_NotifyIcon)— ★推奨

- **実装規模**: 約 250–350 行。`NOTIFYICONDATAW` 構造体、隠しウィンドウ +
  `WM_APP` コールバック、`CreatePopupMenu`/`TrackPopupMenu`(メニュー)、
  `NIM_MODIFY`(アイコン差替)、`NIF_INFO`(balloon → Win11 ではトースト表示)。
  **`clipboard.py::_ClipboardMonitorWindow` に隠しウィンドウ + メッセージポンプ +
  WNDPROC の実績パターンが既にあり**、社内前例ゼロからではない。
- **依存削減**: pystray に加えて **Pillow も削除可能**(アイコンは静的 .ico
  2 枚 — 通常/hold赤 — を同梱し `LoadImageW` で読む)。Pillow はトレイ画像
  生成のためだけの数 MB 級ネイティブ依存で、定期的な CVE 源
  (2026-07 にも 12.3.0 へ更新)。PyInstaller バンドル縮小 + EDR スキャン面の
  縮小 + サプライチェーン面の改善が同時に得られる。
- **daemon 構造との適合**: `run_tray_icon(name, title, image, setup, on_quit)`
  の contract を 1:1 で再実装可能。メッセージループがそのままブロッキング実行になる。
- **EDR 観点 import 数**: 追加依存ゼロ(ctypes は既にロード済み)。
  pystray+Pillow の import チェーン(数十 file open)が消える。
- **リスク / 注意点**:
  - `TaskbarCreated` メッセージ(Explorer 再起動時にアイコン再登録)への対応必須。
  - メニューは `TrackPopupMenu` の既知の癖(フォアグラウンド化 `SetForegroundWindow`
    が必要)に対応すること。
  - Win32 エッジケースを自前で背負う。windows_only テスト + 手動 QA が必要。
- **見積り**: 実装 1.5–2 日(テスト・手動 QA 込み)。

### 案 B: infi.systray(0.1.12.1、2025-01 更新)

- Windows 専用トレイライブラリ。メニュー・`update()` によるアイコン/ツール
  チップ差替・quit コールバックあり。アイコンは .ico ファイル(Pillow 削除可)。
- **通知(balloon/toast)非対応** — `notify()` は自前 `NIF_INFO` か
  windows-toasts の追加が必要 = 半分だけの解決。
- 更新頻度は pystray よりましだが低活動。「半分死んだ依存を別の半分死んだ
  依存に替える」構図になるため、案 A が停滞した場合の fallback。

### 案 C: WinRT / Windows App SDK 系 — ★不成立(記録として重要)

- **WinRT にシステムトレイ API は存在しない**。トレイは今も Win32
  `Shell_NotifyIcon` 一択(Windows App SDK アプリも内部では Win32 を使う)。
- WinRT 系(windows-toasts 1.3.1、2025-05)が置き換えられるのは**通知のみ**。
  しかも winrt バインディングは新しい Python への追従が遅く(明示サポートは
  3.12 まで)、本プロジェクト(>=3.13)とは相性が悪い。トレイ脱出先としては不成立。

### 案 D: pywin32(win32gui)

- pywin32 は活発に保守されている(312)が、巨大パッケージ + PyInstaller での
  取り回しの癖があり、「Win32 は ctypes で最小限に」という本プロジェクトの
  設計原則(clipboard.py / _pipe.py / _dpapi.py)と矛盾する。不採用。

---

## 3. 副次的発見: pywin32 はデッド依存

`grep` の結果、**`press/` 内に `win32api`/`win32gui`/`pywintypes` 等の import は
一切存在しない**。`pyproject.toml` の daemon extra にある
`pywin32>=312; sys_platform == 'win32'` は使われていない(pystray/pynput も
ctypes ベースで pywin32 を要求しない)。mypy overrides の `win32.*`/`pywintypes`
も同様にデッド設定。

**推奨フォローアップ(小タスク・即実施可)**: daemon extra から pywin32 を削除し
`uv lock` + CI で検証。インストールサイズ・PyInstaller バンドル・監査対象
パッケージ数が無条件に減る。

---

## 4. 結論と発動条件

| 順位 | 案 | 位置づけ |
|------|----|---------|
| 1 | 案 A: ctypes 直実装 | 本命。pystray + Pillow(+デッド pywin32)を一掃し daemon extra を pynput + psutil のみへ |
| 2 | 案 B: infi.systray | A が stall した場合の暫定 fallback |
| — | 案 C: WinRT | トレイ API が存在せず不成立(通知のみ可) |
| — | 案 D: pywin32 | 設計原則と矛盾、不採用 |

**発動条件(計画どおり YAGNI 維持)**:
1. CI の 3.15/3.16 レーンで pystray 破損が観測されたとき、または
2. Pillow 削減(バンドル/EDR/サプライチェーン)を目的に v0.7.0 以降で
   計画的に実施すると判断したとき。

条件成立まで実装しない。ただし §3 の pywin32 削除だけは発動条件と無関係に
実施してよい(リスクなし・純減)。

---

## 参照

- pystray 0.19.5(2023-09-17 最終): https://pypi.org/project/pystray/
- infi.systray 0.1.12.1(2025-01-11): https://pypi.org/project/infi.systray/
- windows-toasts 1.3.1(2025-05-06、WinRT、〜3.12): https://pypi.org/project/windows-toasts/
- pystray ラッパー系(tray-manager, psgtray)は依存が pystray のままで脱出先にならない:
  https://pypi.org/project/tray-manager/ / https://github.com/PySimpleGUI/psgtray
- Shell_NotifyIcon(Win32 公式): https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shell_notifyiconw
