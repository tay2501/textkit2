# EDR/DLP 環境パフォーマンス対応 — 対応案ランキングと改修計画

> 計画ドキュメント（**実施記録つき・ナレッジとして保存**）。2026-07-03 作成。
> 前提調査: `EDR_TOOLS_SURVEY.md`（カテゴリ別エージェントサーベイ）。
> 実測ベースライン（ARM コンテナ）: CLI 起動 121ms/回・ファイルオープン 106 件・
> import 178 モジュール。変換 @10KB 最遅 2.2ms、辞書 50k 行 28.4ms。

---

## Part 1 — 対応案ランキング

評価軸: **効果**（EDR/DLP 環境での体感改善）× **実現性**（press 側で完結するか）×
**リスク**（誤検知・保守負担・既存設計との整合）。
情報源: 公式ドキュメント + コミュニティ（Reddit/HN/Google Groups/GitHub Issues/
ITreview/知恵袋。X は有意な一次情報を発見できず — 検索性の問題で Reddit/HN が
開発者の実体験の主要ソースだった）。

### 🥇 1 位: 常駐デーモン利用の徹底（アーキテクチャで回避）

- **効果: 最大。** 監視エージェントの支配的コストは「プロセス生成 + 起動時 106 ファイル
  オープン」への介入。デーモン経由のホットキー実行はこれを**ゼロにする**
  （遅延 import は初回ディスパッチ後キャッシュ済み）。
- **実現性: 実装済み。** 不足しているのは「デーモンを既定の使い方にする」導線のみ
  （自動起動登録、ドキュメント上の位置づけ）。
- **リスク:** デーモン自体が DLP の監視対象（キーボードフック）である点は 4 位で対処。
- 裏付け: JetBrains・Elastic 等が公式に「常駐/信頼プロセス化」を推奨する構図と同型。

### 🥈 2 位: 起動時 I/O 削減（コード改修・即効）

- **効果: 中。** press 固有起動オーバーヘッドの約 20〜25% + dist-info ディレクトリ走査の
  削減。EDR 環境ではファイルオープン削減分が増幅されて効く。
  - `make_parser()` が `--version` 文字列を先行評価 → **毎回** `importlib.metadata`
    （累計 ~16ms、`email`→`urllib`→`ipaddress` 連鎖 + site-packages 走査）を読む。
    遅延 version action で完全回避可能。
  - `argcomplete`（~7ms + オープン数件）は補完実行時（`_ARGCOMPLETE` 環境変数設定時）
    のみ必要。ガードで通常起動から除外可能。
- **実現性: 高。** 数十行、外部依存なし、挙動不変（`--version`/補完の出力は同一）。
- **リスク: 最小。** 既存テストで検証可能。

### 🥉 3 位: 配布形態の最適化 — PyInstaller `--onedir` + コード署名

- **効果: 中〜大（配布版利用者に対して）。**
  - `--onefile` は毎回テンポラリへ自己展開 = **AV が毎回フルスキャン**
    （PyInstaller コミュニティで既知）。`--onedir` は初回スキャン後キャッシュが効く。
    → 既に docs/ROADMAP の方針であり正しい。維持。
  - **Authenticode 署名**: 無署名 exe はリリース（ハッシュ変更）ごとにレピュテーション
    がゼロリセットされ、SmartScreen/Smart App Control 環境で警告・ブロック。同一
    publisher で署名を継続するとレピュテーションが引き継がれる（EV の即時信頼特典は
    2024 年に廃止済みなので OV で開始してよい）。
- **実現性: 中。** 証明書取得コスト（年数万円〜）と CI 署名工程の追加。
- **リスク: 低。** 署名は誤検知も減らす方向にしか働かない。

### 4 位: 組織側ポリシー申請を「製品機能」にする（除外/Trusted App 手順書）— **見送り（2026-07-03 ユーザー判断）**

> OSS として配布しており利用者の監視ツール構成を把握できないため、組織固有の
> 申請テンプレートは作成しない。代替として Phase 3 を「ユーザー自身が環境を
> 診断できる仕組み」（既知エージェント検出 + セルフ診断ガイド）に変更。

- **効果: 大（適用できれば最大級）。** Elastic 公式ドキュメントが示す正攻法は
  「セキュリティ製品同士・信頼プロセスの**相互除外**」。DG の公式ガイドブックも
  同じことを明記している。press.exe（署名済み）を DLP/EDR の Trusted Application に
  登録してもらえば、ファイルスキャンとクリップボード評価の大半が消える。
- **実現性: press 側では書類まで。** 適用判断は情シス。だからこそ「そのまま提出できる
  除外申請テンプレート」（プロセス名・パス・ハッシュ・署名者・アクセス先一覧・
  必要権限の根拠）を docs に用意する価値が高い。
