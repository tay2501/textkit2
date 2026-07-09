# リファクタリング + EDR/DLP 対応計画 v3 — press (textkit2)

> 調査・計画ドキュメント。2026-07-09 作成。
> 前提: `REFACTORING_PLAN.md`（v2, Option A 実施完了）および
> `EDR_PERFORMANCE_PLAN.md`（Phase 1/3 実施完了、署名は保留）の後継。
> 本ドキュメントは**未実施のコード変更を含まない計画**であり、実施はユーザー承認後。

---

## Part 0 — 現状確認（2026-07-09 時点のコード監査）

v2 計画の Option A（A-1〜A-4）と EDR 計画の Phase 1・Phase 3 は**全て実装済み**であることをソースで確認した:

| 項目 | 確認結果 |
|---|---|
| 遅延 `--version`（`_LazyVersionAction`） | ✅ `__main__.py:29` |
| `_ARGCOMPLETE` ガード | ✅ 実装済み（起動オープン数 108→40、-63%） |
| 宣言的 CLI 登録（`cli_args` による `_register_*` 集約） | ✅ `_register_transform_command()` 1 関数に統合済み |
| `%APPDATA%` 一元化 | ✅ `press/_paths.py`（32 行） |
| `requires-python` | ✅ `>=3.13,<3.15`（3.14 対応済み） |
| 監視エージェント検出（`daemon status --json`） | ✅ + `docs/user/edr-environments.md` |
| 性能スイート | ✅ `test/perf/` 3 本（起動・変換・辞書）を CI 常時実行 |
| SHA-256 チェックサム添付 | ✅ `release.yml`（commit 4a76de2） |

**残存する構造的課題**（v2 で棚上げ・トリガー待ちとしたもの）:

1. **コード署名の保留** — 証明書コストを理由に 2026-07-03 に保留（→ Part 1 で状況が変わった）
2. **`daemon.py` 863 行・8 責務混在**（トレイ/hotkey/logging/status/mutex/dispatch/listener/CLI 関数）
3. **pystray 供給リスク** — 0.19.5 のまま約 2 年 10 ヶ月リリースなし（本日再確認、変化なし）
4. **src/ レイアウト未移行**（CI に `PYTHONPATH: .` ハック残存）
5. **zipapp / CLI→デーモン委譲** — トリガー待ちのまま

---

## Part 1 — 最新公式情報の調査結果（2026-07-09）

### 1-1. コード署名: 状況が大きく好転（本計画の最重要更新）

v2/EDR 計画で「証明書取得コスト（年数万円〜）」を理由に保留した前提が変わった。

| 選択肢 | 費用 | press への適格性 | 備考 |
|---|---|---|---|
| **SignPath Foundation（OSS 無償署名）** | **無料** | ✅ **適格**: MIT（OSI 承認）・活発に保守・リリース済み・プロプライエタリ成分なし | 条件: 全メンバー MFA、プロジェクトページに「Code signing policy」明記、CI からの署名フロー。将来 SBOM 等の要件追加の可能性を規約に明記 |
| Certum Open Source Code Signing | 初回 €69 + 更新 €29/年 | ✅ 個人 OSS 開発者向け。商用配布と判断されると失効 | **2026-02-27 以降、証明書の最長有効期間が 459 日に短縮**（業界共通変更）。CN/O に "Open Source Developer" が入る |
| Azure Artifact Signing（旧 Trusted Signing） | $9.99/月 | ❌ **Public Trust の個人開発者は米国・カナダ限定**（組織は US/CA/EU/UK） | 日本の個人開発者は現時点で対象外。GA 済み・名称変更済み |
| 従来 OV 証明書（DigiCert 等） | 年数万円〜 | ○ | v2 時点の前提。上記により劣後 |

**結論: SignPath Foundation 申請が第一候補**（無料・EDR サーベイで確認済みの
「無署名 exe はリリースごとにレピュテーションがゼロリセット」問題を解消）。
却下された場合のフォールバックが Certum（€69）。

### 1-2. Python 3.15 — 起動高速化が press の主課題に直結

- スケジュール（PEP 790）: **RC1 2026-08-04 / RC2 2026-09-01 / GA 2026-10-01**。
- 公式 What's New が **インタープリタ起動の高速化**を明記 — press の EDR 課題
  （起動時ファイル I/O × 監視エージェント増幅）に**無改修で効く**アップデート。
- free-threading は 3.14 で正式サポート化（PEP 779）、3.15 で Stable ABI（PEP 803）。
  press はシングルスレッド CLI + 軽量デーモンなので採用理由なし（現状維持）。
- 制約: pystray 0.19.5 の 3.14+ 互換は未検証のまま（→ 1-3）。

### 1-3. pystray — 供給リスク継続（変化なし）

