
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

- Account > Room
    - tab
        - OwnerTab
        - 参加中Tab（Owner含む）
        - RoomListA
        - RoomListB
        - love
        - hate
    - SummaryList
        - RoomA
        - RoomB
        - RoomC

- Ownerの場合、RoomPageでグレーアウトしてる[参加中]のボタンは[Owner]にしようかな。
- Owner以外のメンバーの場合、[退出]は[退会]のほうがニュアンスに合うかな？[退団]でも面白そう。

## now



## Idea

- Roomの初期Board
    - お知らせ（Thread作成権限がOwnerのみ）
    - 掲示板（権限がフリー）
- Roomの[メンバーX]の表記を[メンバー(X)]に変更。
- Board一覧のSummaryItemをBoard名([Thread数])表記にする。
- SummaryItemの色について、カード的な表現は保留としても、Spot以外のSummaryListにも色を反映させるとこまでは確定として共通化したい。

- Threadの座標行をfixed化。

- RoomPageやAccountPageのスマホレイアウトについて
    - [Thumb左上配置について]Thumbを左上にするレイアウトで統一するって話だったけどRoomPageでしかその仕様になってない。AccountPageではThumbの下に機能ボタン群を配置する以前の仕様のままになってる。
    - [文字サイズについて]Thumb左上配置を適応すると、すごくぎゅうぎゅう詰めになるけど、そもそもスマホ用として文字やボタンが大きすぎる。もっと小さくして～～で、Thumbの高さは機能ボタン群の高さに合わせて～～。

- Profileの機能ボタン上に予定していたボタン群を廃止して、Feedbackに移す。

- AccountPageの機能ボタン群修正案
[AccountIF] [Account]
[Thread] [Response]
[Room] [Board]
[Timeline] [Module]
    - AccountIF
        実装済みのAccountIFをSummaryListに表示。クリックで[実装済みAccountIF閲覧Pane]を展開。
    - Account（AccountIFと文字列が似すぎてるからリネームしたい）
        - Tabs
            - AccountListA
            - AccountListB
            - Love
            - Hate
        - SummaryList

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