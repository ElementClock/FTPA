# 飞机性能操稳数据处理项目

FTPA (Flight Test Performance Analysis) 是一个用于分析飞机性能操稳试飞数据的 Python 工具包，支持 TXT（Tab 分隔）和 CSV 两种飞参数据格式，提供 CLI 分析和 PySide6 GUI 交互界面。

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

安装后可通过以下方式运行：

```bash
# 模块模式
python -m ftpa.main

# 安装命令（pip install -e . 后可用）
ftpa

# GUI 模式
python -m ftpa.main --gui

# 快速验证
python -m ftpa.main -m verify
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

### GUI 模式

启动 PySide6 图形界面，支持数据加载、参数浏览、交互绘图、穿越分析、系统分析等功能：

```bash
python -m ftpa.main --gui
```

### 程序参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--mode` | `-m` | `verify` | 运行模式: `verify` / `chunked` / `analysis` / `stats` / `interactive` |
| `--gui` | 无 | `False` | 启动 GUI 模式 |
| `--nrows` | `-n` | `5` | 验证模式读取行数 |
| `--chunksize` | `-c` | `10000` | 分块模式每块行数 |
| `--max-chunks` | `-mxc` | `None` | 分块模式最大块数 |
| `--data-file` | 无 | 项目根目录下数据文件 | 指定输入数据文件路径 |
| `--excel-file` | 无 | 项目根目录下标签映射文件 | 指定标签映射 Excel 文件路径 |

---

## 数据文件说明

### TXT 格式（Tab 分隔，需映射表）

| 属性 | 值 |
|------|------|
| 文件大小 | ~879 MB |
| 总行数 | 173,185 行（1行表头 + 173,184行数据） |
| 列数 | **470 列** |
| 分隔符 | 制表符 `\t`（Tab-separated） |
| 编码 | UTF-8 / ASCII |
| 采样率 | ~31ms（约32Hz），TIME 格式 `HH:MM:SS:mmm` |
| 映射表 | 需要 `参数名.xlsx` 进行"字段名↔中文标签"转换 |

### CSV 格式（逗号分隔，无需映射表）

| 属性 | 值 |
|------|------|
| 分隔符 | 逗号 `,` |
| 编码 | 自动检测（UTF-8 / GBK / GB18030） |
| 映射表 | **不需要**，列名即为标签 |
| 数据模型 | 与 TXT 统一：`dict[str, np.ndarray]` |

通道映射资源：`性能操稳-元-20241122.PY`（DIAdem 脚本），包含通道→单位和通道→中文名称的映射字典。

---

## 项目结构

