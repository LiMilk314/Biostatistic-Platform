"""Shared card-style variable choices for the Baseline and Survival pages."""
from dash import html


def field(label, picker, error_id, field_id):
    return html.Div([
        html.Label(label),
        html.Div(html.Div(id=f"{picker}-options", className="variable-grid"),
                 className="variable-scroll", **{"aria-label": f"{label}选项"}),
        html.Div(id=error_id, className="field-error", role="alert"),
    ], className="field", id=field_id)


def options(picker, values, selected, multi=False):
    selected_values = set(selected or []) if multi else {selected} if selected is not None else set()
    return [html.Button(
        str(value),
        id={"type": "variable-choice", "picker": picker, "value": str(value)},
        n_clicks=0,
        type="button",
        title=str(value),
        className="variable-option selected" if str(value) in selected_values else "variable-option",
    ) for value in (values or [])]


def toggle(values, picker, value, multi):
    current = dict(values or {})
    value = str(value)
    if multi:
        selected = list(current.get(picker) or [])
        current[picker] = [item for item in selected if str(item) != value] if value in map(str, selected) else selected + [value]
    else:
        selected = current.get(picker)
        current[picker] = None if str(selected) == value else value
    return current


def status(text, state="idle"):
    return html.Span(text, className=f"analysis-status status-{state}")


def empty(title):
    return html.Div([html.H3(title), html.P("点击生成后开始分析")], className="empty analysis-empty")
