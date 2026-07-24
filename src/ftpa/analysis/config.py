"""
分析配置
========

定义各子系统的分析阈值和参数配置。
"""

from __future__ import annotations

# ── 发动机分析 ──
ENGINE_CONFIG = {
    "rpm_threshold": 60.0,
    "egt_threshold": 800.0,
    "oil_pressure_min": 20.0,
    "oil_pressure_max": 100.0,
    "oil_temp_threshold": 120.0,
    "start_time_col": "发动机转速",
}

# ── 燃油分析 ──
FUEL_CONFIG = {
    "fuel_flow_threshold": 1000.0,
    "fuel_quantity_min": 100.0,
    "imbalance_threshold": 5.0,
}

# ── 电源分析 ──
POWER_CONFIG = {
    "voltage_min": 24.0,
    "voltage_max": 32.0,
    "frequency_min": 380.0,
    "frequency_max": 420.0,
    "load_threshold": 80.0,
}

# ── CAS 告警分析 ──
CAS_CONFIG = {
    "warning_level_col": "CAS告警等级",
    "warning_msg_col": "CAS告警信息",
    "min_duration_sec": 1.0,
}
