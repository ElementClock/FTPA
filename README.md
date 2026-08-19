# 飞机性能操稳数据处理项目

FTPA (Flight Test Performance Analysis) 是一个用于分析飞机性能操稳试飞数据的 Python 工具包，支持 TXT（Tab 分隔）和 CSV 两种飞参数据格式，提供 PySide6 GUI 交互界面（外加 `--dry-run` 无界面验证入口）。

> CLI 分析模式（verify/chunked/analysis/stats/interactive）已归档（当前仓库未保留归档目录），不再由 `src/ftpa/main.py` 提供。

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
# GUI 模式（默认）
python -m ftpa.main

# 无界面验证（CI / 无头环境）
python -m ftpa.main --dry-run

# 安装命令（pip install -e . 后可用）
ftpa
```

### 桌面端直接运行

Windows 下可直接双击项目根目录的 `FTPA_GUI.bat` 启动 GUI，
脚本会自动使用 `.venv\Scripts\python.exe`（不存在时回退到系统 `python`），
无需手动输入命令。

## 使用方法

### GUI 模式（默认）

启动 PySide6 图形界面，支持数据加载、参数浏览、交互绘图、穿越分析、系统分析、批量处理、数据导出等功能：

```bash
python -m ftpa.main
```

### 无界面验证

在无头环境（CI、远程服务器）中验证 GUI 入口可用，不实际创建窗口：

```bash
python -m ftpa.main --dry-run
```

### 程序参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--dry-run` | 无 | `False` | 无界面模式，仅校验入口可正常加载（不创建窗口） |

