# AccountPage起点のWorkspace切替

2026-10-06の追加ユーザー訂正。AccountPageからBoard / Peopleを開いたときは、AccountPageを起点として後続Paneを置き換える。既存の共通Workspace prepare / push / Close / historyを使用する。

## 修正前の再現

隔離SQLite、一時StaticLiveServer、Edge headlessで、AccountPage → Thread一覧 → Thread詳細 → 別AccountPage → Moduleという後続を作成した。その後、最初のAccountPageのBoard / Peopleを押すと旧conversation workspaceが見えていた。

- Board: legacy-stage=overview、legacy-conversation-visible=True。
- People: legacy-stage=list、legacy-conversation-visible=True。

修正前画像は`.artifacts/account-origin/before-board.png`と`before-people.png`に保持。通常server pairや8000には触れていない。

## 修正

`.account-page`はmetadata rootで、実際のtrack内の起点Paneは`.account-overview-pane`。Board / Peopleの共通prepareへこの起点を渡す。Board clickの先行stage変更を除き、共通retainから既存onRetainを通してnative Thread詳細・Room詳細・Module・Appliedを片付ける。nested AccountPageは既存のshared entryを起点として維持する。

起点をretainした時点でnative一覧の要求世代を進め、Thread/Response一覧・Room一覧・Applied・詳細の旧要求を無効化する。同じ一覧URLを直後に開き直しても、旧応答はcacheやDOMを上書きしない。shared Paneは既存AbortControllerと接続確認を使用する。

BoardのURL復元では、feature URLを読んだ後にAccountPageの親URLを正規化してpushする。復元後CloseはAccountPage URLへ戻る。Back / Forwardは履歴に記録された画面を復元する。Thread一覧の履歴に戻った場合は一覧を表示し、閉じた旧詳細や旧入力は復活しない。

## QA

`scripts/account_origin_tests.py`はPC1280×900 / mobile390×844（touch / is_mobile）で次を直接検証する。

- native Thread詳細と2個のshared後続がある状態から、Board / People / Module / Threads / Responses / Rooms / Appliedを切り替える。旧shared DOMは全て切断し、AccountPage起点DOMは同一nodeを保持する。
- Board / PeopleはAccountPage + 対象Paneだけになる。Close / Back / Forward、nested AccountPageからの各機能切替も共通Workspaceで成立する。
- real responseを受信後、JavaScriptへのdeliveryを保留したThread詳細 / shared Boardを置き換えてCloseし、release後も旧Paneを再挿入しない。
- native Thread一覧 / Room一覧の古い応答を保留し、People経由で同じURLを開き直す。新DOMのmarkerは旧応答release後も保持する。
- Board / Peopleの直接URLをreloadしてPaneが1個だけ復元され、Closeでcanonical AccountPage URLへ戻る。
- console error / page errorは0。画像は`.artifacts/account-origin/desktop-boards.png`、`desktop-people.png`、`mobile-boards.png`、`mobile-people.png`。

結果と最終画像確認はmodule-list-integration.mdに記録する。途中で、BackがThread一覧へ戻る既存履歴と、初期overviewのstage属性が未記入である仕様をテスト側に反映した。同URL遅延fixtureのThread一覧URL取得先は`.account-thread-workspace`であり、誤ったmetadata root取得を修正した。失敗を隠すための機能制限は加えていない。

一覧・公開Moduleの仕様と保持migrationは[Module List統合](module-list-integration.md)を参照。RoomReview / Mute機能の新規実装、People / AccountList仕様変更は今回の対象外。
