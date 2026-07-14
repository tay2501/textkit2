# 敵対的総合レビュー — press (textkit2)

**実施日**: 2026-07-15
**対象**: main ブランチ commit 612bcea
**レビュー方針**: 仕様・設計・思想・コーディング規約・命名規則・開発手法・セキュリティ・
EDR/セキュリティソフト耐性を、2026-07 時点の最新公式情報と突き合わせて敵対的に検証する。
「動いているから良い」を認めず、攻撃者・EDR ベンダー・将来のメンテナの三者の視点で粗を探す。

---

## 1. 総合評価サマリ

| 領域 | 評価 | 一言 |
|------|------|------|
| アーキテクチャ(純関数 + I/O 分離 + レジストリ駆動) | ★★★★★ | 模範的。攻撃面も小さい |
| EDR 対策設計(import budget / pipe 委譲 / --onedir) | ★★★★★ | 定量測定に基づく設計。業界水準を超える |
| 名前付きパイプのセキュリティ | ★★★★☆ | DACL/FIRST_PIPE_INSTANCE/PID 検証は正しい。残余リスクは §4.3 |
| Win32 ctypes の正確性 | ★★★☆☆ | **SetClipboardData 失敗の黙殺、LRESULT 32bit 切り捨て**(§4.1, §4.2) |
| 機密データの扱い | ★★☆☆☆ | **genpass のパスワードがクリップボード履歴・クラウド同期に乗る**(§4.4)、hold.txt 平文(§4.5) |
| マルチユーザー対応 | ★★☆☆☆ | **Global mutex が全ユーザー共有**(§4.6) |
| CI/サプライチェーン | ★★★☆☆ | セキュリティスキャンが全て advisory-only(§6.1)、Action ピン留めが不統一(§6.2) |
| 依存関係の鮮度 | ★★★★☆ | pystray が 2023 年から未更新(既知・文書化済み)。他は最新 |
| ツールチェーン(uv/ruff/mypy/pytest) | ★★★★★ | 2026-07 時点で全て現行。mypy 2.1 / ruff 0.15 系 / Python 3.15 レーンは PEP 790 と整合 |

**結論**: 設計思想と EDR 対策は最新のベストプラクティスに照らしても推奨水準を上回る。
一方で「セキュリティツールとしての自覚が必要な箇所」— パスワード生成物と保持クリップボード
の平文露出、Win32 エラーの黙殺 — に明確な穴がある。これらは低コストで塞げる。

---

## 2. 最新公式情報との突き合わせ(2026-07-15 時点)

| 項目 | プロジェクト現状 | 最新公式状況 | 判定 |
|------|-----------------|--------------|------|
| Python | `>=3.13,<3.16`、CI に 3.15 allow-failure レーン | PEP 790: 3.15.0b3 リリース済(2026-06)、GA 2026-10-01。b4 は 2026-07-18 予定 | ✅ 整合。CI レーン設計は理想形 |
| ruff | `>=0.15.18` | 0.15.0(2026-02-03)で 2026 style guide 導入、2026-07-09 に最新リリース継続 | ✅ 現行。`target-version` を requires-python から推論させる構成も公式推奨 |
| mypy | `>=2.1.0` | 2.0(2026-05)→ 2.1(2026-05-11)が最新 | ✅ 最新 |
| pynput | `>=1.8.2` | 1.8.2(2026-05-12)が最新。活発に保守中 | ✅ 最新 |
| pystray | `==0.19.5` 固定 | 0.19.5(**2023-09-17**)以降リリースなし。実質保守停止 | ⚠️ 既知リスク(§5.3) |
| uv | `--locked` を CI で強制 | uv 公式 GitHub 統合ガイドの推奨そのもの | ✅ |
| パッケージング | hatchling 1.27+ / PEP 639 SPDX license | PEP 639 は 2024 承認、hatchling 1.27 で実装 | ✅ 先進的 |
| PyInstaller | `--onedir` + SHA-256 checksums + SignPath(休眠) | 公式 FAQ・コミュニティの一致した推奨: --onedir、コード署名、ブートローダー再ビルド、バージョンリソース付与 | ⚠️ バージョンリソース未付与(§7.2) |
| clig.dev 準拠 | サブコマンドなし→help 表示 exit 0、`-q`、stderr へ診断出力 | clig.dev の推奨と一致 | ✅ |

