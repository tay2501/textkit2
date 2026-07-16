# Feature Gap Analysis — 競合ツール網羅調査と不足機能ランキング

**Date:** 2026-07-17
**Scope:** テキスト/クリップボード変換ツールの機能を網羅調査し、press に無いが有用な機能をランキング化。上位機能の追加計画を含む。

---

## 1. 調査対象ツール

| ツール | 分類 | 参照 |
|---|---|---|
| PowerToys Advanced Paste | クリップボード変換 (MS公式) | [Microsoft Learn](https://learn.microsoft.com/en-us/windows/powertoys/advanced-paste) |
| DevToys 2.0 | 開発者ユーティリティ集 (30+ tools) | [devtoys.app](https://devtoys.app/) |
| CopyQ | クリップボードマネージャ + スクリプト | [copyq.net](https://copyq.net/), [copyq-commands](https://github.com/hluk/copyq-commands) |
| Clibor | 日本製クリップボード履歴 + 整形 | [窓の杜](https://forest.watch.impress.co.jp/library/software/clibor/) |
| Boop | スクリプタブル・テキスト変換 (50+ scripts) | [boop.okat.best](https://boop.okat.best/), [Scripts](https://github.com/IvanMathy/Boop/tree/main/Scripts) |
| CyberChef | ブラウザ型データ変換 | (一般知識・操作カタログ参照) |

**press の現有機能 (2026-07-17 時点):** simple 34 / parametric 6 / dict / clear / hold / genpass / chain / pipelines / daemon+hotkey。

---

## 2. 不足機能ランキング

評価軸: ①対象ユーザー価値 (日本語圏 Windows 開発者・事務職) ②クリップボード変換ワークフロー適合 ③実装コスト ④依存方針適合 (新規依存を増やさない)。

| 順位 | 機能 | 根拠 (どのツールにあるか) | 実装コスト | 判定 |
|---|---|---|---|---|
| 1 | **ひらがな⇔カタカナ変換** | Clibor 圏の日本語ニーズ。jaconv は依存済みで `hira2kata`/`kata2hira` を提供 (v0.5.0, 2026-02-08 確認) | 極小 | ✅ 今回実装 |
| 2 | **ハッシュ生成 (SHA-256 等)** | DevToys Hash & Checksum / Boop SHA256 / CyberChef。チェックサム検証の定番。stdlib `hashlib` | 小 | ✅ 今回実装 |
| 3 | **正規表現置換** | Clibor「整形」の目玉機能 / CopyQ スクリプトの代表用途。汎用性最大。stdlib `re` | 小 | ✅ 今回実装 |
| 4 | **文字数カウント/統計** | Boop Count / DevToys Text Analyzer。原稿字数・SNS字数確認 | 小 | ✅ 今回実装 |
| 5 | **HTML エンコード** | DevToys HTML encoder。press は `html-decode` のみで非対称。stdlib `html.escape` | 極小 | ✅ 今回実装 |
| 6 | **TSV/CSV → Markdown 表** | PowerToys Advanced Paste (Paste as Markdown) / DevToys 系。Excel コピー→ドキュメント貼付の頻出動線。stdlib `csv` | 中 | ✅ 今回実装 |
| 7 | **行番号付与 / 行順反転** | Boop / Text Mechanic 系行ユーティリティ。既存 `lines.py` に自然に追加 | 小 | ✅ 今回実装 |
| 8 | Unix time ⇔ 日時変換 | DevToys Date converter / Boop | 小 | ⏳ 次回候補 |
| 9 | slugify (URL スラッグ化) | Boop | 小 | ⏳ 次回候補 |
| 10 | UUID 生成 | DevToys Generators (genpass の前例あり) | 小 | ⏳ 次回候補 |

### 見送り (理由付き)

| 機能 | 理由 |
|---|---|
| JSON ⇔ YAML | PyYAML の新規依存が必要。依存最小方針 (EDR スキャン面) に反する |
| クリップボード履歴 / FIFO | Clibor/Ditto/CopyQ の中核だが press は「変換」に特化。履歴は Win+V と棲み分け (プロダクト境界) |
| OCR / 音声変換 / QR | PowerToys・DevToys 領域。テキスト変換の範囲外、依存肥大 |
| JWT デコード | Base64 デコードで代替可能。ニッチ |
| lorem ipsum 生成 | 日本語圏ユーザー価値が低い |
| rot13 | 実用価値が低い |

---

## 3. 実装計画 (順位 1–7 → 新規 9 コマンド)

公式ドキュメント確認結果:

- **jaconv 0.5.0** (2026-02-08 更新): `hira2kata(text)` / `kata2hira(text)` — 引数は text のみ。依存済み (`pyproject.toml: jaconv>=0.5.0`)
- **hashlib** (Python 3.13 stdlib): `hashlib.new(name)` は未知アルゴリズムで `ValueError` を送出 → EAFP でそのまま活用
- **html** (stdlib): `html.escape(s, quote=True)` は `& < > " '` をエスケープ — `html.unescape` と往復整合
- **re** (Python 3.13 stdlib): `re.error` は 3.13 で `re.PatternError` にリネーム (旧名はエイリアスとして有効)
- **csv** (stdlib): `csv.reader` は引用符付きフィールド対応 — CSV の `"a,b"` を正しく 1 セルに

| コマンド | 別名 | 種別 | モジュール | 関数 |
|---|---|---|---|---|
| `katakana` | `kata` | simple | `transforms/kana.py` (新規) | `to_katakana` = jaconv.hira2kata |
| `hiragana` | `hira` | simple | `transforms/kana.py` (新規) | `to_hiragana` = jaconv.kata2hira |
| `hash` | `hs` | parametric (`--algo`, 既定 sha256) | `transforms/hashing.py` (新規) | `hash_text` |
| `replace` | `rp` | parametric (`--pattern/--repl/--ignore-case/--fixed`) | `transforms/replace.py` (新規) | `regex_replace` |
| `count` | `wc` | simple (レポート出力 — check-norm 前例) | `transforms/stats.py` (新規) | `count_text` |
| `html-encode` | `he` | simple | `transforms/escape.py` (追記) | `encode_html_entities` |
| `markdown-table` | `mdt` | simple (区切り自動判定: タブ優先→カンマ) | `transforms/table.py` (新規) | `to_markdown_table` |
| `number-lines` | `nl` | parametric (`--start`, `--sep`) | `transforms/lines.py` (追記) | `number_lines` |
| `reverse-lines` | `rl` | simple | `transforms/lines.py` (追記) | `reverse_lines` |

**設計判断:**

- 全て純関数 `fn(text, **kwargs) -> str`。新規依存ゼロ (jaconv 再利用 + stdlib のみ)
- レジストリ (`SIMPLE_COMMANDS` / `PARAMETRIC_COMMANDS`) 登録のみで CLI・daemon・pipe 委譲・`_LAZY` に自動配線
- `replace` は pattern 既定 `""` = 恒等変換 (hotkey 経路でも安全)。`--fixed` はリテラル置換 (repl の `\` も無効化) — 正規表現を知らないユーザー向け (Clibor 整形の代替)
- `hash` のアルゴリズム検証は `hashlib.new` の `ValueError` に委ねる (EAFP)。ダイジェスト対象は UTF-8 バイト列 (改行コードそのまま — ドキュメントに明記)
- 別名衝突チェック済み: `kata/hira/hs/rp/wc/he/mdt/nl/rl` は既存 34 別名と非衝突。parametric フラグは予約済み `-c/-C/-v/-q` と非衝突

**後続手順:** 実装 → test (unit 追加) → docs/user/transforms.md + CHANGELOG + README → `--help` (レジストリ help 文字列由来で自動) → ruff/mypy (win32+linux)/pytest → push (github-push-guardian)。
