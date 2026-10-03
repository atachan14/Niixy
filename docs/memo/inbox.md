
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

- Ownerの場合、グレーアウトしてる[参加中]のボタンは[Owner]にしようかな。
- Owner以外のメンバーの場合、[退出]は[退会]

## now

おっけい！確認できた！
一回Git挟むか！

## Idea

- Roomの初期Board
    - お知らせ（Thread作成権限がOwnerのみ）
    - 掲示板（権限がフリー）

- Threadの座標行をfixed化。

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
muteは紹介文無しでも可。
    - Header
        - [評価] | [X]（Lover-Hater）
        - [Love] 
            - クリックで紹介文作成窓を下に展開。
        - [Hate] 
            - クリックで紹介文作成窓を下に展開。
        - [Mute]
            - クリックでMuteに追加。
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
            - Accountの評価順