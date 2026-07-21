import os
from pathlib import Path

import matplotlib.pyplot as plt
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas

from ..main import DEFAULT_EXCEL_FILE, DEFAULT_TXT_FILE, resolve_path


class FileConfigPanel(wx.Panel):
    def __init__(self, parent, on_run=None, on_verify=None):
        super().__init__(parent)
        self.on_run = on_run
        self.on_verify = on_verify
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        group = wx.StaticBox(self, label="文件配置")
        gs = wx.StaticBoxSizer(group, wx.VERTICAL)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(self, label="数据文件："), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        self.data_path = wx.TextCtrl(self, value=str(DEFAULT_TXT_FILE), size=(560, -1))
        row.Add(self.data_path, 1, wx.ALL, 6)
        btn = wx.Button(self, label="浏览")
        btn.Bind(wx.EVT_BUTTON, self.on_browse_data)
        row.Add(btn, 0, wx.ALL, 6)
        gs.Add(row, 0, wx.EXPAND | wx.ALL, 6)

        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(wx.StaticText(self, label="标签文件："), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        self.excel_path = wx.TextCtrl(self, value=str(DEFAULT_EXCEL_FILE), size=(560, -1))
        row2.Add(self.excel_path, 1, wx.ALL, 6)
        btn2 = wx.Button(self, label="浏览")
        btn2.Bind(wx.EVT_BUTTON, self.on_browse_excel)
        row2.Add(btn2, 0, wx.ALL, 6)
        gs.Add(row2, 0, wx.EXPAND | wx.ALL, 6)

        self.status_text = wx.StaticText(self, label="状态：就绪")
        gs.Add(self.status_text, 0, wx.ALL, 6)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        self.run_button = wx.Button(self, label="开始分析")
        self.run_button.Bind(wx.EVT_BUTTON, self.on_run_click)
        btns.Add(self.run_button, 0, wx.ALL, 6)

        self.verify_button = wx.Button(self, label="快速验证")
        self.verify_button.Bind(wx.EVT_BUTTON, self.on_verify_click)
        btns.Add(self.verify_button, 0, wx.ALL, 6)
        gs.Add(btns, 0, wx.ALL, 6)

        self.signal_label = wx.StaticText(self, label="可选信号：")
        gs.Add(self.signal_label, 0, wx.ALL, 6)
        self.signal_list = wx.CheckListBox(self, choices=[])
        gs.Add(self.signal_list, 1, wx.ALL | wx.EXPAND, 6)

        sizer.Add(gs, 1, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(sizer)

    def on_browse_data(self, event):
        with wx.FileDialog(self, "选择数据文件", wildcard="文本文件 (*.txt)|*.txt", style=wx.FD_OPEN) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.data_path.SetValue(dlg.GetPath())

    def on_browse_excel(self, event):
        with wx.FileDialog(self, "选择标签映射文件", wildcard="Excel 文件 (*.xlsx;*.xls)|*.xlsx;*.xls", style=wx.FD_OPEN) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.excel_path.SetValue(dlg.GetPath())

    def on_run_click(self, event):
        if self.on_run is not None:
            self.on_run(event)

    def on_verify_click(self, event):
        if self.on_verify is not None:
            self.on_verify(event)

    def get_data_path(self):
        return self.data_path.GetValue()

    def get_excel_path(self):
        return self.excel_path.GetValue()

    def set_status(self, text):
        self.status_text.SetLabel(text)

    def set_signal_options(self, fields):
        self.signal_list.SetItems(fields)
        self.signal_label.SetLabel(f"可选信号（{len(fields)}）:")

    def get_selected_signals(self):
        selected = []
        for idx in range(self.signal_list.GetCount()):
            if self.signal_list.IsChecked(idx):
                selected.append(self.signal_list.GetString(idx))
        return selected

    def set_buttons_enabled(self, enabled: bool):
        self.run_button.Enable(enabled)
        self.verify_button.Enable(enabled)


class ResultPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.summary = wx.StaticText(self, label="分析摘要：等待执行")
        sizer.Add(self.summary, 0, wx.ALL, 8)

        self.figure = plt.figure(figsize=(6, 3))
        self.canvas = FigureCanvas(self, -1, self.figure)
        sizer.Add(self.canvas, 1, wx.ALL | wx.EXPAND, 8)

        self.log_ctrl = wx.TextCtrl(self, value="欢迎使用 FTPA GUI\n", style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        sizer.Add(self.log_ctrl, 1, wx.ALL | wx.EXPAND, 8)
        self.SetSizer(sizer)

    def append_log(self, message):
        self.log_ctrl.AppendText(message + "\n")

    def set_summary(self, summary):
        self.summary.SetLabel(summary)

    def render_plot(self, series_list, labels):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        for values, label in zip(series_list, labels):
            ax.plot(values, label=label)
        ax.set_title("信号预览")
        ax.set_xlabel("样本点")
        ax.set_ylabel("值")
        ax.grid(True, alpha=0.3)
        if labels:
            ax.legend()
        self.figure.tight_layout()
        self.canvas.draw()
