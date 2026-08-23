"""测试 参数名.csv 单一输入下的参数映射与 LabelMap 行为。"""

from __future__ import annotations

import pandas as pd
import numpy as np

from ftpa.data.label_map import LabelMap
from ftpa.gui._data_context.field_resolver import FieldResolver

SEED_ROW_COUNT = 1225  # src/ftpa/data/参数名.csv 的数据行数（Excel 1211 + 静态独有 14）


class TestParameterMapCsv:
    """种子映射数据完整性（来自已提交的 参数名.csv）。"""

    def test_row_count(self):
        lm = LabelMap()
        assert len(lm.list_all()) == SEED_ROW_COUNT

    def test_original_names_unique(self):
        lm = LabelMap()
        origs = lm.list_all()["原始名称"].tolist()
        assert len(set(origs)) == len(origs)

    def test_known_field_label_and_unit(self):
        lm = LabelMap()
        assert lm.get_label("GNSU1001_L_076") == "高度_G1"
        assert lm.get_unit("GNSU1001_L_076") == "m"

    def test_raw_orig_name_resolves(self):
        lm = LabelMap()
        # 连字符原始名（厂商格式）与下划线字段名均可查询
        assert lm.get_label("GNSU1001-L-076") == lm.get_label("GNSU1001_L_076")

    def test_duplicate_cross_reference(self):
        lm = LabelMap()
        assert lm.get_var_names("3发油门") == [
            "RDC5001_L_323",
            "RDC5001_L_343",
            "RDC6001_L_323",
        ]


class TestLabelMapCsv:
    """LabelMap 单一 CSV 输入行为。"""

    def test_init_default_resolves_seed(self):
        lm = LabelMap()
        assert lm._loaded is True
        assert lm.get_label("GNSU1001_L_076") == "高度_G1"
        assert lm.get_unit("GNSU1001_L_076") == "m"

    def test_init_with_missing_file_degrades_to_empty(self):
        lm = LabelMap("不存在.csv")
        assert lm._loaded is False
        # 空映射：标签回退原名称
        assert lm.get_label("GNSU1001_L_076") == "GNSU1001_L_076"

    def test_duplicate_label_original_behavior(self):
        lm = LabelMap()
        # 原始重复标签仍按原行为返回最后一个
        assert lm.get_var_name("3发油门") == "RDC6001_L_323"
        # 可获取全部字段
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
        assert len(df) == SEED_ROW_COUNT

    def test_add_duplicate_generates_suffix(self):
        lm = LabelMap()
        lm.add("NEW_FIELD", "3发油门", unit="°")
        assert lm.get_var_name("3发油门_4") == "NEW_FIELD"
        assert lm.get_unit("NEW_FIELD") == "°"
        assert lm.get_var_names("3发油门")[-1] == "NEW_FIELD"

    def test_list_fields_matches_count(self):
        lm = LabelMap()
        assert len(lm.list_fields()) == SEED_ROW_COUNT


class TestFieldResolverUnits:
    """GUI 参数树显示单位（完整参数库来自已加载 LabelMap）。"""

    def test_get_field_labels_with_units(self):
        lm = LabelMap()
        fr = FieldResolver({"GNSU1001_L_076": np.array([1.0])}, lm)
        labels = fr.get_field_labels_with_units()
        assert labels["GNSU1001_L_076"] == "高度_G1 (m)"

    def test_get_field_labels_without_unit(self):
        lm = LabelMap()
        fr2 = FieldResolver({"UNKNOWN": np.array([1.0])}, lm)
        assert fr2.get_field_labels_with_units()["UNKNOWN"] == "UNKNOWN"

    def test_get_all_field_labels_with_units(self):
        lm = LabelMap()
        fr = FieldResolver(
            {"GNSU1001_L_076": np.array([1.0]), "EXTRA": np.array([1.0])},
            lm,
        )
        all_labels, available = fr.get_all_field_labels_with_units()

        # 当前数据字段
        assert all_labels["GNSU1001_L_076"] == "高度_G1 (m)"
        assert all_labels["EXTRA"] == "EXTRA"
        # CSV 参数库中存在但当前数据中没有的字段也会出现
        assert "RDC5001_L_323" in all_labels
        assert all_labels["RDC5001_L_323"] == "3发油门_1 (°)"
        # 可用字段只包含当前数据字段
        assert available == {"GNSU1001_L_076", "EXTRA"}  # noqa: C405