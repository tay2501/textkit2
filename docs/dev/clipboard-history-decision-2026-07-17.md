# クリップボード履歴管理機能 — 導入判断ドキュメント

**Date:** 2026-07-17
**Question:** クリップボード履歴管理を (A) textkit2 に統合するか、(B) 別ソフト・別リポジトリにするか、(C) そもそも作るのがナンセンスか。

---

## 1. 調査結果(2026-07-17 時点の一次情報)

### 標準機能: Windows 11 クリップボード履歴 (Win+V)

| 項目 | 仕様 |
|---|---|
| 最大件数 | **25 件**(ピン留め以外は押し出し) |
| 1 件サイズ上限 | 約 4 MB(テキスト/HTML/ビットマップ) |
| 再起動 | ピン留め以外は消える |
| 検索 | なし(一覧スクロールのみ) |
| 同期 | Microsoft アカウント経由のクラウド同期(オプトイン) |
| 除外形式 | `ExcludeClipboardContentFromMonitorProcessing` / `CanIncludeInClipboardHistory` を尊重([Microsoft Learn – Clipboard Formats](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-formats)) |

### サードパーティ市場は現役(=需要は実在)

| ツール | 最新版 | 更新日 | 特徴 |
|---|---|---|---|
| [Ditto](https://github.com/sabrogden/Ditto/releases) | 3.25.113 | 2025-09-27 | GPL-3.0、SQLite 保存、検索、6,100+ stars |
| [CopyQ](https://github.com/hluk/CopyQ/releases/tag/v11.0.0) | 11.0.0 | 2025-08-22 | タブ・スクリプト・[除外形式を尊重](https://copyq.readthedocs.io/en/latest/security.html) |
| [Clibor](https://chigusa-web.com/clibor/history/) | 2.3.4 | 2025-02-02 | 日本製・テキスト特化・最大 10,000 件・**FIFO/LIFO モード**・定型文 |

### セキュリティ上の重要事実

- 除外形式(`CF_CLIPBOARD_VIEWER_IGNORE` 等)は**任意協力**であり強制力はない。KeePass/KeePassXC/Bitwarden が設定し、行儀の良いマネージャ(CopyQ [PR #2500](https://github.com/hluk/CopyQ/pull/2500)、Win+V)だけが尊重する
- **press 自身が genpass で `sensitive=True`(除外形式 3 種)を送出する側**。press が履歴機能を持つなら、これらの形式を尊重する監視側実装が論理的必然(自分が出すマークを自分が無視したら自己矛盾)
- 履歴の永続化は「コピーした全て(パスワード・個人情報含む)をディスクに書く」行為。Ditto は平文 SQLite が既定。press には既に DPAPI 基盤(`press._dpapi`、hold.txt で実運用中)がある

---

## 2. 「ナンセンスか?」への回答 — **ナンセンスではないが、汎用品を作るのはナンセンス**

- Ditto/CopyQ/Clibor が 2025 年も活発に更新され続けている = 標準 Win+V(25件・検索なし・揮発)では足りないユーザーが確実にいる。**需要は本物**
- ただし「汎用履歴マネージャ」を今から新作するのは車輪の再発明:
  - 一覧ポップアップ UI(Clibor の Ctrl×2 等)が UX の本体であり、press には GUI 基盤がない。ここで勝負したら Clibor/Ditto に勝てない
  - 検索・画像対応・定型文などを追うと際限なくスコープが膨らむ
- **press が作る意味があるのは press にしかない交差点だけ**:
  1. **履歴 × 変換** — 「2 つ前にコピーした TSV を markdown-table にして貼る」は既存ツールのどれも一手でできない(CopyQ は JS スクリプトが必要)
  2. **セキュリティ・ファースト履歴** — 除外形式の尊重 + DPAPI 暗号化保存 + 既定で少件数・自動期限。平文 SQLite の Ditto との明確な差別化

---

## 3. 配置の選択肢比較

| 案 | 評価 | 理由 |
|---|---|---|
| **A. textkit2 に統合(daemon のオプション機能)** | ✅ **推奨** | 下記参照 |
| B. 別ソフト・別リポジトリ | ❌ 非推奨 | ①`clipboard.py`/daemon/トレイ/パイプ/DPAPI/TOML 基盤の複製 or 共有ライブラリ化の維持コスト(ソロ開発で二重管理)。②**常駐が 2 つになり、press の ClipboardGuard(嵐検知)と新ソフトの監視が同一クリップボードを取り合う** — 自社製品同士で競合する設計は技術的に不合理 |
| C. 同一ソフト・別リポジトリ(プラグイン) | ❌ 非推奨 | press にプラグイン機構はなく、この 1 機能のために作るのは過剰設計(YAGNI) |
| D. 完全見送り(Win+V/Clibor 併用) | △ 次点 | 現状維持コストゼロ。ただし「履歴×変換」という press 固有の価値を放棄する |

**案 A の根拠 — 基盤の約 7 割が既に存在する:**

| 必要部品 | textkit2 の既存資産 |
|---|---|
| クリップボード監視 | `_ClipboardMonitorWindow`(WM_CLIPBOARDUPDATE、ClipboardGuard で実運用中) |
| 暗号化保存 | `press._dpapi`(hold.txt で実運用中) |
| 常駐・ホットキー・トレイ | daemon パッケージ一式 |
| CLI/daemon 間通信 | 名前付きパイプ(セキュリティ強化済み) |
| 設定 | TOML `PressConfig`(`[history]` セクションを足すだけ) |
| 除外形式の知識 | `_SENSITIVE_FORMATS`(genpass で送出側を実装済み) |

なお 2026-07-17 のギャップ分析では履歴を「プロダクト境界外」として見送った。本ドキュメントはこれを部分改訂する: **汎用履歴マネージャとしては見送りのまま**。「変換ツールの入力バッファ」としての最小履歴は境界内、という整理。

---

## 4. 推奨スコープ(Phase 5 案 — 承認待ち、実装はしない)

### Phase 5A: メモリ内履歴 + FIFO/LIFO(小規模)

- daemon 内テキスト専用リングバッファ(既定 20 件、`[history] size` で変更)— **メモリのみ、ディスク書き込みなし**(セキュリティ論点を最小化)
- 除外形式(`ExcludeClipboardContentFromMonitorProcessing` / `CF_CLIPBOARD_VIEWER_IGNORE` / `CanIncludeInClipboardHistory`)が付いたコピーは**記録しない**(必須要件)
- ホットキー: 「1 つ前 / 1 つ後の履歴をクリップボードへ復元」(サイクル貼り付け = Clibor の FIFO/LIFO 相当、**UI 不要**)
- CLI: `press history list / get N / clear`(パイプ経由で daemon に照会)
- `history get 2 | press markdown-table -C` で「履歴×変換」が即成立

### Phase 5B(5A の利用実績を見てから)

- DPAPI 暗号化での永続化(オプトイン)+ ピン留め
- `press chain` との統合(`press history get 2 --chain cleanup`)

### 作らないもの(明文化)

- 一覧ポップアップ GUI(Win+V/Clibor の領分。press は CLI/ホットキーで完結)
- 画像・ファイル履歴(text-only の設計原則維持)
- クラウド同期・検索 UI

---

## 5. リスクと対策

| リスク | 対策 |
|---|---|
| プロダクトの焦点ぼけ(「変換ツール」→「何でも屋」) | 履歴は既定 **無効**(`[history] enabled = false`)。変換の入力源という位置づけを README で明示 |
| 常時監視による EDR 負荷増 | ClipboardGuard と同一の監視ウィンドウを共用(監視は 1 本のまま) |
| 機密の意図しない保持 | Phase 5A はメモリのみ+除外形式尊重+`press history clear`。永続化は 5B でオプトイン |
| Win+V との重複感 | 25 件・検索なし・揮発という Win+V の実制約と、「履歴×変換」の一手が差別化 |

---

## 6. 結論

1. クリップボード履歴は**ナンセンスではない**(市場が現役で証明)。ただし汎用マネージャの新作は不合理
2. **別リポジトリ化は技術的に不利**(基盤複製 + 自社常駐同士のクリップボード競合)
3. 推奨は **textkit2 統合・既定無効のオプション機能・Phase 5A(メモリ内 FIFO/LIFO + CLI)から**
4. 着手はこのドキュメントの承認後(実装コードは未着手)

---

## 7. 改訂(同日追記): 履歴ではなく「変換前に戻す」(undo)を第一候補とする

§4 の Phase 5A よりさらに狭く深い代替案として **undo(変換前クリップボードの復元)** を検討した結果、こちらを第一候補に格上げする。

### なぜ undo が履歴より優れるか

| 観点 | 履歴 (§4 Phase 5A) | undo |
|---|---|---|
| 解決する痛点 | 「前にコピーしたものを再利用したい」(Win+V/Clibor の領分と重複) | 「**変換をミスった / 意図と違った**」— press 固有の痛点で、現状復旧不能 |
| クリップボード監視 | 必要(全コピーを見る) | **不要**(press が自分で書き換える瞬間だけスナップショット) |
| Clibor/Ditto/Win+V との競合 | 部分的に競合 | **ゼロ**(エディタの Ctrl+Z に相当する自社操作の取り消し) |
| 機密混入リスク | 全コピーが対象 | 書き換え直前の 1 件のみ。除外形式付きならスナップショットしない |
| EDR 追加負荷 | 常時監視(既存窓共用で軽減) | daemon 経路はメモリのみ = **ゼロ** |
| プロダクト整合 | 「変換の入力バッファ」と再定義が必要 | 「変換ツールの undo」— 説明不要 |

### 設計スケッチ(承認後に実装)

- **スナップショット点**: press がクリップボードを書き換える直前のみ — daemon `dispatch()` と CLI `-C` 経路
- **保存先**: daemon 稼働時はメモリ(単一スロット、将来はリング 5 件)。daemon なし CLI はオプトインで DPAPI ファイル(hold.txt と同方式)
- **復元**: `press undo`(CLI)+ ホットキー。**スワップ方式**(undo をもう一度で redo)
- **機密ガード**: 書き換え前クリップボードに除外形式(`_SENSITIVE_FORMATS` / `CF_CLIPBOARD_VIEWER_IGNORE`)が付いていればスナップショットしない — genpass 直後のパスワードを undo 領域に残さない
- **限界(明文化)**: press 起因の書き換えのみが対象。ユーザーの通常コピーで消えた内容の復元は対象外(それは Win+V/Clibor の領分)

### 改訂後の推奨順位

1. **undo(変換前に戻す)** — 小規模・監視不要・競合ゼロ → **✅ 実装済(2026-07-17)**: `press undo` + daemon `Shift+Z`。`clear` も undo 対象に含めた(誤爆ワイプの復旧)。genpass はスナップショット経路外(v1 スコープ)
2. 履歴 Phase 5A(メモリ内 FIFO/LIFO)— undo 運用後に需要が残れば
3. 履歴 Phase 5B(DPAPI 永続化)— 5A の実績次第
