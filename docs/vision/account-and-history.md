# Account と履歴

## Account ページ

将来の AccountPage は、単なるログイン設定画面ではなく、公開プロフィールと活動履歴を扱う。アカウントのサムネイル、表示名、Niixy ID、選択した AccountInterface の情報、作成した Interface、活動数、Thread、ThreadPost、Board、Collection、将来的には Event 参加、Tweet、Room の履歴を表示できるようにする。

表示名は Niixy ID とは別の、重複を許可する呼び名である。空欄を許可し、絵文字は使わない。表示幅は全角 12 文字・半角 24 文字相当までとする。多くの画面では `表示名 @NiixyID` を基本の表示順とするが、DisplayLayout を含むすべての画面に強制する共通レイアウトにはしない。

Account ページでは、SiteHeader の直下に `表示名 @NiixyID` を表示する細い AccountPageHeader を固定する。Account の活動一覧や詳細Paneへ画面内遷移した後も、現在閲覧している Account を識別できるようにする。Account ページの SiteHeader は Niixy ロゴを中心とし、Account 名や Niixy ID を含む長いパンくずは置かない。

## MyPage と管理

MyPage は、本人だけが使う Account の管理ハブとする。公開 Account ページは、本人が開いた場合も含めて公開状態を閲覧する場所とし、編集や管理の操作を集約しない。

MyPage は将来、Album とサムネイルの管理、AccountInterface の実装・作成・更新、ProfileLayout の選択・作成・更新を担当する。Profile 側のサムネイルは Album を閲覧する導線とし、本人であっても画像の変更などの管理操作は MyPage 側から行う。フォロー管理、参加中 Room、通知などの本人用機能も後続で MyPage に追加する。

## Board と Collection

AccountはCollectionを作成し、Boardを掲載できる。初期状態ではMain Collectionとブログ用Boardを用意する方向とする。日記やブログは独立したNote投稿形式を作らず、Board内のThreadとBoardの表示方法で表現する。

AccountのCollectionに配置されたBoardは、そのAccountが管理する。Boardは独立したOwnerを持たず、管理主体は配置先から決まる。Collectionを削除した場合、そこに配置されているBoardは同じAccount内のシステムCollection「未分類」へ移す。

他者のBoardを自分のCollectionへ追加する操作は参照として扱い、Board本体の配置先や管理主体を変更しない。BoardのFollowは設けず、Collectionへの追加と将来の通知購読を別の機能として扱う。

## Album とサムネイル

Niixy では一般的なアバターを使わない。Account は自由に画像を Album へ投稿し、その一つをサムネイルに選択できる。ThreadPost の表示にはサムネイルのスナップショットを使い、Account が後から選び直しても過去の投稿表示が変わらないようにする。

## 保留する機能

ProfileArea、BoardとCollectionのAccount向け管理、Album、画像モデレーション、アカウント評価、フォロー、Tweet、Event参加はv0.6の対象外である。
