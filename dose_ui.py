"""Dose decision pages; statistical calculations remain in R."""
from dash import Input, Output, State, dcc, html, no_update, dash_table
import plotly.graph_objects as go
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
from io import BytesIO

COLORS = {"E":"#87d99a","S":"#f0dc83","D":"#f1ad7e","DE":"#e97f8f"}
LABELS = {"E":"升级至更高剂量","S":"维持当前剂量","D":"降至下一剂量","DE":"排除当前及更高剂量"}


def field(label, component, error_id):
    return html.Div([html.Label(label),component,html.Div(id=error_id,className="field-error",role="alert")],className="field")


def explainer(title, paragraphs):
    return html.Aside([html.H3(title),*paragraphs],className="card dose-explainer")


def legend():
    return html.Div([html.Div([html.Span("",style={"backgroundColor":COLORS[k]},className="dose-swatch"),
        html.Strong(k),html.Span(f"：{LABELS[k]}")],className="dose-legend-item") for k in ("E","S","D","DE")],className="dose-legend")


def boin_explainer():
    return explainer("BOIN 数学原理与参数",[
        html.P("BOIN 用当前剂量观察到的 DLT 率 x/n，与由目标及可接受界限推导出的升级、降级阈值比较。"),
        html.Div("λe = log[(1−φ1)/(1−φ)] / log[φ(1−φ1)/(φ1(1−φ))]",className="dose-equation"),
        html.Div("λd = log[(1−φ)/(1−φ2)] / log[φ2(1−φ)/(φ(1−φ2))]",className="dose-equation"),
        html.P("φ 是目标 DLT 概率；φ1 是认为需要考虑升级的低毒界限；φ2 是认为需要考虑降级的高毒界限。需满足 0 < φ1 < φ < φ2 < 1。"),
        html.Ul([html.Li("x/n ≤ λe：E，升级"),html.Li("λe < x/n < λd：S，维持"),html.Li("x/n ≥ λd：D，降级")]),
        html.P("DE 安全排除：至少 3 人时，使用 Beta(1,1) 先验；若 Pr(p > φ | x,n) > 0.95，排除当前及更高剂量。这里 p 为当前剂量真实 DLT 概率。"),
        html.P("人数上限只决定预计算决策表显示的 n 范围；每格为该 n 与 DLT 数 x 对应的决策。",className="muted")])


def mtpi_explainer():
    return explainer("mTPI 数学原理与参数",[
        html.P("每个剂量独立使用二项似然和 Beta 先验更新毒性概率。输入 n 为该剂量已评估人数，x 为发生 DLT 人数。"),
        html.Div("p | x,n ~ Beta(x+1, n−x+1)",className="dose-equation"),
        html.P("目标 φ 与 epsilon 定义三个区间："),
        html.Div("UI=(0, φ−ε)　 EI=[φ−ε, φ+ε]　 OI=(φ+ε, 1)",className="dose-equation"),
        html.Div("UPM(I) = Pr(p ∈ I | x,n) / 区间宽度",className="dose-equation"),
        html.Ul([html.Li("UI 的 UPM 最大：升级 E"),html.Li("EI 的 UPM 最大：维持 S"),html.Li("OI 的 UPM 最大：降级 D")]),
        html.P("φ 是目标 DLT 概率；epsilon 是目标区间半宽，必须让 φ±epsilon 留在 (0,1) 内。平坦 Beta(1,1) 是演示使用的先验。"),
        html.P("若任一剂量 Pr(p > φ | x,n) > 0.95，则该剂量和更高剂量排除；最低剂量排除时建议停止。"),
        html.P("曲线使用按样本量加权的单调 PAVA 拟合经验 DLT 率，帮助查看剂量趋势；标准 mTPI 的 UPM 决策仍只依赖当前剂量数据。",className="muted")])


