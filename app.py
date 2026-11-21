"""Dash UI. Statistical computation is exclusively performed by R."""
import json
import os
import mimetypes

# Restricted Windows hosts may deny MIME registry enumeration.
try:
    mimetypes.init()
except PermissionError:
    mimetypes._winreg = None
    mimetypes._mimetypes_read_windows_registry = None
    mimetypes.init()

import requests
from dash import ALL, Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update
from flask import Response, request, jsonify
from variable_labels import parse_dictionary, header_tooltips
import survival_ui
import dose_ui
import ae_ui
import variable_picker as vp

API = os.environ.get("R_API_URL", "http://127.0.0.1:8000")
FIELD_NAMES = {"dataset":"ADSL 数据文件","title":"表格标题","group":"治疗分组",
               "group-order":"组别顺序","filter":"人群标志","filter-value":"纳入值",
               "continuous":"连续变量","categorical":"分类变量","statistics":"连续统计量",
               "digits":"小数位数","category-orders":"类别顺序","system":"系统"}
INPUT_FIELDS = [x for x in FIELD_NAMES if x not in ("system","dataset")]


class PlatformError(Exception):
    def __init__(self, message, field="system"):
        super().__init__(message)
        self.field = field


def error_summary(errors):
    return html.Div([html.Strong("请检查以下位置："), html.Ul([
        html.Li(html.A(f"{FIELD_NAMES.get(k,k)}：{v}",href=f"#field-{k}"))
        for k,v in errors.items()])],className="error",role="alert")


app = Dash(__name__, title="Biostatistic Studio", suppress_callback_exceptions=True)
app.server.config["MAX_CONTENT_LENGTH"] = 145 * 1024 * 1024


def call(path, payload=None):
    try:
        r = requests.get(API + path, timeout=30) if payload is None else requests.post(API + path, json=payload, timeout=60)
        body = r.json()
    except requests.RequestException as exc:
        raise PlatformError("无法连接 R 服务或请求超时。请确认 start.ps1 正在运行，再重试。") from exc
    except ValueError as exc:
        raise PlatformError("后端返回格式异常，请重试并检查服务日志。") from exc
    if not r.ok or "error" in body and not body.get("status"):
        raise PlatformError(body.get("error", "服务请求失败，请重试。"),body.get("field","system"))
    return body


def field(label, component):
    key = component.id
    return html.Div([html.Label(label,htmlFor=key), component,
                     html.Div(id=f"error-{key}",className="field-error",role="alert")],
                    className="field",id=f"field-{key}")


