
# Niixy Memo Inbox

開発中に思いついたことを一時的に記録する。

ここに書かれた内容は仕様ではない。

整理・検討後、必要に応じて以下へ移動する。

* `docs/vision/`：将来構想
* `docs/roadmap.md`：実装時期・順序
* `docs/vX.X/backlog.md`：現在のバージョンで検討する作業
* `docs/vX.X/requirements.md`：実装することが確定した要件
* `docs/vX.X/decisions.md`：設計判断と理由

不要になったメモは削除する。

---

## Inbox




## now


## Idea

"Follow"は"watch"にしようかな？
Profileの機能ボタン上に予定していたボタン群を廃止して、
Love/Hateは評価、


Roomの仕様について、ざっと思ってることを書き出した！
とりあえずのたたき台として！
-------------------------
Room内では、Thread置き場（仮名：Board）を複数作れるようにする！

例
Room
    お知らせBoard（Thread作成権限がRoom管理者のみ）
        秋季Saleのお知らせThread
        ポケモンコラボThread
    会員Board（Thread作成権限やResponse権限が会員AccountIF実装者のみ）
        先日はありがとうございました。
        ポケモングミ売ってますか。
        質問スレッド
    非会員Board（Guestも書き込める）
        なんか

こういうの。
Boardの作成はRoom管理者だけでいいや。
BoardごとのPolicyもRoom管理者のみが作成・編集。

Room詳細画面も作る！
機能ボタン群以外はProfile画面と同じで良さそう！Thumbや紹介文やプロフィールはProfile画面と同じで！

機能ボタン群の代わりに表示するのはこんな感じかなぁ。
    - [実装済みRoomIF一覧ボタン][参加者一覧ボタン]
    - [Board一覧]（見出し無しで縦積み。更新が新しい順。）
        - BoardA
        - BoardB
        - BoardC
        - もっと見る
    - [Timeline一覧ボタン][Book一覧ボタン]
    - 参加に必要な条件（見出しの下に横並び。幅が足りなかったら改行）
        - Account条件A
        - Account条件B
        - Account条件C
    - [参加/参加申請ボタン]

RoomPolicyとして設定する予定だった権限は、Board側に移行する。
BoardPolicyの確認はBoard詳細画面（というよりBoard内のThread一覧画面）に導線を配置。

- BoardA [×]（いつものHeader）
- [編集（Room管理者のみに表示）][Policyを確認]
- SummaryList
    - ThreadA
    - ThreadB

------------------------


＞サムネイル｜Room名・紹介文など
Room名はProfile同様にHeaderに表示する！
紹介文（Roomとして自分で書く分？）はProfile欄を使う！
参加者や非参加者が書く紹介文はProfile同様に紹介文欄。

てか、Profile画面と併せて、[紹介文欄]と[Profile欄]の役割や名称を再定義したい！

[紹介文欄]→[評価欄]（暫定）
単に紹介文を書く/表示するだけじゃなくて、[Love/Hate]の合計や[Follower]や[Muter]の合計も表示。

[Profile欄]→[FreeWrite欄]（暫定）

ついでに、Thumbはスマホだと全画面表示になっていたけど、スマホでも左上に画面の半分幅くらいで表示にしたい。

＞Room作成時にデフォルトBoardを自動作成するか
する！名前は「最初のBoard」が良い！で、Board名も後から編集可能にする！つまりBoardにはIDも持たせたほうがよさそう？

＞Board内ThreadをNiiMapへどう表示するか
基本はRoomだけを表示！
けど、将来的に「ThreadIF：Sale」みたいなのを条件に検索することを想定すると、Board内のThreadも検索可能にする仕組みは必要！
暫定案は、検索条件で「中身を対象にする」みたいなフラグの実装！
あるいは、検索条件にThreadIFが含まれていたら、自動的にBoard内も対象にするとか。

また、SummaryItemは種類によって色を変える！
具体的な色は未決定だけど、もうそろそろ決めちゃったほうがいいか？
Thread→ThreadColor
Room/Room内コンテンツ（Board内ThreadやRoom内Bookなど）→RoomColor
Book→BookColor
TimeLine→TimeLineColor
Tweet→TweetColor
みたいな。

