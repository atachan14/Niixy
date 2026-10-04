
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



- SummaryListのレイアウト見直し

具体的にはよくわからん。

SummaryItemの左にBorderを入れた分、Itemがちょっと右に寄ったように感じるし、仕方ないようにも思うし。
余白なしで左にベタ付けでもいいんじゃないかって気もするし、良くない気もするし。
とりあえず、背景色は保留にしても、上下右のBorderは1pxとか2pxとかで入れてみて良い気がするし、やめたほうが良い気もするし？
やるなら角丸のほうが良い気がするし、そうとも限らない気もするし？
左Borderを16pxとかにして、画面左にベタ付けって案もある気がするし、何も見やすくはならない気がするし。

てか、そもそもSummaryItemが縦に太すぎるって問題もありそう。
スマホ版で特にそうだけど、PC版でも既に太そう。
でもSummaryItemだけ細くするとバランスが崩れそうだから、HeaderやらTabやらなんやらも小さくする必要ありそう？っていうかスマホ版のAccountPageやRoomPageの機能ボタン群のサイズ感がとても良い。全体的にそのくらいの調整にすると良くなりそうな気もするし、大がかりな調整で大変そうにも思うし。

Codexくんはデザインもできるじゃん？どう思う？？

## now



## Idea



## backlog

- Policy周り
    - 書き込み不可理由に、Policyに表記のない[RoomAに参加]が表記されてる。
    - Roomの初期Board
        - お知らせ（Thread作成権限がOwnerのみ）
        - 掲示板（権限がフリー）

- Account > Board
    - tab
        - Main（デフォルトCollection。削除可。）
        - CollectionA（ユーザーが追加するやつ）
        - fav
        - bad
    - SummaryList
        - BoardA
        - BoardB
        - BoardC



- Feedback（もっと端的な言葉にリネームしたい）
love/hateは排他的で紹介文とセット。
muteは紹介文無しでも可。紹介文と関係ない。
紹介文を削除したらlove/hateも削除される。
    - Header
        - [評価] | [X]（Lover-Hater）
        - [Love] 色でTrue/falseを表現。
            - クリックでBodyに紹介文作成窓を展開。
        - [Hate] 色でTrue/falseを表現。
            - クリックでBodyに紹介文作成窓を展開。
        - [Mute] 色でTrue/falseを表現。
            - クリックでMuteに追加/解除。
        - [Listに追加]（紹介文作成済（Love or Hate選択済）の場合だけ表示）
            - クリックでAccountList選択Paneを追加。
    - Body
        - Tabs
            - 全ての紹介文(x)
            - Lover(x)
            - Hater(x)
            - Muter(x)
        - Tabs
            - 更新順
            - 紹介文の評価順
            - 作成者の評価順
        - 一覧（Muterのときのみ[#1 Account名@NiixyID 時刻]の1行表示。他は紹介文。紹介文は最大3件。Muterは最大8件くらい？）
            - 紹介文
                - デフォルトLayoutのResponseと殆ど一緒。唯一違うのは、[表示名@NiixyID]の右に[Love/Hate]のどちらかを表示する。
            - 紹介文
            - 紹介文
            - もっと見る（クリックで一覧を、紹介文10個分くらい+ページネーション+畳む（収納導線） くらいに拡張。）