app.layout = html.Div([
    dcc.Location(id="page-location",refresh=False),
    dcc.Store(id="language-store",data="en"),
    dcc.Store(id="dataset"), dcc.Store(id="job"), dcc.Store(id="variable-labels", data={}),
    dcc.Store(id="variable-picks", data={}),
    dcc.Store(id="group-order-values", data={"variable":None,"values":[]}),
    dcc.Store(id="input-errors", data={}), dcc.Store(id="worker-errors", data={}),
    dcc.Interval(id="poll", interval=1000, disabled=True),
    html.Aside([
        html.Div(["Biostatistic", html.Br(), "Platform"],className="brand"),
        html.A("1 Baseline",href="#baseline",id="nav-baseline",className="nav active"),
        html.A("2 Survival",href="#survival",id="nav-survival",className="nav"),
        html.A("3 Adverse Event",href="#ae",id="nav-ae",className="nav"),
        html.A("4 Dose Escalation",href="#dose",id="nav-dose",className="nav"),
        html.Div([
            html.A("BOIN",href="#dose-boin",id="nav-dose-boin",className="subnav"),
            html.A("mTPI",href="#dose-mtpi",id="nav-dose-mtpi",className="subnav"),
        ],id="dose-subnav",className="dose-subnav",style={"display":"none"}),
        html.Div("Dash × R", className="sidebar-foot"),
    ], className="sidebar"),
    html.Main([
        html.Header([html.Div([html.Div("ANALYSIS / BASELINE",id="page-eyebrow", className="eyebrow"),
                               html.H1("Baseline",id="page-title")]),
                     html.Div([html.Span("●  本地工作空间", className="badge"),
                         html.Button("EN/中文",id="language-toggle",n_clicks=0,className="secondary language-toggle",title="Switch language"),
                         html.Button("RESTART",id="restart-service",n_clicks=0,className="secondary restart-toggle",
                             title="重载已保存的代码。页面选择会重置，已保存的数据和结果保留。"),
                         html.Div(id="restart-message",role="status")],className="service-controls")]),
        html.Div([
            html.Section([
                html.H3("01  数据来源"),
                html.Div(id="field-dataset"),
                html.Button("加载演示 ADSL", id="demo", n_clicks=0, className="secondary"),
                dcc.Upload(id="upload", children=html.Div([html.B("ADSL 数据文件"),
                    html.Div("拖入文件，或点击上传"),
                    html.Small("CSV / XPT / SAS7BDAT")]), className="upload"),
                html.Div("尚未加载 ADSL。演示数据由固定种子生成，仅包含基线分析需要的示例变量。", id="data-info", className="muted"),
                html.Div(id="error-dataset",className="field-error",role="alert"),
                dcc.Upload(id="variables-upload", children=[html.B("ADSL variables（可选）"),
                    html.Small("CSV / JSON · variable、label")],
                    className="upload", max_size=5*1024*1024),
                html.Div("未加载 ADSL variables；预览表头不显示标签提示。", id="variables-info", className="muted"),
                html.Button("清除变量字典", id="clear-variables", n_clicks=0, className="secondary"),
                html.H3("02  分析配置"),
                field("表格标题", dcc.Input(id="title", value="Table 1. Baseline Characteristics", type="text")),
                vp.field("治疗分组", "group", "error-group", "field-group"),
                html.Div([html.Label("组别顺序"),
                    html.Div(id="group-order-chips",className="order-chip-container",**{"data-variable":""}),
                    html.Small("拖动方块调整组别顺序。选择治疗分组后自动载入该变量的取值。",className="order-chip-hint"),
                    html.Div(id="error-group-order",className="field-error",role="alert")],className="field",id="field-group-order"),
                vp.field("人群标志（留空使用全部受试者）", "filter", "error-filter", "field-filter"),
                field("纳入值", dcc.Input(id="filter-value", value="Y")),
                vp.field("连续变量", "continuous", "error-continuous", "field-continuous"),
                vp.field("分类变量（数值编码也可在此选择）", "categorical", "error-categorical", "field-categorical"),
                html.Details([html.Summary("统计与显示设置"),
                    field("连续统计量", dcc.Checklist(id="statistics", options=[
                        {"label": " 均值（SD）", "value": "mean"},
                        {"label": " 中位数（Q1，Q3）", "value": "median"},
                        {"label": " 最小值–最大值", "value": "range"}], value=["mean", "median", "range"])),
                    field("小数位数", dcc.Input(id="digits", type="number", min=0, max=5, step=1, value=1)),
                    dcc.Checklist(id="overall",options=[{"label":" 显示总体列","value":"yes"}],value=["yes"]),
                    field('类别顺序 JSON（可选，例如 {"SEX":["F","M"]}）',
                          dcc.Textarea(id="category-orders", value="{}"))],id="advanced-settings"),
                html.Button("生成基线特征→",id="generate",n_clicks=0,className="primary"),
                html.Div(id="submit-status",role="status"),
                html.Div(id="field-system"),
            ],className="card controls"),
            html.Div([
                html.Section([
                    html.Div([html.H3("分析结果"),
                              html.Div(id="status",children=vp.status("待生成"),role="status")],className="result-head"),
                    html.Div(id="result",children=vp.empty("基线分析")),
                    html.Div(id="downloads",className="downloads"),
                ],className="card results"),
                html.Section([
                    html.H3("数据预览"),
                    html.P("每页 10 行；预览不将完整数据集传到浏览器。",className="muted"),
                    dash_table.DataTable(id="preview",page_action="custom",page_current=0,page_size=10,
                        tooltip_header={}, tooltip_delay=200, tooltip_duration=None,
                        style_table={"overflowX":"auto"},style_cell={"fontFamily":"Arial","fontSize":12,
                        "padding":"10px","minWidth":"85px","maxWidth":"180px","overflow":"hidden","textOverflow":"ellipsis"},
                        style_header={"fontWeight":"bold","backgroundColor":"#f3f6f8","border":"none"}),
                ],className="card"),
            ],className="output-column"),
        ],className="workspace",id="baseline-page"),
        survival_ui.layout(),
        ae_ui.layout(),
        dose_ui.layout(),
    ]),
],className="shell")

