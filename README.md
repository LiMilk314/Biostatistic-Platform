# Biostatistic Platform

[中文](README.md) | [English](README.en.md)

本机单用户临床试验统计原型。应用默认英文，右上角 **EN/中文** 可切换界面语言；上方链接切换 README 语言。

## 启动

Windows 用户可双击 [`start-platform.cmd`](start-platform.cmd)：它运行 `start.ps1`，等待服务就绪，再用默认浏览器打开 <http://127.0.0.1:8050>。请保持 PowerShell 服务窗口打开。也可以在项目目录手动运行 `.\start.ps1`。

新电脑先运行 `install.ps1` 安装依赖至 `.venv` 和 `.r-library`。若 R 不在 `C:\Program Files\R`，设置 `RSCRIPT_PATH` 为 `Rscript.exe` 的完整路径。Dash、R API、服务管理器分别使用本机端口 8050、8000、8051；日志位于 `runtime`。

## 架构介绍

Dash 前端由 `app.py`、`survival_ui.py`、`ae_ui.py`、`dose_ui.py` 组成；`assets/style.css` 和 `assets/i18n.js` 管理样式及翻译。页面通过 `backend/api.R` 的 plumber API 提交任务，独立 R 进程运行 `backend/worker.R`，上传数据与结果缓存在本机 `runtime`。`scripts/service_manager.py` 管理 Dash 与 R 服务。浏览器仅接收分页预览与结果。

`scripts/make_demo.py` 用固定随机种子生成精简 ADSL、ADAE、ADTTE 演示数据。这些数据完全合成，不是实际试验或 CDISC 认证数据。当前原型上传上限为 100 MB；R 统计仍需完整读取数据。

## 统计口径

- **基线：** 先进行人群等值筛选。连续变量报告非缺失/缺失人数、均值与样本标准差、中位数与 Q1/Q3、范围；四分位数采用 R `quantile` type 7。分类变量的百分比分母是各组该变量的非缺失人数，缺失数另列。不计算基线 p 值。
- **生存：** 使用 ADTTE 已派生的 OS/PFS；默认 `CNSR=0` 为事件、`1` 为删失。输出 KM 曲线、风险人数、中位生存时间、log-rank p 值。调整后 Cox 模型使用 Efron ties 和所选协变量的完整病例，报告 HR、双侧 Wald p 值及 95% CI。森林图显示模型系数，不是亚组治疗效应。
- **AE：** 每个事件按受试者去重。默认按 `AEREL=Y`、`TRTEMFL=Y` 筛选，重度为 grade ≥3；术语显示阈值为任一组任何级别发生率 ≥10%。优先使用匹配的 ADSL 安全性人群作为分母；没有 ADSL 时，分母只含 ADAE 中出现的受试者。
- **剂量：** BOIN 根据目标 DLT 率及上下界计算升级/降级边界，并以 Beta(1,1) 后验应用安全排除。mTPI 根据当前剂量三个区间的 UPM 提出升阶、维持或降阶建议；拟合的毒性曲线仅展示趋势。

## 功能介绍

### 1 基线分析

上传 ADSL（CSV/XPT/SAS7BDAT）或加载演示数据。可选上传包含 `variable`、`label` 的 variables 文件，为预览表头显示标签。选择治疗组、人群、连续/分类变量，拖动组别块调整顺序，生成三线表并下载 Word/CSV。数值编码的分类变量应放入分类变量栏。

### 2 生存分析

上传 ADTTE，可选上传 ADSL 协变量，或加载配套演示数据。选择 OS/PFS、参考组与比较组、时间与删失编码、基线协变量。输出 KM 图、风险人数、调整后 Cox PH、森林图及 PH 检验，可导出 PDF/CSV/JSON。每名受试者每个终点应只有一条分析记录。

### 3 AE 分析

上传 ADAE，可选上传 ADSL 作为安全性人群分母，或加载演示数据。配置治疗组、术语、分级与筛选变量，生成任何级别/重度 AE 的三线表及汇总行，可下载 Word/CSV。正式分析前须按方案核对相关性、治疗期间标志和处置映射。

### 4 剂量决策

**BOIN：** 输入目标 DLT 概率、低毒/高毒界限和人数上限，生成 E（升级）、S（维持）、D（降级）、DE（排除）彩色决策表，可下载 PNG/Excel。

**mTPI：** 输入各剂量评估人数、DLT 数、当前剂量、目标概率和 epsilon，查看后验区间概率、UPM、毒性曲线及下一步建议。右侧提供方法与参数说明。CRM 和 3+3 尚未纳入当前原型。

输入错误会对应到相关控件。本版尚无多用户认证或生产级任务调度；本地数据与结果保留在 `runtime`。
