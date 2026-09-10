import pandas as pd
import plotly.express as px

def average_ratings_chart(metrics: dict):
    rows = [{"Area": v["label"], "Average": v["mean"]} for v in metrics["ratings"].values() if v["mean"] is not None]
    fig = px.bar(pd.DataFrame(rows), x="Average", y="Area", orientation="h", range_x=[0, 5], text_auto=".2f", color="Average", color_continuous_scale="Blues")
    fig.update_layout(coloraxis_showscale=False, height=330, margin=dict(l=20, r=20, t=20, b=20))
    return fig

def distribution_chart(metrics: dict, column: str = "OverallSatisfaction"):
    dist = metrics["ratings"][column]["distribution"]
    fig = px.bar(x=list(dist), y=list(dist.values()), labels={"x": "Rating", "y": "Responses"}, text_auto=True)
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
    return fig