---

## 3. 設計・思想・規約の敵対的検証

### 3.1 設計思想 — 妥当性を疑う

- **「純関数 transform + I/O は `__main__.py` のみ」**: 攻撃面の局所化・テスト容易性の両面で正しい。
  transform がクリップボードや環境に触れない保証は、pipe サーバーが任意のレジストリ
  コマンドを実行しても被害がテキスト変換に留まることを意味する。`daemon/_pipe.py` の
  「サーバーはクリップボードに触れない」制約と合わせ、**この設計自体が権限分離になっている**。指摘なし。
- **import budget(`_pipe.py` は json/os/sys のみ)**: `TestImportBudget` でテストにより固定
  されている。「最適化はテストで守らなければ腐る」の実践であり正しい。
  ただし **`daemon_pid_path()` の pathlib 回避重複**は将来の改変事故リスクが残る —
  これも `TestPidPathDuplication` で防護済み。合格。
- **argparse 継続採用**: click/typer への移行圧力に対し「stdlib のみ = 起動時 file open 最小」
  という根拠は EDR 環境測定と整合。typer 移行は import コスト増で本プロジェクトの
  存在意義に反する。**現状維持が正解**。

### 3.2 コーディング規約 — 自己ルールとの矛盾

- CLAUDE.md は「`except Exception` 禁止」を掲げるが、実コードには
  `daemon/_pipe.py:_serve`(悪意あるクライアントからデーモン防護)、
  `_dispatch.dispatch`(ホットキー実行の最終防衛線)、`_dispatch._notify`
  など複数の広域 catch がある。**いずれも「境界での最終防衛線」という正当な例外であり、
  コメントで理由が明示されている**。矛盾ではなく規約側に「プロセス境界・スレッド境界の
  最終ハンドラは除く」と明記すべき(現状は新規貢献者が混乱する)。
- `clipboard.py:67` に日本語コメントが 1 行だけ残存(他は英語)。規約上の言語統一が未定義。

### 3.3 命名規則

- 内部モジュール `_cli_*.py` / `_pipe.py` / daemon 内 `_backends.py` 等のアンダースコア
  プレフィックスは PEP 8 準拠で一貫。公開 API は `daemon/__init__.py` 再エクスポートに集約 — 良い。
- `test/`(単数)はプロジェクト内で一貫しているが、エコシステムの慣例は `tests/`。
  実害なし・変更コスト(CI/カバレッジ/ドキュメント)の方が高い。**現状維持を推奨**。
- `json_fmt.py`(モジュール)↔ `json-format`(コマンド)↔ `jf`(alias)のマッピングは
  レジストリ(`commands.py`)が単一真実源なので追跡可能。合格。

### 3.4 開発手法

- TDD + カバレッジ 80% ゲート + mypy strict + 追加 error code は業界水準以上。
- **ただしカバレッジの omit リストが本丸を外している**(§6.3)。
- Conventional Commits、コミット前 `ruff format` 強制、uv.lock の `--locked` 検証 — 全て現行推奨。

---

## 4. セキュリティ — 敵対的検証(重大度順)

### 4.1 【High/正確性】`SetClipboardData` 失敗の黙殺とメモリリーク

`clipboard.py:_win_set_text` は `EmptyClipboard()` と `SetClipboardData()` の戻り値を検査しない。
`SetClipboardData` が NULL を返した場合:

1. **変換結果がクリップボードに書かれていないのに CLI は成功(exit 0)を返す** —
   ユーザーは古い内容を貼り付ける。silent data corruption であり、
   「Copy → press → paste」というツールの根幹契約に対する違反。