> 旧版 `--mode` / `--gui` / `--nrows` / `--chunksize` 等 CLI 参数已随 CLI 模块归档（当前仓库未保留归档目录），主入口不再支持。

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
│       ├── __init__.py           # 包初始化（含公共 API 重导出）
│       ├── main.py               # GUI 入口（--dry-run 支持）
│       ├── config.py             # 配置管理（frozen dataclass + TOML）
│       ├── errors.py             # 自定义异常层次（FtpaError → LoadError → 子类）
│       ├── gui/                  # PySide6 图形界面
│       │   ├── app.py            #   GUI 应用入口
│       │   ├── main_window.py    #   主窗口（菜单、穿越控制、日志）
│       │   ├── services.py       #   32 行纯重导出（向后兼容入口）
│       │   ├── _data_context/    #   DataContext Facade 子包
│       │   │   ├── data_context.py     # 240 行 Facade 协调者
│       │   │   ├── loading.py          # Strategy 模式加载器（TxtLoader/CsvLoader）
│       │   │   ├── query.py            # 只读数据查询服务（含 get_raw_data()）
│       │   │   ├── export_service.py   # 数据导出
│       │   │   ├── plot_data_service.py# 绘图数据提取
│       │   │   ├── statistics_service.py# 统计计算
│       │   │   ├── field_resolver.py   # 字段解析器
│       │   │   └── protocols.py        # 窄接口 Protocol
│       │   ├── panel_plot.py     #   交互绘图画布外观（PlotCanvasWidget）
│       │   ├── panel_batch.py    #   批量处理面板
│       │   ├── panel_export.py   #   导出面板
│       │   ├── panel_log.py      #   日志面板
│       │   ├── panel_stats.py    #   统计面板
│       │   ├── panel_track.py    #   航迹面板
│       │   ├── _layout_ctrl.py   #   布局控制器（1×1 / 4×1 / 2×2）
│       │   ├── _plot_renderer.py #   绘图渲染器（信号绘制 + 管理）
│       │   ├── _crossing_analyzer.py # 穿越分析器（穿越线 + 缩放 + 统计）
│       │   ├── _pan_ctrl.py      #   平移控制器（左键拖拽水平平移）
│       │   ├── _region_ctrl.py   #   区域框选控制器（右键拖动选时间区间）
│       │   ├── _drop_ctrl.py     #   拖放控制器（参数树拖到子图）
│       │   ├── _downsampler.py   #   向量化 min-max 降采样
│       │   ├── _font_config.py   #   Matplotlib CJK 字体配置
│       │   ├── widgets.py        #   自定义控件（参数树、穿越控制）
│       │   ├── worker.py         #   后台线程（DataLoaderWorker + AnalysisWorker）
│       │   └── log_handler.py    #   logging → GUI 日志桥接
│       ├── data/                 # 数据加载子包
│       │   ├── loader.py         #   TXT 数据加载（param_extract / extract_time）
│       │   ├── csv_loader.py     #   CSV 数据加载
│       │   ├── io.py             #   通用文件读取（含 ZIP Slip 防护）
│       │   ├── cache.py          #   文件缓存（LRU + mtime 失效）
│       │   ├── batch.py          #   批处理（batch_process_files 等3个函数）
│       │   ├── label_map.py      #   标签映射（LabelMap）
│       │   ├── exporter.py       #   数据导出
│       │   ├── column_config.py  #   列配置（CSV 列定义）
│       │   ├── summary.py        #   数据摘要（generate/print_data_summary）
│       │   └── enrichment.py     #   数据富化（add_weight_cg_to_data）
│       ├── computing/            # 计算子包
│       │   ├── weight_cg.py      #   重量重心反解
│       │   ├── circle_fit.py     #   Taubin 圆拟合
│       │   ├── fuel_data.py      #   燃油质量特性表
│       │   └── aircraft.py       #   飞机参数常量（AG1007 架次）
│       ├── statistics/           # 统计子包
│       │   ├── basic.py          #   基础统计 + 穿越检测
│       │   ├── multi.py          #   多变量统计 + 穿越分析
│       │   └── event_detection.py#  起降事件检测
│       ├── analysis/             # 系统分析框架（插件化）
│       │   ├── config.py         #   分析配置
│       │   ├── interface.py      #   分析接口定义
│       │   ├── plugin_manager.py #   插件管理器
│       │   ├── utils.py          #   分析工具函数
│       │   ├── engines/          #   发动机分析子系统（*_analysis.py + *_report_generator.py）
│       │   ├── fuel/             #   燃油分析子系统
│       │   ├── power/            #   动力分析子系统
│       │   └── cas/              #   CAS 分析子系统
│       └── utils/                # 工具子包
│           ├── strings.py        #   字符串处理
│           ├── paths.py          #   路径解析（不再依赖 data 层）
│           ├── file_utils.py     #   文件工具（编码检测等）
│           ├── time_utils.py     #   时间工具
│           └── log_utils.py      #   纯 Python 日志配置（零 Qt 依赖）
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
│   ├── test_entrypoint.py        # 入口点测试（--dry-run）
│   ├── test_config.py            # 配置测试
│   ├── test_cache.py             # 缓存测试
│   ├── test_csv_loader.py        # CSV 加载测试
│   ├── test_csv_loader_filter.py # CSV 时间列过滤测试
│   ├── test_plot_renderer.py     # 渲染器测试
│   ├── test_region_ctrl.py       # 区域控制器测试
│   ├── test_event_detection.py   # 事件检测测试
│   ├── test_review_fixes.py      # 代码审阅修复回归测试
│   ├── bench_load.py             # 加载性能基准
│   ├── bench_real.py             # 真实数据基准
│   └── bench_scroll_zoom.py      # 滚动缩放基准
│
├── data/                         # 数据文件目录（当前含参数名.xlsx 与示例 TXT）
│
├── FTPA_GUI.bat                  # Windows 桌面双击启动脚本（直接运行 GUI）
├── pyproject.toml                # Python 项目配置
├── requirements.txt              # 依赖清单（带兼容性上限）
├── ftpa_config.toml              # 项目级 TOML 配置（可选）
├── README.md                     # 项目说明（本文件）
├── AGENTS.md                     # AI 辅助开发指南
├── CHANGELOG.md                  # 变更日志
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
data/label_map.py (标签映射，仅 TXT 需要；CSV 列名即为标签)
    ↓
gui/_data_context/data_context.py (DataContext Facade: 统一数据模型 dict[str, np.ndarray])
    ↓
computing/ (计算子包: weight_cg / circle_fit / fuel_data / aircraft)
    ↓
statistics/ (统计子包: basic / multi / event_detection)
    ↓
analysis/ (系统分析框架: engines / fuel / power / cas)
    ↓
