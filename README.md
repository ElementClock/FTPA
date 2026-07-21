# 飞机性能操稳数据处理项目

FTPA (Flight Test Performance Analysis) 是一个用于分析飞机性能操稳试飞数据的 Python 工具包，主要用于处理 AG600 飞机的试飞数据。

> **AI 辅助开发指南请参阅 [CLAUDE.md](CLAUDE.md)**

---

## 环境要求

- Python 3.10+
- Windows 10/11

## 安装步骤

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境（Windows）
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 以开发模式安装本项目
pip install -e .
```

## 使用方法

### 快速验证

读取文件前几行，验证文件结构：

```bash
python -m ftpa.main --mode verify
python -m ftpa.main --mode verify --nrows 10
```

### 分块读取

逐块读取全部数据，内存友好：

```bash
# 读取全部数据
python -m ftpa.main --mode chunked

# 自定义块大小
python -m ftpa.main --mode chunked --chunksize 5000

# 限制读取块数（用于测试）
python -m ftpa.main --mode chunked --max-chunks 5
```

### 完整分析

加载数据、计算重量重心、绘制交互图表：

```bash
python -m ftpa.main --mode analysis
```

### 统计分析

输出指定时间窗口内的统计结果：

```bash
python -m ftpa.main --mode stats
```

### 交互式查看

启动可交互的多信号查看界面，支持窗口缩放、阈值穿越提示和统计摘要：

```bash
python -m ftpa.main --mode interactive
```

### 程序参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--mode` | `-m` | `verify` | 运行模式: `verify` / `chunked` / `analysis` / `stats` / `interactive` |
| `--nrows` | `-n` | `5` | 验证模式读取行数 |
| `--chunksize` | `-c` | `10000` | 分块模式每块行数 |
| `--max-chunks` | `-mxc` | `None` | 分块模式最大块数 |
| `--data-file` | 无 | 项目根目录下数据文件 | 指定输入数据文件路径 |
| `--excel-file` | 无 | 项目根目录下标签映射文件 | 指定标签映射 Excel 文件路径 |

---

## 数据文件说明

| 属性 | 值 |
|------|------|
| 文件名 | `FTPD-AG600-007-QD-260509-G-1-飞机性能操稳-32.txt` |
| 文件大小 | ~879 MB |
| 总行数 | 173,185 行（1行表头 + 173,184行数据） |
| 列数 | **470 列** |
| 分隔符 | 制表符 `\t`（Tab-separated） |
| 编码 | UTF-8 / ASCII |
| 采样率 | ~31ms（约32Hz），TIME 格式 `HH:MM:SS:mmm` |

通道映射资源：`性能操稳-元-20241122.PY`（DIAdem 脚本），包含通道→单位和通道→中文名称的映射字典。

---

## 项目结构

```
FTPA/
├── src/                          # 源代码目录
│   └── ftpa/                     # 主包
│       ├── __init__.py           # 包初始化
│       ├── main.py               # 主程序入口
│       ├── data_loader.py        # 数据加载模块
│       ├── label_map.py          # 标签映射模块
│       ├── computing.py          # 计算模块
│       ├── statistics.py         # 统计分析模块
│       ├── plotting.py           # 可视化模块
│       ├── time_utils.py         # 时间工具模块
│       └── utils.py              # 通用工具函数
│
├── tests/                        # 测试目录
│   ├── __init__.py
│   ├── test_comprehensive.py     # 综合测试
│   ├── test_modules.py           # 模块测试
│   └── test_unit.py              # 单元测试
│
├── config/                       # 配置文件目录
│   └── config.yaml               # 主配置文件
│
├── data/                         # 数据文件目录
│   ├── raw/                      # 原始数据
│   ├── processed/                # 处理后的数据
│   └── results/                  # 分析结果
│
├── logs/                         # 日志文件目录
├── examples/                     # 示例代码目录
├── docs/                         # 文档目录
│
├── matlab看飞测数据/              # MATLAB参考代码（历史）
│   ├── Param/                    # 参数提取（5个文件）
│   ├── PrivateComputing/         # 计算函数（2个文件）
│   ├── PrivateStatistics/        # 统计函数（6个文件）
│   └── PlotFigure/               # 绘图函数（9个文件）
│
├── pyproject.toml                # Python项目配置
├── requirements.txt              # 依赖清单
├── README.md                     # 项目说明（本文件）
├── CLAUDE.md                     # AI辅助开发指南
├── .gitignore                    # Git忽略规则
├── 性能操稳-元-20241122.PY       # 通道映射定义
└── FTPD-AG600-007-QD-260509-G-1-飞机性能操稳-32.txt  # 原始数据文件
```

---

## 模块架构

### 数据流

```
原始数据文件 (.txt/.zip)
    ↓
data_loader.py (数据加载)
    ↓
label_map.py (标签映射)
    ↓
computing.py (参数计算)
    ↓
statistics.py (统计分析)
    ↓
plotting.py (可视化)
    ↓
输出结果 (图表/报告)
```

### 1. 数据加载层 (data_loader.py)

**职责**: 从各种数据源加载试飞数据

- `param_extract()`: 提取参数数据
- `extract_time()`: 提取时间序列
- `extract_column_efficient()`: 高效提取单列数据（带模块级缓存）
- 支持 ZIP 压缩文件自动解压、数据裁剪（trim_head/trim_tail）

### 2. 标签映射层 (label_map.py)

