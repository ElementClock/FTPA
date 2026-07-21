import os
import threading

import matplotlib
matplotlib.use("WXAgg")
import matplotlib.pyplot as plt
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas

from ..main import DEFAULT_EXCEL_FILE, DEFAULT_TXT_FILE, resolve_path
from .panels import FileConfigPanel, ResultPanel
from .services import build_analysis_preview, get_data_fields, run_analysis


class FTPAGUIFrame(wx.Frame):
    def __init__(self, dry_run=False):
        super().__init__(None, title="FTPA - 飞机性能操稳分析", size=(1120, 760))
        self.dry_run = dry_run
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="FTPA 飞机性能操稳分析")
        title.SetFont(wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        vbox.Add(title, 0, wx.ALL | wx.EXPAND, 12)

        notebook = wx.Notebook(panel)
        self.file_panel = FileConfigPanel(notebook, on_run=self.on_run_analysis, on_verify=self.on_quick_verify)
        self.result_panel = ResultPanel(notebook)
        notebook.AddPage(self.file_panel, "数据与配置")
        notebook.AddPage(self.result_panel, "结果与日志")
        vbox.Add(notebook, 1, wx.ALL | wx.EXPAND, 8)

        panel.SetSizer(vbox)
        self._populate_signal_options()

    def on_quick_verify(self, event):
        self._log("开始执行快速验证...")
        if self.dry_run:
            self._log("dry run 模式：跳过真实文件读取")
            self.file_panel.set_status("状态：dry run 完成")
            return

        try:
            self._populate_signal_options()
            self._render_preview()
            self.file_panel.set_status("状态：快速验证完成")
            self._log("快速验证完成，已加载预览数据。")
        except Exception as exc:
            self._log(f"快速验证失败：{exc}")
            self.file_panel.set_status("状态：验证失败")

    def on_run_analysis(self, event):
        self._log("开始执行分析流程...")
        self._populate_signal_options()
        if self.dry_run:
            self._log("GUI dry run：已进入分析入口，后续可接入真实计算逻辑")
            self.file_panel.set_status("状态：dry run 完成")
            self.result_panel.set_summary("GUI 已就绪，等待接入真实分析服务")
            return

        data_path = self.file_panel.get_data_path()
        excel_path = self.file_panel.get_excel_path()
        self.file_panel.set_status("状态：分析中...")
        self.file_panel.set_buttons_enabled(False)
        self._start_analysis_thread(data_path, excel_path, self.file_panel.get_selected_signals())

    def _start_analysis_thread(self, data_path, excel_path, selected_signals):
        if getattr(self, '_worker', None) and self._worker.is_alive():
            self._log("已有分析任务正在运行，请稍后再试。")
            return

        self._worker = threading.Thread(
            target=self._analysis_worker,
            args=(data_path, excel_path, selected_signals),
            daemon=True,
        )
        self._worker.start()

    def _analysis_worker(self, data_path, excel_path, selected_signals):
        try:
            result = run_analysis(
                data_path=data_path,
                excel_path=excel_path,
                selected_signals=selected_signals,
            )
            wx.CallAfter(self._on_analysis_complete, result)
        except Exception as exc:
            wx.CallAfter(self._on_analysis_error, exc)

    def _on_analysis_complete(self, result):
        self._log("分析完成")
        self.result_panel.set_summary("\n".join(result["summary_lines"]))
        self.result_panel.render_plot(result["plot_series"], result["plot_labels"])
        self.file_panel.set_status("状态：分析完成")
        self.file_panel.set_buttons_enabled(True)

    def _on_analysis_error(self, exc):
        self._log(f"分析失败：{exc}")
        self.file_panel.set_status("状态：分析失败")
        self.file_panel.set_buttons_enabled(True)

    def _log(self, message):
        self.result_panel.append_log(message)

    def _render_preview(self):
        preview = build_analysis_preview(
            data_path=self.file_panel.get_data_path(),
            excel_path=self.file_panel.get_excel_path(),
            selected_signals=self.file_panel.get_selected_signals() or None,
        )
        self.result_panel.set_summary("\n".join(preview["summary_lines"]))
        self.result_panel.render_plot(preview["plot_series"], preview["plot_labels"])

    def _populate_signal_options(self):
        fields = get_data_fields(self.file_panel.get_data_path())
        self.file_panel.set_signal_options(fields)


def main(dry_run=False):
    if dry_run:
        print("GUI dry run: wxPython GUI entrypoint is ready.")
        return 0

    app = wx.App(False)
    frame = FTPAGUIFrame(dry_run=dry_run)
    frame.Show()
    return app.MainLoop()


if __name__ == "__main__":
    main()