def layout():
    sample = [{"dose":"Dose 1","treated":3,"dlt":0},{"dose":"Dose 2","treated":3,"dlt":1},
              {"dose":"Dose 3","treated":3,"dlt":2},{"dose":"","treated":None,"dlt":None},
              {"dose":"","treated":None,"dlt":None}]
    boin = html.Div([
        html.Section([
            html.Div([html.H2("BOIN 决策表"),html.P("基于目标 DLT 率和上下毒性界限，预计算每个队列规模下的 E / S / D / DE 决策。",className="muted")]),
            field("目标 DLT 概率 φ（0–1）",dcc.Input(id="dose-boin-target",type="number",min=0,max=1,step=.01,value=.30),"dose-boin-error"),
            field("下界 φ1（低于目标）",dcc.Input(id="dose-boin-lower",type="number",min=0,max=1,step=.01,value=.20),"dose-boin-error-lower"),
            field("上界 φ2（高于目标）",dcc.Input(id="dose-boin-upper",type="number",min=0,max=1,step=.01,value=.40),"dose-boin-error-upper"),
            field("每队列人数上限 n",dcc.Input(id="dose-boin-maxn",type="number",min=1,max=30,step=1,value=9),"dose-boin-error-maxn"),
            html.Button("生成 BOIN 决策表 →",id="dose-boin-run",n_clicks=0,className="primary"),
            html.Div(id="dose-boin-status",role="status",className="dose-status"),
            html.Div(id="dose-boin-result",className="dose-result"),
            dcc.Store(id="dose-boin-data"),
        ],className="card dose-main-card"),
        boin_explainer(),
    ],id="dose-boin-view",className="dose-design-layout",style={"display":"none"})
    mtpi = html.Div([
        html.Section([
            html.Div([html.H2("mTPI 当前剂量分析"),html.P("按剂量顺序录入已评估人数和 DLT 数，再选取当前剂量。",className="muted")]),
            field("目标 DLT 概率 φ",dcc.Input(id="dose-mtpi-target",type="number",min=0,max=1,step=.01,value=.30),"dose-mtpi-error"),
            field("epsilon（目标等价区间半宽）",dcc.Input(id="dose-mtpi-epsilon",type="number",min=0,max=.49,step=.01,value=.05),"dose-mtpi-error-epsilon"),
            html.Label("每剂量 DLT 数据（单元格可编辑；预填值仅为演示示例）"),
            dcc.Markdown("样例不是临床试验数据；请替换为实际汇总后再解读。剂量按从低到高排序。",className="muted"),
            dash_table.DataTable(id="dose-mtpi-data",data=sample,columns=[
                {"name":"剂量水平","id":"dose","type":"text","editable":True},
                {"name":"已评估人数 n","id":"treated","type":"numeric","editable":True},
                {"name":"DLT 数 x","id":"dlt","type":"numeric","editable":True}],editable=True,row_deletable=True,
                style_table={"overflowX":"auto"},style_cell={"padding":"9px","fontSize":13,"minWidth":"90px","textAlign":"left"},
                style_header={"fontWeight":"bold","backgroundColor":"#f3f6f8","border":"none"}),
            html.Div(id="dose-mtpi-error-data",className="field-error",role="alert"),
            html.Button("添加剂量行",id="dose-mtpi-add",n_clicks=0,className="secondary"),
            field("当前剂量",dcc.Dropdown(id="dose-mtpi-current",options=[{"label":"Dose 2","value":2}],value=2,clearable=False),"dose-mtpi-error-current"),
            html.Button("计算 mTPI 决策 →",id="dose-mtpi-run",n_clicks=0,className="primary"),
            html.Div(id="dose-mtpi-status",role="status",className="dose-status"),
            html.Div(id="dose-mtpi-result",className="dose-result"),
        ],className="card dose-main-card"),
        mtpi_explainer(),
    ],id="dose-mtpi-view",className="dose-design-layout",style={"display":"none"})
    return html.Div([dcc.Download(id="dose-boin-download"),boin,mtpi],id="dose-page",className="dose-page",style={"display":"none"})


def fmt(v, digits=3):
    return "—" if v is None else f"{v:.{digits}f}"


