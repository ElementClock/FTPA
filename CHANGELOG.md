# 变更日志 (Changelog)

本项目所有显著变更均会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
并遵循 [语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。

## [Unreleased]

### Fixed

- **CSV 时间解析丢失时分秒**：`csv_loader._convert_flight_time()` 现在保留合并后的 `_datetime` 作为“飞行时间”列，`TIME` 不再因只保留日期列而全为 0；原始“日期”列和 UTC+8 偏移逻辑保留。
- **小 CSV 文件加载崩溃**：`loader._trim_data()` 不再对 pandas 扩展数组调用无参构造，长度不足时返回同类型空切片，避免 `ArrowStringArray` 等类型抛 `TypeError`。
- **圆拟合经纬度参数颠倒**：`DataContext.compute_fitted_circle()` 与 `panel_track._compute_circle()` 统一为先经度后纬度，避免半径计算偏差。
- **全时段窗口失效**：`select_time_window()` 支持 `None` / 空字符串表示全时段；统计、穿越、起降、拟合等面板不再因默认全时段传入空字符串而只取最后一点。
- **数据摘要通道数多算**：`generate_data_summary()` 不再把 `filename` 等元数据键计入 `total_channels`；批量处理中的通道数同步修正。
- **导出面板摘要表格为空**：`panel_export._run_summary()` 按 `channels` 字典填充表格。
- **统计结果表格无法分列**：`StatsTableWidget.populate()` 兼容 `statistics_params()` 现有字符串格式，正确拆分各统计列。
- **路径常量层级错误**：`main_window.PROJECT_ROOT` 与 `DataContext.DATA_DIRS` 改为指向真实项目根目录。
- **发动机列重复统计**：`EngineAnalysis._find_columns()` 结果去重，避免同一列被多个 pattern 重复加入。
- **批量线程反模式**：`_BatchWorker` 改为普通 `QObject` + `moveToThread`，不再继承 `QThread` 后再次移动线程。
- **绘图 X 轴自适应**：加载数据后绘图区时间轴初始化为数据实际范围；多个子图同步时优先以“有数据的子图”为基准，避免空子图把 X 轴重置为 0~1。

### Added

- **JSON 数据导出**：`export_data()` 支持 `output_format='json'`，并支持 `gzip` 压缩；导出面板在 JSON 格式下自动将 `snappy` 重置为“无”。
- **插件进度回调透传**：`PluginManager.execute_analysis()` 将 `progress_callback` 传给各插件 `analyze()`。
- **回归测试**：新增 `tests/test_review_fixes.py`，覆盖小 CSV 加载、全时段窗口、圆拟合参数顺序、摘要通道数、发动机列去重、插件进度回调透传。
- **桌面启动脚本**：新增 `FTPA_GUI.bat`，Windows 下双击即可直接启动 GUI，自动使用项目虚拟环境 Python 并设置 `PYTHONPATH`。
- **静态参数映射**：新增 `src/ftpa/data/parameter_map.py` 与 `scripts/generate_parameter_map.py`，由 `data/参数名.xlsx` 生成字段名→中文名、单位、重复标签对照表。
- **单位支持**：`LabelMap` 新增 `get_unit()` / `list_all_with_units()`；GUI 参数树显示“中文标签 (单位)”。
- **重复标签对照**：新增 `get_var_names()` / `get_duplicate_labels()`，重复中文标签自动加编号后缀并保留原始标签对照表。
- **完整参数库展示**：右侧参数树显示静态参数库（538 项）+ 当前数据额外字段；当前数据中不存在的参数置灰不可选/拖拽。
- **右下角曲线预览区**：新增 `PreviewPanel`，点选右侧参数时在右下角预览区刷新显示对应数据曲线；可通过「视图 → 曲线预览」显示/隐藏，隐藏时点选参数不再刷新预览。
- **区间分析功能**：新增 `interval_analysis.py` 操作注册表，支持积分、最大值、最小值、平均值、极值；GUI 左下角新增“区间分析”模块，基于当前视图或框选区间分析目标信号并输出到信息框。

### Changed

- **README 项目结构同步**：移除当前仓库不存在的 `references/`、`testdata/`、`logs/`、`examples/`、`docs/`、`CLAUDE.md` 等目录说明，补充 `AGENTS.md` 与实际测试文件。
- **`LabelMap` 数据源**：改为“静态映射 + Excel 可选覆盖”，Excel 缺失时自动回退到静态映射；重复标签发出警告并沿用原行为。
- **`column_config.py`**：`apply_replacement_rules()` 优先使用 Excel 静态映射的精确原始名匹配，再回退到 ATA 子串替换。
- **参数树/参数选择**：`FieldResolver` / `DataContext` 新增完整参数库查询；`ParameterTreeWidget` 支持不可用参数置灰。
- **右侧布局**：参数树下方新增曲线预览区，右侧改为垂直分割布局，点选参数即时预览。
- **预览区精简**：预览曲线不再显示参数名、时间、刻度等已知信息，最大化曲线显示区域。
- **控制面板布局**：阈值控制区右侧新增“区间分析”模块，信息显示框右移，支持可扩展分析操作。

## [1.0.1] - 2026-08-01

本次发布为架构审计修复版本：归档遗留 CLI、将 GUI 确立为唯一入口，并将数据层重构为以 `DataContext` Facade 为核心、由可插拔子服务协作的结构。同时消除多处跨层 / 循环依赖，并修复若干安全与质量问题。

### Added

- **自定义异常层次** `errors.py`：`FtpaError` → `LoadError` → 4 个子类（`FileNotFoundLoadError` / `FormatLoadError` / `ResourceLoadError` / `LabelMapLoadError`）；`loading.py` 中的 Loader 将内置异常转换为此层次（`raise X from e`），`worker.py` 按子类映射为用户友好消息。
- **`data/summary.py`、`data/enrichment.py`**：分别承接 `generate_data_summary` / `print_data_summary` 与 `add_weight_cg_to_data`，消除 `data ↔ statistics` 循环依赖和 `computing → data` 跨层依赖。
- **`gui/_data_context/` Facade 子包**：7 个子服务（`loading` / `query` / `export_service` / `plot_data_service` / `statistics_service` / `field_resolver` / `protocols`）；加载采用 Strategy 模式（`TxtLoader` / `CsvLoader` 注册到 `LOADERS`）。
- **`gui/_downsampler.py`**：向量化 min-max 降采样算法（`np.reshape` + `nanmin` / `nanmax`，500K 点 <1ms）。
- **`gui/_pan_ctrl.py`、`gui/_region_ctrl.py`、`gui/_drop_ctrl.py`**：分别承担左键拖拽平移、右键框选时间区间、参数树拖放到子图三项交互。
- **`gui/worker.py` `AnalysisWorker`**：系统分析后台线程（执行 `SystemAnalyzer.analyze()` + `generate_reports()`），防止大数据集分析时冻结 GUI 主线程。
- **`DataContext.query.get_raw_data()`**：只读数据访问入口（含 `get_signal_data()` / `get_time_sec()` / `get_time_vec()` 等），遵循迪米特法则。
- **7 个遗留属性的 `DeprecationWarning`**：`data` / `time_sec` / `time_vec` / `lm` / `data_path` / `excel_path` / `source_type`，引导迁移到 `ctx.query.*` 方法。
- **依赖兼容性上限约束（P1-CONF-1）**：`pyproject.toml` 与 `requirements.txt` 同步使用 `>=X,<Y` 形式，防止主版本升级引入破坏性变更。
- **`chardet`、`tomli` 依赖**：`chardet` 用于文件编码自动检测（可选带回退）；`tomli` 作为 Python 3.10 的 TOML 解析回退。
- **`computing/aircraft.py`**：AG1007 架次飞机参数常量，更换机型只需修改此文件。
- **`gui/_font_config.py`**：Matplotlib CJK 字体配置（线程安全），从已归档的 `plotting.py` 提取。
- **`utils/log_utils.py`**：纯 Python 日志配置（零 Qt 依赖）。
- **`ftpa_config.toml`**：项目级 TOML 配置文件（支持用户级 `~/.ftpa/ftpa_config.toml` 覆盖）。

### Changed

- **DataContext 重构**：从 582 行 God Object 重构为 240 行 Facade（`gui/_data_context/data_context.py`）+ 子服务；原 `gui/services.py` 缩减为 32 行纯重导出文件，保持向后兼容。
- **CLI 模块归档**：`pipeline.py`、`plotting.py`、`batch_processor.py`、旧 CLI 版 `main.py` 迁移至 `references/cli/`；`main.py` 改为纯 GUI 入口（默认启动 GUI，支持 `--dry-run` 无界面验证）。
- **`constants.py` 合并到 `config.py`**：采用 frozen dataclass（`Config` / `ZoomConfig` / `PlotConfig` / `DataConfig` / `GuiConfig`）+ TOML 文件配置；飞机参数常量拆分到 `computing/aircraft.py`。
- **模块位置迁移**：`label_map.py` / `exporter.py` / `column_config.py` → `data/`；`time_utils.py` / `log_utils.py` → `utils/`。
- **`statistics/multi.py` 消除代码重复**：`statistics_params` 与 `crossing_analysis` 的 with/without-labelmap 分支合并为统一实现（`_statistics_params_impl` / `_crossing_analysis_impl`）。
- **`utils/paths.py` 跨层依赖修复**：`EXCEL_FILENAME` 上移到 `config.py`，`utils` 不再反向依赖 `data` 子包。
- **文档同步更新**：`README.md`、`CLAUDE.md` 重写以反映 Facade 架构与 GUI 唯一入口。

### Fixed

- **Zip Slip 路径遍历漏洞**：`data/io.py` 的 ZIP 解压添加路径遍历校验（拒绝 `..` 组件、绝对路径、逃逸解压目录的成员）。
- **`data ↔ statistics` 循环依赖**：`generate_data_summary` / `print_data_summary` 下沉到 `data/summary.py`。
- **`utils/paths.py` 跨层依赖**：`EXCEL_FILENAME` 移至 `config.py`，消除 `utils → data` 反向依赖。
- **GUI 模块静默异常**：5 处裸 `except` 添加 `logger.debug` 记录（含异常堆栈），便于问题定位。
- **`base_oli` 拼写错误**：修正为 `BASE_OIL`。
- **`.gitignore` `*.txt` 规则过宽**：添加 `!requirements.txt` 例外，保护依赖清单不被误忽略。

### Removed

- **4 个未使用的 `*_data_processor.py` 死代码文件**：从 `analysis/` 各子系统中删除。
- **CLI 模式**：`verify` / `chunked` / `analysis` / `stats` / `interactive` 及对应的 `--mode` / `--gui` / `--nrows` / `--chunksize` / `--max-chunks` 等参数（随 CLI 模块归档至 `references/cli/`）。
- **根目录松散模块**：`label_map.py` / `exporter.py` / `column_config.py` / `time_utils.py`（已迁入子包）。
- **`constants.py`**：拆分合并到 `config.py` 与 `computing/aircraft.py`。
