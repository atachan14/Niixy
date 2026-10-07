# Basicのsection URL復元（2026-10-07）

開始HEADは `b9bb40964d6a62297044ded84380dcb3b0ecb580`。[Basic無効POST補修](basic-information-validation.md)と先行history QAの未commit差分を保持して再開した。現行依頼で候補指定された既存不具合を、[URLからCurrentPaneを復元する既存方針](vision/decisions.md)とApplied／Moduleの経路に沿って補完した。公開・schema・共有DB操作は含まない。

修正前は`/mypage/?section=basic`をJS初期化が読まず、概要のままになっていた。`_panes=1`でBasicが描画されても概要stageの画面外に残る。通常のBasicボタンもURLに選択状態を記録せず、reloadで概要に戻っていた。

[mypage.js](../static/accounts/mypage.js)の製品変更は2行。通常Basicボタンは`?section=basic`を履歴URLへ記録し、起動時はその指定またはサーバーの初期Basic指定を読む。描画済みPaneは`b9bb409`の経路で再利用し、ない場合は従来のfragment取得で開く。未送信入力をreload後に保存する機能は追加しない。API・view・認可・CSRF・Validation・保存処理・DB schema・template・asset versionは変更していない。

## 隔離QA

[既存Basic回帰テスト](../scripts/basic_information_browser_tests.py)へURL復元の直接テストを追加した。PC1280×720／mobile390×844 × 直接URL／描画済みPane付きURL／通常ボタンの**6ケース**で、初期表示・3回reload・Closeを確認。URLのBasic指定、実controllerのstage、Pane一個、保存済み値・focus、右端1px・横はみ出し、page/console errorを同じ期待値で検証した。

- 修正前: **1テスト / 20.440秒、6ケースすべて失敗**。直接URL・描画済みURLは概要stage、通常ボタンは初回BasicだがURL指定なし・reload後概要という実測を保持。
- 修正後: **10テスト / 75.274秒、全件成功**。新規6ケースに加え、既存の無効POST4ケース、修正保存2ケース、MyPage5件、CSRF拒否1件、既存smoke CLIのPC/mobileを確認。無効POSTのエラー・入力保持とinitializer再GETなしは維持した。
- BasicのPC/mobile画像を目視確認。smokeも警告・page/console error 0。ただし最終PC画像はCloseアニメーション途中だったため、[smoke撮影ヘルパー](../scripts/browser_smoke.py)へ既存遷移を待つ350msの1行だけを追加し、smokeだけを再実行した。**1テスト / 32.465秒でPC/mobile成功**し、Workspace／最終画面4画像を目視確認。assertionや製品コードは変えていない。初回画像・ログは削除せず、新しい画像を別ディレクトリへ保存した。

runnerはdotenv読込を無効化し、SQLite `:memory:`・DB一個・test分岐をassert。LiveServerの空きポートのみ使用。Basicブラウザは通常8000番・public接続を遮断し、smoke CLIも`--base-url`に隔離LiveServerを指定した。既存venv／Edgeを使い、依存追加なし。JS構文、test AST、diff checkも確認した。

証跡はignored `.artifacts/basic-section-2026-10-07/` のbefore/after JSONと画像、smoke／smoke-settled画像。前後runとsmoke限定再runのログは許可task-10 workspaceの `basic-section-before.log`、`basic-section-after.log`、`basic-section-smoke-settled.log`、`basic-section-smoke-settled-cli.log`。旧Basic補修のartifact群は別に保持する。

全browser／全Django、共有PostgreSQL、公開反映、MyPage同一Page内Back/Forwardの全経路は本工程の検証外。通常serverは開始時の親子PID・開始時刻を維持し、再起動していない。製品JSだけなのでrestartは不要。root READMEと、開始時点の既存inbox差分を保持し、stageしない。

## 次候補の扱い

1. Basic URL初期表示・reload復元: 今回ローカル補修済み。
2. 後回しの補助Pane GET通信失敗・再試行・破棄後の遅い応答: 既存要件の限定QAを次候補とする。一般Workspaceの成功を全補助Paneの保証とせず、明白な回帰が出た場合だけ最小補修する。
3. RoomPolicy／Template／追加Layout等: 原則があっても未決境界は確定せず保留。表示名Snapshotは明示された長期保留を維持する。

今回新規機能のplaceholderは有効化していない。コードの公開、共有DB書込、schema追加は別確認のまま。
