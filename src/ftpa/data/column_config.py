"""
列名配置模块
============

定义飞参数据列名的 ATA 编号替换规则，
将原始列名中的系统编号简化为中文名称。
"""

from __future__ import annotations

from typing import Dict

from .parameter_map import PARAMETER_LABELS


def get_replacement_rules() -> Dict[str, str]:
    """获取列名替换规则字典。

    键为原始列名中的 ATA 编号子串，值为替换后的中文名称。

    Returns:
        替换规则字典。
    """
    return {
        "ATA345_GNSU1全球卫星定位系统": "全球卫星定位系统1",
        "ATA345_GNSU2全球卫星定位系统": "全球卫星定位系统2",
        "ATA345_SMU短报文": "短报文",
        "ATA342_AHRU航姿基准系统": "航姿基准系统",
        "ATA341_ADRU1大气数据系统": "大气数据系统1",
        "ATA341_ADRU2大气数据系统": "大气数据系统2",
        "ATA341_ADRU3大气数据系统": "大气数据系统3",
        "ATA344_IRU1惯性基准系统": "惯性基准系统1",
        "ATA344_IRU2惯性基准系统": "惯性基准系统2",
        "ATA317_FMCC1飞行管理系统": "飞行管理系统1",
        "ATA317_FMCC2飞行管理系统": "飞行管理系统2",
        "ATA316_IDU1显示控制系统": "显示控制系统",
        "ATA344_RA1无线电高度表": "无线电高度表1",
        "ATA344_RA2无线电高度表": "无线电高度表2",
        "ATA344_RPU气象雷达": "气象雷达",
        "ATA341_ISI备份仪表": "备份仪表",
        "ATA315_CAS1显示告警系统": "显示告警系统",
        "ATA344_LIU_C1波段L综合系统": "波段L综合系统1",
        "ATA344_LIU_C2波段L综合系统": "波段L综合系统2",
        "ATA238_RIU1无线电接口单元": "无线电接口单元1",
        "ATA238_RIU2无线电接口单元": "无线电接口单元2",
        "ATA314_RDC1机电信息采集系统": "机电信息采集系统1",
        "ATA314_RDC2机电信息采集系统": "机电信息采集系统2",
        "ATA314_RDC3机电信息采集系统": "机电信息采集系统3",
        "ATA314_RDC4机电信息采集系统": "机电信息采集系统4",
        "ATA314_RDC5机电信息采集系统": "机电信息采集系统5",
        "ATA314_RDC6机电信息采集系统": "机电信息采集系统6",
        "ATA314_RDC7机电信息采集系统": "机电信息采集系统7",
        "ATA314_RDC8机电信息采集系统": "机电信息采集系统8",
        "ATA314_CPDC1机电信息采集": "机电信息采集",
        "ATA36气源系统": "气源系统",
        "ATA21空调系统": "空调系统",
        "ATA21_CPC1座舱压力系统": "座舱压力系统",
        "ATA21_CPSU座舱压力系统": "座舱压力系统",
        "ATA22_AFCC自动飞行系统": "自动飞行系统",
        "ATA22_AFCP自动飞行系统": "自动飞行系统",
        "ATA24_L_PDU左电源系统": "左电源系统",
        "ATA24_R_PDU右电源系统": "右电源系统",
        "ATA26_HKH17A防火系统": "防火系统",
        "ATA279_CAB1主飞控系统": "主飞控系统1",
        "ATA279_CAB2主飞控系统": "主飞控系统2",
        "ATA279_CAB3主飞控系统": "主飞控系统3",
        "ATA275_FECU1襟翼控制系统": "襟翼控制系统1",
        "ATA275_FECU2襟翼控制系统": "襟翼控制系统2",
        "ATA28_FQC燃油系统": "燃油系统",
        "ATA324_BCU刹车控制系统": "刹车控制系统",
        "ATA293_HECU液压电控系统": "液压电控系统",
        "ATA325_SCU前轮转弯系统": "前轮转弯系统",
        "ATA30_TBDI_TIMER防冰和除雨": "防冰和除雨",
        "ATA30_WTC1防冰和除雨": "防冰和除雨",
        "ATA30_PR_PHC防冰和除雨": "防冰和除雨",
        "ATA52_KZQ舱门系统": "舱门系统",
        "ATA25_WATERCU设备用具": "设备用具",
        "ATA32_PDCU1起落架系统": "起落架系统",
        "ATA48_FTC灭火任务系统": "灭火任务系统",
        "ATA48_FECC灭火任务系统": "灭火任务系统",
        "ATA344_SAVMU环境感知与视频管理系统": "环境感知与视频管理系统",
        "ATA42_NCPP1综合处理系统": "综合处理系统1",
        "ATA42_NCPP2综合处理系统": "综合处理系统2",
        "ATA42_HM_GPM1综合处理系统": "综合处理系统3",
        "ATA313_FDR飞参系统": "飞参系统",
        "ATA313_TACE飞参系统": "飞参系统",
        "ATA313_QAR飞参系统": "飞参系统",
        "ATA73_EUC燃油系统": "燃油系统",
    }


def apply_replacement_rules(column_name: str, rules: Dict[str, str] | None = None) -> str:
    """对单个列名应用替换规则。

    Args:
        column_name: 原始列名。
        rules: 替换规则字典，None 时使用默认规则。

    Returns:
        替换后的列名。
    """
    # Excel/静态映射的精确原始名优先于 ATA 子串替换
    if column_name in PARAMETER_LABELS:
        return PARAMETER_LABELS[column_name]

    if rules is None:
        rules = get_replacement_rules()
    for pattern, replacement in rules.items():
        if pattern in column_name:
            return column_name.replace(pattern, replacement)
    return column_name
