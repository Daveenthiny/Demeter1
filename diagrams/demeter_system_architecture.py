"""
Demeter System Architecture Diagram
Requirements:
pip install graphviz
Graphviz binaries in PATH (brew install graphviz  |  apt-get install graphviz)
"""

from graphviz import Source
import os

# ── Color palette ─────────────────────────────────────────────────────────────
COLOR_USER        = "#FFF9C4"
COLOR_FRONTEND    = "#FFCDD2"
COLOR_APP_RUNNER  = "#E1F5FE"
COLOR_LAMBDA      = "#FFECB3"
COLOR_DB          = "#E8F5E9"
COLOR_BEDROCK     = "#F3E5F5"
COLOR_AUTH        = "#D7CCC8"
COLOR_AMPLIFY     = "#C5CAE9"
COLOR_APPSYNC     = "#D1C4E9"
COLOR_SNS         = "#F8BBD0"
COLOR_DEVOPS      = "#CFD8DC"
COLOR_DOCKER      = "#BBDEFB"
COLOR_ECR         = "#B2DFDB"
COLOR_BORDER      = "#424242"
COLOR_EDGE        = "#616161"

# ── DOT graph ─────────────────────────────────────────────────────────────────
dot_graph = rf'''
digraph G {{
    rankdir=TD; splines=ortho; nodesep=0.8; ranksep=1.1;

    graph [bgcolor="white", pad="0.5",
           fontname="Arial", fontsize=22,
           labelloc=t, fontcolor=black,
           label=<<b>Demeter System Architecture</b>>];

    node [fontname="Arial", fontsize=12,
          style="filled,rounded", penwidth=1,
          color="{COLOR_BORDER}", fontcolor=black];
    edge [fontname="Arial", fontsize=11,
          color="{COLOR_EDGE}", fontcolor=black];

    // ─── User ───────────────────────────────────────────────────────
    node [shape=rect, fillcolor="{COLOR_USER}"];
    user [label=<<b>User</b>>];

    // ─── Front End ───────────────────────────────────────
    node [shape=folder, fillcolor="{COLOR_FRONTEND}"];
    indexHtml [label="index.html"];
    pagesHtml [label="Dashboards"];

    subgraph cluster_front {{
        label = <<b>Front End</b>>;
        style="filled,rounded"; color="{COLOR_AMPLIFY}80"; labelloc=t;

        node [shape=component, fillcolor="{COLOR_AMPLIFY}"];
        amplify [label=<<b>AWS Amplify</b><br/>CloudFront>];
    }}

    // ─── Cognito ────────────────────────────────────────────────────
    node [shape=tab, fillcolor="{COLOR_AUTH}"];
    cognito [label=<<b>Cognito<br/>User Pool</b>>];

    // ─── CI / CD ─────────────────────────────────
    subgraph cluster_ci {{
        label = <<b>CI / CD</b>>;
        style="filled,rounded"; color="{COLOR_DEVOPS}80"; labelloc=t;

        node [shape=component, fillcolor="{COLOR_DEVOPS}"];
        github   [label=<<b>GitHub</b>>];

        node [shape=box3d, fillcolor="{COLOR_DOCKER}"];
        dockerImg [label=<<b>Docker Image</b><br/>demeterrag>];

        node [shape=cylinder, fillcolor="{COLOR_ECR}", peripheries=2];
        ecr [label=<<b>Amazon ECR</b><br/>demeterrag>];
    }}

    // ─── Compute Services ──────────────────────────────────────────
    subgraph cluster_compute {{
        label = <<b>Compute Services</b>>;
        style="filled,rounded"; color="#B0BEC540"; labelloc=t;

        node [shape=component, fillcolor="{COLOR_APP_RUNNER}", height=1.1];
        appSvc [label=<<b>AWS App Runner</b><br/>Flask Backend>];

        node [shape=cds, fillcolor="{COLOR_LAMBDA}"];
        qLambda     [label="Query Lambda"];
        rLambda     [label="Rebuild Lambda"];
        exportLambda[label="CSV Export Lambda"];
    }}

    // ─── AI / ML ─────────────────────────────────────────
    subgraph cluster_ai {{
        label = <<b>AI / ML</b>>;
        style="filled,rounded"; color="#D1C4E940"; labelloc=t;

        node [shape=tab, fillcolor="{COLOR_BEDROCK}"];
        bedrock [label="Bedrock Agent"];
        titan   [label="Titan Embeddings"];
    }}

    // ─── Data Layer ────────────────────────────────────────────────
    subgraph cluster_data {{
        label = <<b>Data Layer</b>>;
        style="filled,rounded"; color="{COLOR_DB}80"; labelloc=t;

        node [shape=cylinder, fillcolor="{COLOR_DB}", peripheries=2];
        tblItems [label="DynamoDB FoodItems"];
        tblUsers [label="DynamoDB Users"];
        s3Csv    [label="S3 CSV Files"];
        s3Vec    [label="S3 Embeddings JSON"];
    }}

    // ─── Messaging (SNS) ────────────────────────────────────────────
    node [shape=octagon, fillcolor="{COLOR_SNS}"];
    snsTopic [label="SNS Topic"];

    // ─── AppSync API ────────────────────────────────────────────────
    node [shape=component, fillcolor="{COLOR_APPSYNC}"];
    appSync [label="AWS AppSync\nGraphQL API"];

    // ─── Flows ──────────────────────────────────────────────────────
    // Static site
    user -> indexHtml [label="GET"];
    indexHtml -> amplify;
    pagesHtml -> amplify;

    // Auth + GraphQL
    amplify -> cognito [label="Auth"];
    amplify -> appSync [label="GraphQL"];
    cognito -> appSync [label="JWT"];
    cognito -> appSvc  [label="JWT"];

    // AppSync data resolvers
    appSync -> tblItems;
    appSync -> tblUsers;

    // NEW: exportLambda creates CSV snapshots
    tblItems -> exportLambda;
    tblUsers -> exportLambda;
    exportLambda -> s3Csv [label="Write CSV"];

    // CSV upload triggers embedding rebuild
    s3Csv -> rLambda [style=dashed, arrowhead=open, label="S3 Event"];
    rLambda -> appSvc [label="/rebuild-embeddings"];

    // Main query path
    appSync -> appSvc  [style=dashed, label="Resolver\n(search)"];
    appSvc  -> bedrock [label="Invoke Agent"];
    bedrock -> qLambda [label="Tool"];
    qLambda -> appSvc  [label="/search-data"];
    appSvc  -> titan   [label="Embed ZIP"];
    appSvc  -> s3Vec   [label="Load Vectors"];

    // Rebuild writes vectors
    appSvc -> titan;
    appSvc -> s3Vec   [label="Write Vectors"];

    // Alerts
    appSvc -> snsTopic;
    snsTopic -> user;

    // CI / CD chain
    github -> dockerImg [label="docker build"];
    dockerImg -> ecr    [label="docker push"];
    ecr -> appSvc       [label="Image pull"];
    github -> amplify   [label="Static deploy"];
}}

'''

# ── Render PNG ────────────────────────────────────────────────────────────────
dst = Source(dot_graph, format='png').render(
    filename=os.path.expanduser('~/Desktop/demeter_system_architecture'),
    view=False, cleanup=True
)
print("Diagram generated →", dst)