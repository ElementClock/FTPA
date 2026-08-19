"""测试静态参数映射与 LabelMap 的静态/Excel 混合加载。"""

from __future__ import annotations

import pandas as pd
import pytest

import numpy as np

from ftpa.data.label_map import LabelMap
from ftpa.data.parameter_map import (
    DISPLAY_LABEL_TO_FIELDS,
    DUPLICATE_LABELS,
    ORIGINAL_LABEL_TO_FIELDS,
    PARAMETER_LABELS,
    PARAMETER_UNITS,
)
from ftpa.gui._data_context.field_resolver import FieldResolver


class TestParameterMapStatic:
    """静态映射数据完整性。"""

    def test_label_count(self):
        assert len(PARAMETER_LABELS) == 538
        assert len(PARAMETER_UNITS) == 538

    def test_original_names_unique(self):
        assert len(set(PARAMETER_LABELS.keys())) == len(PARAMETER_LABELS)

    def test_labels_not_empty(self):
        assert all(label.strip() for label in PARAMETER_LABELS.values())

    def test_units_contains_known_sample(self):
        assert PARAMETER_UNITS["GNSU1001_L_076"] == "m"

    def test_duplicate_cross_reference(self):
        assert ORIGINAL_LABEL_TO_FIELDS["3发油门"] == [
            "RDC5001_L_323",
            "RDC5001_L_343",
            "RDC6001_L_323",
        ]
        assert DUPLICATE_LABELS["3发油门"] == [
            "3发油门_1",
            "3发油门_2",
            "3发油门_3",
        ]

    def test_display_labels_unique(self):
        assert len(set(PARAMETER_LABELS.values())) == len(PARAMETER_LABELS)


class TestLabelMapStatic:
    """LabelMap 在无 Excel 时应回退到静态映射。"""

    def test_init_without_excel(self):
        lm = LabelMap()
        assert lm.get_label("GNSU1001_L_076") == "高度_G1"
        assert lm.get_unit("GNSU1001_L_076") == "m"

    def test_init_with_missing_file_falls_back(self):
        lm = LabelMap("不存在.xlsx")
        assert lm.get_label("GNSU1001_L_076") == "高度_G1"

    def test_duplicate_label_warning_and_original_behavior(self):
        lm = LabelMap()
        # 原始重复标签仍按原行为返回最后一个
        assert lm.get_var_name("3发油门") == "RDC6001_L_323"
        # 新增方法可获取全部字段
        assert lm.get_var_names("3发油门") == [
            "RDC5001_L_323",
            "RDC5001_L_343",
            "RDC6001_L_323",
        ]

    def test_display_label_lookup(self):
        lm = LabelMap()
        assert lm.get_var_name("3发油门_2") == "RDC5001_L_343"

    def test_list_all_with_units(self):
        lm = LabelMap()
        df = lm.list_all_with_units()
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["原始名称", "结构体字段名", "中文标签", "单位"]
        assert len(df) == 538

    def test_add_duplicate_generates_suffix(self):
        lm = LabelMap()
        lm.add("NEW_FIELD", "3发油门", unit="°")
        assert lm.get_var_name("3发油门_4") == "NEW_FIELD"
        assert lm.get_unit("NEW_FIELD") == "°"
        assert lm.get_var_names("3发油门")[-1] == "NEW_FIELD"


class TestFieldResolverUnits:
    """GUI 参数树显示单位。"""

    def test_get_field_labels_with_units(self):
        lm = LabelMap()
        fr = FieldResolver({"GNSU1001_L_076": np.array([1.0])}, lm)
        labels = fr.get_field_labels_with_units()
        assert labels["GNSU1001_L_076"] == "高度_G1 (m)"

    def test_get_field_labels_without_unit(self):
        lm = LabelMap()
        fr = FieldResolver({"TIME": np.array([0.0])}, lm)
        labels = fr.get_field_labels_with_units()
        # TIME 不在字段列表中（FieldResolver 会排除元数据键），因此这里验证未知字段回退
        fr2 = FieldResolver({"UNKNOWN": np.array([1.0])}, lm)
        assert fr2.get_field_labels_with_units()["UNKNOWN"] == "UNKNOWN"
