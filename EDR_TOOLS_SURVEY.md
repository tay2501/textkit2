# エンドポイント監視エージェント カテゴリ別サーベイ — press (textkit2) 視点

> 調査ドキュメント（**ナレッジとして保存**）。2026-07-03 作成。
> 目的: PC 環境ごとに press の体感速度が異なる原因である「常駐監視エージェント」を
> カテゴリ別に整理し、各カテゴリが press のどの動作に干渉するかをマップする。
> 対応案ランキングと改修計画は `EDR_PERFORMANCE_PLAN.md` を参照。

---

## 0. 前提: press が発生させる「監視対象イベント」

実測値（2026-07-03、audit hook 計測）:

| press の動作 | 発生イベント | 監視エージェントから見えるもの |
|---|---|---|
| CLI 起動（毎回） | プロセス生成 1 回 + **ファイルオープン約 106 件**（stdlib 87 / site-packages 11 / press 8）+ dist-info ディレクトリ走査 | 新プロセス起動、大量の .py/.pyc 読み込み |
| 変換実行 | クリップボード読み取り → 書き込み | **クリップボード操作（DLP の主要監視対象）** |
| デーモン起動 | 常駐プロセス + `WH_KEYBOARD_LL` フック + `GlobalHotKeys` | **低レベルキーボードフック（キーロガー類似シグネチャ）** |
| ClipboardGuard (hold) | `WM_CLIPBOARDUPDATE` 監視 + クリップボード即時再書き込み | 高頻度クリップボード書き換え |
| ログ/状態ファイル | `%APPDATA%\press\` への書き込み | ユーザーディレクトリへのファイル書き込み |

---

## 1. カテゴリ A — EDR / XDR（挙動検知型エンドポイント防御）

**代表製品（2026 年時点の主要 3 強 + α）:**

| 製品 | アーキテクチャ | 性能特性 |
|---|---|---|
| CrowdStrike Falcon | クラウドネイティブ。軽量カーネルセンサーがテレメトリを Threat Graph へ送信 | 解析をクラウドにオフロードし端末負荷は小さめ。ただし現場報告（HN 等）では invasive と評される |
| Microsoft Defender for Endpoint | OS 組込み。Defender AV と一体 | M365 E5 環境で標準。AV 部分の on-access スキャンが支配的 |
| SentinelOne Singularity | Storyline エンジンが**端末上で**全プロセス/ファイル操作をリアルタイム解析 | クラウド照会なしで応答する分、端末側 CPU を使う |
| その他 | Palo Alto Cortex XDR、Sophos Intercept X、Trend Micro Apex One、Cybereason、Elastic Defend | 同系統 |

**動作原理（press に効く部分）:**
- **ファイルシステム・ミニフィルタドライバ**が open/read/write/close をカーネルで捕捉し、
  ユーザーモードのスキャナに渡して検査（open 成功時にスキャン、write アクセスなら close 前に再スキャン）。
- **プロセス生成フック** + イベントエンリッチメント: 署名検証・PE 解析・ハッシュ計算・
  エントロピー計算（Elastic 公式ドキュメントが明記する CPU 負荷源）。
- 複数エージェント共存時の**フィードバックループ**（互いのスキャンを互いが検査）が最悪の劣化要因。

**press への影響:** 起動のたびに「新プロセス + 106 ファイルオープン」が全て検査対象。
インタープリタ型 CLI の典型的ペナルティ。キャッシュ後は軽微（+10〜50ms 級）だが、
初回・シグネチャ更新後・低スペック機では顕著。

## 2. カテゴリ B — エンドポイント DLP（情報漏洩対策）★DGAgent はここ

**代表製品:**

| 製品 | 特記事項 |
|---|---|
| **Digital Guardian (DGAgent)** | 最も包括的な DLP の一つ。カーネルレベルでファイル・クリップボード・キーボード・印刷・スクリーンショットを監視。`DgAgent.exe`/`dgsvc` の高 CPU 事例が多数報告されており、公式ガイドは「他のセキュリティ製品と**相互に除外設定**すること」を明記 |
| Forcepoint DLP | copy/paste・画面キャプチャ・印刷・リムーバブルメディアを単一ポリシーで監視（26.1 で Linux もクリップボード監視対応） |
| Symantec (Broadcom) DLP | クリップボード貼り付け検査、ブラウザ API 統合 |
| Microsoft Purview Endpoint DLP | クラウドネイティブ、Windows 組込みで比較的軽量 |
| Trellix (旧 McAfee) DLP | 同系統 |

**動作原理（press に効く部分）:**
- **クリップボード操作のフック** — press の中核機能そのものが監視・評価対象。
  コピー/ペーストごとにコンテンツ分類・ポリシー評価が走る。
- ペースト操作の傍受（press の ClipboardGuard Layer 2 と**同じ場所にフックする**）。
- ファイル操作のコンテンツ検査（タグ付きファイルはさらに重い）。

**press への影響（最重要カテゴリ）:**
1. 変換のたびの get/set クリップボードが DLP 評価を通る → 変換自体の体感遅延。
2. ClipboardGuard の即時再書き込みは DLP のクリップボード監視と**相互作用**し得る
   （高頻度書き換え → 評価ループ → CPU スパイク、または書き込みブロック）。
3. `WH_KEYBOARD_LL` + クリップボード常時アクセス + 無署名バイナリ = **DLP アラートの
   典型シグネチャ**。性能以前にブロック・検疫のリスク。

## 3. カテゴリ C — AV / EPP（シグネチャ型アンチウイルス）

**代表:** Microsoft Defender AV（最普及）、ESET、Kaspersky、Trellix ENS、Sophos。

**動作原理:** on-access スキャン（open 時 + write 後 close 時）、スクリプトは AMSI 経由。
**スキャン結果はキャッシュ**され、ファイル不変・定義不変の間は再スキャンされない
（= 「初回だけ遅い」現象の正体。python-forum 等で「初回 60 秒 → 以後高速」の報告）。

**press への影響:** 初回起動と定義更新直後に .pyc 群がフルスキャン。
PyInstaller **--onefile は毎回テンポラリに自己展開するため毎回フルスキャン**される
（PyInstaller コミュニティで既知）。--onedir は初回のみ。

## 4. カテゴリ D — IT 資産管理・PC 操作ログ（日本企業に特有の負荷源）

**代表製品（国内シェア上位）:**

| 製品 | コミュニティでの性能評価 |
|---|---|
| **SKYSEA Client View** | ITreview/知恵袋で「とにかく重い」「Excel/Word レベルで謎のハングアップ」「重いアプリと競合するとエージェントが落ちる」等の報告多数 |
| **AssetView** | 「業務に支障が出るレベルで重い」「8GB 機でメモリ半分消費、使用率 90% 到達」報告 |
| **LanScope（MOTEX）** | 相対的に軽量との比較評価（クライアント CPU 負荷が低い設計） |
| MaLion、InterSafe 等 | 同系統 |

**動作原理:** 全ファイル操作ログ、ウィンドウタイトル記録、**クリップボードログ**、
印刷ログ、アプリ起動ログ。EDR ほど高度ではないが**フック点はほぼ同じ**で、
実装品質による性能差が大きい（レビュー評価が割れる理由）。

**press への影響:** 「操作ログ系が入った国内企業 PC」は press の想定利用環境そのもの。
プロセス起動ログ + ファイル操作ログで CLI 起動が重くなり、クリップボードログが
変換ごとに走る。**PC によって速度が違う最大の説明変数はこのカテゴリ + B の有無**である
可能性が高い。

## 5. カテゴリ E — アプリケーション制御 / 許可リスト

**代表:** AppLocker、WDAC / Smart App Control（Windows 11）、Carbon Black App Control
（旧 Bit9）、Airlock、Ivanti Application Control。SmartScreen（レピュテーション評価）。

**動作原理:** プロセス生成時に署名・ハッシュ・レピュテーションを評価。
- 無署名ファイルは**バージョンごとにゼロからレピュテーション構築**が必要。
- Smart App Control は「無署名 + レピュテーションなし」を**実行ブロック**。
- EV 証明書の即時信頼特典は **2024 年に廃止**され、OV と同じ蓄積プロセスに。

**press への影響:** pip インストール版は python.exe（署名済み）の実行なので影響小。
**PyInstaller 配布時が本番**: 無署名 exe はハッシュが変わるたび（=リリースごと）に
クラウド照会・ブロック・警告の対象。署名 + 同一 publisher の継続が唯一の緩和策。

## 6. カテゴリ F — ネットワーク系エージェント（SWG/ZTNA/プロキシ）

**代表:** Zscaler Client Connector、Netskope Client、Cisco Secure Client、
i-FILTER（国内）。

**press への影響: ほぼなし。** press はネットワーク I/O を行わない
（`importlib.metadata` の走査もローカルディスクのみ）。このカテゴリは除外してよい。

---

## 7. まとめ — フック点 × press 影響マップ

| フック点 | A: EDR | B: DLP | C: AV | D: 資産管理 | E: アプリ制御 | press の該当動作 |
|---|---|---|---|---|---|---|
| プロセス生成 | ● | ○ | ○ | ● | ● | CLI 起動（毎回） |
| ファイルオープン | ● | ● | ● | ● | — | 起動時 106 オープン |
| ファイル書き込み | ● | ● | ● | ● | — | ログ/hold/config |
| **クリップボード** | △ | **●** | — | **●** | — | **全変換コマンド** |
| **キーボードフック検知** | ● | **●** | △ | △ | — | **デーモン/Guard Layer 2** |
| 署名/レピュテーション | ● | △ | ● | — | **●** | PyInstaller 配布時 |

**結論:**
1. 「PC によって速度が違う」主因は **B（DLP）と D（国内資産管理）の有無・製品差**。
   同じカテゴリでも SKYSEA と LanScope で体感が大きく違うことがレビューから裏付けられる。
2. press 側で制御できるのは (a) 起動時のプロセス/ファイルオープン量、
   (b) 配布形態と署名、(c) クリップボード/フック動作の設定可能性、
   (d) 組織側除外設定の申請しやすさ（ドキュメント）— の 4 点。
3. 最大の構造的回避策は**常駐デーモン**（起動イベント自体を消す）で、press は実装済み。

## 出典

- EDR 3 強比較: [Best EDR Platforms 2026](https://www.decryptiondigest.com/blog/best-edr-platforms-2026) / [SentinelOne: Top 10 EDR](https://www.sentinelone.com/cybersecurity-101/endpoint-security/edr-solutions/)
- ミニフィルタ動作原理: [Microsoft Scanner Minifilter Sample](https://learn.microsoft.com/en-us/samples/microsoft/windows-driver-samples/scanner-file-system-minifilter-driver/) / [Evading EDR Ch.6](https://www.oreilly.com/library/view/evading-edr/9781098168742/xhtml/chapter6.xhtml)
- エンリッチメント負荷・フィードバックループ・Trusted Apps: [Elastic Endpoint PerformanceIssues-Windows.md](https://github.com/elastic/endpoint/blob/main/PerformanceIssues-Windows.md)
- DLP 比較: [Purview vs Forcepoint vs Symantec](https://technologymatch.com/blog/microsoft-purview-vs-forcepoint-vs-symantec-dlp) / [15 Best DLP 2026](https://underdefense.com/blog/dlp-solutions/)
- DGAgent 高 CPU・相互除外: [DgAgent.exe 解説](https://www.file.net/process/dgagent.exe.html) / [DG Endpoint Technical Support Guidebook (PDF)](https://hstechdocs.helpsystems.com/kbfiles/digitalguardian/PDF/Endpoint_Technical_Support_Guidebook_Windows.pdf)
- 国内資産管理の性能レビュー: [SKYSEA ITreview](https://www.itreview.jp/products/skysea-client-view/reviews) / [AssetView ITトレンド口コミ](https://it-trend.jp/it_asset_management/10849/review/168159) / [Yahoo!知恵袋](https://detail.chiebukuro.yahoo.co.jp/qa/question_detail/q14244452859)
- SmartScreen/署名: [SmartScreen reputation (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) / [DigiCert: EV と SmartScreen](https://knowledge.digicert.com/alerts/ev-signed-application-showing-microsoft-defender-smartscreen-warnings)
- Dev Drive パフォーマンスモード: [Microsoft Learn](https://learn.microsoft.com/en-us/defender-endpoint/microsoft-defender-endpoint-antivirus-performance-mode)
- PyInstaller onefile 毎回スキャン: [PyInstaller Google Groups](https://groups.google.com/g/pyinstaller/c/ND3AYeahN3I)
- Nuitka 誤検知: [Nuitka Issue #1470](https://github.com/Nuitka/Nuitka/issues/1470) / [公式 Common Issues](https://nuitka.net/user-documentation/common-issue-solutions.html)
- 現場の声: [Hacker News: Falcon agent](https://news.ycombinator.com/item?id=41032329) / [python-forum: Defender 初回起動遅延](https://python-forum.io/thread-4980.html)
