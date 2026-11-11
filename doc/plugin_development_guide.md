# YOLOForge プラグイン開発ガイド

YOLOForge の `UUIDViewerDialog`（アノテーションビューア）は、Pythonによるプラグインシステムをサポートしています。このドキュメントでは、プラグインの作成方法、提供されるAPI仕様、および開発時のベストプラクティスについて解説します。

## 目次
1. [プラグインの基本構造](#1-プラグインの基本構造)
2. [エントリーポイント (`register_plugin`)](#2-エントリーポイント)
3. [ViewerAPI リファレンス](#3-viewerapi-リファレンス)
    - [状態取得 (Getters)](#31-状態取得-getters)
    - [操作・更新 (Actions)](#32-操作更新-actions)
    - [UI介入 (UI Hooks)](#33-ui介入-ui-hooks)
    - [イベント検知 (Signals)](#34-イベント検知-signals)
4. [⚠️ 座標系に関する重要事項](#4-座標系に関する重要事項)
5. [最小実装サンプル](#5-最小実装サンプル)
6. [参考リンク・公式リポジトリ](#6-参考リンク公式リポジトリ)

---

## 1. プラグインの基本構造

プラグインは単一のPythonファイル（`.py`）として作成し、プロジェクト直下の `plugins/` ディレクトリに配置します。
GUIの「設定 > プラグイン管理」から有効化（チェック）されると、ビューア起動時に動的にインポートされます。

```text
YOLOForge/
├── yoloforc_gui/
├── plugins/
│   ├── tag_checker.py      # 実装済みプラグイン
│   ├── outlier_detector.py # 実装済みプラグイン
│   └── your_plugin.py      # ← ここに配置する
└── main.py
```

### 2. エントリーポイント
プラグインファイルは、必ずモジュールレベルで register_plugin(api) 関数を定義する必要があります。この関数はプラグインのインスタンスを返す必要があります。

```Python
class MyPluginEntry:
    def __init__(self, api):
        self.api = api
        
    def setup_ui(self):
        # UIの構築やボタンの配置を行う
        pass

def register_plugin(api):
    """本体側から最初に呼び出されるエントリーポイント"""
    return MyPluginEntry(api)
```

利用可能なオプショナルメソッド:
本体側は hasattr を用いて以下のメソッドの有無を確認し、存在する場合のみ呼び出します。

setup_ui(self): UIセットアップ時に呼ばれる。

on_image_changed(self, idx, img_path, txt_path): 画像が切り替わった時に呼ばれる。

on_labels_modified(self, text): テキストエディタが編集された時に呼ばれる。

on_labels_saved(self, txt_path): 保存が完了した時に呼ばれる。

### 3. ViewerAPI リファレンス
register_plugin に渡される api オブジェクト（ViewerAPI インスタンス）を通じて、ビューア本体の操作を行います。本体の内部変数へ直接アクセスすることは非推奨です。

#### 3.1 状態取得 (Getters)
get_current_index() -> int
現在表示している画像のインデックスを取得します。

get_total_count() -> int
データセット内の画像総数を取得します。

get_class_names() -> List[str]
現在のクラス（タグ）名のリストを取得します。

get_current_image_path() -> Path | None
現在の画像ファイルのパスを取得します。

get_current_label_path() -> Path | None
現在のラベルファイル（.txt）のパスを取得します。

get_current_labels() -> List[Tuple[int, float, float, float, float]]
現在画面に描画されているBBoxのリストを取得します。（YOLO正規化座標）

get_data_at(index: int) -> Tuple[Path | None, Path | None]
指定したインデックスの画像パスとラベルパスのタプルを取得します。バックグラウンドでのデータ事前解析などに使用します。

#### 3.2 操作・更新 (Actions)
navigate_to(index: int)
指定したインデックスの画像へジャンプし、ビューアを更新します。

navigate_next() / navigate_prev()
次、または前の画像へ移動します。

update_current_labels(new_labels: List[Tuple[int, float, float, float, float]])
プラグイン側で加工したBBoxリストを本体に反映させます。テキストエディタとメインキャンバスが即座に更新されます。

save_current_labels()
本体の「Save」ボタンを押したのと同じ保存処理を実行します。

#### 3.3 UI介入 (UI Hooks)
add_sidebar_widget(widget: QWidget, title: str = "")
ビューアの右側サイドバー下部に、プラグイン専用のウィジェット（ボタンなど）を追加します。title を指定するとGroupBoxで囲まれます。

add_menu_action(menu_name: str, action: QAction)
上部のメニューバーにアクションを追加します。

set_canvas_filter(class_ids: List[int] | None)
メインキャンバスに特定のクラスIDのみを描画させるフィルタを設定します。None で全表示に戻ります。

3.4 イベント検知 (Signals)
APIオブジェクトは以下のPySide6 Signal を公開しています。手動で connect することも可能です。

api.index_changed (int, Path, Path)

api.labels_modified (str)

api.labels_saved (Path)

### 4. 座標系に関する重要事項
YOLOForgeにおける座標の扱いには厳密なルールがあります。プラグインでBBoxを操作・描画する際は以下の違いを必ず意識してください。

YOLO正規化座標 (APIがやり取りする形式)

形式: (class_id, x_center, y_center, width, height)

範囲: 0.0 〜 1.0 の割合。

api.get_current_labels() で取得でき、api.update_current_labels() で渡すべき形式です。

ピクセル絶対座標 (QPainter等で描画する形式)

形式: (x_min, y_min, pixel_width, pixel_height)

プラグイン内で画像をクロップしたり、PySide6のキャンバスに描画する際は、画像本来の幅(iw)と高さ(ih)を掛けて変換する必要があります。

変換例:

``` Python
iw, ih = pixmap.width(), pixmap.height()

# YOLO(正規化) -> ピクセル(左上基準)
px_w = int(w * iw)
px_h = int(h * ih)
px_xmin = int((xc - w/2) * iw)
px_ymin = int((yc - h/2) * ih)

# ピクセル(左上基準) -> YOLO(正規化)
n_xc = (px_xmin + px_w/2) / iw
n_yc = (px_ymin + px_h/2) / ih
n_w = px_w / iw
n_h = px_h / ih
```

### 5. 最小実装サンプル
以下は、サイドバーにボタンを追加し、クリックすると現在の画像の最初のタグをコンソールに出力する最小構成のプラグインです。

``` Python
from PySide6.QtWidgets import QPushButton

class HelloWorldPlugin:
    def __init__(self, api):
        self.api = api

    def setup_ui(self):
        # ボタンを作成してサイドバーに追加
        self.btn = QPushButton("👋 Hello World")
        self.btn.clicked.connect(self._on_click)
        self.api.add_sidebar_widget(self.btn, "Sample Plugin")

    def _on_click(self):
        labels = self.api.get_current_labels()
        if labels:
            print(f"最初のBBox情報: {labels[0]}")
        else:
            print("BBoxがありません。")

    def on_image_changed(self, idx, img_path, txt_path):
        # オプショナル: 画像が変わるたびに呼ばれる
        print(f"画像移動: {img_path.name}")

def register_plugin(api):
    return HelloWorldPlugin(api)

```

### 6. 参考リンク・公式リポジトリ
YOLOForge リポジトリ: https://github.com/HIROAKI-KAJI/YOLOForge (※実際のURLに合わせて調整してください)

PySide6 ドキュメント: Qt for Python (PySide6)

実装例として、同 plugins/ ディレクトリ内の current_adjuster.py (マウスドラッグでの座標変換例) や outlier_detector.py (バックグラウンドでの画像解析例) のソースコードを参考にしてください。