てか、BookとBoardで、用途が違うとはいえ機能的にはほとんど同じなの、やっぱややこしいだけな気がしてきたな。
Boardに統一しちゃおうかな。
Bookで想定していた、お気に入りBookの保存とか、その他もろもろの機能も、そのままBoard保存として使えそう。

＞Book一覧の意味
上記の通りBoardへの統一で考えてる～～
Boardの作成者はAccount/Room
Boardの配置先はAccount/Room/NiiMap座標

で、参照の共有が可能。
AccountProfile>Board一覧では
Accountに配置されているBoard/AccountがfollowしたBoard/BoardListA/BoardListB/fav/bad
みたいな将来想定。

RoomのBoard一覧ボタンは削除して、Board一覧の「もっと見る」ボタンをBoard一覧への導線とする。
Room>Board一覧では、Room管理者だけに[新規作成]と[参照追加]を表示。
[参照追加]で、他のRoomやAccountやNiiMapに配置されているBoardの参照を、Room>Board一覧に追加できる。
Room>Board一覧では、配置されているBoardと参照だけのBoardを区別せずに一覧表示して、どちらをクリックしてもBoard詳細（Thread一覧）にPane遷移する。

例えば、PokeShop本店Roomに配置されているBoardを、PokeShop大阪店Roomやその他店舗のRoomの一覧にも表示するような使い方を想定する。
PokeShop本店Roomに配置されているBoardが、ワルガキRoomに参照されたり、ワルガキAccountにfollowされるような事態も認める。
参照やfollowやBoardListへの追加やfav/badは自由として、対策は閲覧制限や書き込み制限で行う。

以前話していたThreadの共有も同様の仕様にまとめられそう？

ってのはどうじゃろか？

--------------------

てか話飛ぶけど、AccountによるBoardのFollowはやっぱりいらないかもしれないね？BoardListへの追加で十分かも。
そう考えたらさ、RoomはMainBoardListを一つだけ持ってるって捉えるのがシンプルかも？
ついでに、RoomはMain以外のBoardListも保持できるようにしてさ。

Room画面ではMainBoardListから最大3つを表示。
「もっと見る」でのBoard一覧Paneでは
Main/ListA/ListBのTabも表示。

- Main
    - 商品の追加Board（Bookで想定してた#1主体での使い方）
        - XXを入荷しました。
        - YYを入荷しました。
    - イベントのお知らせBoard
    - 本店からのお知らせBoard
- 交流用BoardList
    - 会員Board
    - 非会員Board
    - GuestBoard

みたいな。

そしたらBoardの配置先をBoardListに統一できるかもって思ったけど、
AccountにBoardを配置するってのも、AccountのMainに配置みたいになっちゃって、AccountのMainも参照を持てちゃうと、AccountにBoardを配置したかった意図とはズレてきそうだよなぁ。想定してた意図とは違ってきても、これはこれで面白いか？
って問題とは別に、シンプルにネストが深くてややこしいかもなぁって気もする。
特に「BoardList一覧」みたいな単語がまたややこしそうだから、Boardの集合に新しい名前を付けることも検討かな？

＞└─ 追加の参照先
追加される側が持つの？
追加する側が持つ想定だったけど、される側が持つほうが優れてる？
例えばBoardListAがBoardBの参照を保持する想定だった。
あるいはリレーショナル（？）みたいなDB構造とか？そんなんは要らない？

＞created_by：実際に作成操作をしたAccount
＞owner：Boardを管理するAccountまたはRoom

created_byは保持しなくていいかも。権限さえ整理されてれば誰が作成したかは要らなそう。
ownerもPolicy側で整理できてれば要らないかもしれない。
一方で、考えてみるとownerを移したり増やしたりする必要性は出てきそうな気がして、それを踏まえてもownerでの管理より、Policyでの管理にしたほうがわかりやすそうな気がするし、
でも、先に上記のBoardList周りを固めなきゃよくわかんないや。

