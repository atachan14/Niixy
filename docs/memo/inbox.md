
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

一覧Paneでのスワイプはある程度良い感じなんだけど、詳細Paneでは一覧Paneのようなスワイプにならない。Mapの表示領域を確保したまま、つまりめっちゃ狭い範囲で詳細Pane内だけをスクロールしちゃう。
詳細PaneHeaderの固定化が悪さしちゃってるのかな？

けど、一覧Paneにおいてもスワイプ時、Site-Headerの裏にMapが潜り込んじゃってるみたい？Headerの裏にちょっとMapが透けて見えてる。

この辺のCSSやDOMの構造、一回きちんと整理したほうがいいか？

## Idea