**职责**: 管理参数名称与中文标签的映射关系

- `LabelMap` 类: 从 Excel 加载变量名↔中文标签双向映射
- `get_label()`: 获取参数的中文标签
- `get_var_name()`: 根据标签获取参数名
- `add()`: 动态添加映射关系

### 3. 计算层 (computing.py)

**职责**: 执行飞机性能和操稳参数的计算

- `compute_total_weight_rel_cg()`: 基于燃油质量特性表插值 + 力矩平衡反解，计算总重量和相对重心
- `compute_fitted_circle_radius()`: Taubin 最小二乘圆拟合，计算回转半径

### 4. 统计分析层 (statistics.py)

**职责**: 提供数据统计和分析功能

- `compute_stat()`: 单变量统计（start/end/min/max/range/mean/std/points）
- `compute_var_stats()`: 多变量统计输出
- `show_group_stats()`: 分组统计
- `compute_takeoff_landing_stats()`: 起降统计（触水时刻参数）
- `statistics_params()`: 通用参数统计摘要
- `crossing_analysis()`: 阈值穿越分析

### 5. 可视化层 (plotting.py)

**职责**: 数据可视化

- `plot_time_signals()`: 基础多信号时间序列图
- `plot_time_signals_interactive()`: 交互式时间序列图（带控制面板）
- `plot_track()`: 航线轨迹地理绘图

### 6. 工具层 (time_utils.py, utils.py)

- `select_time_window()`: 时间窗口索引选择
- `format_time_seconds()`: 数值秒→`HH:MM:SS.mmm` 格式化
- `make_valid_name()`: 生成合法变量名
- `column_to_field_name()`: 列名→字段名转换

---

## 配置管理

项目使用 `config/config.yaml` 进行配置管理：

```yaml
data:
  txt_file: "数据文件路径"
  excel_file: "标签映射文件路径"
  chunk_size: 10000
  trim_head: 50
  trim_tail: 50

aircraft:
  base_weight: 48487.0    # 任务总重量 (kg)
  base_rel_cg: 25.28      # 任务重心 (%)
  base_oli: 6000.0        # 任务油量 (kg)
  x0: 15.902              # 重心参考点
  l: 4.453                # 参考长度

output:
  log_dir: "logs"
  result_dir: "data/results"
  plot_dir: "data/plots"

logging:
  level: "INFO"
  file: "logs/ftpa.log"
```

---

## 依赖管理

### 核心依赖

| 库 | 用途 |
|---|---|
| numpy | 数值计算 |
| pandas | 数据处理 |
| matplotlib | 静态可视化 |
| plotly | 交互式可视化 |
| scipy | 科学计算（广义特征值分解） |
| openpyxl | Excel文件处理 |

### 开发依赖

| 库 | 用途 |
|---|---|
| pytest | 单元测试 |
| pytest-cov | 覆盖率测试 |
| black | 代码格式化 |
| flake8 | 代码检查 |
| mypy | 类型检查 |

---

## 测试

### 测试层次

1. **单元测试**: 测试单个函数/方法
2. **模块测试**: 测试模块间交互
3. **综合测试**: 测试完整工作流程

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_unit.py -v

# 生成覆盖率报告（需安装 pytest-cov）
pytest --cov=src/ftpa --cov-report=html
```

---

## 开发规范

### 代码风格

- 遵循 PEP 8 规范，使用 4 空格缩进，最大行宽 100 字符
- 使用类型注解（Type Hints）
- 所有公共函数/类必须有 docstring（Google 风格）
- 注释使用中文

### 命名规范

- 模块名: `snake_case`
- 类名: `PascalCase`
- 函数/方法名: `snake_case`
- 常量: `UPPER_SNAKE_CASE`

### Git 工作流

- `main`: 稳定版本
- `develop`: 开发分支
- `feature/*`: 功能分支
- `bugfix/*`: 修复分支
- `release/*`: 发布分支

---

## 性能指标

| 指标 | 数值 |
|------|------|
| 读取速率 | ~19,000 行/秒 |
| 全文件耗时 | ~9 秒 |
| 单块内存峰值（chunksize=10000） | ~200 MB |
| 引擎 | pandas C engine (`engine='c'`) |

### 已实现的优化

1. **数据加载**: 分块读取、模块级缓存、ZIP 文件直接读取
2. **计算**: NumPy 向量化运算
3. **内存**: 数据裁剪、按需加载

---

## 部署与回滚

### 开发环境部署

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 以开发模式安装
pip install -e .

# 运行测试验证
pytest tests/test_unit.py -v
```

### 验证清单

- [ ] 所有单元测试通过
- [ ] `python -m ftpa.main --mode verify` 正常运行
- [ ] `python -m ftpa.main --mode analysis` 正常运行
- [ ] 数据提取功能正常
- [ ] 重量重心计算正常
- [ ] 统计计算正常
- [ ] 时间解析正常

### 回滚方案

```bash
# 使用 Git 回滚
git log --oneline
git reset --hard HEAD~1

# 或回滚到特定标签
git checkout v1.0.0
```

---

## 扩展性设计

### 插件机制

```python
class CustomPlugin:
    def process(self, data, config):
        # 自定义处理逻辑
        return result
```

### 配置驱动

支持多环境配置（开发、测试、生产）、运行时配置覆盖。

---

*此文件为项目主文档。*
*最后更新：2026-07-21*
