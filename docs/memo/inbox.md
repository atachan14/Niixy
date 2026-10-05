
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

- AND選択ボタン要らないかも？AND選択を選択しなくても、Itemクリックで複数選択、追加ボタンでANDグループとして追加で十分わかりやすそう。複数選択だとわかりやすいよう、追加ボタンに選択件数を表示する。


- 更新時に現在CurrentPaneから動かないようにしたい！NiiMap > Thread詳細までは、確かその処理入ってたよね？NiiMap > Room > Board一覧...みたいに進んでいくと、更新時に一度Spot一覧くらいまで戻ってから現在Paneまで再走するアニメーションが入っちゃう。




## now




## Idea




## backlog

- Policy周り
    - （最新Verで再確認が必要）書き込み不可理由に、Policyに表記のない[RoomAに参加]が表記されてる。
    - Room作成時の初期Board
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
        - [追加]（紹介文作成済（Love or Hate選択済）の場合だけ表示）
            - クリックでAccountList選択Paneを追加。
        - [DM]（送信条件はAccountPolicy）
            - クリックでDM送信Paneに遷移。
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

- AccountPageやRoomPageのHeaderの右端に作成日
- 各PaneのHeaderを座標行くらい細くして、座標行は更に細くする。
- RoomPageの座標行もstickyにする。
- 全幅や残り幅のPaneのBorder（Headerや座標行やThreadPost等）もPaneの端から端までにする。Roomの座標行が.room-overview-contentの中に入ってるのもよくない。
