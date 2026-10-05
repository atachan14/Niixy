# Niixy Backlog（Version未割当）

具体的なBug・Improvement・Taskと完了状況を記録する。登録は実装や優先順の確定ではない。長期構想はVision、確定した実装範囲はVersion別requirements.mdで管理する。

公開状態の基準は `e17e00e188e6863914a0863dc33c67f19cf85e6f`。v0.16と、その後のReview／Mute／各List／fav・badは公開済み。追加機能のVersion番号は未割当。最新のQA・残範囲は[公開状態と限定追加QA](qa-status-2026-10-06.md)を参照する。

## BL-001 - Board作成時にPolicyを設定可能にする

- 種別: Improvement / Feature
- 状態: v0.11実装・直接検証・公開済み
- 実装Version: [v0.11](v0.11/requirements.md)
- 依頼: Board作成フォームでBoardPolicyも設定できるようにする。
- 既存との関係: v0.9はBoard詳細編集でのPolicy設定を実装済み。これは作成時の設定導線を追加する別タスクである。
- 範囲: 共通Account条件UIの4欄、既存初期値、明示的な空allow、未送信payloadの互換性を維持し、認可・Snapshot検証・原子的保存を行う。Templateは対象外。

## BL-002 - Interface作成の「中断／公開」が反映されない報告

- 種別: Bug fix
- 状態: 修正・隔離検証・公開済み（初回修正checkpoint `2cd5ab4`）
- 対応Version: 未割当。v0.10後の不具合修正として実施、v0.11本体の機能追加には混ぜない。
- 再現: 隔離SQLiteのEdge PC/mobile、AccountIF・ThreadIF・ResponseIFで中断／公開の12ケースが修正前に失敗した。発生時期は不明で、v0.10が原因とは確認していない。
- 原因: `name="action"` の関連submitボタンが `form.action` を隠し、誤ったURLへのPOSTが404になる。さらに公開後の応答URLを無視して旧「編集中」一覧へ戻り、中断後は同じ編集Paneを開き直していた。validation errorのredirect最終200と通信エラーもUIに表示されなかった。
- 修正: formのaction属性を直接読む。中断は下書き保存→編集Paneを閉じる→編集中一覧、公開成功は同じInterface種別の自作一覧へ移る。Draft更新のAJAX成功は遷移先・通知を返し、検証失敗は400の可視通知で編集Paneと入力を保持する。通信失敗と再試行、二重送信、閉じたPaneへの遅い応答も扱う。
- 画像確認でフォーム操作のnative水平スクロールにより編集Pane／通知が切れることを再現したため、送信・失敗時に既存Workspaceのalignでスクロールを解除する。共通Workspace/CSSは変更していない。
- 検証: Interface関連50件・全Django156件、隔離ブラウザ6テスト（Interface4件＋既存Workspace2件）通過。PC/mobile・3種類の新規作成、中断、公開、空名／重複名／無効Field、通信失敗と入力保持、再試行、編集v2公開、二重送信、Close、reload、破棄後の遅い保存応答を確認した。既存WorkspaceテストはCLI smoke・履歴・展開/Closeを含む。水平ずれ追加修正後は該当6ケースだけ再実行し通過。画像を確認し、Django check／migration差分なし／JS・Python構文／diff checkも実施。
- 限界: 隔離SQLite fixtureのブラウザ検証であり、実DBの並行性能を保証しない。初回修正QAでは共有NeonでDraft・公開・設定のテスト書込やDB migration・commit/push/deployを行っていない。これは当時の検証境界であり、現在の公開待ちを意味しない。生成証跡は未追跡 `.artifacts/interface-*.log` と `.artifacts/interface-actions/` に置く。

## BL-003 - 新規Roomの初期Board構成を「お知らせ／掲示板」にする

