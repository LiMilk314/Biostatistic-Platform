"""Survival page and callbacks; calculations remain in R."""
import json
from dash import ALL, Input, Output, State, ctx, dcc, html, dash_table, no_update
import plotly.graph_objects as go
from variable_labels import parse_dictionary, header_tooltips
import variable_picker as vp

LABELS = {"sv-tte":"ADTTE 数据","sv-adsl":"ADSL 数据","sv-endpoint-var":"终点变量",
          "sv-endpoints":"分析终点","sv-time":"时间变量","sv-censor":"删失变量",
          "sv-event":"事件与删失编码","sv-unit":"时间单位","sv-group":"治疗分组",
          "sv-reference":"参考组 / 比较组","sv-continuous":"连续协变量","sv-categorical":"分类协变量",
          "sv-population":"分析人群筛选","sv-record":"分析记录筛选","system":"系统"}


def field(key,label,children):
    controls = children if isinstance(children, list) else [children]
    return html.Div([html.Label(label),*controls,html.Div(id=key+"-error",className="field-error")],id=key+"-field",className="field")


def upload(key,title):
    return dcc.Upload(id=key,children=[html.B(title),html.Div("拖入文件，或点击上传"),html.Small("CSV / XPT / SAS7BDAT")],className="upload")


def layout():
    return html.Div([
        dcc.Store(id="sv-data"),dcc.Store(id="sv-subjects"),dcc.Store(id="sv-job"),dcc.Store(id="sv-meta"),dcc.Store(id="sv-picks",data={}),
        dcc.Store(id="sv-labels",data={}),dcc.Store(id="sv-errors",data={}),dcc.Interval(id="sv-poll",interval=1000,disabled=True),
        html.Section([
            html.H3("01  生存分析数据"),
            html.Button("加载演示 ADTTE + ADSL",id="sv-demo",className="secondary"),
            html.P("内置固定种子生成的精简合成数据 · 240 名受试者 · OS / PFS",className="muted"),
            field("sv-tte","ADTTE（必需）",[upload("sv-upload","ADTTE 数据文件"),html.Div(id="sv-data-info",className="muted")]),
            field("sv-adsl","ADSL（可选，用于额外协变量）",[upload("sv-adsl-upload","ADSL 数据文件"),
                html.Button("移除 ADSL",id="sv-clear-adsl",className="secondary"),html.Div(id="sv-adsl-info",className="muted")]),
            dcc.Upload(id="sv-dict-upload",children=[html.B("ADTTE variables（可选）"),html.Small("CSV / JSON · variable、label")],className="upload"),
            html.Div(id="sv-dict-info",className="muted"),
            html.H3("02  终点与治疗组"),
            field("sv-endpoints","分析终点",dcc.Checklist(id="sv-eps",options=["OS","PFS"],value=["OS","PFS"],inline=True)),
            vp.field("治疗分组变量","sv-group-input","sv-group-error","sv-group-field"),
            html.Div([html.Label("参考组 / 比较组"),
                html.Div([html.Div([html.Span("参考组（HR 分母）",className="variable-subtitle"),html.Div(html.Div(id="sv-ref-options",className="variable-grid"),className="variable-scroll")],className="variable-subgroup"),
                    html.Div([html.Span("比较组（HR 分子）",className="variable-subtitle"),html.Div(html.Div(id="sv-comp-options",className="variable-grid"),className="variable-scroll")],className="variable-subgroup")],className="variable-pair"),
                html.Div(id="sv-reference-error",className="field-error",role="alert")],className="field",id="sv-reference-field"),
            html.P("仅分析选定的两个治疗组。ADSL: 前缀表示来自可选 ADSL 的变量。",className="muted"),
            html.Details([html.Summary("时间、事件和筛选设置"),
                vp.field("终点代码变量","sv-ep-var","sv-endpoint-var-error","sv-endpoint-var-field"),
                vp.field("分析时间变量","sv-time-input","sv-time-error","sv-time-field"),
                vp.field("事件 / 删失变量","sv-censor-input","sv-censor-error","sv-censor-field"),
                field("sv-event","事件值 / 删失值（明确指定）",[dcc.Input(id="sv-event-input",value="0",placeholder="事件值"),
                    dcc.Input(id="sv-censor-values",value="1",placeholder="删失值，多值用英文逗号分隔")]),
                field("sv-unit","源时间单位 / 图表时间单位",[dcc.Dropdown(id="sv-source-unit",options=["DAYS","MONTHS","YEARS"],value="DAYS",clearable=False),
                    dcc.Dropdown(id="sv-display-unit",options=["DAYS","MONTHS","YEARS"],value="MONTHS",clearable=False)]),
                html.Div([html.Label("人群标志 = 纳入值（可选）"),html.Div(html.Div(id="sv-pop-var-options",className="variable-grid"),className="variable-scroll"),
                    dcc.Input(id="sv-pop-value",value="Y"),html.Div(id="sv-population-error",className="field-error",role="alert")],className="field",id="sv-population-field"),
                html.Div([html.Label("分析记录标志 = 纳入值（可选）"),html.Div(html.Div(id="sv-record-var-options",className="variable-grid"),className="variable-scroll"),
                    dcc.Input(id="sv-record-value",value="Y"),html.Div(id="sv-record-error",className="field-error",role="alert")],className="field",id="sv-record-field"),
            ],id="sv-advanced"),
            html.H3("03  Cox 调整变量"),
            vp.field("连续协变量","sv-cont","sv-continuous-error","sv-continuous-field"),
            vp.field("分类协变量","sv-cat","sv-categorical-error","sv-categorical-field"),
            html.P("必须选择分析计划规定的基线协变量。调整模型使用完整病例，并报告排除人数。",className="muted"),
            html.Button("生成生存分析 →",id="sv-run",className="primary"),html.Div(id="sv-submit-status",role="status"),
        ],className="card controls"),
        html.Div([
            html.Section([html.Div([html.H3("分析结果"),html.Div(id="sv-status",children=vp.status("待生成"),role="status")],className="result-head"),
                html.Div(id="sv-results",children=vp.empty("生存分析")),
                html.Div(id="sv-downloads",className="downloads")],className="card"),
            html.Section([html.H3("ADTTE 数据预览"),html.P("表头可悬停查看变量标签；每页 10 行。",className="muted"),
                dash_table.DataTable(id="sv-preview",page_action="custom",page_current=0,page_size=10,
                    tooltip_delay=200,tooltip_duration=None,style_table={"overflowX":"auto"},
                    style_cell={"fontSize":12,"padding":"8px","minWidth":"80px","maxWidth":"160px","overflow":"hidden","textOverflow":"ellipsis"})],className="card"),
        ],className="output-column"),
    ],className="workspace",id="survival-page",style={"display":"none"})


