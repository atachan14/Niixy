# v0.11 - Room初期BoardとBoard作成Policy

Status: Complete (local implementation / focused verification)

関連Backlog: [BL-001 / BL-003](../backlog.md)。新規Roomの初期構成と、手動Board作成時のPolicy設定を扱う。

## 新規Room

- 新規作成時だけMain Collectionに「お知らせ」「掲示板」をこの順で生成する。説明は空。従来の「最初のBoard」は生成しない。既存Roomへの追加・移行は行わない。
- 両Boardの閲覧可能条件はGuest OR NiixyAccount、閲覧不可条件は空。
- 「お知らせ」のThread作成可能条件はRoom作成者の特定Account Snapshot。作成時のAccount IDに固定し、後のOwner変更に動的追従しない。
- 「掲示板」のThread作成可能条件は当該Room参加者。Ownerも既存の参加membershipにより含まれる。両BoardのThread作成不可条件は空。
- 特別な保護は設けず、通常のRoomOwner管理権限で名前・Policyの編集と削除を可能とする。
- Room・参加membership・配置・Main／未分類Collection・2Board・配置・Policyは一体のトランザクション。重複送信は既存のsubmission_id方式で処理する。

## 手動Board作成

既存のBoard編集と同じ共通Account条件UIと評価器を用い、閲覧可能／閲覧不可／Thread作成可能／Thread作成不可の4欄を設定できる。

初期値は従来どおり閲覧Guest OR NiixyAccount、Thread作成Room参加者、不可条件は空。Policy未送信の旧payloadは初期値を維持する。明示的に送信した空allowは空として保存し、既存のdeny-all意味とOwnerの閲覧例外を維持する。条件を1つ以上選ぶ必須要件は追加しない。

サーバーでOwner認可と条件Snapshot検証を行う。不正なPolicyならBoard・配置・Policyを残さず400を返す。UIの起点Paneと入力を保持し、条件選択から復帰して作成できる。

## 対象外と検証

Template、RoomPolicy、新しいrole、RoomTag、動的RoomOwner、Owner変更UI、既存Room移行、ThreadPolicyへの親Policyの動的ANDは対象外。DBモデル変更・migrationは不要。共有Neonで作成や設定変更の検証は行わない。

隔離SQLiteで初期Board／条件、通常編集・削除、手動4欄保存、明示空条件、不正入力の原子性、非Owner拒否を確認する。代表PC/mobileブラウザで条件Pickerの起点・復帰と送信を確認する。広域QAは安全な区切りまで保留し、直接検証と区別して報告する。

## ローカル検証結果

Room関連39件＋PC/mobile集中ブラウザ1件（40件、101.105秒）が通過。初期表示順とfocus整列の追加補正後は、直接影響するRoom生成6件＋集中ブラウザ1件（7件、14.076秒）を再実行して通過した。Board作成4欄の保存・明示空条件・400通知と入力保持・再試行・非Owner拒否・初期生成原子性・通常編集削除を確認した。

初期表示順はauto_now_addと同一時刻の揺れを考慮し、お知らせの活動時刻を掲示板より確実に後にする。既存の活動日時によるソートを変更しない。入力focusのnative水平scrollは作成フォーム入力だけ既存trail.alignで補正し、Pickerボタンのfocusは対象にしない。

通常runserverの読取CLI smokeはdesktop/mobileともwarnings・browser_errorsなし。Workspace画像と新しい作成フォーム／Picker画像を確認した。最後の変更は初期時刻と作成フォーム入力focusの補正で、この補正後の直接PC/mobile検証は通過したが、全Djangoや広域smokeの再走はしていない。

Django check、Python／変更JS構文、隔離設定でmigration差分なし、diff checkを確認。証跡は未追跡 `.artifacts/v11-*.log`、`.artifacts/board-creation/`、`.artifacts/browser-smoke/`。共有Neonでテスト作成・設定変更は行わず、migrationは不要。検証済み範囲のcheckpoint commit/pushと公開反映確認は承認済み。広域QAの保留範囲は上記のとおり残す。