- 種別: Feature
- 状態: v0.11実装・直接検証・公開済み
- 実装Version: [v0.11](v0.11/requirements.md)
- 対象: 新規Room作成時のみ。既存RoomへBoardを追加しない。
- 構成: Main Collection配下に「お知らせ」「掲示板」を初期作成する。
- 閲覧: 両Boardとも誰でも閲覧可能（Guest OR NiixyAccount、不可なし）。
- Thread作成: 「お知らせ」はRoom作成時の作成者NiixyID（特定Account Snapshot）に固定。「掲示板」はRoom参加者条件。動的RoomOwner/管理者条件は今回追加しない。
- 作成後: 通常のBoard管理権限に従い、名前・Policy編集・削除を可能にする。誰でも閲覧可能であることは編集権限の付与を意味しない。
- 並び順: 初期表示は「お知らせ → 掲示板」。通常の最終活動日時による表示を維持する。
- 実装: 既存Room初期生成トランザクションを利用する組込初期構成として扱う。Template基盤や既存Roomへのデータ移行を同時に追加しない。
- 関連: 動的RoomOwnerへの将来移行は[Vision](vision/access-policy.md#動的roomowner条件)で管理する。v0.11の実装と公開は完了済み。動的RoomOwnerへの変更は別の仕様判断を要する。

## BL-004 - NiiMapのThread作成からThreadIF／Fieldを開くと逆走する

- 状態: 修正・隔離検証・公開済み（初回修正checkpoint `2cd5ab4`）。BL-002の後、v0.11本体の前に対応した修正。
- 再現・原因: desktopのThread作成→ThreadIF一覧で、検索用の旧stage CSSが起点の作成Paneをdisplay:noneにし、gridの列を詰めて一覧をSpot一覧の右へ移していた。beforeSelectorOpenがある場合は共通prepare(form)も省略されていた。起点displayの修正前失敗を確認した。
- 修正: 作成selectorが存在する場合だけNiiMapをflexで配置し、起点Thread／Roomの表示・幅を保持する。検索selectorはSpot一覧起点の従来表示を維持する。前処理の有無にかかわらずprepare(form)し、一覧へ戻る際に後続詳細を閉じる。入力focus時のnative水平scrollは既存stage整列で補正する。
- 直接回帰: 検索Closeの旧NiiMap同期処理が共通フォームの別属性controlをJSON.parseしてconsole errorになるため、旧controlだけを対象にした。共通フォームの値同期は既存処理を使う。
- 初回検証記録: 隔離SQLite・Edgeの代表1テスト（23.315秒）通過。PC/mobileのThreadIF／Field一覧→詳細→追加・再選択・詳細／一覧Close、タイトルと入力保持、起点隣接とCurrent右端座標、検索用IF／Fieldとの区別を確認。desktopのNiiMap内Room→Boardと共通Workspace Boardでも両種の追加・Closeを確認。page/console errorなし、画像確認、変更JS構文・テストPython構文・diff checkを実施した。
- 初回修正工程ではJS/CSSのみのため通常サーバーは再起動せず、cacheを迂回して更新staticのHTTP 200・内容一致を読取確認した。ユーザー確認はCtrl+F5で更新する。共有Neonで作成／投稿テストは行っていない。migration・commit/push/deployなし。
- 追加QA: 初回に後回しとした広域QAは[夜間QAの過去記録](nightly-qa-2026-10-06.md)へ、Room→Boardの2経路のPC/mobile追加・再選択・詳細CloseとIF／Field限定のreduced-motion・遅い応答は[今回の限定QA](qa-status-2026-10-06.md)へ記録する。一般Workspaceの成功を補助Paneの全域保証とはしない。補助Pane固有の多重reload／history、全通信条件の網羅検証は引き続き未実施。
- 今回の追加回帰: 入力focus後のnative横scrollがアニメーション終了後も残るずれをPC/mobileで再現し、`static/rooms/forms.js`のfocus handlerだけを最小修正した。元の右端／隣接期待を維持した直接失敗→再検証と隔離smokeは[今回のQA記録](qa-status-2026-10-06.md)を参照する。この追補だけはローカルcheckpointまでで未公開。
- 証跡: 未追跡 `.artifacts/module-selector-before.log`、`.artifacts/module-selector-after.log`、`.artifacts/module-selector/`。

## BL-005 - Account配下のCollection／Board

- 状態: v0.13実装・隔離検証・公開済み。最新公開基準は `e17e00e`。
- 範囲: AccountのBoard一覧Pane、本人Collection／Board管理、初期Main／日記、BoardからThread投稿、v0.13時点ではfav／badの未実装Tab枠。後続のBoardList／InterfaceListと公開fav／badも現在は[公開済み](board-interface-lists.md)。
- 要件・初期追加migration・検証・反映計画: [Account Board / Collection](account-boards.md)。

## 次作業の扱い

BL-001～BL-005の公開待ちは残っていない。今回の承認済み追加QAと文書整合は[限定QA記録](qa-status-2026-10-06.md)を参照する。RoomPolicy、Template、追加Layout、削除参照／Mute件数の最終UXなどはVersion未割当の候補・未決事項であり、実装順や仕様をここで新たに確定しない。
