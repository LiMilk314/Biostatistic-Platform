# Baseline Studio

本地单用户临床统计原型：Dash 界面 → R plumber → 独立 Rscript 进程 → 本地结果缓存。

## 启动

在项目目录运行：

```powershell
.\start.ps1
```

打开 http://127.0.0.1:8050 。R API 使用 8000 端口。两者仅监听本机。
本地服务管理器使用 8051 端口，负责启动和停止本项目的子进程。
网页右上角“重启服务并刷新”会先检查已保存的 Python/R 语法，
等待新一代 Dash 和 R 服务就绪后刷新页面。页面选择会重置；runtime 中的数据与结果保留。
有统计任务运行或排队时不会重启。语法检查失败时旧服务继续运行，并显示文件名和行号。
再次运行 start.ps1 会向已有管理器发送重启请求，不会启动重复服务。
启动失败时 PowerShell 窗口会保留错误信息；日志在 runtime/manager.err.log、
runtime/api.err.log、runtime/dash.err.log。若启动器本身被修改，需要停止管理器后重新启动。
若 R 不在 `C:\Program Files\R`，先设置 `$env:RSCRIPT_PATH`。
当前机器依赖已经安装在 `.venv` 和 `.r-library`，没有修改全局 R 包。

## 使用

1. 点击“加载演示 ADSL”，或上传 CSV/XPT/SAS7BDAT。
   可在第二个拖入框上传该数据集的 variables CSV/JSON（包含 `variable`、`label`）。
   数据预览表头仅在对应 label 非空时显示悬停提示。更换数据会清除旧字典，需重新上传。
   字典按变量名精确匹配；未知变量忽略，重复变量名拒绝。标签仅用于预览，不改变统计计算。
2. 指定治疗组、分析人群和基线变量。数值编码的分类变量应放入分类变量列表。
3. 组别顺序会根据治疗分组变量的实际取值自动载入，可拖动色块调整；也可指定小数精度、连续统计量、总体列和类别顺序。
4. 点击“生成三线表”，等待后台任务完成后下载 Word/CSV。

输入问题会在对应控件下方及提交摘要中显示中文原因和修正建议。
摘要中的字段名可点击定位；高级设置有错误时自动展开。
后端在分析前再次校验变量、数据内容与配置；无法归因于输入的异常显示为系统错误，
保留服务日志和失败任务编号供排查，不将 R 索引错误直接显示给用户。

三个分析板块的演示数据由 `scripts/make_demo.py` 使用固定随机种子生成：共用 240 人、两组的精简 ADSL，配套生成精简 ADAE 和 OS/PFS ADTTE。数据完全合成，并非真实试验数据，也不是经过 CDISC 合规认证的数据集。修改生成逻辑后运行 `python scripts/make_demo.py` 更新 CSV。
CSV 使用 UTF-8；USUBJID 必须存在，STUDYID + USUBJID（无 STUDYID 时仅 USUBJID）必须唯一。
SAS 数值标签目前保留原始编码用于分析，不自动替换成标签文本。

## 统计口径

- 连续变量：非缺失 n、缺失 n、均值（样本标准差）、中位数（Q1，Q3）、范围。
- 四分位数采用 R quantile type 7；n < 2 的标准差显示 NE。
- 分类变量：n（%），分母为每列该变量的非缺失人数；缺失数单列。
- 所有受试者用于组列 N；人群筛选在统计之前应用。
- 全缺失连续变量显示 NE，分类变量显示缺失数；不计算基线 p 值。
- 人群筛选仅支持一个变量的等值条件。
- 不自动去重，不静默删除分组缺失者。

## 目录

- `app.py` / `assets/style.css`：界面和 R API 客户端。
- `backend/api.R`：上传、元数据、分页、任务和下载接口。
- `backend/baseline.R`：无 I/O 的统计核心。
- `backend/worker.R`：独立计算、JSON/CSV/Word 输出。
- `runtime/data`：数据快照；`runtime/jobs`：请求、日志、结果。
- `tests/test_baseline.R`：小型已知数值的统计校验。
- `tests/smoke.py`：真实 API、子进程、上传、缓存、下载集成测试。
- `r-packages.csv`：本次安装 R 包版本清单；`requirements.txt`：Python 直接依赖。

## 验证

```powershell
$env:LC_ALL='English_United States.utf8'
& 'C:\Program Files\R\R-4.5.2\bin\Rscript.exe' tests/test_baseline.R
# 启动 API 后：
.\.venv\Scripts\python.exe tests/smoke.py
```

已验证浏览器加载演示数据并生成表格，统计边界、后台任务、缓存和导出接口通过测试。
Word XML 内容与重复表头已检查；当前运行环境缺少配套 LibreOffice，Word 的实际分页视觉检查尚未完成。

## 生存分析原型

入口：左侧「02 生存分析」，或 http://127.0.0.1:8050/#survival 。

