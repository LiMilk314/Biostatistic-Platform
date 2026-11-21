"""Adverse-event summary page and Dash callbacks."""
from dash import ALL, Input, Output, State, ctx, dash_table, dcc, html, no_update
from variable_labels import parse_dictionary, header_tooltips
import variable_picker as vp

LABELS = {
    "ae-data": "ADAE 数据文件", "ae-adsl": "ADSL 分母数据", "ae-group": "ADAE 治疗分组",
    "ae-term": "事件术语", "ae-grade": "毒性分级", "ae-serious": "严重事件标志",
    "ae-action": "事件处置", "ae-death": "死亡标志", "ae-relation": "治疗相关性",
    "ae-emergent": "治疗期间出现标志", "ae-threshold": "发生率阈值", "ae-grade-cutoff": "重度分级界值",
    "ae-relation-values": "治疗相关性纳入值", "ae-emergent-values": "治疗期间出现纳入值",
    "ae-serious-values": "严重事件纳入值", "ae-death-values": "死亡标志纳入值",
    "ae-adsl-group": "ADSL 治疗分组", "ae-adsl-filter": "ADSL 人群标志",
    "ae-adsl-filter-value": "ADSL 纳入值", "system": "系统"
}


def _field(label, component, key):
    return html.Div([html.Label(label, htmlFor=component.id), component,
                     html.Div(id=f"{key}-error", className="field-error", role="alert")],
                    className="field", id=f"{key}-field")


