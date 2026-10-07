# 補助Paneの通信失敗・起点破棄後の遅い応答（2026-10-07）

基準HEADは `450f30d5737d6e5b08c1d621fc9ae3264739fe5c`。既存のBasic修正と未commit差分を保持し、補助Paneの代表QAだけを追加した。

## 再現した問題と修正

NiiMap内のRoom → Board → Field詳細で、詳細GETの取得済み応答を保留し、起点BoardのClose処理を呼ぶと、Board/formは切断されても補助一覧・詳細が2枚残った。PC/mobileとも同じassertで失敗した。対照の共通Workspace Room → Board → ThreadIFは補助Paneも破棄され、別Boardの入力へ遅い応答が混入しなかった。

[map.js](../static/events/map.js) のNiiMap Room関連Pane削除を `removeEmbeddedRoomPane` に揃えた。削除対象Paneに所属する `workspaceOwner` を持つ補助Paneを先に除去する。既存のClose・置換・起点保持処理が削除する対象Paneとstage/URLの指定は維持した。詳細Paneが切断されるため、[共通selectorの既存接続・世代判定](../static/rooms/forms.js) が遅い応答を無視する。作成API・入力形式・schema・新機能は変更していない。

## 集中QA

[AuxiliaryPaneBrowserTests](../scripts/auxiliary_pane_browser_tests.py) は既存selector fixture・geometry helper・取得済み応答の保留helperを再利用する。本人、PC1280×720/mobile390×844、共通WorkspaceのThreadIF/NiiMap内BoardのFieldという2代表経路に限定した。

| ケース | 件数 | 確認内容 |
| --- | --- | --- |
| 詳細取得のreject / HTTP503 → 一覧へClose → 同じ項目を再選択 | 8 | エラー表示、titleと選択済み値の保持、再取得後の値復元・反映、重複追加なし、補助Pane Close、右端・隣接1px/横scroll 0 |
| 取得済み応答を保留 → 起点BoardをClose → 別Boardで選択・別kind詳細へ入力 → 古い応答を解放 | 4 | 古いformと補助Paneの切断、Pane復活なし、新しいtitle/選択値/詳細入力・HTML・URLの保持、右端・隣接1px/横scroll 0 |

通信失敗は実際の隔離detail GETが200で完了した後、fetch境界でTypeError rejectまたはResponse(status=503)を注入する。ブラウザのconsole errorを除外せずUIのエラー分岐を検証する方法であり、実回線の切断やサーバーが返す503そのものを試した結果ではない。遅い応答も実GETの応答本文を取得後に保留・解放し、abortだけで古いcallbackを隠せないようにした。

起点のCloseボタンは既存Workspace QAと同じ `el.click()` で呼ぶ。mobileで画面外にある祖先ボタンの手動到達性は、このテストの保証範囲ではない。破棄済みformをreloadから復元する仕様は追加せず、残る起点や別起点の未送信入力を保持することを確認した。

修正前は2テスト / 67.022秒、10ケース成功・NiiMap起点破棄の2ケース失敗。修正後は同じ2テスト / 65.086秒、**12ケース成功**。成功ケースはpage/console error 0。Thread / ThreadPost / ThreadPlacement件数はブラウザ操作前後で不変。PC/mobile両経路の補助詳細画像を目視確認した。

AGENTS指定の既存 `scripts/browser_smoke.py --base-url <隔離LiveServer> --output-dir <今回のsmoke artifact>` も別の隔離fixtureで実行した。**1テスト / 32.729秒、PC/mobile成功**。両viewportのwarnings/browser_errorsは空で、Workspace遷移・Close・history/reload・native Room Threadを確認した。全Django292件や過去の広いbrowser suiteは再実行していない。

## 境界・残る確認

dotenvを無効化してからDjango設定をimportし、SQLite ENGINE・`:memory:`・DB数1をassertした外部runnerを使用した。LiveServerの空きポートだけを使用し、ブラウザの通常127.0.0.1:8000と公開Niixyへの接続を禁止した。実地図SDKを使うが地図styleだけは固定背景へ置換し、地図タイルは対象外。

証跡はignored `.artifacts/auxiliary-network-2026-10-07/` の `before/result.json`、`after/result.json`、各ケース画像。修正前の失敗記録も残す。runnerと実行ログは共有task-10 workspaceへ保持する。

残る範囲は全補助Pane/全起点/全historyの網羅、Guest・他者の作成導線、実回線障害や全通信の遅延、別browser/別mobile幅、PostgreSQL transaction/lock、未送信入力のreload復元。曖昧な仕様差や長期機能は[機能状態一覧](feature-status-2026-10-07.md)の分類を変えず、新たな必須機能にはしていない。

通常server・共有Neon・公開環境・deployment・pushを操作していない。root README/inboxと開始時に存在した他差分を保持する。