gui/ (PySide6 交互界面 + matplotlib 渲染)
    ↓
输出结果 (图表 / 报告 / 截图)
```

### 1. 数据加载层 (data/)

**职责**: 从各种数据源加载试飞数据，并管理标签映射、批量处理、数据富化与摘要

- `loader.py` — `param_extract()`: 统一入口提取参数数据（含 TIME 解析和 float64 转换，单次读取）；`extract_time()`: 从缓存提取时间序列
- `csv_loader.py` — `csv_param_extract()`: CSV 格式数据加载，自动编码检测（chardet），列配置驱动处理
- `io.py` — `read_data_file()`: 通用文件读取（支持 dtype 预声明跳过类型推断）；`resolve_zip_file()`: ZIP 自动解压（含 Zip Slip 路径遍历校验）
- `cache.py` — `FileCache`: OrderedDict LRU 缓存 + mtime 失效策略
- `label_map.py` — `LabelMap`: 参数名称↔中文标签双向映射（从 Excel 加载，仅 TXT 需要）
  - `get_label()` / `get_var_name()` / `add()`: 标签查询与动态扩展
- `batch.py` — `batch_process_files()` / `batch_analyze_statistics()` / `batch_export_summaries()`: 批量处理（从 `batch_processor.py` 迁入）
- `summary.py` — `generate_data_summary()` / `print_data_summary()`: 数据摘要（从 `statistics/multi.py` 迁入，消除循环依赖）
- `enrichment.py` — `add_weight_cg_to_data()`: 数据富化（从 `computing/weight_cg.py` 迁入，修复跨层依赖）
- `exporter.py` — `export_data()` / `export_statistics()`: 数据导出（支持 CSV / Parquet / HDF5 / Excel / JSON，JSON 可选 gzip 压缩）
- `column_config.py` — `get_replacement_rules()` / `apply_replacement_rules()`: CSV 列配置

### 2. 计算层 (computing/)

**职责**: 执行飞机性能和操稳参数的纯计算

- `weight_cg.py` — `compute_total_weight_rel_cg()`: 基于燃油质量特性表插值 + 力矩平衡反解，计算总重量和相对重心
- `circle_fit.py` — `compute_fitted_circle_radius()`: Taubin 最小二乘圆拟合，计算回转半径
- `fuel_data.py` — 机型燃油质量特性表（硬编码常数组）
- `aircraft.py` — AG1007 架次飞机参数常量（`BASE_WEIGHT` / `BASE_REL_CG` / `BASE_OIL` / `X0` / `L`），更换机型只需修改此文件

### 3. 统计分析层 (statistics/)

**职责**: 提供数据统计和分析功能

- `basic.py` — `compute_stat()`: 单变量统计（start/end/min/max/range/mean/std/points）；`find_crossing_points()`: 基础阈值穿越点查找（FirstUp/LastUp/FirstDown/LastDown）
- `multi.py` — `compute_var_stats()`: 多变量统计输出；`show_group_stats()`: 分组统计；`statistics_params()`: 通用参数统计摘要（统一实现 `_statistics_params_impl`）；`crossing_analysis()`: 阈值穿越分析（统一实现 `_crossing_analysis_impl`）；并重导出 `generate_data_summary` / `print_data_summary` 以保持向后兼容
- `event_detection.py` — `compute_takeoff_landing_stats()`: 起降统计（触水时刻参数）

### 4. 系统分析框架 (analysis/)

**职责**: 插件化的子系统分析，支持发动机、燃油、动力、CAS 等分析模块

- `interface.py` — 分析接口基类定义
- `plugin_manager.py` — 插件注册与发现
- `config.py` — 分析配置管理
- `utils.py` — 分析工具函数
- `engines/` — 发动机分析子系统（`*_analysis.py` + `*_report_generator.py`）
- `fuel/` — 燃油分析子系统
- `power/` — 动力分析子系统
- `cas/` — CAS 分析子系统

### 5. GUI 层 (gui/)

**职责**: PySide6 交互式图形界面

- `app.py` — GUI 应用入口（`main(dry_run=False)`，安装 GUI 日志桥接）
- `main_window.py` — 主窗口：菜单栏、穿越控制面板（阈值/模式/应用/重置）、信息显示
- `services.py` — 32 行纯重导出文件，仅保留 `from ._data_context import DataContext, ...`，确保外部 `from .services import DataContext` 仍可用
- `_data_context/` — **DataContext Facade 子包**（原 582 行 God Object 已拆分）：
  - `data_context.py` — 240 行 Facade 协调者，持有数据与子服务，仅负责生命周期管理与请求分发
  - `loading.py` — Strategy 模式加载器（`TxtLoader` / `CsvLoader`，注册到 `LOADERS`），新增格式只需实现 `DataLoader` Protocol
  - `query.py` — 只读数据查询服务（`DataQueryService`，含 `get_raw_data()`），遵循迪米特法则
  - `export_service.py` — 数据导出
  - `plot_data_service.py` — 绘图数据提取
  - `statistics_service.py` — 统计计算
  - `field_resolver.py` — 字段解析器
  - `protocols.py` — 窄接口 Protocol
  - 7 个遗留可变属性（`data` / `time_sec` / `time_vec` / `lm` / `data_path` / `excel_path` / `source_type`）已标记 `@deprecated`，推荐改用 `ctx.query.*` 方法
- `panel_plot.py` — `PlotCanvasWidget`: 交互绘图画布外观容器，委托给 **5 个控制器**：
  - `_layout_ctrl.py` — `LayoutController`: 布局模式切换（1×1/4×1/2×2）、子图选择
  - `_plot_renderer.py` — `PlotRenderer`: 数据绘制、信号添加/移除、右键菜单
  - `_crossing_analyzer.py` — `CrossingAnalyzer`: 穿越线绘制、缩放应用/重置、Y轴自动适配、统计更新
  - `_pan_ctrl.py` — `PanController`: 左键拖拽水平平移画布（5 像素阈值区分点击/拖拽）
  - `_region_ctrl.py` — `RegionController`: 右键拖动框选时间区间（半透明覆盖层 + 时间标注）
- `_drop_ctrl.py` — `TreeDragHelper` + `CanvasDropFilter`: 参数树拖拽到子图的拖放控制器
- `_downsampler.py` — `min_max_downsample()`: 向量化 min-max 降采样（np.reshape + nanmin/nanmax，500K 点 <1ms）
- `_font_config.py` — `configure_display_font()`: Matplotlib CJK 字体配置（线程安全，从 `plotting.py` 提取）
- `widgets.py` — `ParameterTreeWidget`: 参数树面板；`CrossingCtrl`: 穿越控制组件
- `worker.py` — 后台线程：
  - `DataLoaderWorker`: 数据加载 QThread
  - `AnalysisWorker`: 系统分析后台线程（执行 `SystemAnalyzer.analyze()` + `generate_reports()`，防 GUI 冻结）
- `log_handler.py` — `install_gui_logger()`: logging → GUI 信息显示桥接

#### 穿越分析交互（参照 MATLAB plotCoreInteractive.m）

| 按钮 | 行为 |
|------|------|
| **应用** | 在当前视图时间窗口内（或框选区域内）检测穿越点（排除 NaN），未找到时回退到窗口边界，缩放 X 轴至穿越区间，自动调整 Y 轴适配可见数据（5% 边距） |
| **重置** | 恢复到数据加载时的初始时间范围，同步调整 Y 轴 |

### 6. 工具层 (utils/)

**职责**: 项目通用工具，零业务依赖（`paths.py` 不再依赖 data 层，`EXCEL_FILENAME` 已上移到 `config.py`）

- `time_utils.py` — `select_time_window()`: 时间窗口索引选择；`format_time_seconds()`: 数值秒→`HH:MM:SS.mmm` 格式化；`parse_time_to_seconds()` / `time_to_seconds_array()`: 时间解析
- `strings.py` — `make_valid_name()`: 生成合法变量名；`column_to_field_name()`: 列名→字段名转换
- `paths.py` — `resolve_path()`: 路径解析（相对路径自动搜寻已知目录）；`resolve_excel_path()`: 自动发现标签映射 Excel 文件
- `file_utils.py` — 文件编码自动检测（chardet）、`is_safe_path()` 安全校验
- `log_utils.py` — `setup_logging()`: 纯 Python 日志配置（零 Qt 依赖）

---

## 配置管理

项目使用 `src/ftpa/config.py` 进行集中配置管理，采用 **frozen dataclass + TOML 文件** 模式：

- `Config` 为不可变（`@dataclass(frozen=True)`）顶层配置，包含 `ZoomConfig` / `PlotConfig` / `DataConfig` / `GuiConfig` 四个子配置
- 默认值在代码中定义；项目级覆盖通过 `ftpa_config.toml`（项目根目录）或用户级 `~/.ftpa/ftpa_config.toml` 提供
- TOML 解析兼容 Python 3.11+ 内置 `tomllib`，Python 3.10 通过 `tomli` 回退
- 模块级单例 `CONFIG = load_config()` 在导入时加载一次

飞机参数常量位于 `src/ftpa/computing/aircraft.py`（`BASE_WEIGHT` / `BASE_REL_CG` / `BASE_OIL` / `X0` / `L`），如需更换机型只需修改此文件。

| 参数 | 默认值 | 说明 |
|------|-----|------|
| `BASE_WEIGHT` | 48487.0 | 任务总重量 (kg) |
| `BASE_REL_CG` | 25.28 | 任务重心 (%) |
| `BASE_OIL` | 6000.0 | 任务油量 (kg) |
| `X0` | 15.902 | 参考点绝对重心 (m) |
| `L` | 4.453 | 参考长度 (m) |
| `DataConfig.trim_head` | 50 | 文件头部裁剪行数 |
| `DataConfig.trim_tail` | 50 | 文件尾部裁剪行数 |
| `DataConfig.cache_max_size` | 5 | 文件缓存最大条目数 |
| `PlotConfig.downsample_threshold` | 3000 | 触发降采样的可见点数阈值 |

### 异常层次

`src/ftpa/errors.py` 定义结构化异常层次，所有自定义异常均为 `FtpaError` 子类：

```
FtpaError                       # FTPA 基础异常
└─ LoadError                    # 数据加载错误基类（携带 path 属性）
   ├─ FileNotFoundLoadError     # 文件不存在 / 路径无效
   ├─ FormatLoadError           # 文件格式错误 / 解析失败（携带 detail）
   ├─ ResourceLoadError         # 内存不足 / I/O 错误
   └─ LabelMapLoadError         # 映射表加载失败（不阻塞主流程，降级到无标签模式）