def fmt(value,digits=3):
    if value is None: return "NE"
    return f"{value:.{digits}f}"


def pvalue(value):
    if value is None: return "NE"
    return "<0.001" if value<.001 else f"{value:.3f}"


def table(headers,rows):
    return html.Div(html.Table([html.Thead(html.Tr([html.Th(x) for x in headers])),
        html.Tbody([html.Tr([html.Td(x) for x in row]) for row in rows])],className="three-line"),className="table-scroll")


def render(result):
    children = [html.P(f"HR 方向：{result['comparison']} / {result['reference']}；时间单位：{result['display_unit']}。排除其他治疗组记录 {result['other_group_records']} 条。",className="muted")]
    colors = ["#137f76","#b96c40"]
    for ep in result["endpoints"]:
        fig = go.Figure()
        for i,c in enumerate(ep["curves"]):
            color = colors[i]
            fig.add_trace(go.Scatter(x=c["time"],y=c["upper"],line={"width":0,"shape":"hv"},mode="lines",showlegend=False,hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=c["time"],y=c["lower"],line={"width":0,"shape":"hv"},mode="lines",fill="tonexty",
                fillcolor="rgba(19,127,118,.12)" if i==0 else "rgba(185,108,64,.12)",showlegend=False,hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=c["time"],y=c["survival"],name=c["group"],mode="lines",line={"shape":"hv","color":color,"width":2},
                hovertemplate="Time: %{x:.2f}<br>S(t): %{y:.3f}<extra>%{fullData.name}</extra>"))
            fig.add_trace(go.Scatter(x=c["censor_time"],y=c["censor_survival"],mode="markers",marker={"symbol":"cross-thin","size":7,"line":{"color":color,"width":1}},
                showlegend=False,name=c["group"]+" censored",hovertemplate="Censored at %{x:.2f}<extra></extra>"))
        fig.update_layout(template="plotly_white",height=440,title=f"{ep['endpoint']} · Kaplan–Meier",margin={"l":55,"r":20,"t":55,"b":45},
                          xaxis_title=result["display_unit"],yaxis_title="Survival probability",yaxis_range=[0,1.03],legend={"orientation":"h","y":-.2})
        children += [html.H3(f"{ep['endpoint']} · N={ep['n']} · Events={ep['events']}",className="survival-heading"),
            html.P(f"Log-rank p = {pvalue(ep['logrank_p'])}；阴影为 95% CI，十字为删失标记。",className="muted"),
            dcc.Graph(figure=fig,config={"displaylogo":False,"toImageButtonOptions":{"format":"svg","filename":ep["endpoint"]+"_KM"}}),
            html.H4("Number at risk"),table(["Group"]+[fmt(x,2) for x in ep["risk_times"]],[[c["group"]]+c["risk"] for c in ep["curves"]]),
            table(["Group","N","Events","Median","Median 95% CI"],[[c["group"],c["n"],c["events"],fmt(c["median"]),f"{fmt(c['median_lower'])} – {fmt(c['median_upper'])}"] for c in ep["curves"]])]
        for model in ep["models"]:
            label = "Adjusted Cox PH 回归"
            children += [html.H4(label),html.P(f"纳入 {model['n']} 人，事件 {model['events']}，因协变量缺失排除 {model['excluded']} 人。",className="muted")]
            if model["message"]: children.append(html.P(model["message"],className="analysis-notice"))
            if model["status"]!="ok": continue
            co = model["coefficients"]
            children.append(table(["Term","HR","95% CI","Wald p"],[[c["term"],fmt(c["hr"]),f"{fmt(c['lower'])} – {fmt(c['upper'])}",pvalue(c["p"])] for c in co]))
            forest = go.Figure(go.Scatter(x=[c["hr"] for c in co],y=[c["term"] for c in co],mode="markers",
                error_x={"type":"data","symmetric":False,"array":[c["upper"]-c["hr"] for c in co],"arrayminus":[c["hr"]-c["lower"] for c in co]},marker={"color":"#137f76","size":9}))
            forest.add_vline(x=1,line_dash="dash",line_color="#8b98a4")
            forest.update_layout(template="plotly_white",height=max(210,55*len(co)+100),margin={"l":20,"r":20,"t":45,"b":40},
                title=label+" · 系数森林图",xaxis={"type":"log","title":"Hazard ratio (95% CI)"},yaxis={"autorange":"reversed"})
            children.append(dcc.Graph(figure=forest,config={"displaylogo":False,"toImageButtonOptions":{"format":"svg","filename":ep["endpoint"]+"_"+model["model"]+"_forest"}}))
            children.append(html.Details([html.Summary("PH 比例风险假设检验（Schoenfeld）"),
                table(["Term","PH test p"],[[r["term"],pvalue(r["p"])] for r in model["ph"]]),
                html.P("PH 检验 p 值不是治疗效应 p 值。较小值提示可能违反比例风险假设；需结合诊断图与分析计划进一步评估。",className="muted")]))
    children += [html.Hr(),html.P("调整模型使用所选协变量完整的病例。森林图展示 Cox 模型系数，不是亚组治疗效应。",className="muted")]
    return children