1. 点击「加载演示 ADTTE + ADSL」，或拖入 ADTTE（CSV/XPT/SAS7BDAT）。演示数据由本项目固定种子生成，包含 240 名受试者、两组及 OS/PFS 两个终点；不依赖 random.cdisc.data。
2. 可选上传 ADSL 补充协变量，按 STUDYID + USUBJID（没有 STUDYID 时按 USUBJID）连接；ADSL 每名受试者必须唯一。补充变量显示为 `ADSL:变量名`。
3. 确认 OS/PFS、参考组/比较组、时间和删失编码。默认 PARAMCD、AVAL、CNSR，0=事件、1=删失，天转换为月。这里只分析已派生的终点，不从原始记录派生 OS/PFS。
4. 选择连续和分类协变量（例如 AGE、SEX）拟合 Adjusted Cox PH。页面要求至少选择一个分析计划规定的基线协变量。可用人群/分析记录标志进行等值筛选；每人每个终点必须一行。
5. 生成 KM 曲线（log-log 95% CI、删失标记）、风险人数、中位生存时间、log-rank p；Cox 输出 HR、Wald 95% CI、双侧 Wald p、系数森林图及 Schoenfeld 残差 PH 检验。

Cox 使用 Efron ties。调整模型仅使用所选协变量完整的病例，分别报告 N、事件数和排除人数；分类协变量参考水平显示在结果中。森林图展示模型系数，尚未实现亚组治疗效应森林图。当前支持两个治疗组，不含分层 Cox、交互项和时间依赖协变量。

PDF 导出包含 KM 和 Cox 表格，CSV 为 Cox 系数，JSON 包含完整配置与结果；页面图表工具栏可导出 SVG。日/月/年转换使用 30.4375 天/月和 365.25 天/年。输入问题在对应控件下显示；不可估计的模型显示原因而不输出虚假的 HR。

主要代码：`survival_ui.py`（页面）、`backend/survival_analysis.R`（校验、统计、导出）；沿用 plumber、独立 R worker 和本地缓存。

验证：`tests/test_survival.R` 核对手算 KM、原生 coxph、风险人数与异常数据；启动服务后运行 `.\.venv\Scripts\python.exe tests/survival_smoke.py` 验证接口、队列、缓存和下载。

## 剂量决策原型

左侧「04 剂量决策」展开 BOIN 与 mTPI 两个页面，默认进入 BOIN；每个页面右侧均显示数学原理和参数说明。BOIN 输入目标 DLT 率 φ、低毒界限 φ1、高毒界限 φ2（须满足 φ1 < φ < φ2）和每队列人数上限，按标准公式计算 λe/λd，再绘制 n 与 DLT 数组合的 E/S/D/DE 决策图。E 为升级、S 为维持、D 为降级；当至少 3 人且 Beta(1,1) 后验 Pr(p > φ) > 0.95 时，DE 排除当前及更高剂量。决策图可下载 PNG，彩色决策矩阵可下载 Excel。人数上限用于控制预计算表格范围。

mTPI 输入每剂量的入组数、DLT 数、当前剂量、目标 φ 和 epsilon。使用 Beta(1,1) 先验，输出当前剂量三个区间的后验概率和 UPM，并按最大 UPM 给出升阶、维持或降阶建议。若任一剂量后验 Pr(p > φ) > 0.95，则该剂量及更高剂量排除，最低剂量被排除时建议停止。各剂量毒性曲线是按入组人数加权的单调 PAVA 经验率拟合，用于展示趋势，不用于标准 mTPI 的 UPM 决策。

剂量决策使用新的纯 R 核心 `backend/dose_decision.R` 与 Dash 页面 `dose_ui.py`；临床样例表初始显示可编辑示例值。

## AE 统计原型

左侧「03 AE 统计」读取 ADAE，并可选上传 ADSL 作为安全性分析人群分母。默认变量映射为 TRT01A / AEDECOD / AETOXGR / AEREL / TRTEMFL / AESER / AEACN / AESDTH；可在页面中更改。默认按 AEREL=Y 和 TRTEMFL=Y 筛选，术语按任一组任何级别发生率 ≥10% 展示，严重级别默认为 ≥3。每个事件按受试者去重，表格对每组并列显示任何级别与重度事件的 n (%)，并包含总 AE、剂量处置、死亡和严重 AE 汇总行；可下载 Word 或 CSV。

推荐提供匹配的 ADSL，并在页面选择安全性人群标志（例如 SAFFL=Y），以将未发生 AE 的受试者也纳入百分比分母。未提供 ADSL 时，原型会退回使用 ADAE 中出现的受试者，可能不包含未发生 AE 的受试者。处置行根据 AEACN 文本中的剂量降低、中断、撤药等关键词识别；生成正式报告前应按研究方案核对映射和筛选值。演示 ADAE/ADSL 由本项目固定种子生成，仅含该汇总分析所需字段。

页面位于 `ae_ui.py`，统计及校验位于 `backend/ae_analysis.R`；`tests/test_ae.R` 覆盖分母、去重和分级计数。

方法定义参考：[BOIN 方法综述](https://pmc.ncbi.nlm.nih.gov/articles/PMC9260438/)、[mTPI 区间与 UPM 定义](https://academic.oup.com/biostatistics/article/21/4/807/5460289)。

## 平台运行边界

上传限制 100 MB，最多 8 个治疗组，每个分类变量最多 50 类。
浏览器只接收 10 行预览，但 R 目前仍完整读取 RDS，不是大型数据的流式分析方案。
结果缓存包含数据 ID、请求配置和统计代码内容；升级 R 或统计包后应使用新的 runtime 缓存目录。
任务每次只运行一个，由提交/状态查询推进；页面轮询负责持续推进队列。
本版没有多用户认证、生产任务调度、取消任务或崩溃恢复机制。
导出标题和样式变更目前也会触发新任务。
本地上传文件和分析结果会保留在 runtime，尚未提供界面清理功能。
