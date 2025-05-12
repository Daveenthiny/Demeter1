"""
Demeter Process Flow
Requirements:
pip install graphviz
Graphviz binaries in PATH (brew install graphviz  |  apt-get install graphviz)
"""

from graphviz import Digraph, escape
import os, textwrap

# ── Color palette ────────────────────────────────────────────────────
COLORS = {
    "USER"   : "#FFF9C4",
    "FRONT"  : "#FFCDD2",
    "AUTH"   : "#D7CCC8",
    "APPSYNC": "#D1C4E9",
    "APP"    : "#E1F5FE",
    "LAMBDA" : "#FFECB3",
    "BEDROCK": "#F3E5F5",
    "DB"     : "#E8F5E9",
    "SNS"    : "#F8BBD0",
}

# ── Helper functions ────────────────────────────────────────────────
def add_node(graph, name, label, fill, shape="rect"):
    graph.node(
        name,
        f"<<b>{label}</b>>",
        shape=shape,
        style="filled,rounded",
        fillcolor=fill,
        fontname="Arial",
        fontsize="11",
    )

def add_edge(graph, src, dst, label, bidir=False, style="solid"):
    html_label = f"<<b>{escape(textwrap.fill(label, 28))}</b>>"
    graph.edge(
        src,
        dst,
        label=html_label,
        dir="both" if bidir else "forward",
        style=style,
        fontname="Arial",
        fontsize="9",
    )

# ── Build the diagram ───────────────────────────────────────────────
g = Digraph(
    "demeter_process_flow",
    filename=os.path.expanduser("~/Desktop/demeter_process_flow"),
    format="png",
)
g.attr(
    rankdir="LR",
    bgcolor="white",
    fontname="Arial",
    label="<<b>Demeter&nbsp;Process&nbsp;Flow</b>>",
    labelloc="t",
    fontsize="22",
    nodesep="0.8",
    ranksep="0.9",
)

# Nodes
add_node(g, "User",      "User",                                                COLORS["USER"])
add_node(g, "Amplify",   "AWS&nbsp;Amplify<br/>Front-End",                      COLORS["FRONT"])
add_node(g, "Cognito",   "AWS&nbsp;Cognito<br/>User&nbsp;Pool",                 COLORS["AUTH"])
add_node(g, "AppSync",   "AWS&nbsp;AppSync<br/>GraphQL&nbsp;API",               COLORS["APPSYNC"])
add_node(g, "Dynamo",    "AWS&nbsp;DynamoDB",                                   COLORS["DB"], shape="cylinder")
add_node(g, "AppRunner", "AWS&nbsp;App&nbsp;Runner<br/>Flask&nbsp;Backend",     COLORS["APP"])
add_node(g, "Lambda",    "AWS&nbsp;Lambda<br/>Functions",                       COLORS["LAMBDA"], shape="cds")
add_node(g, "Bedrock",   "AWS&nbsp;Bedrock&nbsp;Agent",                         COLORS["BEDROCK"], shape="tab")
add_node(g, "SNS",       "AWS&nbsp;SNS",                                        COLORS["SNS"], shape="octagon")

# Edges
add_edge(g, "User",    "Amplify",   "Open site / Submit ZIP")
add_edge(g, "Amplify", "Cognito",   "Registration / Sign-in",  bidir=True)
add_edge(g, "Amplify", "AppSync",   "GraphQL calls",           bidir=True)
add_edge(g, "AppSync", "Dynamo",    "Get / Put Items",         bidir=True)

add_edge(g, "Amplify",   "AppRunner", "REST /ask-agent")
add_edge(g, "AppRunner", "Lambda",    "Invoke query tool")
add_edge(g, "Lambda",    "Bedrock",   "Invoke Bedrock")
add_edge(g, "Bedrock",   "Lambda",    "Return matches")
add_edge(g, "Lambda",    "AppRunner", "Return JSON")
add_edge(g, "AppRunner", "Amplify",   "Return answer")

add_edge(g, "Lambda", "SNS",  "Publish alert", style="dashed")
add_edge(g, "SNS",    "User", "Email notification")

# ── Render ───────────────────────────────────────────────────────────
path = g.render(cleanup=True)
print("Diagram saved →", path)