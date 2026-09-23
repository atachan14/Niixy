# Niixy v0.4.1 要件

## 目的

本人用の最小 MyPage を追加し、Account の基本情報として表示名を編集できるようにする。表示名を公開 Profile、MyPage、ThreadPost の Account 投稿者表示へ反映する。

## スコープ

- `/mypage/` をログイン必須の本人用ページとして追加する。
- SiteHeader 右側のログイン中メニューを `マイページ / プロフィール / ログアウト` にする。
- MyPageHeader に `表示名 @NiixyID のマイページ` を表示する。
- MyPage の初期表示は、サムネイルのプレースホルダーと機能ボタン群を並べる。
- v0.4.1 では機能ボタン群の `基本情報` だけを有効にする。
- `基本情報` を選ぶと、Profile の Thread 表示と同様に概要からPaneを切り替え、表示名を編集・保存できる。
- 表示名を Profile のHeader、MyPageHeader、ThreadPost の Account 投稿者表示へ反映する。

## Account 基本情報

表示名は Account の基本情報であり、AccountInterface には含めない。

- 空欄を許可する。
- 重複を許可する。
- 前後の空白は保存時に削除する。
- 改行、制御文字、絵文字は許可しない。
- 表示幅は全角12文字相当、半角24文字相当までとする。
- 空欄時は `@NiixyID`、入力時は `表示名 @NiixyID` を基本表示とする。
- この基本表示は全画面に強制しない。DisplayLayout など、個別の表示仕様は将来決める。

## MyPage

### 公開 Profile との役割分担

- 公開 Profile は、本人を含めて公開状態を閲覧するページとする。
- MyPage は本人だけが使う管理ハブとする。
- Album、サムネイル、AccountInterface、ProfileLayout、フォロー管理、参加中Room、通知などの管理は将来 MyPage に追加する。
- v0.4.1 では画像のアップロードやサムネイル選択は実装しない。

### レイアウトと動線

- SiteHeader の直下に MyPageHeader を固定する。
- 初期画面は左にサムネイルの未実装プレースホルダー、右に機能ボタン群を置く。
- `基本情報` を選択すると、概要を左へ退避し、基本情報Paneを表示する。
- PCと小さい画面のどちらでも、概要と基本情報Paneを横スライドで切り替える。
- 編集完了後も MyPage を表示し、保存結果と最新の表示名を反映する。

## SiteHeader の Account メニュー

ログイン中は `@NiixyID` を押してメニューを開く。

1. マイページ: `/mypage/`
2. プロフィール: `/accounts/<NiixyID>/`
3. ログアウト

未ログイン時は既存どおり `新規登録` と `ログイン` を表示する。

## Security と Validation

- MyPage と更新エンドポイントはログイン必須とする。
- 更新対象は常に `request.user` とし、フォーム値で対象Accountを指定できない。
- CSRF を有効にする。
- サーバー側で表示名のValidationを行う。クライアント側の `maxlength` などは補助にすぎない。

## 対象外

- サムネイル画像、Album、画像ストレージ、画像モデレーション
- 紹介文、AccountInterface、ProfileLayout の実装・編集
- フォロー、DM、Mute、通知、参加中Room
- MyPage における Thread、Response、Room、Book の管理一覧
- DisplayLayout への表示名の強制適用

## 完了条件

- 未ログイン利用者は MyPage を開けない。
- ログイン中利用者は SiteHeader のメニューから MyPage と自分の Profile を開ける。
- MyPage で空欄または有効な表示名を保存できる。
- 無効な表示名は保存されず、対象入力欄にエラーを表示する。
- 保存した表示名が MyPage、公開 Profile、ThreadPost の投稿者表示に反映される。