def register(app,call,PlatformError):
    @app.callback(Output("sv-data","data"),Output("sv-subjects","data"),Output("sv-data-info","children"),Output("sv-adsl-info","children"),
        Input("sv-demo","n_clicks"),Input("sv-upload","contents"),Input("sv-adsl-upload","contents"),Input("sv-clear-adsl","n_clicks"),
        State("sv-upload","filename"),State("sv-adsl-upload","filename"),prevent_initial_call=True)
    def load(n,tte,adsl,clear,tf,af):
        is_adsl=ctx.triggered_id=="sv-adsl-upload"
        try:
            if ctx.triggered_id=="sv-clear-adsl": return no_update,None,no_update,"未使用额外 ADSL"
            if ctx.triggered_id=="sv-demo":
                d=call("/survival-demo",{});return d["tte"],d["adsl"],f"演示 ADTTE · {d['tte']['n']} 条记录 · OS / PFS",f"演示 ADSL · {d['adsl']['n']} 名受试者"
            contents=adsl if is_adsl else tte;name=af if is_adsl else tf
            d=call("/upload",{"filename":name,"content":contents.split(",",1)[1]})
            if is_adsl:return no_update,d,no_update,f"{name} · {d['n']} 行"
            return d,None,f"{name} · {d['n']} 行","ADTTE 已更换，请按需重新加载匹配 ADSL。"
        except Exception as e:
            msg=str(e) if isinstance(e,PlatformError) else "文件读取失败，请检查格式。"
            return no_update,no_update,no_update if is_adsl else msg,msg if is_adsl else no_update

    @app.callback(Output("sv-meta","data"),Input("sv-data","data"),Input("sv-subjects","data"))
    def meta(tte,adsl):
        if not tte:return {"columns":[],"numeric":[],"values":{}}
        cols=list(tte["columns"]);nums=list(tte["numeric"]);values=dict(tte.get("values",{}))
        if adsl:
            cols += ["ADSL:"+v for v in adsl["columns"] if v not in ("STUDYID","USUBJID")]
            nums += ["ADSL:"+v for v in adsl["numeric"]]
            values.update({"ADSL:"+v:x for v,x in adsl.get("values",{}).items()})
        return dict(columns=cols,numeric=nums,values=values)

    @app.callback(Output("sv-picks","data"),Input("sv-meta","data"))
    def default_picks(m):
        m=m or {"columns":[],"numeric":[],"values":{}};cols=m["columns"]
        if not cols:return {}
        group=next((v for v in ["TRT01P","ARM"] if v in cols),None)
        values=m.get("values",{}).get(group,[])
        ref=next((v for v in values if "placebo" in str(v).lower() or "control" in str(v).lower()),values[0] if values else None)
        comp=next((v for v in values if v!=ref),None)
        return {"sv-group-input":group,"sv-ep-var":"PARAMCD" if "PARAMCD" in cols else None,
            "sv-time-input":"AVAL" if "AVAL" in cols else None,"sv-censor-input":"CNSR" if "CNSR" in cols else None,
            "sv-ref":ref,"sv-comp":comp,"sv-pop-var":None,"sv-record-var":None,
            "sv-cont":["ADSL:AGE"] if "ADSL:AGE" in m.get("numeric",[]) else [],
            "sv-cat":["ADSL:SEX"] if "ADSL:SEX" in cols else []}

    @app.callback(Output("sv-group-input-options","children"),Output("sv-ref-options","children"),Output("sv-comp-options","children"),
        Output("sv-ep-var-options","children"),Output("sv-time-input-options","children"),Output("sv-censor-input-options","children"),
        Output("sv-pop-var-options","children"),Output("sv-record-var-options","children"),Output("sv-cont-options","children"),Output("sv-cat-options","children"),
        Input("sv-meta","data"),Input("sv-picks","data"))
    def render_picks(m,picks):
        m=m or {"columns":[],"values":{}};columns=m.get("columns",[]);picks=picks or {}
        group_values=m.get("values",{}).get(picks.get("sv-group-input"),[])
        return (vp.options("sv-group-input",columns,picks.get("sv-group-input")),
            vp.options("sv-ref",group_values,picks.get("sv-ref")),vp.options("sv-comp",group_values,picks.get("sv-comp")),
            vp.options("sv-ep-var",columns,picks.get("sv-ep-var")),vp.options("sv-time-input",columns,picks.get("sv-time-input")),
            vp.options("sv-censor-input",columns,picks.get("sv-censor-input")),vp.options("sv-pop-var",columns,picks.get("sv-pop-var")),
            vp.options("sv-record-var",columns,picks.get("sv-record-var")),vp.options("sv-cont",columns,picks.get("sv-cont",[]),multi=True),
            vp.options("sv-cat",columns,picks.get("sv-cat",[]),multi=True))

    @app.callback(Output("sv-picks","data",allow_duplicate=True),
        Input({"type":"variable-choice","picker":ALL,"value":ALL},"n_clicks"),State("sv-picks","data"),prevent_initial_call=True)
    def select_survival_variable(clicks,picks):
        if not ctx.triggered or ctx.triggered[0].get("value") in (None,0):return no_update
        triggered=ctx.triggered_id
        if not isinstance(triggered,dict):return no_update
        picker=triggered.get("picker")
        if picker not in {"sv-group-input","sv-ref","sv-comp","sv-ep-var","sv-time-input","sv-censor-input","sv-pop-var","sv-record-var","sv-cont","sv-cat"}:
            return no_update
        multi=picker in {"sv-cont","sv-cat"}
        updated=vp.toggle(picks,picker,triggered["value"],multi)
        if picker=="sv-group-input" and (picks or {}).get(picker)!=updated.get(picker):
            updated["sv-ref"]=None;updated["sv-comp"]=None
        return updated

    @app.callback(Output("sv-labels","data"),Output("sv-dict-info","children"),Input("sv-dict-upload","contents"),Input("sv-data","data"),State("sv-dict-upload","filename"),prevent_initial_call=True)
    def labels(contents,data,name):
        if ctx.triggered_id=="sv-data":return {},"可上传当前 ADTTE 的变量字典。"
        try:return parse_dictionary(contents,name),f"已加载 {name}"
        except Exception as e:return {},f"Variables：{e}"

    @app.callback(Output("sv-preview","data"),Output("sv-preview","columns"),Output("sv-preview","page_count"),Output("sv-preview","tooltip_header"),
        Input("sv-data","data"),Input("sv-preview","page_current"),Input("sv-labels","data"))
    def preview(d,page,labels):
        if not d:return [],[],0,{}
        try:
            r=call(f"/data/{d['id']}?page={page or 0}")
            return r["rows"],[{"id":v,"name":v} for v in d["columns"]],(r["total"]+9)//10,header_tooltips(d["columns"],labels or {})
        except Exception:return [],[],0,{}

    states=["sv-eps","sv-event-input","sv-censor-values","sv-source-unit","sv-display-unit","sv-pop-value","sv-record-value"]
    @app.callback(Output("sv-job","data"),Output("sv-submit-status","children"),Output("sv-errors","data"),Input("sv-run","n_clicks"),
        State("sv-data","data"),State("sv-subjects","data"),State("sv-picks","data"),[State(k,"value") for k in states],prevent_initial_call=True)
    def submit(n,tte,adsl,picks,*v):
        keys=["endpoints","event_value","censor_values","source_unit","display_unit","population_value","record_value"]
        cfg=dict(zip(keys,v));picks=picks or {}
        cfg.update(endpoint=picks.get("sv-ep-var"),time=picks.get("sv-time-input"),censor=picks.get("sv-censor-input"),
            group=picks.get("sv-group-input"),reference=picks.get("sv-ref"),comparison=picks.get("sv-comp"),
            continuous=picks.get("sv-cont",[]),categorical=picks.get("sv-cat",[]),population_var=picks.get("sv-pop-var"),record_var=picks.get("sv-record-var"))
        try:
            if not tte:raise PlatformError("请先加载 ADTTE。","sv-tte")
            for key,label in [("sv-group-input","治疗分组变量"),("sv-ep-var","终点代码变量"),("sv-time-input","分析时间变量"),("sv-censor-input","事件 / 删失变量"),("sv-ref","参考组"),("sv-comp","比较组")]:
                if not cfg.get({"sv-group-input":"group","sv-ep-var":"endpoint","sv-time-input":"time","sv-censor-input":"censor","sv-ref":"reference","sv-comp":"comparison"}[key]):
                    field="sv-reference" if key in ("sv-ref","sv-comp") else {"sv-group-input":"sv-group","sv-ep-var":"sv-endpoint-var","sv-time-input":"sv-time","sv-censor-input":"sv-censor"}[key]
                    raise PlatformError(f"请选择{label}。",field)
            if cfg["reference"]==cfg["comparison"]:raise PlatformError("参考组和比较组必须不同。","sv-reference")
            if not cfg["continuous"] and not cfg["categorical"]:raise PlatformError("Adjusted Cox PH 回归至少需要选择一个基线协变量。","sv-continuous")
            cfg.update(dataset=tte["id"],adsl=adsl["id"] if adsl else "")
            cfg["censor_values"]=[s.strip() for s in (cfg["censor_values"] or "").split(",") if s.strip()]
            job=call("/survival",cfg);return job,"任务已提交。结果对应本次提交的配置。",{}
        except Exception as e:
            key=e.field if isinstance(e,PlatformError) else "system"
            msg=str(e) if isinstance(e,PlatformError) else "提交失败，请检查服务日志。"
            return None,html.Div(html.A(f"{LABELS.get(key,key)}：{msg}",href="#"+key+"-field"),className="error"),{key:msg}

    @app.callback([Output(k+"-error","children") for k in LABELS if k!="system"]+[Output("sv-advanced","open")],Input("sv-errors","data"),Input("sv-picks","data"))
    def errors(e,picks):
        if ctx.triggered_id=="sv-picks":e={}
        e=e or {};return [e.get(k,"") for k in LABELS if k!="system"]+[True if any(k in e for k in ("sv-event","sv-unit","sv-record","sv-population","sv-time","sv-censor","sv-endpoint-var")) else no_update]

    @app.callback(Output("sv-results","children"),Output("sv-status","children"),Output("sv-downloads","children"),Output("sv-poll","disabled"),Input("sv-job","data"),Input("sv-poll","n_intervals"),prevent_initial_call=True)
    def poll(job,n):
        if not job:return vp.empty("生存分析"),vp.status("输入未就绪","error"),[],True
        try:
            d=call(f"/jobs/{job['id']}")
            if d["status"]=="failed":return html.Div(f"{LABELS.get(d.get('field'),'系统')}：{d['error']} · 任务 {job['id']}",className="error"),vp.status("分析失败","error"),[],True
            if d["status"]!="complete":return html.Div("R 正在生成生存分析…",className="empty analysis-empty"),vp.status("排队中" if d["status"]=="queued" else "计算中","running"),[],False
            return render(d["result"]),vp.status("已完成","success"),[html.A("下载 "+fmt.upper(),href=f"/survival-export/{job['id']}/{fmt}",className="download") for fmt in ("pdf","csv","json")],True
        except Exception as e:
            app.server.logger.exception("Survival result failed")
            return html.Div(str(e) if isinstance(e,PlatformError) else "结果显示失败，请检查日志。",className="error"),vp.status("系统异常","error"),[],True
