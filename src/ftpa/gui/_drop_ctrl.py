"""
拖放控制器 — 参数树拖拽到子图。

提供两个组件：
- TreeDragHelper:  安装在 ParameterTreeWidget.tree.viewport() 上，
                    处理拖拽发起（mousePress → mouseMove → QDrag）
- CanvasDropFilter: 安装在 PlotCanvasWidget.canvas 上，
                    处理拖放接收（dragEnter → dragMove → drop）

交互流程：
  用户按下参数树项 → 拖动超阈值 → QDrag 启动
  → 进入 canvas → DragEnter 接受
  → 在 canvas 移动 → 命中子图 → 绿色虚线高亮
  → 释放 → Drop → _add_to_subplot(idx, field) + 发射 param_dropped
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QPoint, Qt, QObject, QMimeData
from PySide6.QtGui import QDrag, QColor, QPainter, QPixmap
from PySide6.QtWidgets import QTreeWidgetItem

if TYPE_CHECKING:
    from .panel_plot import PlotCanvasWidget
    from .widgets import ParameterTreeWidget

logger = logging.getLogger(__name__)

# ── 自定义 MIME 类型 ──
MIME_TYPE = "application/x-ftpa-field-name"


# ════════════════════════════════════════════════════════════════
#  拖拽源：参数树 → QDrag
# ════════════════════════════════════════════════════════════════

class TreeDragHelper(QObject):
    """参数树拖拽辅助 — 从 QTreeWidget 发起拖拽。

    安装在 ParameterTreeWidget.tree.viewport() 上，
    拦截鼠标按下和移动事件，超过阈值后启动 QDrag。
    不拦截 MouseButtonRelease，保证树本身的点击选择正常工作。
    """

    DRAG_THRESHOLD = 10  # 像素，区分点击与拖拽

    def __init__(self, param_tree: ParameterTreeWidget) -> None:
        super().__init__(param_tree)
        self._param_tree = param_tree
        self._press_pos: QPoint | None = None
        self._press_item: QTreeWidgetItem | None = None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """拦截鼠标按下和移动事件。"""
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                # 记录按下位置和当前 item
                item = self._param_tree.tree.itemAt(event.position().toPoint())
                if item is not None and item.data(0, Qt.ItemDataRole.UserRole) is not None:
                    self._press_pos = event.position().toPoint()
                    self._press_item = item
                else:
                    self._press_pos = None
                    self._press_item = None
        elif event.type() == QEvent.Type.MouseMove:
            if self._press_pos is not None and self._press_item is not None:
                delta = event.position().toPoint() - self._press_pos
                if delta.manhattanLength() >= self.DRAG_THRESHOLD:
                    self._start_drag(self._press_item)
                    # 拖拽已启动，清除状态（drag.exec 是阻塞的，返回时拖拽已结束）
                    self._press_pos = None
                    self._press_item = None
                    return True  # 拖拽启动时消费此事件
        elif event.type() == QEvent.Type.MouseButtonRelease:
            # 释放时清除按下状态
            self._press_pos = None
            self._press_item = None
        return False  # 不拦截其他事件

    def _start_drag(self, item: QTreeWidgetItem) -> None:
        """创建 QDrag 并执行拖拽。"""
        field_name: str = item.data(0, Qt.ItemDataRole.UserRole)
        if not field_name:
            return

        drag = QDrag(self._param_tree)
        mime = QMimeData()
        mime.setData(MIME_TYPE, field_name.encode("utf-8"))
        drag.setMimeData(mime)

        # 创建半透明标签 pixmap 作为拖拽视觉提示
        label_text = item.text(0)
        pixmap = QPixmap(140, 28)
        pixmap.fill(QColor(76, 175, 80, 200))  # 半透明绿色背景
        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))  # 白色文字
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, label_text)
        painter.end()
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(10, 14))

        # 执行拖拽（阻塞，直到拖拽结束）
        drag.exec(Qt.DropAction.CopyAction)


# ════════════════════════════════════════════════════════════════
#  拖放目标：canvas → 子图
# ════════════════════════════════════════════════════════════════

class CanvasDropFilter(QObject):
    """Canvas 拖放事件过滤器 — 处理参数拖入子图。

    安装在 PlotCanvasWidget.canvas 上，
    拦截 DragEnter/DragMove/DragLeave/Drop 事件。
    """

    def __init__(self, widget: PlotCanvasWidget) -> None:
        super().__init__(widget.canvas)
        self._widget = widget
        self._hovered_subplot: int | None = None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """分发拖放事件到对应处理方法。"""
        etype = event.type()
        if etype == QEvent.Type.DragEnter:
            self._drag_enter(event)
            return True
        elif etype == QEvent.Type.DragMove:
            self._drag_move(event)
            return True
        elif etype == QEvent.Type.DragLeave:
            self._drag_leave(event)
            return True
        elif etype == QEvent.Type.Drop:
            self._drop(event)
            return True
        return False

    # ── 拖放事件处理 ──

    def _drag_enter(self, event: QEvent) -> None:
        """拖拽进入 canvas — 检查 MIME 类型，接受或忽略。"""
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drag_move(self, event: QEvent) -> None:
        """拖拽在 canvas 上移动 — 更新悬停子图高亮。"""
        if not event.mimeData().hasFormat(MIME_TYPE):
            event.ignore()
            return

        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        hit_idx = self._hit_test_subplot(pos)

        if hit_idx != self._hovered_subplot:
            self._hovered_subplot = hit_idx
            self._widget._layout.apply_drag_highlight(hit_idx)

        if hit_idx is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drag_leave(self, event: QEvent) -> None:
        """拖拽离开 canvas — 清除高亮。"""
        self._hovered_subplot = None
        self._widget._layout.clear_drag_highlight()

    def _drop(self, event: QEvent) -> None:
        """释放拖拽 — 添加参数到目标子图。"""
        mime = event.mimeData()
        if not mime.hasFormat(MIME_TYPE):
            event.ignore()
            return

        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        hit_idx = self._hit_test_subplot(pos)

        if hit_idx is None:
            event.ignore()
            self._hovered_subplot = None
            self._widget._layout.clear_drag_highlight()
            return

        # 提取 field_name
        field_name = bytes(mime.data(MIME_TYPE)).decode("utf-8")

        # 清除拖拽高亮
        self._hovered_subplot = None
        self._widget._layout.clear_drag_highlight()

        # 添加信号到目标子图
        self._widget.add_signal_to_subplot(hit_idx, field_name)

        # 通知外部更新参数树指示器
        self._widget.param_dropped.emit(field_name)

        event.acceptProposedAction()

    # ── 子图命中检测 ──

    def _hit_test_subplot(self, qt_pos: QPoint) -> int | None:
        """将 Qt 坐标转换为 matplotlib figure 坐标，检测命中的子图索引。

        坐标转换链：
          Qt 局部坐标 (左上原点)
          → matplotlib display 坐标 (左下原点, Y 翻转)
          → figure 归一化坐标 (0-1)
          → Axes Bbox contains() 命中测试
        """
        w = self._widget
        if not w.axes:
            return None

        canvas = w.canvas
        dpi_ratio = canvas.devicePixelRatio()

        # Qt 坐标 → matplotlib display 坐标
        # matplotlib display 坐标: 原点左下角, Y 向上
        fig_width_px, fig_height_px = canvas.get_width_height()
        display_x = qt_pos.x() * dpi_ratio
        display_y = fig_height_px * dpi_ratio - qt_pos.y() * dpi_ratio

        # display → figure 归一化坐标 (0-1)
        try:
            inv = w.figure.transFigure.inverted()
            fig_x, fig_y = inv.transform((display_x, display_y))
        except Exception:
            logger.debug("display→figure 坐标转换失败", exc_info=True)
            return None

        # 遍历 Axes Bbox 命中测试
        for i, ax in enumerate(w.axes):
            bbox = ax.get_position()
            if bbox.contains(fig_x, fig_y):
                return i

        return None
