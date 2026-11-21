"""Read the CSV/JSON variable dictionaries exported by the extraction script."""
import base64
import csv
import io
import json


def parse_dictionary(contents, filename):
    raw = base64.b64decode(contents.split(",", 1)[1], validate=True)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("variables 文件最大为 5 MB。")
    text = raw.decode("utf-8-sig")
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    if ext == "csv":
        reader = csv.DictReader(io.StringIO(text))
        if not {"variable", "label"}.issubset(reader.fieldnames or []):
            raise ValueError("需要 variable 和 label 两列。")
        rows = list(reader)
    elif ext == "json":
        rows = json.loads(text)
        if not isinstance(rows, list):
            raise ValueError("JSON 必须为变量记录数组。")
    else:
        raise ValueError("variables 文件支持 CSV 或 JSON。")
    labels = {}
    for row in rows:
        if not isinstance(row, dict) or not {"variable", "label"}.issubset(row):
            raise ValueError("每条记录需要 variable 和 label。")
        name, label = row["variable"], row["label"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("variable 不能为空。")
        name = name.strip()
        if name in labels:
            raise ValueError(f"变量 {name} 重复；请上传单个数据集的 variables 文件。")
        if label is not None and not isinstance(label, str):
            raise ValueError(f"{name} 的 label 必须为文本或空值。")
        labels[name] = (label or "").strip()
    return labels


def header_tooltips(columns, labels):
    return {name: {"value": labels[name], "type": "text"}
            for name in columns if labels.get(name)}
