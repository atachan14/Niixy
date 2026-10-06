# 共通コントロールの密度調整（2026-10-06）

公開済み `0db2705` を基点にしたローカル確認用の変更。Header、SummaryList、スマホのRoom/Account上段を基準に、フォームと操作ボタンの文字・余白を揃えた。変更箇所は `static/shared/controls.css` とbaseテンプレートのCSS読み込み。DB・schema・Policy・API・JavaScriptの処理は変更していない。

大きさの差は、bodyから継承される16px文字と、各コンポーネントの40px入力・ボタン、18px/58pxの上段ボタンなどが個別に定義されていたため。共有CSSの寸法変数と対象コンポーネントの上書きにまとめ、基準部品を除外した。

## 寸法と対象

| 対象 | 変更前 → 変更後 |
| --- | --- |
| PCの「条件を追加」「Fieldを追加」など一般操作 | 16px・高さ40px → 14px・最低32px |
| PCの一般テキスト入力 | 16px・高さ41〜42px → 14px・約32px |
| スマホの一般入力 | 16px・最低44px。検索の旧13px入力も16pxへ |
| スマホのフォーム操作 | 14px・最低44px（coarse pointer） |
| PC Account上段 | 18px・高さ58px → 14px・高さ36px |
| スマホ Account/Room上段 | 13px・高さ36pxを維持 |
| Draftフォームの節間隔 | 28px → 16px。フォーム内の標準間隔10px |
| フォームの見出し・ラベル | 主に15px・13pxへ |
| Review本文欄 | 高さ190px → PC128px、スマホ152px。縦リサイズ可能 |
| 補助的な追加ボタン | 全幅から内容幅へ。保存操作をフォーム右側へ |

条件Picker/Account選択、Thread/Room/Boardの作成・編集、Module/Applied/Layout、Review、Lists、認証フォームを対象にした。Summary行、読書用本文、ユーザーLayout、Workspaceの幅・current・アニメーションの定義は保持。Headerの高さ64px・ブランド20pxと、スマホ上段の実測値は変更前後で一致した。

一括zoomや新しい `!important` は使っていない。入力はスマホ16pxで自動拡大を避け、coarse pointerのフォーム操作は44pxを確保。フォーカス輪郭、赤いエラー表示、折り返し、日本語の長文、disabled状態も維持した。既存Header・上段操作の寸法は基準として残している。

## QAと証跡

隔離SQLiteとローカルEdgeで17画面×PC1280×900/スマホ390×844の34ケースを変更前後に採取。本人フォーム、他者AccountのReview、Guest認証を含む。入力寸法・ページ横はみ出し・Headerと上段の維持・実際のReviewエラー表示・キーボードフォーカスを確認し、JavaScript/console errorは0。Thread作成フォーム内の従来20pxのSummary余白は悪化しておらず、ページ自体の横はみ出しはない。

画像と実測JSONはignoredの `.artifacts/ui-density/before/`、`after/`。代表比較は `desktop-module-draft.png`、`desktop-board-policy.png`、`mobile-account-selector.png`、`mobile-validation-error.png`。ブラウザーsmokeの最終画像は `.artifacts/browser-smoke/desktop-workspace.png`、`mobile-workspace.png`、`desktop.png`、`mobile.png`。

隔離QAでは外部Geolonia style配信のCORS不安定を避けるため、地図の背景styleだけを固定した。実SDK、クリック、NiixyのAPIはそのまま使用。地図タイル表示そのものはこのフォームQAの対象外。通常サーバーのGuest確認は書き込みを遮断し、既存データだけを閲覧した。

- 隔離QA: 新34ケース＋既存Workspace 2テスト＋Account Layout 1テスト、計4テスト通過。最後のField選択寸法修正後に新34ケースだけ再確認し通過。共有DB使用なし。
- 通常サーバーsmoke: PC/スマホ各14チェック、JS/console error 0。選ばれたBoardが空のためStandalone Thread確認に警告各1件。既存の公開Room/Threadで各3チェック（本文・reload・Close）を補完し通過。
- 通常条件画面: PC/スマホの「条件を追加」とField選択を実測し通過。条件Paneの描画も確認。JS/console error 0、共有データ書き込み0。
- 通常GETの既知の待ち時間を踏まえて、smokeのページnavigationだけ45秒とした。元のUI assertionは10秒のまま。
- 上記証跡は `.artifacts/ui-density/live-smoke.json`、`local-room-browser.json`、`live-conditions.json`、`live-GET.json`。

通常サーバーはAGENTSに従って旧親子プロセスのPID・パス・開始時刻とlistenerを確認し、停止後に残存process/portが0であることを確認して一組だけ起動。`http://127.0.0.1:8000/` のGETと配信CSSのSHA256一致を確認した。CSS版は `20261006-ui-density`。

## 再実行

共有Neonを使わないよう明示して実行する。

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
.\.venv\Scripts\python.exe manage.py test scripts.ui_density_browser_tests scripts.workspace_browser_tests scripts.account_layout_browser_tests --noinput
```

新テストはSQLite以外を拒否する。ignoredの変更前測定があれば前後比較も行い、fresh checkoutでは入力・操作寸法、フォーカス、エラー、横はみ出しの検証を行う。本人向け保存などの書き込みは隔離DB内だけ。

## 今回変更しなかった既存の挙動

Basic情報の無効POSTで描画されたエラーが、初期化時の `openBasic(false)` による再GETで消える挙動を隔離QA中に確認した（`accounts/views.py:my_page`、`static/accounts/mypage.js:openBasic`）。また `?section=basic` のGETだけではBasic Paneの初期表示指定が成立しない。今回の寸法調整には含めず、機能修正の候補として残す。

通常条件画面の撮影では、地図側の「地図の読み込みに失敗しました」表示が出る回があった。条件フォームとPane操作の検証は通過したが、地図の完全表示は未確認。この変更で地図処理は変更していない。通常の撮影に地図styleのモックは使っていない。

root READMEと `docs/memo/inbox.md` の既存差分を保持。成果物・画像・DB・認証情報はstageしない。公開・pushは保留。