```
FTPA/
├── src/                          # 源代码目录
│   └── ftpa/                     # 主包
│       ├── __init__.py           # 包初始化
│       ├── main.py               # 主程序入口
│       ├── pipeline.py           # 业务流水线（load_and_prepare / full_analysis / interactive_view）
│       ├── constants.py          # 配置常量
│       ├── label_map.py          # 标签映射模块
│       ├── plotting.py           # 可视化模块
│       ├── time_utils.py         # 时间工具模块
│       ├── exporter.py           # 数据导出模块
│       ├── batch_processor.py    # 批处理模块
│       ├── column_config.py      # 列配置模块（CSV 列定义）
│       ├── computing/            # 计算子包
│       │   ├── weight_cg.py      #   重量重心反解
│       │   ├── circle_fit.py     #   Taubin 圆拟合
│       │   └── fuel_data.py      #   燃油质量特性表
│       ├── data/                 # 数据加载子包
│       │   ├── loader.py         #   TXT 数据加载（param_extract / extract_time）
│       │   ├── csv_loader.py     #   CSV 数据加载
│       │   ├── io.py             #   通用文件读取
│       │   └── cache.py          #   文件缓存（LRU + mtime 失效）
│       ├── statistics/           # 统计子包
│       │   ├── basic.py          #   基础统计 + 穿越检测
│       │   ├── multi.py          #   多变量统计 + 穿越分析
│       │   └── event_detection.py #  起降事件检测
│       ├── analysis/             # 系统分析框架（插件化）
│       │   ├── config.py         #   分析配置
│       │   ├── interface.py      #   分析接口定义
│       │   ├── plugin_manager.py #   插件管理器
│       │   ├── utils.py          #   分析工具函数
│       │   ├── engines/          #   发动机分析子系统
│       │   ├── fuel/             #   燃油分析子系统
│       │   ├── power/            #   动力分析子系统
│       │   └── cas/              #   CAS 分析子系统
│       ├── gui/                  # PySide6 图形界面
│       │   ├── app.py            #   GUI 应用入口
│       │   ├── main_window.py    #   主窗口（菜单、穿越控制、日志）
│       │   ├── services.py       #   DataContext 数据模型（TXT/CSV 双路径）
│       │   ├── panel_plot.py     #   交互绘图画布（PlotCanvasWidget）
│       │   ├── _layout_ctrl.py   #   布局控制器（1×1 / 4×1 / 2×2）
│       │   ├── _plot_renderer.py #   绘图渲染器（信号绘制 + 管理）
│       │   ├── _crossing_analyzer.py # 穿越分析器（穿越线 + 缩放 + 统计）
│       │   ├── widgets.py        #   自定义控件（参数树、穿越控制）
│       │   ├── worker.py         #   后台数据加载线程
│       │   └── ...               #   其他面板（batch / data / export / log / stats / track）
│       └── utils/                # 工具子包
│           ├── strings.py        #   字符串处理
│           ├── paths.py          #   路径解析
│           └── file_utils.py     #   文件工具（编码检测等）
│
├── tests/                        # 测试目录
│   ├── test_unit.py              # 单元测试
│   ├── test_modules.py           # 模块测试
│   ├── test_comprehensive.py     # 综合测试
│   ├── test_gui.py               # GUI 测试
│   ├── test_analysis.py          # 系统分析测试
│   ├── test_exporter.py          # 导出测试
│   ├── test_file_utils.py        # 文件工具测试
│   ├── test_column_config.py     # 列配置测试
│   ├── test_entrypoint.py        # 入口点测试
│   ├── bench_load.py             # 加载性能基准
│   └── bench_real.py             # 真实数据基准
│
├── references/                   # 参考代码
│   ├── matlab/                   #   MATLAB 原始实现
│   │   ├── Param/                #     参数提取（5个文件）
│   │   ├── PrivateComputing/     #     计算函数（2个文件）
│   │   ├── PrivateStatistics/    #     统计函数（6个文件）
│   │   └── PlotFigure/           #     绘图函数（9个文件）
│   └── flight_parameter/         #   参考项目（CSV 加载 + 分析框架）
│
├── testdata/                     # 测试数据文件（git 管理）
├── data/                         # 数据文件目录
│   ├── raw/                      # 原始数据
│   ├── processed/                # 处理后的数据
│   └── results/                  # 分析结果
│
├── logs/                         # 日志文件目录
├── examples/                     # 示例代码目录
├── docs/                         # 文档目录
│
├── pyproject.toml                # Python 项目配置
├── requirements.txt              # 依赖清单
├── README.md                     # 项目说明（本文件）
├── CLAUDE.md                     # AI 辅助开发指南
└── .gitignore                    # Git 忽略规则
```

---

## 模块架构

### 数据流

```
原始数据文件 (.txt / .csv / .zip)
    ↓
data/ (数据加载子包)
  ├─ loader.py    → TXT: param_extract() → dtype 预声明 + 单次读取
  └─ csv_loader.py → CSV: 自动编码检测 + 列配置
    ↓
label_map.py (标签映射，仅 TXT 需要；CSV 列名即为标签)
    ↓
gui/services.py (DataContext: 统一数据模型 dict[str, np.ndarray])
    ↓
computing/ (计算子包: weight_cg / circle_fit / fuel_data)
    ↓
statistics/ (统计子包: basic / multi / event_detection)
    ↓
analysis/ (系统分析框架: engines / fuel / power / cas)
    ↓
plotting.py / gui/ (可视化 / 交互界面)
    ↓
输出结果 (图表 / 报告 / 截图)
```

### 1. 数据加载层 (data/)

