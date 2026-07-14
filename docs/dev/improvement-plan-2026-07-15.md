# 改善計画(ランキング形式)— press (textkit2)

**作成日**: 2026-07-15
**根拠文書**: [adversarial-review-2026-07-15.md](adversarial-review-2026-07-15.md)
**ランキング基準**: `(実害の大きさ × 発生可能性 × ツールの信頼への影響) ÷ 実装コスト`
各項目に見積り工数・受け入れ条件・リスクを付す。**着手前にユーザー承認を得ること。**

> **実施状況(2026-07-15 更新)**: バッチ A(第 1・4・8 位)実施済み ✅ —
> クリップボード書き込みエラー処理、mutex per-user 化、LRESULT/GetMessageW/
> パイプタイムアウトキャンセルの修正。テスト 688 件 green。

---

## 第 1 位: クリップボード書き込みの Win32 エラー処理修正(Review #1)✅ 実施済み(2026-07-15)

**なぜ 1 位か**: 「変換結果が書かれていないのに成功を返す」はツールの根幹契約違反。
修正は数十行、リスクほぼゼロ、効果は全コマンドに及ぶ。

- `_win_set_text`: `SetClipboardData` の戻り値を検査。NULL なら `GlobalFree(h_mem)` して
  `RuntimeError`(`ctypes.get_last_error()` 付き)。`EmptyClipboard` も同様。
- `clipboard.py` の `windll` 直参照を `WinDLL(use_last_error=True)` に統一
  (`_pipe.py`/`_lifecycle.py` は統一済み、clipboard.py だけが古い流儀)。
- テスト: ctypes をモックした失敗パスのユニットテスト追加(non-Windows でも実行可能)。

**工数**: 0.5 日 / **受け入れ条件**: 失敗時 exit 1 + stderr メッセージ、リークなし。

---

## 第 2 位: genpass を Win+V 履歴・クラウド同期から除外(Review #2)

**なぜ 2 位か**: セキュリティ機能(パスワード生成)が逆にパスワードを拡散している。
KeePassXC/Chrome が採用する公式クリップボード形式で塞げる。公式ドキュメント:
[Clipboard Formats — Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-formats)

- `set_clipboard_text(text, *, sensitive=False)` を追加。`sensitive=True` のとき
  `RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")` と
  `CanIncludeInClipboardHistory`(DWORD=0)を CF_UNICODETEXT と同時に設定。
- `genpass` の書き込みを `sensitive=True` に。
- フェーズ 2(任意): 業界標準に合わせた自動クリア `--clear-after N` 秒(既定 30、0 で無効)。
  短命 CLI からのタイマーは持てないため、実装は「daemon 稼働時のみ有効」または
  デタッチ子プロセス方式を比較検討してから決める。

**工数**: 0.5 日(フェーズ 2 は +1 日) / **受け入れ条件**: genpass 実行後に Win+V 履歴へ
残らないことを実機確認(手動確認手順を docs に記録)。

---

## 第 3 位: セキュリティ CI の実効化(Review #3, #7)

**なぜ 3 位か**: 現状は Critical CVE 混入でも CI が緑。コード変更ゼロ・YAML のみで直せる。

1. pip-audit の `|| true` を削除し fail 化(誤検知は `--ignore-vuln` で個別管理)。
2. OSV-Scanner `fail-on-vuln: true` 化。
3. Bandit/Semgrep は advisory 継続(SAST 誤検知率を考慮した意図的判断として README/コメントに明記)。
4. タグ参照の Action(`actions/checkout` 等 + 特に `signpath/github-action-submit-signing-request`)
   を SHA ピンに統一。Dependabot が SHA ピンも追従することを確認。

**工数**: 0.5 日 / **リスク**: 既存依存に既知脆弱性があると直ちに CI 赤 → それが目的。
初回はローカルで `uv run pip-audit` を実行し、現状の検出件数を見てから投入する。

---

## 第 4 位: シングルトン mutex の per-user 化(Review #4)✅ 実施済み(2026-07-15)

**なぜ 4 位か**: 共有 PC で確定的に発生するバグ + 誰でも撃てる squat DoS。修正は実質 1 行。

- `_MUTEX_NAME` を `Global\press_daemon_singleton_{USERNAME}` に変更
  (`_pipe.pipe_name()` と同じユーザー名導出を共有し、導出一致をテストで固定)。
- `daemon_status` の mutex プローブも自動的に per-user 化される。
- 注意: 旧名称で稼働中のデーモンがいる状態で更新すると二重起動し得る —
  CHANGELOG に「更新前に `press daemon stop`」を明記。

**工数**: 0.5 日 / **受け入れ条件**: 名称導出のユニットテスト + 既存 daemon テスト green。

---

## 第 5 位: PyInstaller 成果物の信頼性メタデータ + 署名推進(Review #9, §5.2)

**なぜ 5 位か**: EDR/SmartScreen の behavioral score を下げる最後の大物。署名(SignPath)は
外部承認待ちのため、**先に自力でできるメタデータ付与を済ませる**。

1. `--version-file` 用の version resource(ProductName/FileDescription/CompanyName/
   FileVersion=パッケージ版数)を生成するスクリプトを追加し、release.yml と
   ローカルビルド手順の双方に組み込む。
