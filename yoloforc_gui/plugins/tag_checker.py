from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, 
    QLabel, QDialog, QSpinBox, QGroupBox, QMessageBox
)
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PySide6.QtCore import Qt
from pathlib import Path

class TagCheckerWindow(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Tag Checker - タグ別領域インスペクタ")
        self.resize(700, 650)
        
        self.target_class_id = -1
        # matches = [(img_idx, bbox_line_idx, raw_line_str), ...]
        self.matches = [] 
        self.current_match_idx = 0
        
        self._build_ui()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # --- 上部: タグ選択とスキャン ---
        top_lay = QHBoxLayout()
        top_lay.addWidget(QLabel("検査するタグ:"))
        
        self.combo_tags = QComboBox()
        self.combo_tags.addItems(self.api.get_class_names())
        self.combo_tags.currentIndexChanged.connect(self._on_tag_changed)
        top_lay.addWidget(self.combo_tags)
        
        self.btn_scan = QPushButton("再スキャン")
        self.btn_scan.clicked.connect(self._scan_dataset)
        top_lay.addWidget(self.btn_scan)
        layout.addLayout(top_lay)
        
        # --- ステータス表示 (例: IMG12345 / TAGNAME / (1/3)) ---
        self.lbl_status = QLabel("待機中...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.lbl_status.setFont(font)
        layout.addWidget(self.lbl_status)

        # --- 中央: 画像クロップ表示 ---
        self.lbl_image = QLabel("画像領域")
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setMinimumSize(400, 300)
        self.lbl_image.setStyleSheet("background-color: #1e1e1e; border: 2px solid #444; border-radius: 4px;")
        layout.addWidget(self.lbl_image, stretch=1)
        
        # --- 下部: BBox 微調整 (スピンボックス) ---
        adjust_group = QGroupBox("BBox 微調整 (ピクセル)")
        adj_lay = QHBoxLayout()
        
        # マウスドラッグの代わりに、確実な数値入力で微調整できるようにしています
        self.sp_xc = QSpinBox(); self.sp_xc.setRange(0, 9999); self.sp_xc.setPrefix("Xc: ")
        self.sp_yc = QSpinBox(); self.sp_yc.setRange(0, 9999); self.sp_yc.setPrefix("Yc: ")
        self.sp_w = QSpinBox(); self.sp_w.setRange(1, 9999); self.sp_w.setPrefix("W: ")
        self.sp_h = QSpinBox(); self.sp_h.setRange(1, 9999); self.sp_h.setPrefix("H: ")
        
        for sp in [self.sp_xc, self.sp_yc, self.sp_w, self.sp_h]:
            sp.valueChanged.connect(self._preview_bbox)
            adj_lay.addWidget(sp)
            
        self.btn_apply = QPushButton("修正を保存")
        self.btn_apply.clicked.connect(self._apply_bbox)
        adj_lay.addWidget(self.btn_apply)
        adjust_group.setLayout(adj_lay)
        layout.addWidget(adjust_group)
        
        # --- ナビゲーション ---
        nav_lay = QHBoxLayout()
        self.btn_prev = QPushButton("◀ 前へ")
        self.btn_next = QPushButton("次へ ▶")
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        nav_lay.addWidget(self.btn_prev)
        nav_lay.addWidget(self.btn_next)
        layout.addLayout(nav_lay)
        
        # 初回起動時に自動スキャン
        if self.api.get_class_names():
            self.combo_tags.setCurrentIndex(0)
            self._scan_dataset()

    def _on_tag_changed(self, idx):
        self.target_class_id = idx
        self._scan_dataset()
        
    def _scan_dataset(self):
        """データセット全体を舐めて、対象タグのBBoxを抽出する"""
        self.matches = []
        if self.target_class_id < 0:
            return
            
        total = self.api.get_total_count()
        for i in range(total):
            _, txt_path = self.api.get_data_at(i)
            if not txt_path or not txt_path.exists():
                continue
            
            try:
                lines = txt_path.read_text(encoding="utf-8").strip().splitlines()
                for b_idx, line in enumerate(lines):
                    parts = line.split()
                    # クラスIDが一致するものをリストに追加
                    if len(parts) == 5 and int(parts[0]) == self.target_class_id:
                        self.matches.append((i, b_idx, line))
            except Exception:
                pass
                
        self.current_match_idx = 0
        self._update_view()
        
    def _update_view(self):
        """抽出したBBoxの画像を表示し、ビューア本体も同期させる"""
        if not self.matches:
            self.lbl_status.setText("対象タグの領域は見つかりませんでした")
            self.lbl_image.clear()
            return
            
        img_idx, bbox_idx, line = self.matches[self.current_match_idx]
        img_path, txt_path = self.api.get_data_at(img_idx)
        tag_name = self.api.get_class_names()[self.target_class_id]
        
        # UI更新: IMG12345 / TAGNAME / (1/3) の形式
        self.lbl_status.setText(f"{img_path.name}  /  {tag_name}  /  ({self.current_match_idx + 1} / {len(self.matches)})")
        
        # ★ ビューア本体も該当画像へジャンプ（同期）
        if self.api.get_current_index() != img_idx:
            self.api.navigate_to(img_idx)
            
        # 画像の読み込みとパース
        self.current_pix = QPixmap(str(img_path))
        if self.current_pix.isNull():
            return
            
        parts = line.split()
        xc, yc, w, h = map(float, parts[1:])
        iw, ih = self.current_pix.width(), self.current_pix.height()
        
        # YOLO相対座標 -> ピクセル絶対座標
        self.sp_xc.blockSignals(True)
        self.sp_yc.blockSignals(True)
        self.sp_w.blockSignals(True)
        self.sp_h.blockSignals(True)
        
        self.sp_xc.setValue(int(xc * iw))
        self.sp_yc.setValue(int(yc * ih))
        self.sp_w.setValue(int(w * iw))
        self.sp_h.setValue(int(h * ih))
        
        self.sp_xc.blockSignals(False)
        self.sp_yc.blockSignals(False)
        self.sp_w.blockSignals(False)
        self.sp_h.blockSignals(False)
        
        self._preview_bbox()

    def _preview_bbox(self):
        """スピンボックスの値を使ってクロップ画像を描画する"""
        if not hasattr(self, 'current_pix') or self.current_pix.isNull():
            return
            
        iw, ih = self.current_pix.width(), self.current_pix.height()
        px_xc = self.sp_xc.value()
        px_yc = self.sp_yc.value()
        px_w = self.sp_w.value()
        px_h = self.sp_h.value()
        
        # BBoxの周囲に余裕（パディング）を持たせてクロップ
        pad = max(50, int(px_w * 0.8))
        crop_x = max(0, int(px_xc - px_w/2 - pad))
        crop_y = max(0, int(px_yc - px_h/2 - pad))
        crop_w = min(iw - crop_x, int(px_w + pad*2))
        crop_h = min(ih - crop_y, int(px_h + pad*2))
        
        cropped = self.current_pix.copy(crop_x, crop_y, crop_w, crop_h)
        
        # 赤枠を描画
        painter = QPainter(cropped)
        painter.setPen(QPen(QColor(255, 50, 50), max(2, int(crop_w/100))))
        b_x = int(px_xc - px_w/2) - crop_x
        b_y = int(px_yc - px_h/2) - crop_y
        painter.drawRect(b_x, b_y, px_w, px_h)
        painter.end()
        
        # QLabel にセット
        scaled = cropped.scaled(
            self.lbl_image.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_image.setPixmap(scaled)

    def _apply_bbox(self):
        """スピンボックスの修正値をテキストに書き込み、本体を更新"""
        if not self.matches: return
        
        img_idx, bbox_idx, _ = self.matches[self.current_match_idx]
        _, txt_path = self.api.get_data_at(img_idx)
        
        iw, ih = self.current_pix.width(), self.current_pix.height()
        
        # ピクセル絶対座標 -> YOLO相対座標
        n_xc = self.sp_xc.value() / iw
        n_yc = self.sp_yc.value() / ih
        n_w = self.sp_w.value() / iw
        n_h = self.sp_h.value() / ih
        
        new_line = f"{self.target_class_id} {n_xc:.6f} {n_yc:.6f} {n_w:.6f} {n_h:.6f}"
        
        if txt_path.exists():
            lines = txt_path.read_text(encoding="utf-8").splitlines()
            if bbox_idx < len(lines):
                lines[bbox_idx] = new_line
                txt_path.write_text("\n".join(lines), encoding="utf-8")
                
                # 本体へリロード指示
                self.api.navigate_to(img_idx)
                
                # キャッシュも更新
                self.matches[self.current_match_idx] = (img_idx, bbox_idx, new_line)
                QMessageBox.information(self, "保存", "修正を保存しました。")

    def _prev(self):
        if self.current_match_idx > 0:
            self.current_match_idx -= 1
            self._update_view()

    def _next(self):
        if self.current_match_idx < len(self.matches) - 1:
            self.current_match_idx += 1
            self._update_view()

class TagCheckerEntry:
    """プラグインエントリーポイント"""
    def __init__(self, api):
        self.api = api
        self.window = None
        
    def setup_ui(self):
        # APIを通じて本体のサイドバーに起動ボタンを追加
        self.btn = QPushButton("🏷️ タグ別チェッカーを開く")
        self.btn.clicked.connect(self._open_window)
        self.api.add_sidebar_widget(self.btn, "Tag Checker Plugin")
        
    def _open_window(self):
        if not self.window:
            self.window = TagCheckerWindow(self.api)
        self.window.show()

# プラグインマネージャーから呼ばれる関数
def register_plugin(api):
    return TagCheckerEntry(api)