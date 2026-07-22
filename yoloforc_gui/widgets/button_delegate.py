"""テーブルセル内にボタン風を描画し、クリックを検知する Delegate"""
from PySide6.QtWidgets import (
    QStyledItemDelegate, QStyleOptionButton, QApplication, QStyle
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter


class ButtonDelegate(QStyledItemDelegate):
    buttonClicked = Signal(int)  # row

    def __init__(self, label: str = "VIEW", parent=None):
        super().__init__(parent)
        self.label = label

    def paint(self, painter: QPainter, option, index):
        # ボタン風の QStyleOptionButton を作成
        btn_opt = QStyleOptionButton()
        btn_opt.text = self.label
        btn_opt.rect = option.rect.adjusted(4, 2, -4, -2)
        btn_opt.state = QStyle.State_Enabled

        if option.state & QStyle.State_MouseOver:
            btn_opt.state |= QStyle.State_MouseOver
        if option.state & QStyle.State_Selected:
            btn_opt.state |= QStyle.State_Selected

        # 正しくインスタンスメソッドとして呼び出す
        style = QApplication.style()
        if option.widget:
            style = option.widget.style()

        style.drawControl(QStyle.CE_PushButton, btn_opt, painter, option.widget)

    def editorEvent(self, event, model, option, index):
        if isinstance(event, QMouseEvent):
            if event.type() == event.Type.MouseButtonRelease:
                if option.rect.contains(event.pos()):
                    self.buttonClicked.emit(index.row())
                    return True
        return super().editorEvent(event, model, option, index)