PyPI 最新は 0.19.5 のまま（2023-09-17 から約 2 年 10 ヶ月リリースなし）。
代替（tray-manager, psgtray, crosstray 等）はいずれも pystray ラッパーか未成熟で、
**乗り換え先として本命が存在しない状況も変化なし**。v2 の判断
（Protocol シームはトリガー待ち）を維持するが、トリガーに「CI での 3.14 実測破損」を追加。

### 1-4. PyInstaller — 6.21.0（2026-06-13）

Python 3.14/3.15 対応済み。`--onedir` 方針（EDR キャッシュ有効）は引き続き正しい。
ビルド CI のバージョン追随のみ。

### 1-5. Defender / Dev Drive — 変化なし

performance mode（非同期スキャン）の公式ドキュメントは内容据え置き。
`docs/user/edr-environments.md` の記載は最新のまま有効。

---

## Part 2 — EDR/DLP（変換処理を遅延させる常駐ソフト）対応案 総合ランキング v3

評価軸は v2 と同一: **効果**（EDR/DLP 環境での体感改善）× **実現性** × **リスク**。
実施済み施策（デーモン常用導線・起動 I/O 削減・診断機能・--onedir・SHA-256）は殿堂入りとして除外し、**未実施の選択肢を網羅的に再ランキング**する。

### 🥇 1 位: コード署名の実施（SignPath Foundation → Certum の順で申請）

- **効果: 大。** カテゴリ E（SmartScreen / Smart App Control / アプリ制御）の警告・ブロックを解消し、カテゴリ A/C（EDR/AV)のレピュテーション評価・クラウド照会コストを恒久的に削減。同一 publisher の継続署名でリリースごとのゼロリセットが消える。DLP の Trusted Application 登録（組織側除外）も署名済みバイナリが事実上の前提条件。
- **実現性: 高（新事実）。** SignPath Foundation は無料で、press は適格条件
  （MIT・保守中・リリース済み・マルウェアなし）を満たす。必要作業は
  (a) リポジトリ管理者の MFA 有効化（GitHub は既定で満たしやすい）、
  (b) README / docs に「Code signing policy」ページ追加、
  (c) 申請、(d) `release.yml` に署名ステップ統合。
- **リスク: 低。** 却下されても Certum €69 フォールバックあり。署名は誤検知を減らす方向にしか働かない。
- **v2 からの変化:** 「保留」→「即実施可能」。**本計画で最優先。**

### 🥈 2 位: Python 3.15 追随（CI 先行 + GA 後に上限開放）

- **効果: 中。** 公式の起動高速化が press の支配的コスト（起動×EDR 増幅）を無改修で削る。`test/perf/test_startup.py` が既にあるため効果を定量確認できる。
- **実現性: 高。** RC1（2026-08-04）以降に CI マトリクスへ allow-failure 枠で 3.15 を追加 → GA 後に `requires-python = ">=3.13,<3.16"` へ拡大。
- **リスク: 中(限定的)。** pystray/pynput の 3.15 互換が unknown。CI 先行追加はまさにこれを検出するための施策であり、壊れた場合は 4 位（バックエンドシーム）のトリガーが発火する。

### 🥉 3 位: CLI→デーモン処理委譲（named pipe 経由のシングルインスタンス化）

- **効果: 最大級（EDR 環境限定）。** デーモン稼働中に `press <cmd>` を実行した場合、変換をデーモン側で行い CLI は薄いクライアントになる。プロセス生成 1 回 +
  最小 import（~10 ファイル）まで削減でき、「ホットキーは速いが CLI は遅い」という
  EDR 環境の残存ギャップを閉じる。Windows named pipe（`CreateNamedPipe`）は
  ctypes 直叩きで実装可能（`clipboard.py` と同パターン、外部依存ゼロ）。
- **実現性: 中。** プロトコル設計（コマンド名 + kwargs の JSON 1 往復）、
  デーモン側 pipe サーバスレッド、CLI 側「pipe があれば委譲 / なければ従来動作」の
  フォールバックが必要。挙動互換の担保（exit code / stderr / --in/--out フラグ）に
  テスト工数がかかる。
- **リスク: 中。** DLP から見ると「常駐プロセスへのローカル IPC」が新たな監視面になるが、named pipe はブラウザ等が常用する標準的手法で異常シグネチャ性は低い。
  **破壊的ではない**（デーモン不在時は完全に従来動作）。
- **判定: v2 の「トリガー待ち」から「v0.7.0 候補に格上げ」を提案。** 理由: 配布版利用が始まる v1.0.0 前に入れておくと、署名（1 位)と合わせて EDR 対応が完成形になる。

### 4 位: pystray/pynput バックエンドシーム + daemon.py パッケージ分割（構造リファクタリング）