＞ただし、SummaryItem上段に小さくPokeShop本店Roomのような管理主体を出す余地は残したい。
それめっちゃ良さそう！採用したい！
けど、それを踏まえると上記の、配置先がRoomやAccountじゃなくてBoardListになっちゃう案だとややこしいな？
やっぱownerは必要っぽいか？ownerとしてRoomやAccountを設定できれば上記案でも問題なさそう。

＞Boardは必ず一つの主配置先を持つか
持つ！ただしBoardListにするか、Room or Accountにするかは再検討！

＞Roomの最後のBoardを削除できるか
できる！Boardを使用しないRoomも認める！

＞BoardPolicyと個別ThreadPolicyはANDで重ねるか
重ねる！

＞Room管理者はOwner一人から始めるか、最初から複数管理者にするか
ちょっとわからん。Room管理者はRoom作成者から始めて、参加メンバーにRoom内Tag的なのを付与して、Room内Tag的なのを使って複数の管理者を表現する想定。


----------

＞AccountにBoardを作成した場合は、
＞1. 主配置先をAccountにする
＞2. AccountのMainへ自動掲載する
＞Roomなら同様にRoomのMainへ自動掲載する。

この案、わかりやすさはかなり良いんだけど、1つ重要な問題があってさ、
RoomのMainはRoomPaneへの表示を選択する役割があるのよ。
さっきの例でいうと、Mainには公式情報用のBoardだけを置くって運用になってるわけ。
それが、Mainに[会員Board]とか[非会員Board]とかも自動的に載っちゃうのはよくない。
かつ、さっきの例だとMainに[本店Board]の参照も持たせたい。

で、新案だけど、
RoomPaneには、Mainに限定せずに、Room管理者が選択したCollectionを表示することにしようかな。

Room
    Main
    公式情報Collection（RoomPaneに表示するよう設定する）
    交流用Collection

っていう案。

っていうか、これ、以前に話したTimeLineについての案とほとんど同じだと思っててさ、
CollectionにおいてもTimelineと同様に、Collectionの参照対象にCollectionも含められるようにしたいと思っててさ。
そういう意味でも、Timelineと仕様を合わせられるのはかなりわかりやすいんだけどさ、

これも一つ問題があって、このときMain（あるいは配置先としてのRoomやAccount）は果たして必要なのかね？
要らなそうな気がしていて、だったら更に新案の以下のほうが良くない？

- Collectionは必ずRoom/Accountに配置させる。NiiMapへの配置は無し。
- BoardはCollection/NiiMapに配置される。

こっちの案でもBoardは、Board→Collection→Roomと掲載元を辿ることができそう。

Accountの場合も、
Account
    Boardボタン
        MainTab（デフォルトで作成済みのCollection。作成したBoardが勝手に登録されるわけではない。）
            ブログ（デフォルトで作成済みのBoard。BoardLayoutで、通常の[一覧｜詳細]の2Paneじゃなく、[ThreadTitle]と[Thread#1（適度なとこで省略）]と[もっと見る]を1itemとして縦に並べた1Paneをデフォルトとする。）
        CollectionATab
        CollectionBTab

こんな感じでいいんじゃないか？
どうじゃろか？

---------------

あと、Profile下部のAboutだけど、
単に自由記述ってだけじゃなくて、Layoutを使って色々できるようにしたいんだよね。
特定のTimelineを表示したり、特定のThreadやBoardを表示したりとか。
それらを縦に並べたり横に並べたりとか。
デフォルトのLayoutをどうするかは未定だけど、自由記述の欄は設けるつもり。
自由記述の欄は追加のFieldじゃなくて基本情報に持たせちゃおうと思っていて、

つまり
1. 自由記述のField名
2. 自由記述のField（を含めるかは任意）や、その他Fieldやコンテンツを使うLayout名
3. そのLayoutによって表示されるArea名

の三つが必要そう。
⓶が決まれば、⓷は[⓶Area]で十分かなって思ってるけど、
⓵も⓶も[About]は微妙そうじゃない？

