from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QProgressBar, QStackedWidget, QWidget, QGroupBox, QFormLayout, QTableView
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPainter
from PySide6.QtCharts import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis

class StatsWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, reporter, parent=None):
        super().__init__(parent)
        self.reporter = reporter

    def run(self):
        try:
            stats = self.reporter.collect_stats()
            self.finished.emit(stats)
        except Exception as e:
            self.error.emit(str(e))

class DatasetReportDialog(QDialog):
    def __init__(self, reporter, parent=None):
        super().__init__(parent)
        self.reporter = reporter
        self.setWindowTitle(f"レポート - {self.reporter.title}")
        self.resize(800, 600)
        self.worker = None
        
        self._build_ui()
        self._start_calculating()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        
        # [ページ0] ロード中
        self.page_loading = QWidget()
        load_lay = QVBoxLayout(self.page_loading)
        self.lbl_loading = QLabel("バックグラウンドで統計を計算しています...")
        self.lbl_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        load_lay.addStretch(); load_lay.addWidget(self.lbl_loading); load_lay.addWidget(self.progress_bar); load_lay.addStretch()
        
        # [ページ1] 結果画面
        self.page_results = QWidget()
        res_lay = QVBoxLayout(self.page_results)
        
        self.lbl_summary = QLabel("-")
        res_lay.addWidget(self.lbl_summary)
        
        data_lay = QHBoxLayout()
        self.table_stats = QTableWidget(0, 4)
        self.table_stats.setHorizontalHeaderLabels(["ID", "クラス名", "BBox数", "平均面積(%)"])
        self.table_stats.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_stats.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        data_lay.addWidget(self.table_stats, stretch=1)
        
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        data_lay.addWidget(self.chart_view, stretch=1)
        res_lay.addLayout(data_lay)
        
        export_lay = QHBoxLayout()
        self.btn_export_csv = QPushButton("📊 CSV 出力")
        self.btn_export_csv.clicked.connect(self._on_export_csv)
        self.btn_export_pdf = QPushButton("📄 PDF レポート出力")
        self.btn_export_pdf.clicked.connect(self._on_export_pdf)
        export_lay.addStretch(); export_lay.addWidget(self.btn_export_csv); export_lay.addWidget(self.btn_export_pdf)
        res_lay.addLayout(export_lay)

        self.stack.addWidget(self.page_loading)
        self.stack.addWidget(self.page_results)
        layout.addWidget(self.stack)

    def _start_calculating(self):
        self.stack.setCurrentWidget(self.page_loading)
        self.worker = StatsWorker(self.reporter, self)
        self.worker.finished.connect(self._on_stats_calculated)
        self.worker.error.connect(self._on_stats_error)
        self.worker.start()

    def _on_stats_calculated(self, stats: dict):
        total = stats['total_images']
        annotated = stats['total_annotated']
        boxes = stats['total_bboxes']
        ratio = (annotated / total * 100) if total > 0 else 0
        self.lbl_summary.setText(f"総画像数: {total} 枚 | アノテーション済: {annotated} 枚 ({ratio:.1f}%) | 総BBox: {boxes}")
        
        self.table_stats.setRowCount(0)
        class_counts = stats['class_counts']
        categories = []
        bar_set = QBarSet("BBox数")
        
        for cid in sorted(class_counts.keys()):
            cname = self.reporter.class_names[cid] if cid < len(self.reporter.class_names) else f"Unknown ({cid})"
            count = class_counts[cid]
            areas = stats['class_areas'][cid]
            avg_area = (sum(areas) / len(areas) * 100) if areas else 0.0
            
            row = self.table_stats.rowCount()
            self.table_stats.insertRow(row)
            self.table_stats.setItem(row, 0, QTableWidgetItem(str(cid)))
            self.table_stats.setItem(row, 1, QTableWidgetItem(cname))
            self.table_stats.setItem(row, 2, QTableWidgetItem(str(count)))
            self.table_stats.setItem(row, 3, QTableWidgetItem(f"{avg_area:.2f}%"))
            
            categories.append(cname)
            bar_set.append(count)

        chart = QChart()
        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)
        axisX = QBarCategoryAxis(); axisX.append(categories); chart.addAxis(axisX, Qt.AlignmentFlag.AlignBottom); series.attachAxis(axisX)
        axisY = QValueAxis(); axisY.setRange(0, max(class_counts.values() or [10]) * 1.1); chart.addAxis(axisY, Qt.AlignmentFlag.AlignLeft); series.attachAxis(axisY)
        chart.legend().setVisible(False)
        self.chart_view.setChart(chart)
        
        self.stack.setCurrentWidget(self.page_results)

    def _on_stats_error(self, err_msg):
        QMessageBox.critical(self, "エラー", f"計算エラー:\n{err_msg}")
        self.reject()

    def _on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSVを保存", f"{self.reporter.title}_stats.csv", "CSV Files (*.csv)")
        if path: self.reporter.export_csv(path); QMessageBox.information(self, "完了", "CSVを出力しました。")

    def _on_export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "PDFを保存", f"{self.reporter.title}_report.pdf", "PDF Files (*.pdf)")
        if path: self.reporter.export_pdf(path); QMessageBox.information(self, "完了", "PDFを出力しました。")