**职责**: 从各种数据源加载试飞数据

- `loader.py` — `param_extract()`: 统一入口提取参数数据（含 TIME 解析和 float64 转换，单次读取）；`extract_time()`: 从缓存提取时间序列
- `csv_loader.py` — `load_csv_data()`: CSV 格式数据加载，自动编码检测（chardet），列配置驱动处理
- `io.py` — `read_data_file()`: 通用文件读取（支持 dtype 预声明跳过类型推断）；`resolve_zip_file()`: ZIP 自动解压
- `cache.py` — `FileCache`: OrderedDict LRU 缓存 + mtime 失效策略

### 2. 标签映射层 (label_map.py)

**职责**: 管理参数名称与中文标签的映射关系（仅 TXT 需要）

- `LabelMap` 类: 从 Excel 加载变量名↔中文标签双向映射
- `get_label()`: 获取参数的中文标签
- `get_var_name()`: 根据标签获取参数名
- `add()`: 动态添加映射关系

### 3. 计算层 (computing/)

**职责**: 执行飞机性能和操稳参数的计算

- `weight_cg.py` — `compute_total_weight_rel_cg()`: 基于燃油质量特性表插值 + 力矩平衡反解，计算总重量和相对重心；`add_weight_cg_to_data()`: 将计算结果合并到数据容器
- `circle_fit.py` — `compute_fitted_circle_radius()`: Taubin 最小二乘圆拟合，计算回转半径
- `fuel_data.py` — 机型燃油质量特性表（硬编码常数组）

### 4. 统计分析层 (statistics/)

**职责**: 提供数据统计和分析功能

- `basic.py` — `compute_stat()`: 单变量统计（start/end/min/max/range/mean/std/points）；`find_crossing_points()`: 基础阈值穿越点查找（FirstUp/LastUp/FirstDown/LastDown）
- `multi.py` — `compute_var_stats()`: 多变量统计输出；`show_group_stats()`: 分组统计；`statistics_params()`: 通用参数统计摘要；`crossing_analysis()`: 阈值穿越分析；`generate_data_summary()` / `print_data_summary()`: 整体数据摘要
- `event_detection.py` — `compute_takeoff_landing_stats()`: 起降统计（触水时刻参数）

### 5. 系统分析框架 (analysis/)

**职责**: 插件化的子系统分析，支持发动机、燃油、动力、CAS 等分析模块

- `interface.py` — 分析接口基类定义
- `plugin_manager.py` — 插件注册与发现
- `config.py` — 分析配置管理
- `engines/` — 发动机分析子系统（数据处理器 + 分析器 + 报告生成器）
- `fuel/` — 燃油分析子系统
- `power/` — 动力分析子系统
- `cas/` — CAS 分析子系统

### 6. 可视化层 (plotting.py)

**职责**: 数据可视化（CLI 模式）

- `plot_time_signals()`: 基础多信号时间序列图
- `plot_time_signals_interactive()`: 交互式时间序列图（带控制面板）
- `plot_track()`: 航线轨迹地理绘图

### 7. GUI 层 (gui/)

**职责**: PySide6 交互式图形界面

- `services.py` — `DataContext`: 核心数据模型，桥接所有模块；TXT/CSV 双路径加载（`_load_txt()` / `_load_csv()`），CSV 不加载映射表
- `main_window.py` — 主窗口：菜单栏、穿越控制面板（阈值/模式/应用/重置）、信息显示
- `panel_plot.py` — `PlotCanvasWidget`: 交互绘图画布外观容器，委托给三个控制器：
  - `_layout_ctrl.py` — `LayoutController`: 布局模式切换（1×1/4×1/2×2）、子图选择
  - `_plot_renderer.py` — `PlotRenderer`: 数据绘制、信号添加/移除、右键菜单
  - `_crossing_analyzer.py` — `CrossingAnalyzer`: 穿越线绘制、缩放应用/重置、Y轴自动适配、统计更新
- `widgets.py` — `ParameterTreeWidget`: 参数树面板；`CrossingCtrl`: 穿越控制组件
- `worker.py` — `DataLoaderWorker`: 后台线程数据加载