2. 失敗時はメモリ所有権が OS に移らないため **`GlobalFree` されず h_mem がリーク**する
   (Microsoft Learn: SetClipboardData が失敗した場合、呼び出し側が解放責任を持つ)。

クリップボードは他プロセス(RDP、クリップボードマネージャ、Office)との競合で
現実に失敗する API であり、「起きない」とは言えない。**修正必須**。

### 4.2 【Medium/正確性】WNDPROC の LRESULT が 32bit 切り捨て

`clipboard.py` の `_WNDPROC = WINFUNCTYPE(ctypes.c_long, ...)` と
`DefWindowProcW.restype = c_long`。LRESULT は x64 では 64bit(LONG_PTR)。
現状扱うメッセージ(WM_CLIPBOARDUPDATE/WM_DESTROY)は 0 を返すだけなので顕在化しないが、
`DefWindowProcW` がポインタ値を返すメッセージ(NCCREATE 系など)が将来通ると上位 32bit が
壊れる。`ctypes.c_longlong`(または `LRESULT` 相当)へ修正。
併せて `GetMessageW` の戻り値 `-1`(エラー)を `!= 0` で「継続」扱いしている点も、
エラー時に busy loop 化し得るため `> 0` 判定に修正すべき。

### 4.3 【Medium/残余リスク受容可】パイプ委譲の PID リサイクル窓

現行防御(owner-only DACL `D:P(A;;GA;;;OW)`、`FILE_FLAG_FIRST_PIPE_INSTANCE`、
`PIPE_REJECT_REMOTE_CLIENTS`、`SECURITY_SQOS_PRESENT` 匿名 impersonation、
`GetNamedPipeServerProcessId` × PID ファイル照合)は **Microsoft の名前付きパイプ
セキュリティ推奨事項をほぼ完全に実装している**。指摘できる残余は:

- デーモン異常終了で PID ファイルが残留 → 攻撃者が同一 PID を獲得するまでプロセスを
  スポーンし、パイプ名をスクワット → CLI が照合を通過しクリップボードテキストを送る。
  **ただし前提が「同一ユーザーとして動く悪意プロセス」であり、その攻撃者はそもそも
  クリップボードを直接読める**。脅威モデル上、追加防御(サーバープロセスの実行イメージ
  パス検証)は defense-in-depth としてのみ価値がある。優先度低。
- `_round_trip_with_timeout` はタイムアウト時にワーカースレッドとパイプハンドルを
  リークする。CLI は短命プロセスなので実害は限定的だが、ハンドルを閉じてから
  諦める設計(CancelIoEx / CancelSynchronousIo)の方が正確。優先度低。

### 4.4 【High/機密性】genpass のパスワードがクリップボード履歴・クラウドに残る

`press genpass` は TTY では**デフォルトで**パスワードをクリップボードへ書き込むが、
`set_clipboard_text` は `CF_UNICODETEXT` しか設定しない。結果:

- **Win+V クリップボード履歴に平文パスワードが保存される**(既定で最大 25 項目、再起動後も保持)。
- ユーザーが Cloud Clipboard を有効にしていれば **Microsoft アカウント経由で他デバイスへ同期**される。

Microsoft Learn 公式のクリップボード形式 `ExcludeClipboardContentFromMonitorProcessing`
(履歴・同期の両方から除外)と `CanIncludeInClipboardHistory`(DWORD 0)が正にこの用途の
ためにあり、KeePassXC・Chrome Incognito が採用している。
**パスワードマネージャ相当の機能を持つ以上、この形式の併記は必須**。
実装は `_win_set_text` に `sensitive: bool = False` を追加し、
`RegisterClipboardFormatW` した追加フォーマットを同時に `SetClipboardData` するだけ。
さらに業界標準(KeePassXC 等)に合わせた**自動クリア(既定 ~30 秒)**も検討価値あり。

### 4.5 【Medium/機密性】hold.txt の平文永続化

