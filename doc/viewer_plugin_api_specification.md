# YOLO Dataset Viewer - Plugin API 仕様書

## 概要
本ドキュメントは、YOLOデータセット確認ツール（`UUIDViewerDialog`）の機能を拡張するためのプラグイン向けAPI（`ViewerAPI`）の仕様を定義するものです。
プラグインはビューアの内部変数（GUIコンポーネントやデータリスト）に直接アクセスするのではなく、本APIを介して安全に情報の取得、操作、UIの拡張を行います。

## プレロード（事前読み込み）の設計方針について
画像のプレロードや重いデータ処理については、**プラグイン側で独自にキャッシュを管理する方針**（方針A）を採用しています。
プラグインは `get_data_at(index)` と `get_total_count()` を組み合わせて使用し、現在のインデックスより先の画像パスを取得して、バックグラウンドスレッド等で独自に事前読み込みを行ってください。

---

## 1. 状態取得 API (Read / Getters)
現在の状態や、データセット全体の構成情報を取得します。

| メソッド名 / プロパティ | 戻り値の型 | 説明 |
| :--- | :--- | :--- |
| `get_current_index()` | `int` | 現在表示中の画像のインデックス（0始まり）を取得します。 |
| `get_total_count()` | `int` | データセット内の全画像ペア（画像とラベルのセット）の数を取得します。 |
| `get_class_names()` | `List[str]` | 読み込まれているクラス名（タグ）のリストを取得します。 |
| `get_current_image_path()` | `Path` | 現在表示中の画像のファイルパスを取得します。 |
| `get_current_label_path()` | `Path` | 現在表示中のラベルファイル（.txt）のパスを取得します。 |
| `get_current_labels()` | `List[Tuple[int, float, float, float, float]]` | 現在表示中のYOLOフォーマットのBBoxリストを取得します。 |
| `get_data_at(index: int)` | `Tuple[Path, Path]` | **[プレロード用]** 指定したインデックスの (画像パス, ラベルパス) を取得します。範囲外の場合は `(None, None)` を返します。 |
| `get_uuid()` | `str` | 現在開いているデータセットのUUIDを取得します。 |

---

## 2. 操作・更新 API (Write / Actions)
ビューアの状態を変化させたり、データを更新したりします。

| メソッド名 | 引数 | 説明 |
| :--- | :--- | :--- |
| `navigate_to(index: int)` | `index: int` | 指定したインデックスの画像へジャンプします。 |
| `navigate_next()` | なし | 次の画像へ移動します。 |
| `navigate_prev()` | なし | 前の画像へ移動します。 |
| `update_current_labels(new_labels)` | `new_labels: List[Tuple[...]]` | プラグイン側で修正した新しいBBoxリストを、本体のテキストエディタ及びキャンバスに反映します（未保存状態）。 |
| `save_current_labels()` | なし | 現在のテキストエディタの内容をファイル（.txt）に上書き保存します。 |

---

## 3. イベント通知 API (Signals)
PySide6の `Signal` として実装されます。プラグイン側で `connect()` して状態変化を購読します。

| シグナル名 | 発火タイミング | コールバック引数 |
| :--- | :--- | :--- |
| `index_changed` | 画像が切り替わった直後 | `index: int`, `img_path: Path`, `txt_path: Path` |
| `labels_modified` | エディタのテキストが手動で編集された時 | `raw_text: str` (編集後のプレーンテキスト) |
| `labels_saved` | 保存処理が成功した時 | `txt_path: Path` |

**実装例:**
```python
def on_index_changed(self, index, img_path, txt_path):
    print(f"Moved to {index}: {img_path.name}")

# セットアップ時に接続
api.index_changed.connect(self.on_index_changed)
```

---

## 4. 描画・UI介入 API (UI Hooks)
プラグイン独自のUIを本体に組み込んだり、キャンバスの描画に介入したりするためのAPIです。

| メソッド名 | 引数 | 説明 |
| :--- | :--- | :--- |
| `set_canvas_filter(class_ids)`| `class_ids: List[int]` | キャンバスに描画するBBoxを特定のクラスIDのみに制限します。`None` を渡すと全表示に戻ります。 |
| `add_sidebar_widget(title, widget)` | `title: str`, `widget: QWidget` | 本体のサイドバー（下部）に、プラグイン用のグループボックス/ウィジェットを追加します。 |
| `add_menu_action(menu_name, action)` | `menu_name: str`, `action: QAction` | 本体のメニューバーにアクションを追加します（別ウィンドウ起動用など）。 |

---

## プラグインの基本構造（テンプレート）

```python
from pathlib import Path
from PySide6.QtWidgets import QWidget

class BasePlugin:
    def __init__(self, api):
        """
        api: ViewerAPI インスタンス
        """
        self.api = api
        self.plugin_name = "Base Plugin"

    def setup_ui(self):
        """初期化時に呼ばれる。UIの構築やシグナルの接続を行う。"""
        pass
```