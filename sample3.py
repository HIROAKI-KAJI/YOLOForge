from YoloForC import YoloForC, DatasetMeta

# 1. ルート初期化
YoloForC.init_root("./yoloforc_root")

# 2. 接続
yfc = YoloForC(root="./yoloforc_root")

# 3. データセット定義
yfc.init_dataset(
    dataset_name="cb10b",
    classes=["cb", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "b10"],
    notes="cb10bのデータセットです。",
)

# 4. インポート（自動で index.yaml, dataset.yaml total_images が更新される）
result = yfc.import_folder(
    source="/home/kaji-yoloworld/workspace-p/YOLOForge/cb-10b/dataset-9d8c605d-e266-439c-8920-10c91ff97503/",
    dataset_name="cb10b",
    classes=["cb", "b1", "b2"],
    note="夜間バッチ",
    annotator="yamada",
)

# 5. 一覧（GUI連携）
print(yfc.list_datasets())           # ['cb10b']
print(yfc.list_uuids("cb10b"))       # [{'uuid': '...', 'image_count': 150, ...}]
print(yfc.get_uuid_detail("cb10b", result.uuid))
# → {'meta': {...}, 'files': {'images': [...], 'labels': [...]}}

# 6. 更新ボタン（明示的 index 再構築）
yfc.rebuild_index("cb10b")

# 7. 学習連携（シンボリックリンク集約 + data.yaml 自動生成）
train_dir = yfc.export_yolo_ready(
    "cb10b",
    output_dir="/tmp/yolo_train/cb10b",
    mode="symlink",           # 容量ゼロ
    filter_status="approved", # 任意
)
# → /tmp/yolo_train/cb10b/data.yaml が生成済み
#   ultralytics で使う場合: model.train(data="/tmp/yolo_train/cb10b/data.yaml", ...)