`press hold` はクリップボード内容(機密の可能性)を `%APPDATA%\press\hold.txt` に平文保存する。
2 回目の呼び出しまで**無期限に**ディスクに残り、バックアップ・クラウド同期(OneDrive の
AppData Roaming 同期環境)・フォレンジックに露出する。

- 最小対応: ドキュメントへの明記 + `press clear` 時に hold.txt も削除するオプション。
- 推奨対応: Win32 DPAPI(`CryptProtectData`, ユーザースコープ)で暗号化して保存。
  ctypes 数十行で依存追加なし。デーモン版(メモリ内保持)は問題なし。

### 4.6 【Medium/可用性・正確性】シングルトン mutex が全ユーザー共有

`_lifecycle.py: _MUTEX_NAME = "Global\\press_daemon_singleton"`。
パイプ名(`press-daemon-v1-{user}`)と PID ファイル(%APPDATA% = ユーザー毎)は
per-user なのに、**mutex だけがマシングローバル**。帰結:

1. 共有 PC / ターミナルサーバーで「ユーザー A のデーモンが動いていると
   ユーザー B はデーモンを起動できない」— 明確なバグ。
2. 任意のローカルユーザーが同名 mutex を先取りすれば、**全ユーザーのデーモンを
   恒久的に起動不能にできる**(squat DoS)。
3. `daemon_status` の mutex プローブも他ユーザーのデーモンを「running」と誤報する。

