# v0.10 ThreadPolicy Foundation 要件

Status: Complete (implementation / isolated verification / shared Neon migration)

## 目的と範囲

Threadの閲覧・Response投稿を、v0.9と共通のAccount条件、設定UI、Policy評価器で制御する。
Templateは別Versionで実装し、今回、親Templateの保存・推奨・強制処理を追加しない。

## 決定済みの方針

- Threadの閲覧・返信はThreadPolicyで判定する。親Room・BoardのPolicyを動的にANDで重ねない。
- 操作ごとに許可・不可を持ち、Item間OR、グループ内AND、不可優先、空の許可は不許可とする。
- 既存Account条件からGuest、NiixyAccount、自分のNiixyID、特定Account、Room参加を選択する。未対応のAccountIF・Field条件は保存時に拒否する。
- 条件の定義とLabelをSnapshotで保存する。履歴の削除・変更は保存済みPolicyを変えない。Room参加などの現在状態は利用時に判定する。
- 自分のNiixyIDは保存者のIDへ確定する。GuestのDefault候補はGuestのみで、履歴は一時保持する。
- ThreadPolicyは作成時に確定し、作成後変更しない。ログインした作成者の既存の閲覧例外を維持し、返信に例外を広げない。
- 返信POSTでは閲覧と書込の両方を確認し、不可の場合は投稿を作成しない。
- BoardでThreadを作成する操作には引き続きBoardの閲覧・作成判定を使う。これは作成後のThread利用判定とは別である。
- Account・NiiMap・Board・復元の各導線で同じ判定を使い、本文、投稿一覧、Field値、Interface値を閲覧不可Responseや検索結果に含めない。

## 設定と不可時UI

NiiMap・BoardのThread作成フォームのPolicy欄を、閲覧可能／閲覧不可／書込可能／書込不可の四欄とし、既存Account条件選択Paneを使う。

閲覧不可でも到達可能な一覧に存在を残す。Summaryは「閲覧不可・Title・更新日時」でクリック可能とする。詳細HeaderとCloseを残し、Bodyに不足した許可条件と該当した不可条件を示す。返信不可は投稿欄の位置に角丸枠の説明を常時表示し、Policy全体への導線を残す。ORの選択肢を「すべて必要」と案内しない。

## 移行と初期値（2026-10-05合意）

既存データは開発テストデータとして、旧Guest/NiixyAccount保存ルールだけを共通条件へ移す。旧固定Room参加ゲートは条件として永続化せず除去する。非参加者の返信範囲が変わり得ることは承認済み。本文、Response、配置、Field、Interfaceは削除しない。旧ルールが空の場合は空を維持する。共有Neonへの反映は追加承認を受け、バックアップと隔離SQLite復元確認の後に0016/0017のみ適用した。

Templateなし新Threadの初期値はNiiMap・Boardとも閲覧/書込がGuest OR NiixyAccount、不可なしとする。作成時に変更できる。一律Room参加初期値は設けない。GuestのDefault候補がGuestのみであることと、この既定Policyの値は別である。

## 閲覧不可時の公開範囲（合意済み）

閲覧不可時はTitle・更新日時・閲覧不可表示/理由だけを公開し、件数・配置・Field/Interfaceメタ情報をHTML/JSONに返さない。検索で保護内容から存在や値を推測できないようにする。

## 受入条件

- 各対応条件、許可OR、AND、不可優先、空許可、作成者閲覧例外を保存・判定できる。
- 履歴変更や参加・退出による挙動がSnapshotと現在状態の区別に一致する。
- 各作成フォームから条件設定ができ、拒否Response、検索、AccountのResponse履歴に保護内容が漏れない。
- 閲覧不可ThreadをBoard一覧から消さず、親Board自身を閲覧不可なら子一覧は返さない。
- 旧データの移行は合意した互換性に従い、無承認の公開範囲変更をしない。
- Threadに明示保存したRoom条件はBoard削除後も維持する。
- Django・JS構文・隔離SQLiteブラウザPC/mobileで検証し、既存Workspace、展開/Close、Field/ThreadIFを維持する。

## 対象外

Template、Layout、RoomPolicy、ResponsePolicy、作成後Policy編集、管理権限委譲、未対応条件の実評価、成立不能AND検出、共有DB更新。


## 検証とローカル反映

2026-10-05、全153 Djangoテストが通過した。Response履歴の拒否Summary集約を追加後、影響範囲のAccount＋ThreadPolicy 49テストも通過した。migration 0015→0017は隔離SQLiteで実適用し、旧Guest/Account保存ルールだけをコピーし、空Policy・本文・旧ルールを保持することを確認した。Django check、未生成migrationなし、変更JS構文、git diff --checkも正常。

隔離SQLiteのStaticLiveServerTestCaseでEdge PC/mobileのNiiMap/Board四欄設定、GuestのDefault候補、条件追加、reset、拒否詳細、reload復元、Closeを確認した。Workspaceは展開/Closeのtransitionrun・transitionendとRAFの途中位置、連続切替、子孫置換、破棄後の遅い応答、補助Pane、復元、reduced-motionを検証した。browser_smoke.py CLIも同じ隔離サーバーに実行し、PC/mobile画像を目視した。任意のfavicon.ico 404は既存smokeと同じ除外とし、それ以外のconsole/page errorを失敗として扱った。

閲覧不可の件数・配置・Field/Interface関連情報はHTMLに含めず、地図座標はmarker JSONへ返さない。NiiMapでは座標を使わず拒否Summaryを一覧に残す。本文/Field/InterfaceやCreator/Policy条件で保護対象を推測する検索は返さず、Titleと更新日時は検索可能とする。Response履歴の拒否Summaryは同じThreadを一行にまとめ、重複行やページ数からResponse件数が漏れないようにした。

2026-10-05、ユーザーが共有Neonへの移行とcommit/push・Vercel反映確認を追加承認した。migration対象のThread 33件・ThreadPost 61件・旧ThreadAccessRule 125件を認証情報なしの移行範囲限定JSONとしてGit管理外にバックアップし、隔離SQLiteへの実復元で219件すべての一致を確認した。通常Neonに0016/0017のみ適用し、トランザクション内で旧3テーブルの全レコード不変と新ThreadPolicyCondition 125件の内容一致を検証した。全DBバックアップではなく、移行が変更しない参照Account・他テーブルは復元対象に含めていない。公開アプリとのコード同期のため、追加承認されたcommit/pushとVercelの対象SHA確認を行う。通常runserverはAGENTS.mdの親子プロセス・port確認に従って再起動する。データ削除・投稿・設定変更は行わない。

再検証コマンド:
- `.\.venv\Scripts\python.exe manage.py test --noinput`
- `.\.venv\Scripts\python.exe manage.py test scripts.thread_policy_browser_tests scripts.workspace_browser_tests --noinput`

生成画像と検証ログは未追跡の `.artifacts/thread-policy/`、`.artifacts/browser-smoke/`、`.artifacts/workspace-regression/` に保存する。

隔離ブラウザ検証の途中で、Django LiveServerが全リクエストスレッドへ共有するin-memory SQLite接続の同時使用により、prefetch時にInterfaceError（bad parameter or other API misuse）が発生した。scripts/browser_test_server.pyのテスト専用handlerでapplication呼出しを直列化し、最終3ブラウザテスト（PC/mobileで各6回reloadを含む）を通過した。この対策はテストfixtureに限定され、アプリ本体・通常runserver・共有Neonの並行処理を変更せず、それらのDB競合を検証したという意味でもない。
