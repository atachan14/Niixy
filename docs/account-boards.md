# v0.13 - Account Board / Collection

Status: 実装・隔離検証済み。公開反映・共有Neon初期追加・通常server再起動承認済み。反映の実測結果は作業スレッドと未追跡の`.artifacts/account-boards-release/`に記録する。

## 範囲

AccountPageとWorkspace内のAccountPaneの`Board`から、共通Board一覧Paneを開く。通常Collectionを作成順に並べ、常設の`未分類`、未実装の`fav`／`bad`、本人向けの`管理`Tabを表示する。SummaryList、Collection詳細確認／Board作成、Board詳細情報／Thread作成は既存Roomと同じUI・共通処理を使う。

本人はCollection作成・改名・削除とBoard作成・基本情報／BoardPolicy編集・削除を行える。他Account／Guestは管理できない。管理権限は配置先Accountから決まり、別Account・RoomのCollection／Board IDを指定しても操作できない。

新規Accountには通常Collectionの`Main`、その配下のBoard「日記」、システムCollectionの`未分類`を作成する。日記の初期BoardPolicyは閲覧がGuest OR NiixyAccount、Thread作成が対象Accountの固定ID条件、不可なし。Mainと日記は通常のCollection／Boardとして改名・削除でき、閲覧・Account更新時に復活させない。作成後のBoardPolicyは本人が編集できる。

Mainなどの通常Collectionを削除すると、配置されたBoardを同じAccountの`未分類`へ退避する。未分類は固定名・削除不可、Board作成先として選択でき、退避後も一覧・Board詳細・Thread作成へ到達できる。Boardの物理削除はThread／Response／ThreadPolicy／Field／Interfaceを残す。Threadは未配置になり、Account活動履歴などの既存導線から利用できる。

Thread作成はBoardの閲覧条件・作成条件を確認し、既存のAccount条件Snapshot、ThreadPolicy、Field／ThreadIF入力・保存を共通処理で適用する。日記のThread作成条件をThreadの返信条件へコピーしない。Thread閲覧・返信はThreadPolicy自身で決まり、他Accountの返信や明示的に許可されたGuest返信も可能である。

fav／badの保存・解除、参照追加、配置先移動、Layout、Interface凍結・版更新、Template基盤は今回の範囲外。v0.12のAccount Appliedに続くv0.13として区切り、commit件名へ版を明記する。

## 初期生成とmigration

新規Accountの初期構造は`accounts.signals`から生成する。通常のsignupはAccount本体・Profile・初期Collection／Boardを一つのtransactionで保存する。通常閲覧で不足データを補う処理は置かない。

`rooms/0009_initial_account_boards`は一度限りのデータmigrationで、Account配下のCollectionが一つもない既存AccountにだけMain／日記／未分類を追加する。未分類だけを持つAccountも含め、何らかのCollectionがあるAccountはスキップする。既存Collection／Board／Policyの名前・内容・配置を変えず、同名のCollectionを流用しない。この保守的な対象判定により、すでに削除や整理を行った構成も上書きしない。

新しいtable／columnは追加しない。GuestとNiixyAccountの閲覧条件、対象Account IDのThread作成条件を初期Boardへ保存する。履歴モデルとmigrationのDB aliasを使う。編集可能な生成データをrollbackで削除することはできないため、逆向きmigrationは用意しない。反映後の修正は追加の前向きmigrationで行う。

ローカル検証段階では共有Neonへのmigration・テスト投稿・通常server再起動・commit／push／deployを行っていない。2026-10-05にcommit／push・新コード公開確認・共有Neon初期追加・通常server再起動まで承認された。共有DBのテスト投稿・設定変更は引き続き行わない。通常runserverと公開版は同じDBを使う。

反映時は、適用予定がrooms 0009であることとDBバックアップ／対象件数を読取確認する。0009はデータ追加だけで、新コードは適用前のschemaでも動く。公開版の新規Account初期生成コードを先に反映し、旧signup処理の稼働が終わってからmigrationを一度適用する順を推奨する。DBだけを先に反映すると、その後に旧公開版で登録されたAccountへ初期Boardが付かない期間が生じるため、親スレッドで公開版・ローカルserver・migrationの切替順を調整する。

実構成ではVercelの本番buildCommandがmigrationを自動実行する。このため新コードを先行commit／公開し、公開確認後に0009とその専用直接テストを別commitで追加する二段階で反映する。0009は二段目のproduction build内で実行され、ローカルからは適用済みかを読取確認する。予想外のmigrationや既存データ変更があれば適用を止めて親スレッドへ相談する。

通常serverを更新する際は、AGENTS.mdに従って検証済みのNiixy runserverペアだけを停止・再起動し、Accountの更新markup／asset配信をGETで確認する。Python／template変更を含むため明示的restartが必要。共有DBでは作成・編集・削除の試験を行わない。

## 隔離検証

`manage.py test`はconfig/settings.pyの既存分岐によりSQLite専用DBを使う。ブラウザはStaticLiveServerTestCaseのランダムportと共有SQLite用handlerを使用し、通常8000番のrunserverには接続しない。

- `manage.py test rooms.tests_account_boards rooms.tests scripts.account_board_browser_tests scripts.board_creation_browser_tests --noinput`: 53件通過（143.649秒）。Account／Roomの直接認可・データ整合とEdge PC/mobile、既存browser_smoke.pyを含む。
- Accountの新規初期生成、CRUD拒否／別配置先ID拒否、日記作成とThreadPolicyによる他Account・Guest返信、Main削除退避、未分類の保護、改名／削除後の非再生成、Board削除後のThread維持、invalid payloadの原子的拒否、二重送信と別配置先へのtoken再利用拒否を確認した。
- PC/mobileのAccount → Collection／Board作成 → Thread投稿／返信、reload、Close、Accountの別機能による後続Pane置換、NiiMap内AccountPaneからのBoard遷移を確認した。既存RoomのPolicy選択UIとWorkspace smokeも通過し、browser error／warningはなかった。
- 過去モデルによる既存Account初期追加の再確認と、Board削除後のField保持を含むAccount直接11件も通過した。
- 最終の`manage.py test rooms.tests_account_boards scripts.account_board_browser_tests --noinput`: 13件通過（47.015秒）。AccountのAccount条件選択／Field補助Pane、入力保持、Field付きThread保存をPC/mobileで追加確認し、既存browser_smoke.pyも再実行した。検証コードのField型定数とPlaywright中のORM確認位置を修正した後の結果である。
- `manage.py test accounts.tests.AuthenticationTests --noinput`: signup／Loginの既存3件通過（2.876秒）。SQLiteを明示したDjango check、makemigrationsのcheck／dry-run、Python／変更JSの構文、禁止ファイルを除外したdiff checkも通過。roomsのmigration末尾は0009のみで、追加schema差分はない。
- `.artifacts/account-boards/`、`.artifacts/board-creation/`、`.artifacts/browser-smoke/`へ未追跡画像を生成し、PC/mobileのWorkspace画像を確認した。

広域Django全件、PostgreSQL実DBでの並行処理・性能、共有Neonのmigration・公開版確認は未実施。検証結果は隔離fixtureに対するものである。
