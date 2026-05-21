"""Diagrams for architecture and process visualization."""
from __future__ import annotations

import plotly.graph_objects as go

from .status_rules import STATUS_COLORS, STATUS_HEX


def _add_box(fig, x, y, text, fillcolor="rgba(148, 163, 184, 0.18)", width=1.8, height=0.55):
    fig.add_shape(
        type="rect", x0=x - width/2, x1=x + width/2, y0=y - height/2, y1=y + height/2,
        line=dict(color="rgba(30, 41, 59, 0.8)", width=1), fillcolor=fillcolor, layer="below"
    )
    fig.add_annotation(x=x, y=y, text=text, showarrow=False, font=dict(size=12, color="#f8fafc"))


def _add_arrow(fig, x0, y0, x1, y1):
    fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="#475569")


def architecture_diagram():
    fig = go.Figure()
    boxes = [
        (0, 5, "Источники данных\nERP / WMS / MES / ТОиР / Excel"),
        (0, 4, "Загрузка и\nвалидация данных"),
        (0, 3, "Расчётное ядро\nA → σLT → Bstat → Btar → Bopt"),
        (0, 2, "Сценарный анализ\nи тестирование"),
        (0, 1, "Визуализация и\nмониторинг ROP"),
        (0, 0, "Рекомендации\nи экспорт результатов"),
    ]
    for x, y, text in boxes:
        _add_box(fig, x, y, text, width=2.8, fillcolor="rgba(59, 130, 246, 0.12)")
    for i in range(len(boxes)-1):
        _add_arrow(fig, boxes[i][0], boxes[i][1]-0.32, boxes[i+1][0], boxes[i+1][1]+0.32)
    fig.update_layout(title="Архитектура программного решения", xaxis=dict(visible=False), yaxis=dict(visible=False), height=620, margin=dict(l=20, r=20, t=60, b=20), plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(range=[-2.2, 2.2])
    fig.update_yaxes(range=[-0.6, 5.6])
    return fig


def process_diagram(row: dict):
    status = row.get("status", "Не рассчитано")
    status_color = STATUS_COLORS.get(status, "rgba(148, 163, 184, 0.18)")
    item = row.get("item_id", "позиция")
    rop = row.get("rop_name", "ROP")
    A = row.get("A", 0)
    Bopt = row.get("Bopt", 0)
    Ibuf = row.get("Ibuf", 0)
    reorder_point = row.get("reorder_point", 0)
    pshort_current = row.get("Pshort_current", 0)

    fig = go.Figure()
    boxes = [
        (0, 2, "Поставщик"),
        (2, 2, "Ожидаемые\nпоступления P"),
        (4, 2, f"Склад / доступная\nпозиция A={A:.2f}"),
        (6, 2, f"Буфер ROP\nBopt={Bopt:.2f}\ns={reorder_point:.2f}"),
        (8, 2, f"{rop}\nIbuf={Ibuf:.2f}\nPshort={pshort_current:.1%}"),
        (10, 2, "Производственный\nвыпуск"),
        (6, 0.8, f"Статус:\n{status}"),
    ]
    for x, y, text in boxes:
        fill = status_color if x in [6, 8] or y == 0.8 else "rgba(148, 163, 184, 0.14)"
        _add_box(fig, x, y, text, fillcolor=fill, width=1.55, height=0.65)
    for i in range(5):
        _add_arrow(fig, boxes[i][0]+0.8, boxes[i][1], boxes[i+1][0]-0.8, boxes[i+1][1])
    _add_arrow(fig, 6, 1.65, 6, 1.12)
    fig.add_annotation(x=4, y=3.05, text=f"Контролируемая позиция: {item}", showarrow=False, font=dict(size=13, color="#f8fafc"))
    fig.update_layout(title="Процессная схема контроля буфера", xaxis=dict(visible=False), yaxis=dict(visible=False), height=460, margin=dict(l=20, r=20, t=60, b=20), plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(range=[-1, 11])
    fig.update_yaxes(range=[0.2, 3.4])
    return fig
