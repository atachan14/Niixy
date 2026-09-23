# Profile Pane Refactor Handoff

更新日: 2026-09-23

## 目的

Profile の初期表示を軽くし、Thread、Response、将来の Room / Book / Timeline などを追加しても、初期HTMLに全一覧・全詳細を先読みしない構造へ変更する。

## 採用方針

- 公開Profileは `/accounts/<NiixyID>/` を基点にする。
- 閲覧体験は別ページ遷移ではなく、Profile内のPaneスライドを維持する。
- Paneの状態はURLにも反映する。暫定案:
  - `/accounts/<NiixyID>/?pane=thread`
  - `/accounts/<NiixyID>/?pane=response`
  - `/accounts/<NiixyID>/?pane=response&thread=<ThreadID>&post=<PostNumber>`
- `history.pushState()` / `popstate` を使い、戻る・進む・リロード・共有URLでPane状態を復元できるようにする。
- Profileの初期HTMLは概要だけを返す。
- Thread / Response ボタンを押した時点で一覧Paneを取得する。
- 一覧内のThread見出しを押した時点でDetailPaneを取得する。
- 一度取得したPaneやDetailはブラウザ側で保持して、同じProfile内での往復を速くする。

## ResponsePane 要件

- Profileの `Response` ボタンから、ThreadPaneと同じ `一覧Pane | DetailPane` 構造を開く。
- Tabは `作成 / fav / bad / bookmark`。v0.4.1では `作成` だけ実装する。
- `#1` は含めず、Accountが投稿した `#2` 以降のResponseを一件ずつ、投稿日時の新しい順に表示する。
- Itemは次の順で表示する。
  1. `ThreadTitle (Response数)` のHeader
  2. 通常のThread内表示と同じResponse本体
- Headerを押すと対象ThreadをDetailPaneに表示し、対象Responseへスクロールして一時強調する。
- 発見権限がないThreadはItem全体を表示しない。
- 発見できても閲覧権限がないThreadは、Headerだけを表示しResponse本文は出さない。
- 一ページ10件、ページネーションを使う。

## 現在の実装状況

- v0.4.1の表示名、MyPage、Headerメニュー、`AccountProfile` Migrationは実装済み。MigrationはNeonへ反映済み。
- Threadの`返信`Tabは廃止済み。
- ResponsePaneを一度仮実装したが、ThreadPaneと同じGridに混在してレイアウトを壊したため撤去した。
- 現在の未コミット差分は、仮ResponsePaneを外してThreadPaneを元の `Thread一覧 | DetailPane` へ戻す正常化作業である。
- 現在のテストは `manage.py test accounts events` が18件通過している。

## 次に行う実装順

1. 現在の正常化差分をユーザーが画面で確認し、必要ならコミットする。
2. Profile本体テンプレートからThread一覧とThread詳細の先読みHTMLを外す。
3. Thread一覧PaneとThread DetailPaneを返す部分テンプレート・取得エンドポイントを作る。
4. Profile側JSでPane取得、表示、キャッシュ、URL更新、戻る・進むを実装する。
5. ResponsePaneを同じ取得基盤で実装する。
6. Thread詳細で特定Responseへ移動・強調する処理を追加する。
7. Discover / View / Write権限、ページネーション、Guest/Accountのテストを追加する。

## 注意

- 既存のProfile実装は、Thread一覧の先頭10件と、それらの詳細ThreadPostを初期HTMLに描画している。
- 今回のリファクタでは、見た目のPaneスライドを保ったまま、データ取得だけを遅延化する。
- Room、Book、Timelineなどを同じProfileへ追加する前に、このPane取得基盤を完成させる。
