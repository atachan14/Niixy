
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

Thread詳細Paneでの「ThreadIF」アコーディオンのレイアウトで迷っててさ、
てか「制限」アコーディオンも要件として追加するつもりなんだけど
- ThreadIF
    - InterfaceA
    - InterfaceB
- 制限
っていう二重アコーディオンは見た目的にも操作的にもやっぱ重いかなぁ。
「ThreadIF」っていう親アコーディオンを廃止して
- InterfaceA
- InterfaceB
- 制限
ってする案も検討中だけど、
Interfaceが継承を前提としてる都合上、1Interface毎に1フィールドみたいなのを大量に継承するとめっちゃ縦長になっちゃうよね。
もはや、上記のアコーディオンとか関係なく、各フィールドの上に各Interface名も陳列されるっていう。

てことで、フィールドはInterfaceの外で定義するって案を考えてる
「開始時間@NiixyID v1/field」
みたいな。
で、Interfaceは、Interface外で定義済みのフィールドから好きなものを選択してまとめる。
「参加状況」みたいな既存フィールドを参照して自動反映するようなフィールドはフィールドがRequireFieldを持つ。
DisplayLayoutもRequireFieldを持って、InterfaceはDisplayLayoutも保持できる。
「参加」ボタンみたいな機能もRequireFieldを持つのかなぁ。この辺はどういう仕組みで実装するかまだ見えてなくて、よくわかんないね？

Interface
    Field
        RequireField
    function
        RequireField
    DisplayLayout
        RequireField

こういう感じになるのかなぁ？
そしたら、Interfaceを多重継承してInterface欄が縦長になる問題が、
たくさんのFieldを保持した1つのInterfaceで表現できるようになりそう？
そしたらもう、ThreadIFは1つまででいっか。AccountIFは微妙に事情変わるかもだけど。

この案どう思う？

## Idea

