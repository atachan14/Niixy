# Mute / Muter

Status: 公開済み（最新公開基準 `e17e00e188e6863914a0863dc33c67f19cf85e6f`、親工程からの引き継ぎ）。新しいVersion番号は未割当。以下の実装開始時の基準・公開計画・隔離QAの「未実施」は当時の記録として保持する。accounts0003～0005、rooms0010～0011、interfaces0010は共有環境に適用済み。[最新状態と検証境界](qa-status-2026-10-06.md)を参照する。

2026-10-05承認済みの次工程。Muteは公開の意思表示であり、Love / Hateと紹介文を持つReviewとは独立した行に保存する。紹介文は不要。Review削除でMuteは消えず、Mute解除でReviewは変わらない。

## 保存と表示

`AccountMute(muter, muted_account, created_at)`を追加し、組合せを一意にする。ログイン本人だけが他AccountへのMuteを追加・解除できる。自分へのMuteは通常意味がないため既存の自己Review禁止と揃えて禁止する。APIは本人をrequest.user、対象をURLから取得し、POSTされた別Accountの指定を無視する。POST / CSRFを使い、enabled=true / falseの明示状態で重複追加・重複解除を冪等にする。DBでも一意・自己Mute禁止を保証する。

既存Reviewヘッダへ保存状態付きMuteボタン、Bodyへ公開Muter(count)タブを追加する。Muterは対象をMuteしているAccountsを表示名 @NiixyID・日時の一行Summaryで新しい順（同時刻はID降順）に表示する。初期8件、もっと見るは10件単位、前へ / 次へ / 畳むを既存Reviewと共通化する。Guestは閲覧でき、操作ボタンはGuest / 本人で無効。Muterタブで公開性が分かるため追加の「公開される」警告は設けない。

Mute変更成功後は現在URLを再取得し、保持している一覧・本文・map markerを一緒に更新する。解除によって初期HTMLに無かった対象も復帰する。Workspace内に未保存Reviewがある場合は、既存共通Paneと同じwindow.confirmで送信前に入力破棄の確認を求める。キャンセル時は送信・再取得を行わず、開いている／閉じた／別AccountのReview入力と保存済み評価を保持する。破棄を承認した場合だけMute変更後に再取得する。送信中はReviewの入力・新規編集を固定し、後から入力を黙って失うことを防ぐ。通信失敗時は変更済み表示にせずエラーを示し、再送を可能にする。重複POSTは状態を反転しない。

## 本人の表示filter

Muteをアクセス制御に使わない。共通`accounts.mutes.filter_muted`で閲覧者本人のMuteを取得し、Threadはcreator、Boardはcreator、Roomはownerを一覧queryから除外する。AccountのThread一覧、Response履歴のThread見出し、Room一覧、Account / RoomのBoard一覧、BoardのThread一覧、NiiMap一覧 / search / markerに適用する。ページ件数はfilter後、BoardのThread件数もfilter後の同じ条件で求める。Response自身は数と番号を残し、本文を「ミュート中 · 一時表示」の折り畳みにする。一時表示はそのDOMだけを展開し、Muteを解除しない。HTML escapeと既存ThreadPolicyによる本文非公開は維持する。

NiiMapの直接`?thread=`は必要な詳細だけを取得し、filtered SummaryList / markerへ対象を戻さない。直接Thread / Board / Room URLは従来のPolicyと配置先管理判定に従って開ける。Guestには個別Mute状態がない。他AccountによるMuteは対象本人の閲覧・投稿にも影響しない。公開Muter countとReview scoreに表示filterを適用しない。Block、通知、DM拒否、新しいSecurityPolicyを導入しない。

個別表示queryを共有cacheに保存しない。対象ページ・断片にはprivate / no-storeを付ける。Mute IDsの一括取得は各一覧準備処理内に限定し、共有または永続user cacheに保持しない。

## Board creatorとmigration

`Board.creator`はnullable / SET_NULL。新規Accountの日記は本人、新規Roomの初期お知らせ・掲示板は実作成主体のOwner、Account / Room内とNiiMapでの新規Boardはrequest.user、Guestはnullを記録する。既存unknownはnullのままで、配置先やRoomOwnerから推測backfillしない。初期Boardを再生成する経路も追加しない。creatorはMute判定だけに使い、Owner・編集・削除権は追加しない。管理主体は従来どおり配置先から決まる。

追加migrationは`accounts/0004_accountmute`と`rooms/0010_board_creator`。Reviewの`accounts/0003`と既存`interfaces/0009`を前提にする。schema追加だけで既存値やPolicyを書換えず、データbackfillは含めない。共有Neonへの適用、public push、通常server再起動は親taskが影響を確認して公開順序を調整する。新コードは0003 / 0004 / 0010適用後に有効化する。rollbackは先にコードを戻し、Muteとcreator記録を保全する。追加migrationの逆適用は自動で行わない。

## 隔離QA

`manage.py test accounts.tests_mutes accounts.tests_mute_migration accounts.tests_reviews accounts.tests_review_migration accounts.tests.AccountPageTests rooms.tests_account_boards rooms.tests_map_boards scripts.mute_browser_tests`をSQLiteテストDBで実施する。PC / mobileはEdgeの隔離LiveServerを使い、同じserverで既存browser_smoke.pyのentry pointを実行する。通常runserver / 共有Neonにテストデータを作成しない。

今回対象外: AccountList、fav / bad、Collection rename、通知、DM、Review評価sort、公開環境反映。PostgreSQLでの実並行競合と公開後Guestの確認は公開工程へ引き継ぐ。


2026-10-05の結果: 直接回帰55件（Mute11件、Mute / Review migration2件、Review10件、AccountPage15件、Account Board / Map Board17件）とPC / mobile browser1件が成功。browser内の既存smokeは両viewport各17check、warnings / browser_errorsとも0。Muter / Response / WorkspaceのPC・mobile画像を目視確認し、mobileの長いMuter名による横はみ出しを修正して、viewport / scroll幅assertionとブラウザを再実行した。`manage.py check`問題なし、`makemigrations --check --dry-run`追加差分なし。途中の失敗はテスト期待（Roomの既存非表示説明、Review count契約、Board selector、更新asset version）と上記横幅問題を修正済み。全域反復は行っていない。

画像は`.artifacts/mute/`と`.artifacts/browser-smoke/`に未追跡で保存する。通常serverは37132 → 34712（開始2026-10-05 21:48:11、8000 listener 34712）を維持し、起動・停止・restartは行っていない。共有Neon migration / テスト書込み、push、公開後GETは未実施。公開DB上の行保全・PostgreSQL並行競合は未検証。新規migrationはコード準備だけで、隔離SQLite以外に適用していない。root READMEは不変更、inboxの既存差分は変更・stageせず残す。


追補（未保存Review保護）: Mute送信前にWorkspace全体のdirty draftを確認し、既存共通Paneのwindow.confirmで破棄確認する。CancelではPOST / reloadを行わない。未変更のReviewでは確認不要。入力と別AccountのReview保存をMute送信中に進めず、成功時はnavigationまで固定、失敗時は元のdisabled状態とdraftを復元する。永続storageへdraftを保存しない。隔離対象3件（新しいPC / mobile確認試験、既存Review browser回帰、asset marker直接試験）が成功し、既存smokeは各17check / warnings・browser_errorsとも0。さらに新規対象だけを再実行し、保留Mute失敗時の入力固定・復元も確認した。通常server / 共有DB / pushは未実施、新規migration追加なし。