- **リスク:** なし（承認されなくても現状維持なだけ）。

### 5 位: DLP との衝突面の縮小（クリップボード/フック挙動の設定化・診断）

- **効果: 環境依存で大。** DGAgent・国内資産管理（SKYSEA 等）の**クリップボードログ/
  ペースト傍受**と press の ClipboardGuard・`WH_KEYBOARD_LL` は同じフック点で衝突する。
  - `intercept_paste_keys = false`（実装済みフラグ）を「DLP 環境向け推奨設定」として
    文書化。
  - `press daemon status --json` に「検知した監視エージェント」情報（実行中プロセス名の
    既知リスト照合）を追加すれば、環境差の診断が一気に楽になる（psutil で実装可能）。
- **実現性: 高（診断機能は小規模実装）。リスク: 低。**

### 6 位: Defender 環境限定 — Dev Drive / performance mode の案内

- **効果: 小〜中（開発者・上級者限定）。** 信頼済み Dev Drive 上では Defender が
  **非同期スキャン**になり、同期 open スキャンのブロッキングが消える。フォルダ除外より
  安全と Microsoft が明言。venv/リポジトリを Dev Drive に置く運用ガイドとして掲載価値
  あり。ただし第三者 EDR/DLP には効かない。
- **実現性: ドキュメントのみ。リスク: なし。**

### 7 位: zipapp（.pyz）化によるファイルオープン数削減

- **効果: 中（理論上）。** zipimport なら 106 オープン → アーカイブ 1 つ + stdlib に
  圧縮できる可能性。EDR のオープン単価が高い環境ほど効く。
- **実現性: 中。リスク: 中。** ctypes/Win32 まわりの互換検証が必要で、配布チャネルが
  もう 1 本増える。**Phase 4（トリガー付き将来枠）**。

### 圏外（見送り）: Nuitka/mypyc 等ネイティブ化、Rust/Go 移植

- Nuitka は **Hello World ですら AV 誤検知の報告**があり（GitHub Issue #1470、公式も
  Commercial プラン + 署名を前提に案内）、無署名では逆効果。起動最速化の効果はあるが、
  リスクと工数が Option 1〜3 の合計を上回る。移植は論外（ゼロ依存 CLI 設計の放棄）。

---

## Part 2 — 改修計画（フェーズ別）

### Phase 1 — 起動 I/O 削減 + 計測基盤（即実施可、~半日）

1. **遅延 `--version`**: `argparse` の `action="version"` をカスタム action に置き換え、
   `_version()`（importlib.metadata）を**表示時のみ**呼ぶ。
2. **argcomplete ガード**: `if "_ARGCOMPLETE" in os.environ:` のときだけ
   `argcomplete.autocomplete(parser)` を実行。
3. **ベンチの前倒し**: ROADMAP v0.6.0 の `test/perf/bench_startup.py` をこの機会に
   実装し、起動時間とオープン数（audit hook）の回帰を CI で監視。
   - 受け入れ基準: オープン数 ≤ 90（現状 106）、`--help`/`--version` 出力バイト同一、
     補完動作維持（`_ARGCOMPLETE` セットで従来どおり）。
- **影響範囲:** `__main__.py`、`test/perf/`（新規）、`ci.yml`。**可逆。**

### Phase 2 — 配布と署名（v1.0.0 マイルストーンに統合、~2 週間）

1. PyInstaller `--onedir` ビルドを CI の release workflow に追加（既定方針の実装）。
2. OV コード署名証明書を取得し、exe + インストーラに署名。リリースごとに同一
   publisher で継続署名（レピュテーション蓄積）。
3. リリースノートに SHA-256 を掲載（除外申請用）。
- **影響範囲:** `release.yml`、docs。**署名者情報以外は可逆。**

### Phase 3 — EDR/DLP 運用ドキュメント + 診断機能（~1 週間）

1. `docs/user/edr-environments.md` 新設:
   - カテゴリ別（EDR/DLP/資産管理）の症状と推奨設定
     （デーモン常用、`intercept_paste_keys = false`、hold 動作確認手順）。
   - **除外申請テンプレート**（プロセス名・インストールパス・署名者・
     アクセスするパス一覧 `%APPDATA%\press\*`・フック使用の根拠と無効化手段）。
   - Defender 環境向け Dev Drive 運用ガイド。
2. `press daemon status` に既知エージェント検出（DgAgent/CSFalconService/SentinelAgent/
   SkySeaClientView 等のプロセス名照合）を追加し、問い合わせ時の環境把握を自動化。
- **影響範囲:** docs、`daemon.py`（status 拡張 + テスト）。**可逆。**

### Phase 4 — トリガー付き将来枠

