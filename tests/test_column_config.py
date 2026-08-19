"""
测试 column_config 模块
"""

from ftpa.data.column_config import get_replacement_rules, apply_replacement_rules


class TestReplacementRules:
    """ATA 列名替换规则测试。"""

    def test_rules_not_empty(self):
        rules = get_replacement_rules()
        assert len(rules) > 0

    def test_known_ata_rule(self):
        rules = get_replacement_rules()
        assert "ATA345_GNSU1全球卫星定位系统" in rules
        assert rules["ATA345_GNSU1全球卫星定位系统"] == "全球卫星定位系统1"

    def test_apply_replacement_match(self):
        result = apply_replacement_rules("ATA345_GNSU1全球卫星定位系统_1发")
        assert "ATA345" not in result
        assert "全球卫星定位系统1" in result

    def test_apply_replacement_no_match(self):
        result = apply_replacement_rules("普通列名")
        assert result == "普通列名"

    def test_apply_custom_rules(self):
        custom = {"OLD": "NEW"}
        result = apply_replacement_rules("OLD_COLUMN", rules=custom)
        assert result == "NEW_COLUMN"

    def test_apply_excel_exact_name_first(self):
        """Excel 静态映射的精确原始名优先于 ATA 子串规则。"""
        result = apply_replacement_rules("GNSU1001_L_076")
        assert result == "高度_G1"