app.layout.children.append(html.Div(id="language-apply",style={"display":"none"}))

survival_ui.register(app,call,PlatformError)
ae_ui.register(app,call,PlatformError)
dose_ui.register(app,call,PlatformError)

@app.callback(Output("language-store","data"),Output("language-toggle","children"),Output("restart-service","children"),
              Input("language-toggle","n_clicks"),State("language-store","data"),prevent_initial_call=True)
def toggle_language(n,current):
    language="zh" if current=="en" else "en"
    return language,"EN/中文","刷新" if language=="zh" else "RESTART"

app.clientside_callback(
    "function(language){if(window.setAppLanguage){window.setAppLanguage(language||'en');}return language||'en';}",
    Output("language-apply","children"),Input("language-store","data"))

@app.callback(Output("baseline-page","style"),Output("survival-page","style"),Output("ae-page","style"),Output("dose-page","style"),
              Output("dose-subnav","style"),Output("dose-boin-view","style"),Output("dose-mtpi-view","style"),
              Output("page-title","children"),Output("page-eyebrow","children"),Output("nav-baseline","className"),
              Output("nav-survival","className"),Output("nav-ae","className"),Output("nav-dose","className"),Output("nav-dose-boin","className"),
              Output("nav-dose-mtpi","className"),Output("nav-baseline","children"),Output("nav-survival","children"),
              Output("nav-ae","children"),Output("nav-dose","children"),Output("nav-dose-boin","children"),
              Output("nav-dose-mtpi","children"),Input("page-location","hash"),Input("language-store","data"))
def navigate(fragment,language):
    survival = fragment == "#survival" or (fragment or "").startswith("#sv-")
    ae = fragment == "#ae"
    dose = fragment == "#dose" or (fragment or "").startswith("#dose-")
    mtpi = fragment == "#dose-mtpi"
    active = "mtpi" if mtpi else "boin"
    return ({"display":"none"} if survival or ae or dose else {},{} if survival else {"display":"none"},{} if ae else {"display":"none"},{ } if dose else {"display":"none"},
            {} if dose else {"display":"none"},{"display":"none"} if not dose or mtpi else {},
            {"display":"none"} if not dose or not mtpi else {},
            (("生存分析" if survival else "AE分析" if ae else "剂量决策" if dose else "基线分析") if language=="zh" else
             ("Survival" if survival else "Adverse Event" if ae else "Dose Escalation" if dose else "Baseline")),
            "ANALYSIS / SURVIVAL" if survival else "ANALYSIS / ADVERSE EVENTS" if ae else "ANALYSIS / DOSE DECISION" if dose else "ANALYSIS / BASELINE",
            "nav" if survival or ae or dose else "nav active","nav active" if survival else "nav","nav active" if ae else "nav","nav active" if dose else "nav",
            "subnav active" if dose and active=="boin" else "subnav","subnav active" if dose and active=="mtpi" else "subnav",
            *( ["1 基线分析","2 生存分析","3 AE分析","4 剂量决策","BOIN","mTPI"] if language=="zh" else
               ["1 Baseline","2 Survival","3 Adverse Event","4 Dose Escalation","BOIN","mTPI"] ))


@app.callback(Output("dataset","data"),Output("data-info","children"),
              Input("demo","n_clicks"),Input("upload","contents"),State("upload","filename"),prevent_initial_call=True)
def load_data(n, contents, filename):
    try:
        if ctx.triggered_id == "demo":
            d = call("/demo", {})
            name = "合成演示 ADSL"
        else:
            if not contents:
                return no_update, no_update
            d = call("/upload", {"filename":filename,"content":contents.split(",",1)[1]})
            name = filename
        return d, f"{name} · {d['n']} 名受试者 · {len(d['columns'])} 个变量"
    except Exception as exc:
        app.server.logger.exception("Data upload failed")
        msg = str(exc) if isinstance(exc,PlatformError) else "文件处理失败，请检查文件格式后重新上传。"
        return no_update, html.Div(f"ADSL 数据文件：{msg}",className="field-error",role="alert")


@app.callback(Output("variable-labels","data"),Output("variables-info","children"),
              Input("variables-upload","contents"),Input("clear-variables","n_clicks"),
              Input("dataset","data"),State("variables-upload","filename"),prevent_initial_call=True)
