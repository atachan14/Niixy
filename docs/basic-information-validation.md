# Basic無効POSTのエラー・入力保持（2026-10-07）

基準は `ddef8887100d93aa435d2e0eb506eef6689ddf2a`。[v0.4.1の既存要件](v0.4.1/requirements.md)で必要な「無効表示名は保存せず入力欄にエラーを表示する」動作を補修した。新機能の仮実装や長期項目の優先繰上げではない。結果はローカルcheckpointまで、未公開。

無効POSTに対して[my_page](../accounts/views.py)は、エラーと入力を含む正しいHTMLを返していた。しかし[mypage.js](../static/accounts/mypage.js)の起動時`openBasic(false)`が描画済みPaneを削除し、`/mypage/?_panes=1`を再GETするため、エラーが消えて保存済み値へ戻っていた。

初期Basic Paneが既に存在する場合はそのDOMを使ってstage・Header・Close・focusを初期化する。通常のBasicボタンから開く場合は従来の取得経路を使い、Close/focusのbindingだけを共通化した。API・view・フォームValidation・認可・CSRF・保存処理・DB schema・template・asset versionは変更していない。

## 同じ期待値での修正前後QA

[隔離ブラウザ回帰テスト](../scripts/basic_information_browser_tests.py)を追加。既存venv・Microsoft Edge headlessを使用し、新依存はない。実フォームからCSRF token付きPOSTを行い、サーバー応答、描画済みエラー、入力、initializer GET、Basic stage、Pane数、focus、右端1px・横はみ出し、page/console errorを確認した。

| 対象 | 修正前 | 修正後 |
| --- | --- | --- |
| PC1280×720 / mobile390×844 × 絵文字 / 全角13文字 | **4ケースとも期待値に失敗**。サーバーHTMLにはエラーと入力があるが、画面はエラーなし・保存済み値・再GET一回。 | **同じ4ケースすべて成功**。エラー・無効入力を保持、再GETなし、DBの保存済み値は不変。Close→概要→再度Basicでは保存済み値を取得。 |
| PC / mobileの無効入力→修正→保存→Basic再表示→Close | ― | **2ケース成功**。正しい値を保存しHeaderに反映、再表示値一致・エラーなし、遷移完了後の座標も確認。 |
| 既存MyPageTests | ― | **5件成功**。Guest・表示名保存/Validation・概要・メニュー。 |
| 既存CSRF拒否テスト | ― | **1件成功**。通常MyPageフォームのtokenなしPOSTも403を維持。 |
| 既存browser_smoke CLI | ― | **PC / mobile成功**。警告・page/console error 0、Workspace／最終画面4画像を目視確認。 |

入口runnerはdotenvを無効化してからsettingsを読み、`test`分岐、SQLite ENGINE、`:memory:`、DB一個をassertした。LiveServerの空きポートだけを使用し、Basicテストは通常8000番・publicへの接続を遮断。通常runserverは共有Neonを使うため、smokeも既存CLIの`--base-url`を隔離LiveServerに指定した。通常serverや共有DBを操作していない。JavaScriptのみの製品変更で、通常serverのrestartは不要。

## 実行記録と検証境界

- 修正前: 1テスト / 10.633秒、期待どおり4 failures。修正後初回: 7テスト / 32.950秒で、主対象4ケースと既存MyPage5件は成功。追加保存確認2ケースだけ、新QAが初期概要のDOM stage属性を仮定して失敗した。
- 初期概要はDOM stage属性を持たないため、実controllerのstageを読むよう新QAを補正した。期待値`overview`は不変。補正した保存確認・既存CSRF・smokeの限定runは3テスト / 39.824秒で成功。主対象4ケースの期待値や製品コードは変えていない。
- 保存後の再表示画像がアニメーション途中だったため、既存遷移を待って右端・横はみ出しもassertし、このPC/mobile2ケースだけ再実行。1テスト / 7.607秒で成功。遷移完了後の両画像を目視確認した。
- 新QAの失敗ログ、遷移途中の画像も保持。証跡はignored `.artifacts/basic-information-2026-10-07/` のbefore/after JSON・画像・smoke画像。入口runnerと4runのログは許可task-10 workspaceの `run_basic_qa.py`、`basic-before.log`、`basic-after.log`、`basic-followup.log`、`basic-save-settled.log`、`basic-smoke-cli.log`。
- JS構文・test AST・diff checkを確認。全Django／全browser suite、共有PostgreSQL、公開反映は検証していない。`?section=basic`の初期表示問題はこの補修の対象外として残す。

表示名Snapshotは会話で「現段階で対応しなくていい」と明示された長期保留項目であり、今回の一般的な仮実装依頼から実装へ進めない。他の未決機能・placeholderも有効化しない。root README、既存inbox差分、先行history QAの未commit差分を保持し、今回のBasic補修3ファイルだけをcheckpoint対象とする。
