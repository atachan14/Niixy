# Account と履歴

## Account ページ

将来の Account ページは、単なるログイン設定画面ではなく、公開プロフィールと活動履歴を扱う。アカウントのサムネイル、表示名、Niixy ID、選択した AccountInterface の情報、作成した Interface、活動数、Thread、ThreadPost、Book、将来的には Event 参加、Tweet、Room の履歴を表示できるようにする。

表示名は Niixy ID とは別の、重複を許可する呼び名である。空欄を許可し、絵文字は使わない。表示幅は全角 12 文字・半角 24 文字相当までとする。多くの画面では `表示名 @NiixyID` を基本の表示順とするが、DisplayLayout を含むすべての画面に強制する共通レイアウトにはしない。

Account ページでは、SiteHeader の直下に `表示名 @NiixyID` を表示する細い AccountPageHeader を固定する。Account の活動一覧や詳細Paneへ画面内遷移した後も、現在閲覧している Account を識別できるようにする。Account ページの SiteHeader は Niixy ロゴを中心とし、Account 名や Niixy ID を含む長いパンくずは置かない。

## Book と購読

Account は Book を作成でき、他者の公開 Book を購読できる。Account ページでは作成した Book と購読中の Book を扱う。Book は日記やブログを含む Thread のコレクションであり、独立した Note 投稿形式は作らない。

## Album とサムネイル

Niixy では一般的なアバターを使わない。Account は自由に画像を Album へ投稿し、その一つをサムネイルに選択できる。ThreadPost の表示にはサムネイルのスナップショットを使い、Account が後から選び直しても過去の投稿表示が変わらないようにする。

## 保留する機能

Account ページ、Book、Album、画像モデレーション、アカウント評価、紹介文、フォロー、Tweet、Event 参加は v0.3 の対象外である。