def excel_bytes(result):
    max_n = int(result["max_n"])
    actions = {(int(r["n"]),int(r["dlt"])):r["action"] for r in result["table"]}
    col_names = ["DLT 人数 x / 可评估人数 n"]+[f"n={n}" for n in range(1,max_n+1)]
    rows = [col_names]
    for y in range(max_n,-1,-1):
        rows.append([y]+[actions.get((n,y),"") for n in range(1,max_n+1)])
    for action in ("E","S","D","DE"):
        rows.append([f"{action}：{LABELS[action]}"]+[""]*(max_n))
    rows += [["目标 φ",result["target"]]+[""]*(max_n-1),["下界 φ1",result["lower"]]+[""]*(max_n-1),
             ["上界 φ2",result["upper"]]+[""]*(max_n-1),["升级阈值 λe",result["lambda_e"]]+[""]*(max_n-1),
             ["降级阈值 λd",result["lambda_d"]]+[""]*(max_n-1),["DE 安全规则","n≥3 且 Pr(p>φ|x,n)>0.95；Beta(1,1) 先验"]+[""]*(max_n-1)]
    letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    xml_rows=[]
    for ri,row in enumerate(rows,1):
        cells=[]
        for ci,val in enumerate(row,1):
            col=letters[ci-1] if ci<=26 else "A"+letters[ci-27]
            address=f"{col}{ri}"
            if ri==1: cells.append(f'<c r="{address}" s="1" t="inlineStr"><is><t>{escape(str(val))}</t></is></c>');continue
            if 2<=ri<=max_n+2 and ci==1: cells.append(f'<c r="{address}" s="1"><v>{val}</v></c>');continue
            if 2<=ri<=max_n+2 and ci>1 and val:
                style={"E":2,"S":3,"D":4,"DE":5}[val]
                cells.append(f'<c r="{address}" s="{style}" t="inlineStr"><is><t>{val}</t></is></c>');continue
            if isinstance(val,(int,float)):cells.append(f'<c r="{address}" s="6"><v>{val}</v></c>')
            elif val:cells.append(f'<c r="{address}" s="0" t="inlineStr"><is><t>{escape(str(val))}</t></is></c>')
        xml_rows.append(f'<row r="{ri}">'+"".join(cells)+"</row>")
    sheet=f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="B2" activePane="bottomRight" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="28" customWidth="1"/><col min="2" max="{max_n+1}" width="9" customWidth="1"/></cols><sheetData>'+"".join(xml_rows)+"</sheetData></worksheet>"
    styles='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="7"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF87D99A"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF0DC83"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF1AD7E"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE97F8F"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FF244454"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="7"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/><xf numFmtId="0" fontId="1" fillId="6" borderId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="3" borderId="0" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="4" borderId="0" applyFill="1"/><xf numFmtId="0" fontId="1" fillId="5" borderId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    workbook='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="BOIN 决策表" sheetId="1" r:id="rId1"/></sheets></workbook>'
    content='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'''
    rootrels='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    wbrel='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    output=BytesIO()
    with ZipFile(output,"w",ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",content);z.writestr("_rels/.rels",rootrels);z.writestr("xl/workbook.xml",workbook)
        z.writestr("xl/_rels/workbook.xml.rels",wbrel);z.writestr("xl/styles.xml",styles);z.writestr("xl/worksheets/sheet1.xml",sheet)
    return output.getvalue()


def boin_figure(result):
    max_n=int(result["max_n"]);records={(int(r["n"]),int(r["dlt"])):r["action"] for r in result["table"]}
    code={"E":0,"S":1,"D":2,"DE":3}
    z=[];texts=[]
    for y in range(max_n+1):
        zr=[];tr=[]
        for n in range(1,max_n+1):
            action=records.get((n,y)) if y<=n else None
            zr.append(code[action] if action else None);tr.append(action or "")
        z.append(zr);texts.append(tr)
    colorscale=[]
    for i,key in enumerate(("E","S","D","DE")):
        colorscale.extend([[i/4,COLORS[key]],[(i+1)/4,COLORS[key]]])
    fig=go.Figure(go.Heatmap(z=z,x=list(range(1,max_n+1)),y=list(range(max_n+1)),zmin=0,zmax=3,colorscale=colorscale,
        showscale=False,xgap=2,ygap=2,hovertemplate="当前剂量评估人数 n=%{x}<br>DLT 人数 x=%{y}<extra></extra>"))
    for y,row in enumerate(texts):
        for n,label in enumerate(row,1):
            if label:fig.add_annotation(x=n,y=y,text=label,showarrow=False,font={"size":12,"color":"#253645","family":"Arial"})
    fig.update_layout(template="plotly_white",height=max(480,42*(max_n+1)+150),margin={"l":75,"r":20,"t":35,"b":70},
        xaxis={"title":"当前剂量可评估人数 n","dtick":1,"side":"bottom","showgrid":False},
        yaxis={"title":"DLT 人数 x","dtick":1,"showgrid":False,"range":[-.5,max_n+.5]},
        paper_bgcolor="#ffffff",plot_bgcolor="#f2f4f5",autosize=True)
    return fig


def register(app, call, PlatformError):
    @app.callback(Output("dose-mtpi-data","data"),Input("dose-mtpi-add","n_clicks"),State("dose-mtpi-data","data"),prevent_initial_call=True)
    def add_dose(n,rows):
        rows=list(rows or []);rows.append({"dose":"","treated":None,"dlt":None});return rows

    @app.callback(Output("dose-mtpi-current","options"),Output("dose-mtpi-current","value"),Input("dose-mtpi-data","data"),State("dose-mtpi-current","value"))
    def current_options(rows,current):
        rows=rows or [];options=[{"label":str(r.get("dose") or f"第 {i+1} 行"),"value":i+1} for i,r in enumerate(rows) if str(r.get("dose") or "").strip()]
        values={o["value"] for o in options};return options,current if current in values else (options[0]["value"] if options else None)

    @app.callback(Output("dose-boin-result","children"),Output("dose-boin-status","children"),Output("dose-boin-error","children"),
        Output("dose-boin-error-lower","children"),Output("dose-boin-error-upper","children"),Output("dose-boin-error-maxn","children"),Output("dose-boin-data","data"),
        Input("dose-boin-run","n_clicks"),State("dose-boin-target","value"),State("dose-boin-lower","value"),State("dose-boin-upper","value"),State("dose-boin-maxn","value"),prevent_initial_call=True)
    def run_boin(n,target,lower,upper,maxn):
        try:
            r=call("/dose/boin",{"target":target,"lower":lower,"upper":upper,"max_n":maxn})
            graph=dcc.Graph(id="boin-heatmap",figure=boin_figure(r),config={"displaylogo":False,"toImageButtonOptions":{"format":"png","filename":"BOIN-决策表","height":max(600,43*(int(r['max_n'])+1)+160),"width":max(1100,76*int(r['max_n'])+180)}})
            controls=html.Div([html.Button("下载 Excel",id="dose-boin-xlsx-button",n_clicks=0,className="secondary"),
                html.Button("下载 PNG",id="dose-boin-png-button",n_clicks=0,className="secondary"),html.Div(id="dose-boin-download-status",role="status")],className="dose-export-controls")
            note=html.P(f"目标 φ={target:.3f}；φ1={lower:.3f}；φ2={upper:.3f}；λe={r['lambda_e']:.4f}；λd={r['lambda_d']:.4f}。",className="muted")
            return [note,graph,legend(),controls],"决策表已生成", "","","","",r
        except Exception as e:
            msg=str(e) if isinstance(e,PlatformError) else "计算失败，请检查输入。";key=getattr(e,"field","")
            return no_update,"输入有误",msg if key=="dose-boin-target" else "",msg if key=="dose-boin-error-lower" else "",msg if key=="dose-boin-error-upper" else "",msg if key=="dose-boin-error-maxn" else "",no_update

    @app.callback(Output("dose-boin-download","data"),Input("dose-boin-xlsx-button","n_clicks"),State("dose-boin-data","data"),prevent_initial_call=True)
    def download_xlsx(n,result):
        if not n or not result:return no_update
        return dcc.send_bytes(excel_bytes(result),"BOIN-决策表.xlsx")

    app.clientside_callback("""function(n){if(!n)return window.dash_clientside.no_update;var p=document.querySelector('#boin-heatmap .js-plotly-plot');if(!p||!window.Plotly)return '请先生成 BOIN 决策表';window.Plotly.downloadImage(p,{format:'png',filename:'BOIN-决策表'});return 'PNG 已导出';}""",
        Output("dose-boin-download-status","children"),Input("dose-boin-png-button","n_clicks"),prevent_initial_call=True)

    @app.callback(Output("dose-mtpi-result","children"),Output("dose-mtpi-status","children"),Output("dose-mtpi-error","children"),
        Output("dose-mtpi-error-epsilon","children"),Output("dose-mtpi-error-current","children"),Output("dose-mtpi-error-data","children"),
        Input("dose-mtpi-run","n_clicks"),State("dose-mtpi-data","data"),State("dose-mtpi-target","value"),State("dose-mtpi-epsilon","value"),State("dose-mtpi-current","value"),prevent_initial_call=True)
    def run_mtpi(n,rows,target,epsilon,current):
        try:
            r=call("/dose/mtpi",{"rows":rows or [],"target":target,"epsilon":epsilon,"current":current});doses=r["doses"]
            x=list(range(len(doses)));fig=go.Figure()
            fig.add_hrect(y0=r["lower"],y1=r["upper"],fillcolor="rgba(19,127,118,.12)",line_width=0,annotation_text="目标等价区间")
            fig.add_hline(y=target,line_dash="dash",line_color="#7a8793")
            fig.add_trace(go.Scatter(x=x,y=[d["observed"] for d in doses],mode="markers",name="观察 DLT 率",marker={"size":10,"color":"#b96c40"},hovertemplate="%{x}<br>观察 DLT 率 %{y:.3f}<extra></extra>"))
            fig.add_trace(go.Scatter(x=x,y=[d["isotonic"] for d in doses],mode="lines+markers",name="加权单调拟合",line={"color":"#137f76","width":3},hovertemplate="%{x}<br>单调拟合 %{y:.3f}<extra></extra>"))
            fig.update_layout(template="plotly_white",height=340,margin={"l":55,"r":20,"t":30,"b":45},
                xaxis={"tickmode":"array","tickvals":x,"ticktext":[d["dose"] for d in doses],"title":"剂量（由低到高）"},yaxis={"range":[0,1],"title":"DLT 概率"},legend={"orientation":"h","y":1.12})
            c=r["current"];upm=c["upm"]
            upm_table=dash_table.DataTable(data=[{"区间":"过低（升级）","区间范围":f"(0, {r['lower']:.3f})","后验概率":fmt(upm["underdose"]*r["lower"],4),"UPM":fmt(upm["underdose"],4)},
                {"区间":"目标（维持）","区间范围":f"[{r['lower']:.3f}, {r['upper']:.3f}]","后验概率":fmt(upm["equivalence"]*(r["upper"]-r["lower"]),4),"UPM":fmt(upm["equivalence"],4)},
                {"区间":"过高（降级）","区间范围":f"({r['upper']:.3f}, 1)","后验概率":fmt(upm["overdose"]*(1-r["upper"]),4),"UPM":fmt(upm["overdose"],4)}],
                columns=[{"name":k,"id":k} for k in ["区间","区间范围","后验概率","UPM"]],style_cell={"padding":"9px"},style_header={"fontWeight":"bold"})
            all_table=dash_table.DataTable(data=[{"剂量":d["dose"],"n":d["treated"],"DLT":d["dlt"],"观察率":fmt(d["observed"]),"单调拟合率":fmt(d["isotonic"]),"后验均值":fmt(d["posterior_mean"]),"后验 95% CrI":f"{d['posterior_lower']:.3f} – {d['posterior_upper']:.3f}"} for d in doses],
                columns=[{"name":k,"id":k} for k in ["剂量","n","DLT","观察率","单调拟合率","后验均值","后验 95% CrI"]],style_table={"overflowX":"auto"},style_cell={"padding":"8px","fontSize":12})
            children=[html.H3(f"建议：{r['action']}"+(f" → {r['next_dose']}" if r.get("next_dose") else ""),className="dose-recommendation"),
                html.P(f"当前剂量 {c['dose']}：{c['dlt']}/{c['treated']} DLT；后验均值 {c['posterior_mean']:.3f}，95% CrI {c['posterior_lower']:.3f}–{c['posterior_upper']:.3f}；Pr(p > φ)={c['posterior_over_target']:.3f}。",className="muted"),
                html.H4("当前剂量三个区间的后验概率与 UPM"),upm_table,dcc.Graph(figure=fig,config={"displaylogo":False}),html.H4("各剂量汇总"),all_table,html.P(r["exclusion"],className="analysis-notice")]
            return children,"已完成 mTPI 分析","","","",""
        except Exception as e:
            msg=str(e) if isinstance(e,PlatformError) else "计算失败，请检查剂量输入。";key=getattr(e,"field","")
            return no_update,"输入有误",msg if key=="dose-mtpi-target" else "",msg if key=="dose-mtpi-error-epsilon" else "",msg if key=="dose-mtpi-error-current" else "",msg if key=="dose-mtpi-error-data" else ""