def layout():
    return html.Div([
        dcc.Store(id="ae-data"), dcc.Store(id="ae-adsl"), dcc.Store(id="ae-meta", data={}), dcc.Store(id="ae-labels", data={}),
        dcc.Store(id="ae-picks", data={}), dcc.Store(id="ae-job"), dcc.Store(id="ae-errors", data={}),
        dcc.Interval(id="ae-poll", interval=1000, disabled=True),
        html.Div([
            html.Section([
                html.H3("01  数据来源"),
                html.Button("加载演示 ADAE + ADSL", id="ae-demo", n_clicks=0, className="secondary"),
                dcc.Upload(id="ae-upload", children=html.Div([html.B("ADAE 数据文件"), html.Div("拖入文件，或点击上传"), html.Small("CSV / XPT / SAS7BDAT")]), className="upload"),
                html.Div("尚未加载 ADAE。", id="ae-data-info", className="muted"),
                html.Div(id="ae-data-error", className="field-error", role="alert"),
                dcc.Upload(id="ae-dict-upload", children=[html.B("ADAE variables（可选）"), html.Small("CSV / JSON · variable、label")], className="upload"),
                html.Div("未加载 ADAE variables；预览表头不显示标签提示。", id="ae-dict-info", className="muted"),
                dcc.Upload(id="ae-adsl-upload", children=html.Div([html.B("ADSL 安全性分析人群（推荐）"), html.Div("用于准确计算各组分母；拖入文件，或点击上传"), html.Small("CSV / XPT / SAS7BDAT · 最大 100 MB")]), className="upload"),
                html.Div("未提供 ADSL；暂以 ADAE 中出现的受试者作为分母。", id="ae-adsl-info", className="muted"),
                html.Div(id="ae-adsl-error", className="field-error", role="alert"),
                html.H3("02  分析配置"),
                _field("表格标题", dcc.Input(id="ae-title", value="Table 2. Adverse Events", type="text"), "ae-title"),
                vp.field("ADAE 治疗分组", "ae-group", "ae-group-error", "ae-group-field"),
                vp.field("不良事件术语（优先选择 AEDECOD）", "ae-term", "ae-term-error", "ae-term-field"),
                vp.field("毒性分级（优先选择 AETOXGR）", "ae-grade", "ae-grade-error", "ae-grade-field"),
                html.Details([
                    html.Summary("筛选与汇总设置"),
                    vp.field("治疗相关性变量（留空不筛选）", "ae-relation", "ae-relation-error", "ae-relation-field"),
                    _field("治疗相关性纳入值（逗号分隔；如 Y）", dcc.Input(id="ae-relation-values", value="Y", type="text"), "ae-relation-values"),
                    vp.field("治疗期间出现标志（留空不筛选）", "ae-emergent", "ae-emergent-error", "ae-emergent-field"),
                    _field("纳入值（逗号分隔；如 Y）", dcc.Input(id="ae-emergent-values", value="Y", type="text"), "ae-emergent-values"),
                    vp.field("严重不良事件标志（可选）", "ae-serious", "ae-serious-error", "ae-serious-field"),
                    _field("严重事件纳入值", dcc.Input(id="ae-serious-values", value="Y", type="text"), "ae-serious-values"),
                    vp.field("事件处置（用于剂量降低 / 中断 / 终止行，可选）", "ae-action", "ae-action-error", "ae-action-field"),
                    vp.field("死亡标志（可选）", "ae-death", "ae-death-error", "ae-death-field"),
                    _field("死亡标志纳入值", dcc.Input(id="ae-death-values", value="Y", type="text"), "ae-death-values"),
                    html.H4("安全性分析分母（上传 ADSL 后启用）"),
                    vp.field("ADSL 治疗分组", "ae-adsl-group", "ae-adsl-group-error", "ae-adsl-group-field"),
                    vp.field("ADSL 人群标志（可选）", "ae-adsl-filter", "ae-adsl-filter-error", "ae-adsl-filter-field"),
                    _field("ADSL 纳入值", dcc.Input(id="ae-adsl-filter-value", value="Y", type="text"), "ae-adsl-filter-value"),
                    _field("事件术语显示阈值（任一组任何级别发生率，%）", dcc.Input(id="ae-threshold", type="number", min=0, max=100, step=0.1, value=10), "ae-threshold"),
                    _field("重度事件分级界值", dcc.Input(id="ae-grade-cutoff", type="number", min=1, max=5, step=1, value=3), "ae-grade-cutoff"),
                ], id="ae-advanced"),
                html.Button("生成 AE 统计→", id="ae-run", n_clicks=0, className="primary"),
                html.Div(id="ae-submit-status", role="status"), html.Div(id="ae-system-error", className="field-error", role="alert"),
            ], className="card controls"),
            html.Div([
                html.Section([
                    html.Div([html.H3("分析结果"), html.Div(id="ae-status", children=vp.status("待生成"), role="status")], className="result-head"),
                    html.Div(id="ae-results", children=vp.empty("不良事件分析")),
                    html.Div(id="ae-downloads", className="downloads"),
                    html.Div("分母优先采用上传的 ADSL 安全性分析人群；未上传 ADSL 时，将使用 ADAE 中出现的受试者作为分母。", id="ae-denominator-note", className="analysis-notice"),
                ], className="card results"),
                html.Section([
                    html.H3("ADAE 数据预览"), html.P("每页 10 行；预览不将完整数据集传到浏览器。", className="muted"),
                    dash_table.DataTable(id="ae-preview", page_action="custom", page_current=0, page_size=10,
                        tooltip_header={}, tooltip_delay=200, tooltip_duration=None, style_table={"overflowX":"auto"},
                        style_cell={"fontFamily":"Arial", "fontSize":12, "padding":"10px", "minWidth":"85px", "maxWidth":"180px", "overflow":"hidden", "textOverflow":"ellipsis"},
                        style_header={"fontWeight":"bold", "backgroundColor":"#f3f6f8", "border":"none"}),
                ], className="card"),
            ], className="output-column"),
        ], className="workspace", id="ae-page", style={"display":"none"}),
    ])