- **効果: 直接の速度効果なし（保守性・供給網リスク対応）。** ただし 3 位を実装するなら daemon.py はさらに肥大化する（863 行 + pipe サーバ）ため、**3 位の前提工事**として価値が上がった。
- **実現性: 高。** v2 Option B-1/B-2 の内容そのまま: `press/daemon/` 分割
  （`_tray` / `_hotkeys` / `_lifecycle` / `_dispatch` / `_pipe`）+ pystray/pynput を
  Protocol 越しに隔離。公開 API 4 関数は `__init__.py` で維持し外部互換を保つ。
- **リスク: 低〜中。** diff は大きいがテスト済み領域の機械的移動が主。可逆。

### 5 位: zipapp（.pyz）配布によるファイルオープン数削減

- **効果: 中（理論値）。** 残存 40 オープンをさらに圧縮できる可能性はあるが、
  Phase 1 で 106→40 に削減済みのため**限界効用が v2 時点より低下**。
- **実現性/リスク: 中/中。** ctypes・Win32 互換検証 + 配布チャネル増。
- **判定: トリガー据え置き**（「オープン数起因の遅延報告が配布版で継続」した場合のみ）。3 位が入ればさらに不要になる公算が大きい。

### 6 位: src/ レイアウト移行

- **効果: EDR とは無関係（開発体験・パッケージング衛生）。** CI の `PYTHONPATH: .` ハック除去と「インストール済み配布物をテストする」保証が得られる。
- **リスク: 事実上一方通行（破壊的）。** 履歴が荒れる。
- **判定: v1.0.0 の PyPI 公開直前に単独 PR で実施**（それまで据え置き）。破壊的だがメリット（公開パッケージの品質保証）がその時点で発生するため。

### 圏外（引き続き見送り、再調査済み）

- **Nuitka / mypyc / ネイティブ移植**: Nuitka の AV 誤検知問題は解消の公式発表なし。署名（1 位）実施後も、ゼロ依存 CLI 設計の放棄に見合う利得がない。
- **Azure Artifact Signing**: 日本の個人開発者は Public Trust 対象外（米加限定)のため現時点で選択不可。対象地域が拡大したら 1 位の代替として再評価。
- **whitespace 正規表現統合等のマイクロ最適化**: 実測で効果なしと確認済み（`project_performance_benchmarks` 記録)。再着手しない。

---

## Part 3 — 実施計画（フェーズ別・承認待ち）

| Phase | 内容 | 対応ランク | 工数 | 破壊性 |
|---|---|---|---|---|
| **A** | SignPath Foundation 申請（Code signing policy ページ新設 + MFA 確認 + 申請 + `release.yml` 署名ステップ） | 1 位 | ~2日 + 審査待ち | なし |
| **B** | Python 3.15 を CI allow-failure で追加（RC1 = 2026-08-04 以降）→ GA 後 `<3.16` 開放 | 2 位 | ~半日 ×2 回 | なし |
| **C** | daemon パッケージ分割 + バックエンド Protocol シーム（B-1/B-2） | 4 位 | ~2〜3日 | なし(可逆) |
| **D** | CLI→デーモン named pipe 委譲(C の完了を前提) | 3 位 | ~1 週間 | なし(フォールバック維持) |
| **E**(トリガー) | zipapp / src/ レイアウト / pystray 置換 | 5・6 位ほか | — | 部分的 |

**推奨順序: A → B → C → D**（審査待ち・リリース日程という外部イベントに
合わせて A/B を先行し、コード構造は C→D の依存順で進める）。
Phase E は従来どおりトリガー発火まで着手しない。

---

## Part 4 — 実施記録（2026-07-09〜10、ユーザー指示「推奨順で全て対応」）

### Phase A ✅ 署名は「承認即適用」状態まで準備（commit 26bc355）

- `docs/dev/code-signing.md` 新設 — SignPath Foundation が要求する
  **Code signing policy**（committers / approvers / privacy policy）を掲載。
  README にも規約どおりの文言を追加。
- `release.yml` に `sign-windows-exe` ジョブ（`signpath/github-action-submit-signing-request@v2`）を追加。
  **`vars.SIGNPATH_ORGANIZATION_ID` が未設定の間はスキップ**され、現在のリリースは
  一切変わらない。承認後は「リポジトリ変数 3 つ + シークレット 1 つを設定する」だけで
  有効化され、**ワークフロー変更は不要**。
- `create-release` は署名済みアーティファクトがあればそれを配布し、
  SHA-256 は**署名後に計算**するため常にリリース物と一致する。
- 申請そのものはユーザーが実施（本計画の前提どおり）。手順は `docs/dev/code-signing.md`
  の「Activation checklist」。

### Phase B ✅ Python 3.15 先行レーン（commit c071e3d）