def load_variables(contents, clear, dataset, filename):
    if ctx.triggered_id in ("dataset", "clear-variables"):
        return {}, "变量字典已清除；可上传与当前 ADSL 对应的 variables 文件。"
    try:
        if not dataset:
            return {}, "请先加载 ADSL 数据，再上传对应的 variables 文件。"
        labels = parse_dictionary(contents, filename)
        columns = dataset["columns"]
        matched = header_tooltips(columns, labels)
        unknown = len(set(labels) - set(columns))
        note = f"{filename} · {len(matched)} 个变量有标签 · {len(columns)-len(matched)} 个无标签"
        if unknown:
            note += f" · 忽略 {unknown} 个不在数据中的变量"
        return labels, note
    except Exception as exc:
        return {}, f"字典加载失败：{exc}（已清除旧标签）"


@app.callback(Output("preview","tooltip_header"),Input("dataset","data"),Input("variable-labels","data"))
def update_header_labels(dataset, labels):
    return header_tooltips(dataset["columns"], labels or {}) if dataset else {}


@app.callback(Output("variable-picks","data"),Input("dataset","data"))
def configure(d):
    if not d:
        return {}
    cols = d["columns"]
    group = next((x for x in ["TRT01P","ARM","TRT01A"] if x in cols),cols[0])
    cont = [x for x in ["AGE","BMIBL","WEIGHTBL"] if x in d["numeric"]]
    cat = [x for x in ["SEX","RACE","ECOG"] if x in cols]
    return {"group":group,"filter":None,"continuous":cont,"categorical":cat}


@app.callback(Output("group-order-values","data"),Output("group-order-chips","children"),Output("group-order-chips","data-variable"),
              Input("dataset","data"),Input("variable-picks","data"),State("group-order-values","data"))
def render_group_order(dataset,picks,order):
    picks=picks or {};order=order or {};group=picks.get("group")
    available=[str(value) for value in ((dataset or {}).get("values",{}).get(group,[]) if group and dataset else [])]
    saved=[str(value) for value in order.get("values",[])]
    if order.get("variable")!=group or len(saved)!=len(available) or set(saved)!=set(available):
        saved=available
    children=[html.Div((chr(0x2460+index) if index<20 else f"{index+1}.")+value,
                        className="order-chip",draggable="true",**{"data-order-value":value})
              for index,value in enumerate(saved)]
    if not children:
        children=[html.Span("先选择治疗分组变量",className="muted")]
    return {"variable":group,"values":saved},children,group or ""


@app.callback(Output("group-options","children"),Output("filter-options","children"),
              Output("continuous-options","children"),Output("categorical-options","children"),
              Input("dataset","data"),Input("variable-picks","data"))
def render_baseline_picks(dataset,picks):
    columns=dataset["columns"] if dataset else []
    picks=picks or {}
    return (vp.options("group",columns,picks.get("group")),
            vp.options("filter",columns,picks.get("filter")),
            vp.options("continuous",columns,picks.get("continuous",[]),multi=True),
            vp.options("categorical",columns,picks.get("categorical",[]),multi=True))


@app.callback(Output("variable-picks","data",allow_duplicate=True),
              Input({"type":"variable-choice","picker":ALL,"value":ALL},"n_clicks"),
              State("variable-picks","data"),prevent_initial_call=True)
def select_baseline_variable(clicks,picks):
    if not ctx.triggered or ctx.triggered[0].get("value") in (None,0):
        return no_update
    triggered=ctx.triggered_id
    if not isinstance(triggered,dict) or triggered.get("picker") not in {"group","filter","continuous","categorical"}:
        return no_update
    multi=triggered["picker"] in {"continuous","categorical"}
    return vp.toggle(picks,triggered["picker"],triggered["value"],multi)


@app.callback(Output("preview","data"),Output("preview","columns"),Output("preview","page_count"),
              Input("dataset","data"),Input("preview","page_current"))
def preview(d,page):
    if not d:
        return [],[],0
    try:
        data = call(f"/data/{d['id']}?page={page or 0}")
        return data["rows"],[{"name":c,"id":c} for c in d["columns"]],(data["total"]+9)//10
    except Exception:
        return [],[],0


@app.callback(Output("job","data"),Output("submit-status","children"),Output("input-errors","data"),
              Input("generate","n_clicks"),State("dataset","data"),State("variable-picks","data"),
              State("filter-value","value"),State("statistics","value"),State("digits","value"),
              State("overall","value"),State("title","value"),State("group-order-values","data"),
              State("category-orders","value"),prevent_initial_call=True)
