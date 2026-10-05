# Niixy Backlog（Version未割当）

具体的な未対応Bug・Improvement・Taskを記録する。登録は実装や優先順の確定ではない。長期構想はVision、確定した実装範囲はVersion別requirements.mdで管理する。

## BL-001 - Board作成時にPolicyを設定可能にする

- 種別: Improvement / Feature
- 状態: v0.11実装・直接検証済み（checkpoint公開承認済み）
- 実装Version: [v0.11](v0.11/requirements.md)
- 依頼: Board作成フォームでBoardPolicyも設定できるようにする。
- 既存との関係: v0.9はBoard詳細編集でのPolicy設定を実装済み。これは作成時の設定導線を追加する別タスクである。
- 範囲: 共通Account条件UIの4欄、既存初期値、明示的な空allow、未送信payloadの互換性を維持し、認可・Snapshot検証・原子的保存を行う。Templateは対象外。

## BL-002 - Interface作成の「中断／公開」が反映されない報告

- 種別: Bug fix
- 状態: ローカル修正・隔離検証済み（未コミット／未公開）
- 対応Version: 未割当。v0.10後の不具合修正として実施、v0.11本体の機能追加には混ぜない。
- 再現: 隔離SQLiteのEdge PC/mobile、AccountIF・ThreadIF・ResponseIFで中断／公開の12ケースが修正前に失敗した。発生時期は不明で、v0.10が原因とは確認していない。
- 原因: `name="action"` の関連submitボタンが `form.action` を隠し、誤ったURLへのPOSTが404になる。さらに公開後の応答URLを無視して旧「編集中」一覧へ戻り、中断後は同じ編集Paneを開き直していた。validation errorのredirect最終200と通信エラーもUIに表示されなかった。
- 修正: formのaction属性を直接読む。中断は下書き保存→編集Paneを閉じる→編集中一覧、公開成功は同じInterface種別の自作一覧へ移る。Draft更新のAJAX成功は遷移先・通知を返し、検証失敗は400の可視通知で編集Paneと入力を保持する。通信失敗と再試行、二重送信、閉じたPaneへの遅い応答も扱う。
- 画像確認でフォーム操作のnative水平スクロールにより編集Pane／通知が切れることを再現したため、送信・失敗時に既存Workspaceのalignでスクロールを解除する。共通Workspace/CSSは変更していない。
- 検証: Interface関連50件・全Django156件、隔離ブラウザ6テスト（Interface4件＋既存Workspace2件）通過。PC/mobile・3種類の新規作成、中断、公開、空名／重複名／無効Field、通信失敗と入力保持、再試行、編集v2公開、二重送信、Close、reload、破棄後の遅い保存応答を確認した。既存WorkspaceテストはCLI smoke・履歴・展開/Closeを含む。水平ずれ追加修正後は該当6ケースだけ再実行し通過。画像を確認し、Django check／migration差分なし／JS・Python構文／diff checkも実施。
- 限界: 隔離SQLite fixtureのブラウザ検証であり、実DBの並行性能を保証しない。今回共有NeonでDraft・公開・設定のテスト書込はせず、DB migration・commit/push/deployも行わない。生成証跡は未追跡 `.artifacts/interface-*.log` と `.artifacts/interface-actions/` に置く。

## BL-003 - 新規Roomの初期Board構成を「お知らせ／掲示板」にする

- 種別: Feature
- 状態: v0.11実装・直接検証済み（checkpoint公開承認済み）
- 実装Version: [v0.11](v0.11/requirements.md)
- 対象: 新規Room作成時のみ。既存RoomへBoardを追加しない。
- 構成: Main Collection配下に「お知らせ」「掲示板」を初期作成する。
- 閲覧: 両Boardとも誰でも閲覧可能（Guest OR NiixyAccount、不可なし）。
- Thread作成: 「お知らせ」はRoom作成時の作成者NiixyID（特定Account Snapshot）に固定。「掲示板」はRoom参加者条件。動的RoomOwner/管理者条件は今回追加しない。
- 作成後: 通常のBoard管理権限に従い、名前・Policy編集・削除を可能にする。誰でも閲覧可能であることは編集権限の付与を意味しない。
- 並び順: 初期表示は「お知らせ → 掲示板」。通常の最終活動日時による表示を維持する。
- 実装: 既存Room初期生成トランザクションを利用する組込初期構成として扱う。Template基盤や既存Roomへのデータ移行を同時に追加しない。
- 関連: 動的RoomOwnerへの将来移行は[Vision](vision/access-policy.md#動的roomowner条件)で管理する。今回のローカル実装は承認済み。共有DB変更・公開更新は別の承認で扱う。

## BL-004 - NiiMapのThread作成からThreadIF／Fieldを開くと逆走する

- 状態: ローカル修正・直接関連の隔離検証済み（未コミット／未公開）。BL-002の後、v0.11本体の前に対応する承認済み修正。
- 再現・原因: desktopのThread作成→ThreadIF一覧で、検索用の旧stage CSSが起点の作成Paneをdisplay:noneにし、gridの列を詰めて一覧をSpot一覧の右へ移していた。beforeSelectorOpenがある場合は共通prepare(form)も省略されていた。起点displayの修正前失敗を確認した。
- 修正: 作成selectorが存在する場合だけNiiMapをflexで配置し、起点Thread／Roomの表示・幅を保持する。検索selectorはSpot一覧起点の従来表示を維持する。前処理の有無にかかわらずprepare(form)し、一覧へ戻る際に後続詳細を閉じる。入力focus時のnative水平scrollは既存stage整列で補正する。
- 直接回帰: 検索Closeの旧NiiMap同期処理が共通フォームの別属性controlをJSON.parseしてconsole errorになるため、旧controlだけを対象にした。共通フォームの値同期は既存処理を使う。
- 検証: 隔離SQLite・Edgeの代表1テスト（23.315秒）通過。PC/mobileのThreadIF／Field一覧→詳細→追加・再選択・詳細／一覧Close、タイトルと入力保持、起点隣接とCurrent右端座標、検索用IF／Fieldとの区別を確認。desktopのNiiMap内Room→Boardと共通Workspace Boardでも両種の追加・Closeを確認。page/console errorなし、画像確認、変更JS構文・テストPython構文・diff checkを実施した。
- JS/CSSのみのため通常サーバーは再起動せず、cacheを迂回して更新staticのHTTP 200・内容一致を読取確認した。ユーザー確認はCtrl+F5で更新する。共有Neonで作成／投稿テストは行っていない。migration・commit/push/deployなし。
- 後回しQA: 今回変更後の全Django・広域smoke、多重reload／history／遅い応答／reduced-motionの網羅確認、mobile Room／Board補助Pane全経路は未実施。BL-002の156 Django・広域ブラウザ成功を今回修正後の全体保証とはしない。進められる承認済み実装がなくなった安全な区切りでdeferred QAを行う。
- 証跡: 未追跡 `.artifacts/module-selector-before.log`、`.artifacts/module-selector-after.log`、`.artifacts/module-selector/`。

## BL-005 - Account配下のCollection／Board

- 状態: v0.13実装・隔離検証済み。公開・共有Neon初期追加・通常server再起動承認済み。
- 範囲: AccountのBoard一覧Pane、本人Collection／Board管理、初期Main／日記、BoardからThread投稿、fav／badの未実装Tab枠。
- 要件・初期追加migration・検証・反映計画: [Account Board / Collection](account-boards.md)。

## 次作業の優先候補

BL-002／BL-004の修正を公開した後、承認済みv0.11のBL-001／BL-003を実装・直接検証済み。広域QAは直接関連の検証後、安全な区切りで行う。