```

`loading.py` 中的 Loader 将内置异常转换为此层次中的对应类型（`raise X from e`），`worker.py` 按 `FtpaError` 子类映射为用户友好消息。

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
| tomli | Python 3.10 TOML 解析回退 |

所有核心依赖均添加了兼容性上限约束（见 `requirements.txt`），防止主版本升级引入破坏性变更。

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

# 入口点测试（无头环境可用）
pytest tests/test_entrypoint.py -v

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
- 异常处理使用 `errors.py` 中的自定义异常层次（`FtpaError` 子类），禁止裸 `except` 和静默吞错

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
| min-max 降采样（500K 点） | <1 ms |
| 引擎 | pandas C engine (`engine='c'`) |

### 已实现的优化

1. **数据加载**: 统一入口 `param_extract()` 消除双重读取，dtype 预声明跳过类型推断，FileCache LRU + mtime 失效
2. **计算**: NumPy 向量化运算
3. **内存**: 数据裁剪、按需加载
4. **GUI 渲染**: 后台线程加载防阻塞；向量化降采样（`_downsampler.py`）避免大数据集渲染卡顿；拖拽平移与 Y 轴自适应分离防抖
5. **系统分析**: `AnalysisWorker` 后台线程执行，防 GUI 冻结

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
- [ ] `python -m ftpa.main --dry-run` 正常运行（无头环境可用）
- [ ] `python -m ftpa.main` 正常启动 GUI
- [ ] 数据提取功能正常（TXT / CSV）
- [ ] 重量重心计算正常
- [ ] 统计计算正常
- [ ] 时间解析正常
- [ ] GUI 穿越分析（应用/重置）正常
- [ ] GUI 拖拽平移 / 区域框选 / 参数拖放正常

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
*最后更新：2026-08-10 | 版本：1.0.1（下一版本变更见 CHANGELOG）*