| 施策 | 実施トリガー |
|---|---|
| zipapp 配布 | Phase 1 実施後もオープン数起因の遅延報告が続く場合 |
| CLI→デーモン処理委譲（named pipe） | 「CLI 経由でも遅い」報告が配布版で継続する場合 |
| pystray 置換（既存計画 B-2） | Python 3.14+/Pillow 更新で破損、または v1.0.0 公開前 |

### 実施順序と工数まとめ

| Phase | 効果(ランキング対応) | 工数 | リスク | 不可逆性 |
|---|---|---|---|---|
| 1 | 2 位 | ~半日 | 最小 | なし |
| 2 | 3 位 | ~2 週間(証明書調達含む) | 低 | 実質なし |
| 3 | 1・4・5・6 位 | ~1 週間 | 低 | なし |
| 4 | 7 位ほか | トリガー待ち | 中 | 部分的 |

**推奨: Phase 1 → 3 → 2 の順**（コード改修 → ドキュメント/診断 → 調達を伴う署名）。
1 位のデーモン活用は Phase 3 のドキュメントで「既定の使い方」に格上げする。

---

## 選択

採用フェーズ: **Phase 1 + Phase 3（除外申請テンプレートを除き、セルフ診断に差し替え）**
（2026-07-03 ユーザー指示「推奨順番で改修」。4 位の申請テンプレートは OSS のため
利用者環境が不明であり見送り。）

### 実施結果（2026-07-03）

- **Phase 1 完了**: 遅延 `--version` action + `_ARGCOMPLETE` ガード +
  `test/perf/test_startup.py`（壁時計時間 / 遅延 import 契約 / オープン数バジェット）。
  実測: 変換コマンド実行のファイルオープン **108 → 40 件（-63%）**、
  import モジュール 180 → 102、起動時間 **-40%**（ARM 計測環境）。
- **Phase 3 完了**: `press daemon status --json` に `monitoring_agents`
  （既知エージェント検出、Defender/CrowdStrike/SentinelOne/Digital Guardian/
  Symantec DLP/Trellix/Cylance/Zscaler）を追加。
  `docs/user/edr-environments.md`（症状→原因→設定のセルフ診断ガイド）を新設。
- **Phase 2**: `release.yml` は既に `--onedir` ビルドだったため CI 変更不要。
  **コード署名は保留（2026-07-03 ユーザー判断）** — 証明書取得後に release
  workflow へ署名ステップを追加する。署名なしでも配布物検証ができるよう、
  リリースに **SHA-256 チェックサム**（`SHA256SUMS.txt` + リリースノート掲載）
  を追加済み。
- **追補（証明書以外の残タスク消化、2026-07-03）**: ROADMAP v0.6.0 の性能
  スイートを完成 — `test/perf/test_transforms.py`（全 36 コマンド @10KB ≤50ms、
  レジストリから自動列挙）と `test/perf/test_dictionary.py`（50k 行 ≤100ms）を
  追加し、通常 CI で常時実行。デーモン RSS/CPU ベンチのみ headless CI の制約で
  据え置き。

## 出典（ランキング根拠の主要ソース）

- [Elastic Endpoint PerformanceIssues-Windows.md](https://github.com/elastic/endpoint/blob/main/PerformanceIssues-Windows.md) — 負荷源の内訳と Trusted Applications による正攻法
- [Digital Guardian Endpoint Technical Support Guidebook](https://hstechdocs.helpsystems.com/kbfiles/digitalguardian/PDF/Endpoint_Technical_Support_Guidebook_Windows.pdf) — 相互除外の公式推奨
- [PyInstaller Google Groups: onefile と AV 毎回スキャン](https://groups.google.com/g/pyinstaller/c/ND3AYeahN3I)
- [Microsoft: SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) / [DigiCert: EV 特典廃止](https://knowledge.digicert.com/alerts/ev-signed-application-showing-microsoft-defender-smartscreen-warnings)
- [Microsoft: Dev Drive performance mode（非同期スキャン）](https://learn.microsoft.com/en-us/defender-endpoint/microsoft-defender-endpoint-antivirus-performance-mode)
- [Nuitka Issue #1470（誤検知）](https://github.com/Nuitka/Nuitka/issues/1470) / [Nuitka Common Issues](https://nuitka.net/user-documentation/common-issue-solutions.html)
- コミュニティ実体験: [HN: Falcon agent](https://news.ycombinator.com/item?id=41032329)、[python-forum: Defender 初回遅延](https://python-forum.io/thread-4980.html)、[SKYSEA ITreview](https://www.itreview.jp/products/skysea-client-view/reviews)、[AssetView 口コミ](https://it-trend.jp/it_asset_management/10849/review/168159)