- `ci.yml` に 3.15 を `continue-on-error` の experimental レーンとして
  Ubuntu/Windows 両方に追加。`requires-python = ">=3.13,<3.16"`。
- `uv python install 3.15` が 3.15.0b3 を解決することをローカルで確認済み。
- GA（2026-10-01）後に experimental フラグを外す運用。

### Phase C ✅ daemon 分割 + バックエンドシーム（commit 6a3e0b8）

- `daemon.py`（863 行 / 8 責務）→ `press/daemon/` パッケージへ分割。
  公開 API 4 関数は `__init__.py` で維持し、外部インターフェース不変。
- **pystray / pynput の import は `_backends.py` のみ**に隔離（`TrayIcon` /
  `KeyListener` Protocol 越し）。v2 で棚上げした B-2 シームが完成し、
  pystray 置換は 1 モジュール改修で済むようになった。
- 実機検証: デーモン起動（トレイ + フック）→ 変換ディスパッチ → 停止 まで確認。

### Phase D ✅ CLI→デーモン named pipe 委譲（commit 2a110e0）

- 実測（Windows 11 / audit hook による open 数）:

  | コマンド | 委譲時 | ローカル | 壁時計 |
  |---|---|---|---|
  | `fix-encoding` | **55** | 155 | 151ms → 100ms |
  | `halfwidth` | 55 | 56 | ほぼ同等 |
  | `nfc` / `sort` | 55 | 51〜57 | 同等 |

  → **効果はコマンドのimport重量に比例**。全コマンドが一定コストに平坦化される。

- **計画時の想定と実測が食い違った点（重要）**:
  当初実装では `press._pipe` がモジュール先頭で `ctypes` + `threading` を import して
  おり、**デーモン非稼働時に 54 → 61 opens の回帰**が発生した。
  「委譲で速くするはずの環境（デーモンなし EDR 機）を逆に遅くする」ため、
  - PID ファイルの `stat` による**軽量ゲート**を先に置き、
  - ctypes は**ゲート通過後に遅延 import**、
  - `pathlib`（20 opens）を避けて PID パスを `os.path` で再導出（`press._paths` と
    一致することをテストで固定）
  に修正。回帰は +7 → +2 opens に縮小した。
  この「ゲートはパイプより安くなければならない」という制約は
  `docs/dev/architecture.md` と `CLAUDE.md` に明記済み。

- 挙動互換: デーモン不在 / stale PID / 応答なし（2秒デッドライン）/ 不正応答は
  すべてローカル変換へフォールバック。`PRESS_NO_DAEMON=1` で完全に無効化可能。
  CLI フラグはリクエストに同梱され、デーモンの config 既定値より優先される。
  パイプ経由で到達できるのはレジストリ変換のみ（`hold` / `clear` / `dict` は拒否）。
  DACL 既定（本人 + 管理者）+ `PIPE_REJECT_REMOTE_CLIENTS`。

- テスト: `test/unit/test_pipe.py` 31 件（プロトコル / サーバ検証 / ゲート /
  import バジェット / CLI 互換）。全体 665 passed。

### 残タスク

| 項目 | 状態 |
|---|---|
| SignPath Foundation 申請 | **ユーザー実施待ち**（承認後は変数設定のみ） |
| 3.15 GA 後に experimental を外す | 2026-10-01 以降 |
| Phase E（zipapp / src/ レイアウト / pystray 置換） | トリガー待ち（据え置き） |

---

## 出典（本計画 v3 の新規根拠）

- SignPath Foundation 適格条件: https://signpath.org/terms.html / https://signpath.io/solutions/open-source-community
- Certum Open Source Code Signing（€69/更新 €29、459 日制限）: https://shop.certum.eu/code-signing.html / https://piers.rocks/2025/10/30/certum-open-source-code-sign.html
- Azure Artifact Signing 提供地域・価格: https://azure.microsoft.com/en-us/products/artifact-signing / https://learn.microsoft.com/en-us/azure/artifact-signing/faq
- Python 3.15 スケジュール（PEP 790）と起動高速化: https://docs.python.org/3.15/whatsnew/3.15.html / https://peps.python.org/pep-0790/
- PyInstaller 6.21.0（3.14/3.15 対応）: https://pyinstaller.org/en/stable/CHANGES.html
- pystray 0.19.5 据え置き: https://pypi.org/project/pystray/
- Defender performance mode（据え置き確認）: https://learn.microsoft.com/en-us/defender-endpoint/microsoft-defender-endpoint-antivirus-performance-mode
- v2 までの根拠は `EDR_TOOLS_SURVEY.md` / `EDR_PERFORMANCE_PLAN.md` / `REFACTORING_PLAN.md` の出典欄を参照。