#### 穿越分析交互（参照 MATLAB plotCoreInteractive.m）

| 按钮 | 行为 |
|------|------|
| **应用** | 在当前视图时间窗口内检测穿越点（排除 NaN），未找到时回退到窗口边界，缩放 X 轴至穿越区间，自动调整 Y 轴适配可见数据（5% 边距） |
| **重置** | 恢复到数据加载时的初始时间范围，同步调整 Y 轴 |

### 8. 工具层 (time_utils.py, utils/)

- `select_time_window()`: 时间窗口索引选择
- `format_time_seconds()`: 数值秒→`HH:MM:SS.mmm` 格式化
- `make_valid_name()`: 生成合法变量名
- `column_to_field_name()`: 列名→字段名转换
- `resolve_excel_path()`: 自动发现标签映射 Excel 文件（搜索 testdata/ 和 src/ftpa/data/）
- `file_utils.py`: 文件编码自动检测（chardet）

---

## 配置管理

项目使用 `src/ftpa/constants.py` 进行集中配置管理。此文件为唯一的配置来源（single source of truth），包含以下参数：

| 参数 | 值 | 说明 |
|------|-----|------|
| `BASE_WEIGHT` | 48487.0 | 任务总重量 (kg) |
| `BASE_REL_CG` | 25.28 | 任务重心 (%) |
| `BASE_OIL` | 6000.0 | 任务油量 (kg) |
| `X0` | 15.902 | 参考点绝对重心 (m) |
| `L` | 4.453 | 参考长度 (m) |
| `TRIM_HEAD` | 50 | 文件头部裁剪行数 |
| `TRIM_TAIL` | 50 | 文件尾部裁剪行数 |
| `CHUNK_SIZE` | 10000 | 分块读取每块行数 |

如需修改默认参数（如更换机型），只需编辑 `constants.py` 中的对应值。

---

## 依赖管理

### 核心依赖

| 库 | 用途 |
|---|---|
| numpy | 数值计算 |
| pandas | 数据处理 |
| matplotlib | 静态可视化 |
| PySide6 | GUI 图形界面 |
| plotly | 交互式可视化 |
| scipy | 科学计算（广义特征值分解） |
| openpyxl | Excel 文件处理 |
| chardet | 文件编码自动检测 |

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
4. **GUI 测试**: 测试界面组件和数据流
5. **性能基准**: 数据加载耗时基准

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
- 异常处理必须使用 `except Exception:`，禁止裸 `except` 和静默吞错

### 命名规范

- 模块名: `snake_case`
- 类名: `PascalCase`
- 函数/方法名: `snake_case`
- 常量: `UPPER_SNAKE_CASE`

### Git 工作流

- `main`: 稳定版本（对应已发布的 commit）
- `dev`: 开发主线，所有变更在此推进
- 阶段性重构或大规模变更在 `dev` 上线性开发，完成后以语义化 commit message 标记

---

## 性能指标

| 指标 | 数值 |
|------|------|
| TXT 冷启动加载（879MB） | ~20 秒 |
| extract_time()（缓存命中） | <0.001 秒 |
| 单块内存峰值（chunksize=10000） | ~200 MB |
| 引擎 | pandas C engine (`engine='c'`) |

### 已实现的优化

1. **数据加载**: 统一入口 `param_extract()` 消除双重读取，dtype 预声明跳过类型推断，FileCache LRU + mtime 失效
2. **计算**: NumPy 向量化运算
3. **内存**: 数据裁剪、按需加载
4. **GUI**: 后台线程加载防阻塞，DataFrame 一次性构建避免碎片化

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
- [ ] `python -m ftpa.main --gui` 正常启动
- [ ] 数据提取功能正常（TXT / CSV）
- [ ] 重量重心计算正常
- [ ] 统计计算正常
- [ ] 时间解析正常
- [ ] GUI 穿越分析（应用/重置）正常

### 回滚方案

```bash
# 使用 Git 回滚
git log --oneline
git reset --hard HEAD~1

# 或回滚到特定标签
git checkout v1.0.0
```

---

*此文件为项目主文档。*
*最后更新：2026-07-24*