def submit(n,d,picks,filter_value,statistics,digits,overall,title,order,categories):
    picks=picks or {}
    group=picks.get("group");continuous=picks.get("continuous") or [];categorical=picks.get("categorical") or []
    filter_var=picks.get("filter")
    errors = {}
    if not d: errors["dataset"] = "请先上传 ADSL 数据或加载演示 ADSL。"
    if not group: errors["group"] = "请选择治疗分组变量，例如 TRT01P。"
    if not continuous and not categorical: errors["continuous"] = "连续变量和分类变量至少选择一项。"
    if filter_var and not (filter_value or "").strip(): errors["filter-value"] = f"已选择 {filter_var}，请填写纳入值，例如 Y。"
    if continuous and not statistics: errors["statistics"] = "已选择连续变量，请至少勾选一种统计量。"
    if not isinstance(digits,(int,float)) or digits not in range(6): errors["digits"] = "请输入 0–5 之间的整数。"
    try:
        category_orders = json.loads(categories or "{}")
        if not isinstance(category_orders,dict) or any(not isinstance(v,list) for v in category_orders.values()):
            errors["category-orders"] = '请使用“变量名: 类别数组”的 JSON 对象，例如 {"SEX":["F","M"]}。'
    except (ValueError,TypeError):
        errors["category-orders"] = 'JSON 格式无效，请使用英文双引号，例如 {"SEX":["F","M"]}；不设置时填 {}。'
    if errors:
        return None,error_summary(errors),errors
    try:
        cfg = dict(dataset=d["id"],group=group,continuous=continuous,categorical=categorical,
                   filter=filter_var or "",filter_value=filter_value,statistics=statistics or [],
                   digits=digits,overall="yes" in overall,title=title,
                   group_order=(order or {}).get("values",[]) if isinstance(order,dict) else [],
                   category_orders=category_orders)
        return call("/baseline",cfg),"任务已提交；下方结果对应最近提交的配置。",{}
    except Exception as exc:
        app.server.logger.exception("Baseline submission failed")
        errors = {exc.field:str(exc)} if isinstance(exc,PlatformError) else {"system":"提交任务时发生系统异常，请重试并检查日志。"}
        return None,error_summary(errors),errors


@app.callback(
    [Output(f"error-{key}","children") for key in ["dataset"]+INPUT_FIELDS]+[Output("advanced-settings","open")],
    Input("input-errors","data"),Input("worker-errors","data"),
    [Input(key,"value") for key in ["title","filter-value","statistics","digits","overall","category-orders"]],
    Input("group-order-values","data"),
    Input("variable-picks","data"),Input("dataset","data"),prevent_initial_call=True)
def show_input_errors(submit_errors, worker_errors, *values):
    # Input edits clear old inline messages; the summary remains the last submission's report.
    errors = {**(submit_errors or {}),**(worker_errors or {})} if ctx.triggered_id in ("input-errors","worker-errors") else {}
    advanced = any(key in errors for key in ("statistics","digits","category-orders"))
    return [errors.get(key,"") for key in ["dataset"]+INPUT_FIELDS]+[True if advanced else no_update]


@app.callback(Output("result","children"),Output("status","children"),Output("downloads","children"),
              Output("poll","disabled"),Output("worker-errors","data"),Input("job","data"),Input("poll","n_intervals"),prevent_initial_call=True)
def poll(job,n):
    if not job:
        return vp.empty("基线分析"),vp.status("输入未就绪","error"),[],True,{}
    try:
        data = call(f"/jobs/{job['id']}")
        if data["status"]=="failed":
            errors = {data.get("field","system"):data.get("error","计算失败，请重试。")}
            return html.Div([error_summary(errors),html.Small(f"任务编号：{job['id']}")]),vp.status("分析失败","error"),[],True,errors
        if data["status"]!="complete":
            return html.Div("R 正在处理分析任务…",className="empty analysis-empty"),vp.status("排队中" if data["status"]=="queued" else "计算中","running"),[],False,{}
        r = data["result"]
        table = html.Table([
            html.Thead(html.Tr([html.Th("Characteristic")]+[html.Th(x) for x in r["headers"]])),
            html.Tbody([html.Tr([html.Td(row["label"])]+[html.Td(v) for v in row["values"]],
                className="section-row" if row["section"] else "") for row in r["rows"]])
        ],className="three-line")
        return html.Div([html.H3(r["title"]),html.Div(table,className="table-scroll"),
                         html.P(r["footnote"],className="footnote")]),vp.status("已完成","success"),[
            html.A("下载 Word",href=f"/export/{job['id']}/docx",className="download"),
            html.A("下载 CSV",href=f"/export/{job['id']}/csv",className="download secondary")],True,{}
    except Exception as exc:
        app.server.logger.exception("Job polling failed")
        msg = str(exc) if isinstance(exc,PlatformError) else "获取结果时发生系统异常，请重试并检查服务日志。"
        return html.Div(msg,className="error"),vp.status("系统异常","error"),[],True,{"system":msg}