修正: `Global\press_daemon_singleton_{username}` へ変更(パイプ名と同じ導出を再利用)、
またはセッション毎で良いなら `Local\` 名前空間。1 行 + テスト修正で完了する。

### 4.7 【Low】`press daemon stop` のプロセス名検証

`python*`/`press*` プレフィックス照合は PID リサイクル対策として文書化済みの妥協。
同一ユーザーの無関係な python プロセスを誤殺する余地はあるが、PID ファイル改竄も
同一ユーザー前提であり脅威モデル外。現状維持で可。

### 4.8 【Low】ClipboardGuard L1 の「クリップボード戦争」

`_ClipboardMonitorWindow` は自己再入(`_restoring`)しか防がない。クリップボード履歴
マネージャや他の常駐ツールが書き戻しを行う環境では**相互復元ループ**(ping-pong)に
なり得る。CPU 浪費と他アプリの誤動作を招く。復元回数のレート制限
(例: 1 秒あたり N 回超で自動解除 + 通知)を入れるべき。

---

## 5. セキュリティソフト(EDR/AV)耐性の検証

### 5.1 高速化設計 — 現状の到達点(高評価)

- import budget のテスト固定、PID ファイル stat による委譲ゲート、`_LazyVersionAction`、
  PEP 562 lazy loading、argcomplete の環境変数ゲート — **すべて「file open 数 = EDR コスト」
  という実測モデルに基づいており、この規模の OSS では例外的に優れている**。
- `--onedir` 選択(--onefile の毎回展開は EDR 再スキャンを誘発)は PyInstaller 公式 FAQ・
  コミュニティの一致見解と合致。
- `daemon_status --json` の監視エージェント検出(`_KNOWN_MONITORING_AGENTS`)は
  診断機能として秀逸。

### 5.2 行動シグネチャの問題 — 「インフォスティーラーの三点セット」

敵対的に見ると、press daemon の実行時挙動は EDR の行動検知モデルにとって
**infostealer / keylogger と同型**である:

| press の挙動 | マルウェアの同型挙動 |
|---|---|
| WH_KEYBOARD_LL 全キー監視(pynput: GlobalHotKeys + PasteInterceptor) | キーロガー |
| クリップボード常時監視(WM_CLIPBOARDUPDATE)+ 即時書き換え | クリップボードハイジャッカー(仮想通貨アドレス差し替え型) |
| 名前付きパイプでテキスト受け渡し | C2/プロセス間ステージング |
| 未署名の PyInstaller 実行ファイル | パッカー付きペイロード |

個々は正当でも、**未署名バイナリが 4 つ同時に行うと behavioral score は跳ね上がる**。
緩和の優先順位:

1. **コード署名の実現が最重要**(SignPath 申請は進行中 — 計画v3 参照)。署名は
   ハッシュベース信頼と SmartScreen レピュテーション蓄積の前提条件。
2. **PyInstaller にバージョンリソース(会社名/製品名/説明/バージョン)と
   マニフェストを付与する**。ヒューリスティック採点で「メタデータなし exe」は減点対象。
   `--version-file` は現在未使用 — 低コストで効果あり。
3. ClipboardGuard Layer 2(LL フック)は hold 有効中のみ動く設計になっており正しい。
   **デーモン起動中に常時フックしないこと**を今後も設計不変条件として維持する
   (pynput の GlobalHotKeys 自体は常時 LL フックである点は不可避のコスト)。
4. リリース後に主要ベンダー(Microsoft 含む)への false positive 申告と
   VirusTotal での事前確認をリリース手順に組み込む。

### 5.3 依存ライブラリのリスク

- **pystray 0.19.5(2023-09-17 以降更新なし、実質保守停止)**: 既にピン留め・
  CI レーンで将来 Python 対応を監視しており、短期リスクは管理下。ただし
  3.16 時代に非互換が出た時の脱出先(Win32 Shell_NotifyIcon 直叩き ~200 行、
  または winrt 系)の**技術検証だけは先行しておくべき**。tray は daemon の
  ライフサイクル根幹(run_tray_icon がメインループ)なので、代替は疎結合化とセット。
- pynput 1.8.2(2026-05-12)は活発に保守されており問題なし。

---

## 6. CI/CD・サプライチェーンの敵対的検証

### 6.1 【High/プロセス】セキュリティスキャンが全て「飾り」

`security.yml` の実効性を検証した結果:

- pip-audit: `|| true` — **失敗しても常に成功**
- Bandit: `|| true`
- Semgrep: `|| true`
- OSV-Scanner: `fail-on-vuln: false`

つまり**既知の Critical CVE を持つ依存を導入しても CI は緑のまま**。SARIF が
Security タブに出るのは良いが、誰も見なければ存在しないのと同じ。
これは CLAUDE.md 自身の規約「`|| true` で誤魔化さない(rule 7)」と正面から矛盾する。
最低ラインとして **pip-audit と OSV は fail させる**(誤検知は ignore 設定で個別管理)。
Bandit/Semgrep は SAST の誤検知率を考慮して advisory 継続でも許容。

### 6.2 【Medium】GitHub Actions のピン留めが不統一

`astral-sh/setup-uv`、`codecov-action`、`softprops/action-gh-release`、`osv-scanner` は
コミット SHA ピン(正解)だが、`actions/checkout@v6`、`actions/upload-artifact@v7`、
`actions/download-artifact@v8`、`github/codeql-action@v4`、`signpath/...@v2` は
タグ参照。タグは書き換え可能であり、tj-actions 事件(2025-03)以降の業界標準は
**全 Action の SHA ピン + Dependabot による更新**。first-party(actions/)は
リスク低だが、方針は統一すべき。`signpath` action は署名鍵に近い位置にあるため特に。

### 6.3 【Medium】カバレッジゲートが最重要コードを除外

`omit = ["press/__main__.py", "press/_cli_*.py", "press/clipboard.py", "press/daemon/*"]`。
「カバレッジ 80% 強制」と言いながら、**バグが実害を生む I/O 層・Win32 層・デーモンが
全て分母から除外されている**。§4.1 のバグが検出されなかったのはこの構造の帰結でもある
(ctypes 呼び出しの失敗パスはユニットテストでモック可能)。
Windows ランナーでは `windows_only` テストが実走しているのだから、少なくとも
`clipboard.py` の純粋ロジック部と `_cli_*.py` は分母に戻し、実測してから
閾値を調整すべき。

### 6.4 その他

- `release.yml` の checksum 生成が署名後に行われる順序は正しい。
- `uv.lock` が Dependabot で更新されない問題は既知(CLAUDE.md 記載)。
  `dependabot.yml` の pip エコシステム更新後に `uv lock` を回す follow-up を
  自動化する余地あり(uv 公式は Renovate の uv lockfile サポートを案内している —
  Renovate 移行も選択肢)。

---

## 7. 良い点(維持すべき決定)

敵対的レビューの結論として、以下は**変更圧力がかかっても守るべき**:

1. import budget とそのテスト固定(`TestImportBudget`)— 本プロジェクトの存在意義そのもの。
2. パイプセキュリティ 5 点セット(DACL/FIRST_PIPE_INSTANCE/REJECT_REMOTE/SQOS/PID 照合)。
3. `secrets` モジュールによるパスワード生成(CSPRNG)、`WinDLL(use_last_error=True)` 規律。
4. レジストリ駆動のコマンド追加(1 エントリで CLI/daemon/pipe/lazy-load 全対応)。
5. `--onedir` / uv `--locked` / PEP 639 / 3.15 allow-failure レーン。
6. argparse 継続(typer/click 移行はこのプロジェクトでは退行)。

---

## 8. 指摘一覧(重大度順)

| # | 重大度 | 領域 | 指摘 | 参照 |
|---|--------|------|------|------|
| 1 | High | 正確性 | SetClipboardData/EmptyClipboard 失敗の黙殺 + GlobalFree リーク | §4.1 |
| 2 | High | 機密性 | genpass パスワードがクリップボード履歴/クラウド同期に残存 | §4.4 |
| 3 | High | プロセス | セキュリティスキャン全件 advisory-only(`|| true`) | §6.1 |
| 4 | Medium | 可用性 | Global mutex の全ユーザー共有(共有 PC で起動不能 + squat DoS) | §4.6 |
| 5 | Medium | 正確性 | LRESULT 32bit 切り捨て、GetMessageW -1 未処理 | §4.2 |
| 6 | Medium | 機密性 | hold.txt 平文永続化 | §4.5 |
| 7 | Medium | サプライチェーン | Actions の SHA ピン不統一 | §6.2 |
| 8 | Medium | 品質保証 | カバレッジ omit が I/O・Win32・daemon を除外 | §6.3 |
| 9 | Medium | EDR | PyInstaller exe にバージョンリソース/マニフェストなし | §5.2 |
| 10 | Low | 堅牢性 | ClipboardGuard L1 の復元ループ(clipboard war) | §4.8 |
| 11 | Low | 正確性 | パイプクライアントのタイムアウト時ハンドル/スレッドリーク | §4.3 |
| 12 | Low | 依存 | pystray 保守停止 — 脱出先の技術検証未着手 | §5.3 |
| 13 | Low | 規約 | 「except Exception 禁止」規約と境界ハンドラ実態の不整合(規約側の明文化不足) | §3.2 |

---

## 参照(2026-07-15 検索)

- PEP 790 – Python 3.15 Release Schedule: https://peps.python.org/pep-0790/
- Python 3.15.0b3 (2026-06): https://blog.python.org/2026/06/python-3150-beta-3/
- Ruff v0.15.0 (2026 style guide): https://astral.sh/blog/ruff-v0.15.0 / Releases: https://github.com/astral-sh/ruff/releases
- Mypy 2.1 Released (2026-05-11): https://mypy-lang.blogspot.com/2026/05/mypy-21-released.html
- pynput 1.8.2 (2026-05-12): https://pypi.org/project/pynput/
- pystray 0.19.5 (2023-09-17): https://pypi.org/project/pystray/
- Clipboard Formats (ExcludeClipboardContentFromMonitorProcessing / CanIncludeInClipboardHistory):
  https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-formats
- PyInstaller AV false positives(--onedir / 署名 / ブートローダー再ビルド):
  https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/ /
  https://github.com/orgs/pyinstaller/discussions/5877
