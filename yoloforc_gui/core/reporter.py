import csv
from pathlib import Path
from collections import defaultdict
from PySide6.QtGui import QTextDocument, QPdfWriter, QPageSize, QPageLayout
from PySide6.QtCore import QMarginsF

class DatasetReporter:
    def __init__(self, title: str, image_paths: list[Path], label_paths: list[Path], class_names: list[str]):
        """
        title: レポートのタイトル（データセット名 や UUID）
        image_paths, label_paths: 走査対象のファイルリスト
        """
        self.title = title
        self.image_paths = image_paths
        self.label_paths = label_paths
        self.class_names = class_names

    def collect_stats(self):
        stats = {
            "total_images": len(self.image_paths),
            "total_annotated": 0,
            "total_bboxes": 0,
            "class_counts": defaultdict(int),
            "class_areas": defaultdict(list)
        }
        
        for txt_path in self.label_paths:
            if txt_path.exists():
                try:
                    lines = txt_path.read_text(encoding="utf-8").strip().splitlines()
                    if lines:
                        stats["total_annotated"] += 1
                        stats["total_bboxes"] += len(lines)
                        for line in lines:
                            parts = line.split()
                            if len(parts) == 5:
                                cid = int(parts[0])
                                w, h = float(parts[3]), float(parts[4])
                                stats["class_counts"][cid] += 1
                                stats["class_areas"][cid].append(w * h)
                except Exception:
                    pass
        return stats

    def export_csv(self, output_path: str):
        stats = self.collect_stats()
        with open(output_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Class ID", "Class Name", "BBox Count", "Avg Area (Ratio)"])
            for cid in sorted(stats["class_counts"].keys()):
                cname = self.class_names[cid] if cid < len(self.class_names) else f"Unknown ({cid})"
                count = stats["class_counts"][cid]
                areas = stats["class_areas"][cid]
                avg_area = sum(areas) / len(areas) if areas else 0.0
                writer.writerow([cid, cname, count, f"{avg_area:.4f}"])

    def export_pdf(self, output_path: str):
        stats = self.collect_stats()
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; color: #333; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #34495e; padding-bottom: 5px; }}
                h2 {{ color: #2980b9; margin-top: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ border: 1px solid #bdc3c7; padding: 8px; text-align: left; }}
                th {{ background-color: #ecf0f1; }}
                .summary-box {{ background-color: #f9f9f9; padding: 15px; border-left: 5px solid #27ae60; }}
            </style>
        </head>
        <body>
            <h1>YOLO Dataset Summary Report</h1>
            <h2>Target: {self.title}</h2>
            
            <div class="summary-box">
                <p><b>Total Images:</b> {stats["total_images"]}</p>
                <p><b>Annotated Images:</b> {stats["total_annotated"]} ({(stats["total_annotated"]/max(1, stats["total_images"]))*100:.1f}%)</p>
                <p><b>Total Bounding Boxes:</b> {stats["total_bboxes"]}</p>
            </div>
            <h2>Class Distribution</h2>
            <table>
                <tr><th>ID</th><th>Class Name</th><th>BBox Count</th><th>Avg Area (%)</th></tr>
        """
        for cid in sorted(stats["class_counts"].keys()):
            cname = self.class_names[cid] if cid < len(self.class_names) else f"Unknown ({cid})"
            count = stats["class_counts"][cid]
            avg_area = sum(stats["class_areas"][cid]) / max(1, len(stats["class_areas"][cid])) * 100
            html += f"<tr><td>{cid}</td><td>{cname}</td><td>{count}</td><td>{avg_area:.2f}%</td></tr>"
            
        html += "</table></body></html>"

        doc = QTextDocument()
        doc.setHtml(html)
        writer = QPdfWriter(output_path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
        doc.print_(writer)