@app.server.route("/export/<job_id>/<fmt>")
def export(job_id,fmt):
    if fmt not in ("csv","docx"):
        return "Unsupported format",400
    r = requests.get(f"{API}/download/{job_id}/{fmt}",timeout=30)
    return Response(r.content,status=r.status_code,headers={
        "Content-Type":r.headers.get("Content-Type","application/octet-stream"),
        "Content-Disposition":f'attachment; filename="baseline.{fmt}"'})


@app.server.route("/local/ready")
def local_ready():
    try:
        healthy = requests.get(API+"/health",timeout=2).ok
    except requests.RequestException:
        healthy = False
    return jsonify(generation=os.environ.get("SERVICE_GENERATION","unmanaged"),ready=healthy)


@app.server.route("/survival-export/<job_id>/<fmt>")
def survival_export(job_id,fmt):
    if fmt not in ("pdf","csv","json"): return "Unsupported format",400
    r=requests.get(f"{API}/survival-download/{job_id}/{fmt}",timeout=30)
    return Response(r.content,status=r.status_code,headers={"Content-Type":r.headers.get("Content-Type","application/octet-stream"),
        "Content-Disposition":f'attachment; filename="survival.{fmt}"'})


@app.server.route("/ae-export/<job_id>/<fmt>")
def ae_export(job_id,fmt):
    if fmt not in ("csv","docx"): return "Unsupported format",400
    r=requests.get(f"{API}/download/{job_id}/{fmt}",timeout=30)
    return Response(r.content,status=r.status_code,headers={"Content-Type":r.headers.get("Content-Type","application/octet-stream"),
        "Content-Disposition":f'attachment; filename="adverse-events.{fmt}"'})


@app.server.route("/local/restart",methods=["POST"])
def local_restart():
    if request.headers.get("X-Baseline-Restart")!="1" or (
            request.headers.get("Origin") and request.headers["Origin"]!=request.host_url.rstrip("/")):
        return jsonify(error="无效的重启请求，请从本地页面按钮操作。"),403
    token = os.environ.get("SERVICE_MANAGER_TOKEN")
    if not token:
        return jsonify(error="当前服务未由新版启动器管理，请重新运行 start.ps1。"),503
    try:
        r = requests.post("http://127.0.0.1:8051/restart",
                          headers={"X-Service-Token":token},timeout=25)
        return jsonify(r.json()),r.status_code
    except requests.RequestException:
        return jsonify(error="重启管理器不可用，请运行 start.ps1。"),503


app.clientside_callback(
    """async function(n) {
        if (!n) return window.dash_clientside.no_update;
        const button = document.getElementById('restart-service');
        document.getElementById('restart-message').textContent = '正在检查并重启；页面选择将重置…';
        button.disabled = true;
        try {
            const res = await fetch('/local/restart', {method:'POST',headers:{'X-Baseline-Restart':'1'}});
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || '无法重启');
            for (let i=0;i<90;i++) {
                await new Promise(resolve => setTimeout(resolve,1000));
                try {
                    const r = await fetch('/local/ready?t='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(1500)});
                    const state = await r.json();
                    if (state.ready && state.generation === data.generation) {
                        window.location.reload();
                        return '服务已恢复，正在刷新…';
                    }
                } catch (_) {}
            }
            throw new Error('启动尚未完成。请运行 start.ps1 查看原因；日志位于 runtime 文件夹。');
        } catch (e) {
            button.disabled = false;
            return e.message;
        }
    }""",
    Output("restart-message","children"),Input("restart-service","n_clicks"),prevent_initial_call=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1",port=8050,debug=False)
