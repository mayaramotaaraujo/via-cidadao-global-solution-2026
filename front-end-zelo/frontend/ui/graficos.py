"""Estilo único para todos os gráficos Plotly (componente reutilizável)."""

import plotly.graph_objects as go

FONTE = "Public Sans, system-ui, sans-serif"
TINTA, ASFALTO, GRADE = "#1A2533", "#5B6675", "#EEF1F4"


def estilizar(fig: go.Figure, altura: int = 380, legenda: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=altura,
        font={"family": FONTE, "size": 13, "color": TINTA},
        margin={"t": 36 if legenda else 12, "b": 8, "l": 8, "r": 8},
        showlegend=legenda,
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0, "title_text": "",
                "font": {"color": ASFALTO}},
        hoverlabel={"bgcolor": "#fff", "bordercolor": "#DCE1E7", "font": {"family": FONTE, "color": TINTA}},
        paper_bgcolor="#fff",
        plot_bgcolor="#fff",
    )
    fig.update_xaxes(gridcolor=GRADE, zerolinecolor=GRADE, linecolor="#DCE1E7", title_font={"color": ASFALTO})
    fig.update_yaxes(gridcolor=GRADE, zerolinecolor=GRADE, linecolor="#DCE1E7", title_font={"color": ASFALTO})
    return fig