2. リリース手順に「VirusTotal で事前スキャン → 検知があれば各ベンダーへ false positive
   申告」を追記(docs/dev/release-checklist)。
3. SignPath 承認後: 署名済み exe で SmartScreen レピュテーション蓄積を開始し、
   その後 **winget マニフェスト公開**を検討(署名が前提条件のため本計画では順序のみ確定)。

**工数**: 1 日(1–2 のみ) / **受け入れ条件**: exe のプロパティにバージョン情報が表示される。

---

## 第 6 位: カバレッジ分母の是正(Review #8)

**なぜ 6 位か**: 第 1 位のバグを見逃した構造要因。ゲートの誠実性はプロジェクトの
品質主張の裏付けになる。

- `omit` から `press/_cli_*.py` と `press/clipboard.py` を外し、Windows CI ランナーの
  実測値を確認 → 不足分は「モック可能な失敗パス」(第 1 位のテストと相乗)で埋める。
- `daemon/*` は tray/hotkey の実行系が CI で動かせないため omit 継続を許容。ただし
  `_lifecycle.py`/`_pipe.py(handle_request)` は既にプラットフォーム非依存テストが
  あるので分母へ戻す。
- `fail_under` は実測後に再設定(80 を下回るなら一時的に現実値 +2% で刻む)。

**工数**: 1 日 / **リスク**: CI が一時的に赤くなる可能性 → ブランチで実測してから調整。

---

## 第 7 位: hold.txt の DPAPI 暗号化(Review #6)

**なぜ 7 位か**: 機密性の実害はあるが、攻撃には「ディスク/バックアップへのアクセス」が
必要で genpass より条件が厳しい。依存追加なし(ctypes + CryptProtectData)で実装可能。

- `toggle_hold_file` の read/write を DPAPI(ユーザースコープ)でラップ。
  非 Windows テストパスは平文フォールバック(テスト専用)を維持。
- 旧平文 hold.txt の後方互換: 復号失敗時は平文として読む(1 リリースのみ)→ 次版で削除。
- 併せて `press clear` に `--hold` オプション(hold.txt 破棄)を追加。

**工数**: 1 日 / **受け入れ条件**: hold.txt がバイナリ化し、他ユーザー/他マシンで復号不能。

---

## 第 8 位: Win32 型・エラーパスの残修正(Review #5, #11)✅ 実施済み(2026-07-15)

- `_WNDPROC`/`DefWindowProcW` の LRESULT を 64bit 型へ(`c_longlong`)。
- `GetMessageW` 戻り値 `-1` をループ終了として扱う(`> 0` 判定)。
- パイプクライアントのタイムアウト経路で `CancelSynchronousIo` + ハンドルクローズ。

**工数**: 0.5 日 / まとめて 1 コミットで可。挙動変化なしのため回帰リスク最小。

---

## 第 9 位: ClipboardGuard 復元レート制限(Review #10)

- Layer 1 の復元回数を計測し、閾値超過(例: 5 回/秒 × 3 秒継続)で hold を自動解除して
  トレイ通知「他のクリップボードツールと競合したため保護を解除しました」。
- クリップボード履歴マネージャ(CopyQ/Ditto/PowerToys)ユーザーとの共存を docs に明記。

**工数**: 1 日 / **受け入れ条件**: 競合シミュレーション(テストでコールバック連打)で自動解除。

---

## 第 10 位: pystray 脱出先の技術検証(Review #12)— 調査のみ

- コードは書かない。Shell_NotifyIcon 直実装(ctypes)と winrt 系の 2 案について、
  (a) 実装規模 (b) メッセージループと daemon 構造の適合 (c) EDR 観点の import 数
  を比較する調査メモを docs/dev に残す。press-researcher で実施。
- トリガー条件を明文化: 「3.16 レーンで pystray が破損」または「pynput が pystray 依存を切る」
  まで実装しない(YAGNI)。

**工数**: 調査 0.5 日

---

## 対象外(検討の上、不採用)

| 提案 | 不採用理由 |
|------|-----------|
| typer/click への CLI 移行 | import 数増 = EDR コスト増。プロジェクトの存在意義に反する |
| `test/` → `tests/` リネーム | 実害なし。CI/カバレッジ/ドキュメントの変更コストが上回る |
| --onefile 化・単一 exe 配布 | EDR 再展開コスト。既定の --onedir が公式・実測の両面で正 |
| pipe プロトコルの暗号化 | 同一ユーザー境界内の IPC。DACL で保護済み、脅威モデル外 |
| stop_daemon のプロセス名検証強化 | 同一ユーザー前提の攻撃であり脅威モデル外(文書化済みの妥協) |

---

## 実施順序の提案

- **バッチ A(1 リリース: v0.5.1 パッチ)**: 第 1・4・8 位 — 純粋なバグ修正群。
- **バッチ B(v0.6.0)**: 第 2・7 位 — 機密性強化(クリップボード履歴除外 + DPAPI)。
- **バッチ C(CI のみ、随時)**: 第 3・6 位 — YAML/設定変更。コード変更と独立に投入可。
- **バッチ D(リリースフロー)**: 第 5 位 — 次回タグ push までに。
- **常設**: 第 9 位は B と同時、第 10 位は調査タスクとして空き時間に。

各バッチは CLAUDE.md のワークフロー(research → TDD → pythonic → quality → git-quality →
github-push-guardian)に従う。
