# yoloデータセット管理プロジェクト

YOLOForgeはyoloのデータセットを、ローカルあるいはセキュアに個別管理するためのプロジェクトです。　データは一意なUUIDを以て操作単位で管理できるように設計しています。

構成イメージ図
```

[ 既存タグのインポート yolo形式]
       |
       v
+------------------------------------------+
|             統一データ構造                |
+------------------------------------------+
            ^                       |
            |                       |
            v                       |
+--------------------------+        |
|   SAM3 などでクリーニング   |        |
+--------------------------+        |
                                    |
                                    V
                        +--------------------------+
                        |   指定した形式で出力        |
                        +--------------------------+

```

統一データ構造との接続には、統一された変換及び接続ミドルウェア(YOLOForgeConnector : YoloForC)を作成している。



### ミドルウェア YOLOForgeConnector

構成

```
YoloForC/
├── __init__.py              # 公開API（外部向けに必要最小限のみ export）
├── YoloForC.py              # メイン・ファサードクラス（外部ツールが触るのはこれ）
├── config.py                # ROOTパス・環境設定
├── exceptions.py            # ライブラリ独自例外
├── models.py                # 内部データ表現（dataclass）
├── storage/
│   ├── __init__.py
│   ├── proxy.py             # 物理ストレージ（NFS等）への読み書き
│   └── index_manager.py     # index.yaml の全走査・再構築
├── converter/
│   ├── __init__.py
│   ├── auto_detect.py       # フォルダ形式の自動判別
│   ├── base.py              # 変換器の基底I/F
│   ├── yolo_native.py       # 内部形式 ↔ 内部形式（コピー・検証）
│   ├── pascal_voc.py        # Pascal VOC → 内部形式
│   ├── coco.py              # COCO JSON → 内部形式
│   └── labelme.py           # Labelme JSON → 内部形式
├── importer/
│   ├── __init__.py
│   └── batch.py             # 外部フォルダを1バッチとしてUUIDに格納
└── validator/
    ├── __init__.py
    ├── structure.py         # フォルダ・ファイル構造チェック
    └── integrity.py         # image/labels 対応関係・meta.yaml 整合性
```



呼び出せるapiめも v1

```
from YoloForC import YoloForC

# --- 初期化 ---
yfc = YoloForC()                    # 環境変数/設定ファイルから自動
yfc = YoloForC(root="/mnt/nfs")     # 明示指定

# --- 外部タグ付けデータのインポート（自動判別） ---
result = yfc.import_folder(
    source="/tmp/annotator_output",
    dataset_name="defect_detection",
    tags=["batch_jan", "line_A"],
    annotator="yamada"
)
# → ImportResult(uuid="a3f7...", image_count=150, warnings=[...])

# --- データセット全体のチェック ---
report = yfc.validate_dataset("defect_detection", rebuild_index=True)
# → errors[], warnings[], summary{}

# --- 既存データの参照・更新 ---
uuids = yfc.list_uuids("defect_detection", status="approved")
paths = yfc.get_uuid_paths("defect_detection", "a3f7...")
yfc.update_uuid_meta("defect_detection", "a3f7...", {"status": "reviewed"})

# --- 学習連携（YOLO学習器へ渡す用のシンボリック集約） ---
yfc.export_yolo_ready(
    "defect_detection",
    output_dir="/tmp/yolo_train",
    filter_tags=["approved"]
)
```