def register(app, call, PlatformError):
    @app.callback(Output("ae-data", "data"), Output("ae-data-info", "children"), Output("ae-data-error", "children"),
        Input("ae-demo", "n_clicks"), Input("ae-upload", "contents"), State("ae-upload", "filename"), prevent_initial_call=True)
    def load_ae(n, contents, filename):
        try:
            if ctx.triggered_id == "ae-demo":
                d = call("/ae-demo", {}); return d["ae"], f"演示 ADAE · {d['ae']['n']} 条事件记录", ""
            if not contents: return no_update, no_update, no_update
            d = call("/upload", {"filename":filename, "content":contents.split(",",1)[1]})
            return d, f"{filename} · {d['n']} 条事件记录 · {len(d['columns'])} 个变量", ""
        except Exception as e:
            return no_update, no_update, str(e) if isinstance(e, PlatformError) else "ADAE 文件读取失败，请检查文件格式。"

    @app.callback(Output("ae-labels", "data"), Output("ae-dict-info", "children"),
        Input("ae-dict-upload", "contents"), Input("ae-data", "data"), State("ae-dict-upload", "filename"), prevent_initial_call=True)
    def load_ae_labels(contents, data, filename):
        if ctx.triggered_id == "ae-data": return {}, "可上传当前 ADAE 的 variables 文件。"
        try:
            labels = parse_dictionary(contents, filename)
            return labels, f"已加载 {filename} · {len(labels)} 个变量标签"
        except Exception as e:
            return {}, f"Variables：{e}"

    @app.callback(Output("ae-adsl", "data"), Output("ae-adsl-info", "children"), Output("ae-adsl-error", "children"),
        Input("ae-demo", "n_clicks"), Input("ae-adsl-upload", "contents"), State("ae-adsl-upload", "filename"), prevent_initial_call=True)
    def load_adsl(n, contents, filename):
        try:
            if ctx.triggered_id == "ae-demo":
                d = call("/ae-demo", {}); return d["adsl"], f"演示 ADSL · {d['adsl']['n']} 名受试者", ""
            if not contents: return no_update, no_update, no_update
            d = call("/upload", {"filename":filename, "content":contents.split(",",1)[1]})
            return d, f"{filename} · {d['n']} 名受试者", ""
        except Exception as e:
            return no_update, no_update, str(e) if isinstance(e, PlatformError) else "ADSL 文件读取失败，请检查文件格式。"

    @app.callback(Output("ae-meta", "data"), Input("ae-data", "data"), Input("ae-adsl", "data"))
    def meta(ae, adsl):
        if not ae: return {"columns":[], "values":{}, "adsl_columns":[], "adsl_values":{}}
        return {"columns":ae["columns"], "values":ae.get("values",{}),
                "adsl_columns":adsl["columns"] if adsl else [], "adsl_values":adsl.get("values",{}) if adsl else {}}

    @app.callback(Output("ae-picks", "data"), Input("ae-meta", "data"))
    def defaults(m):
        m=m or {}; c=m.get("columns",[]); ac=m.get("adsl_columns",[])
        if not c: return {}
        return {"ae-group":next((x for x in ("TRT01A","TRT01P","ARM") if x in c),None),
                "ae-term":next((x for x in ("AEDECOD","AETERM") if x in c),None),
                "ae-grade":next((x for x in ("AETOXGR","AESEV") if x in c),None),
                "ae-relation":"AEREL" if "AEREL" in c else None,
                "ae-emergent":"TRTEMFL" if "TRTEMFL" in c else None,
                "ae-serious":"AESER" if "AESER" in c else None,
                "ae-action":"AEACN" if "AEACN" in c else None,
                "ae-death":"AESDTH" if "AESDTH" in c else None,
                "ae-adsl-group":next((x for x in ("TRT01A","TRT01P","ARM") if x in ac),None),
                "ae-adsl-filter":"SAFFL" if "SAFFL" in ac else None}

    pickers=["ae-group","ae-term","ae-grade","ae-relation","ae-emergent","ae-serious","ae-action","ae-death","ae-adsl-group","ae-adsl-filter"]
    @app.callback([Output(f"{p}-options","children") for p in pickers], Input("ae-meta","data"), Input("ae-picks","data"))
    def render_picks(m,picks):
        m=m or {};picks=picks or {};out=[]
        for p in pickers:
            vals=m.get("adsl_columns",[]) if p.startswith("ae-adsl") else m.get("columns",[])
            out.append(vp.options(p,vals,picks.get(p)))
        return out

    @app.callback(Output("ae-picks","data",allow_duplicate=True), Input({"type":"variable-choice","picker":ALL,"value":ALL},"n_clicks"), State("ae-picks","data"), prevent_initial_call=True)
    def select(clicks,picks):
        if not ctx.triggered or ctx.triggered[0].get("value") in (None,0): return no_update
        t=ctx.triggered_id
        if not isinstance(t,dict) or t.get("picker") not in pickers:return no_update
        return vp.toggle(picks,t["picker"],t["value"],False)

    @app.callback(Output("ae-preview","data"), Output("ae-preview","columns"), Output("ae-preview","page_count"), Output("ae-preview","tooltip_header"),
        Input("ae-data","data"), Input("ae-preview","page_current"), Input("ae-labels","data"))
    def preview(d,page,labels):
        if not d:return [],[],0,{}
        try:
            z=call(f"/data/{d['id']}?page={page or 0}")
            return z["rows"],[{"id":x,"name":x} for x in d["columns"]],(z["total"]+9)//10,header_tooltips(d["columns"],labels or {})
        except Exception:return [],[],0,{}

    @app.callback(Output("ae-job","data"), Output("ae-submit-status","children"), Output("ae-errors","data"),
        Input("ae-run","n_clicks"), State("ae-data","data"), State("ae-adsl","data"), State("ae-picks","data"),
        State("ae-title","value"), State("ae-relation-values","value"), State("ae-emergent-values","value"),
        State("ae-serious-values","value"), State("ae-death-values","value"), State("ae-adsl-filter-value","value"),
        State("ae-threshold","value"), State("ae-grade-cutoff","value"), prevent_initial_call=True)
    def submit(n,ae,adsl,picks,title,rel,emergent,serious,death,popvalue,threshold,cutoff):
        picks=picks or {}; errors={}
        if not ae: errors["ae-data"]="请先上传 ADAE 或加载合成演示数据。"
        for key,label in (("ae-group","治疗分组"),("ae-term","不良事件术语"),("ae-grade","毒性分级")):
            if not picks.get(key): errors[key]=f"请选择{label}变量。"
        for var_key,val_key,label in (("ae-relation","ae-relation-values","治疗相关性纳入值"),
            ("ae-emergent","ae-emergent-values","治疗期间出现纳入值"),
            ("ae-serious","ae-serious-values","严重事件纳入值"),("ae-death","ae-death-values","死亡标志纳入值")):
            raw={"ae-relation-values":rel,"ae-emergent-values":emergent,"ae-serious-values":serious,"ae-death-values":death}[val_key]
            if picks.get(var_key) and not (raw or "").strip(): errors[val_key]=f"已选择变量，请填写{label}，多个值用逗号分隔。"
        if adsl and not picks.get("ae-adsl-group"): errors["ae-adsl-group"]="请选择 ADSL 治疗分组变量。"
        if picks.get("ae-adsl-filter") and not (popvalue or "").strip(): errors["ae-adsl-filter-value"]="已选择 ADSL 人群标志，请填写纳入值，例如 Y。"
        if not isinstance(threshold,(int,float)) or not 0<=threshold<=100: errors["ae-threshold"]="请输入 0–100 之间的发生率百分比。"
        if not isinstance(cutoff,(int,float)) or cutoff not in range(1,6): errors["ae-grade-cutoff"]="重度事件分级界值请输入 1–5 之间的整数。"
        if errors: return None,html.Div([html.Strong("请检查以下位置："),html.Ul([html.Li(html.A(f"{LABELS.get(k,k)}：{v}",href=f"#{k}-field")) for k,v in errors.items()])],className="error"),errors
        cfg=dict(dataset=ae["id"],adsl=adsl["id"] if adsl else "",title=title or "不良事件汇总",threshold=threshold,grade_cutoff=cutoff,
            group=picks.get("ae-group"),term=picks.get("ae-term"),grade=picks.get("ae-grade"),relation=picks.get("ae-relation") or "",
            relation_values=[x.strip() for x in (rel or "").split(",") if x.strip()],emergent=picks.get("ae-emergent") or "",
            emergent_values=[x.strip() for x in (emergent or "").split(",") if x.strip()],serious=picks.get("ae-serious") or "",
            serious_values=[x.strip() for x in (serious or "").split(",") if x.strip()],action=picks.get("ae-action") or "",
            death=picks.get("ae-death") or "",death_values=[x.strip() for x in (death or "").split(",") if x.strip()],
            adsl_group=picks.get("ae-adsl-group"),adsl_filter=picks.get("ae-adsl-filter") or "",adsl_filter_value=popvalue or "")
        try:return call("/ae",cfg),"任务已提交。结果对应本次提交的配置。",{}
        except Exception as e:
            k=e.field if isinstance(e,PlatformError) else "system";return None,html.Div(f"{LABELS.get(k,k)}：{e}"),{k:str(e)}

    @app.callback([Output(f"{k}-error","children") for k in ("ae-group","ae-term","ae-grade","ae-relation","ae-relation-values","ae-emergent","ae-emergent-values","ae-serious","ae-serious-values","ae-action","ae-death","ae-death-values","ae-adsl-group","ae-adsl-filter","ae-adsl-filter-value","ae-threshold","ae-grade-cutoff")]+[Output("ae-system-error","children")],
        Input("ae-errors","data"))
    def show_errors(e):
        e=e or {}; mapped=("ae-group","ae-term","ae-grade","ae-relation","ae-relation-values","ae-emergent","ae-emergent-values","ae-serious","ae-serious-values","ae-action","ae-death","ae-death-values","ae-adsl-group","ae-adsl-filter","ae-adsl-filter-value","ae-threshold","ae-grade-cutoff")
        other=next((f"{LABELS.get(k,k)}：{v}" for k,v in e.items() if k not in mapped),"")
        return [e.get(k,"") for k in mapped]+[e.get("system","") or other]

    @app.callback(Output("ae-results","children"), Output("ae-status","children"), Output("ae-downloads","children"), Output("ae-poll","disabled"),
        Input("ae-job","data"), Input("ae-poll","n_intervals"), State("ae-adsl","data"), prevent_initial_call=True)
    def poll(job,n,adsl):
        if not job:return vp.empty("不良事件分析"),vp.status("输入未就绪","error"),[],True
        try:
            d=call(f"/jobs/{job['id']}")
            if d["status"]=="failed":return html.Div(f"{LABELS.get(d.get('field'),'系统')}：{d['error']} · 任务 {job['id']}",className="error"),vp.status("分析失败","error"),[],True
            if d["status"]!="complete":return html.Div("R 正在生成 AE 汇总表…",className="empty analysis-empty"),vp.status("排队中" if d["status"]=="queued" else "计算中","running"),[],False
            r=d["result"]
            table=html.Table([html.Thead(html.Tr([html.Th("不良事件")]+[html.Th(x) for x in r["headers"]])),html.Tbody([
                html.Tr([html.Td(row["label"])]+[html.Td(v) for v in row["values"]],className=("section-row " if row.get("section") else "")+("ae-indent" if row.get("indent") else "")) for row in r["rows"]])],className="three-line")
            note=r["footnote"]
            return html.Div([html.H3(r["title"]),html.Div(table,className="table-scroll"),html.P(note,className="footnote")]),vp.status("已完成","success"),[
                html.A("下载 Word",href=f"/ae-export/{job['id']}/docx",className="download"),html.A("下载 CSV",href=f"/ae-export/{job['id']}/csv",className="download secondary")],True
        except Exception as e:
            return html.Div(str(e) if isinstance(e,PlatformError) else "结果显示失败，请检查服务日志。",className="error"),vp.status("系统异常","error"),[],True
