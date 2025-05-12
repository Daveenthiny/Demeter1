"""
Demeter Chatbot Agent System Architecture Diagram
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
COLOR_S3          = "#E8F5E9"
COLOR_S3_EDGE     = "#8B0000"

# ── DOT graph ─────────────────────────────────────────────────────────────────
dot_graph = rf'''
digraph G {{
    rankdir=TD; // Top-to-Down layout
    splines=ortho; // Use orthogonal lines
    nodesep=0.8; // Increase separation between nodes further
    ranksep=1.2; // Increase separation between ranks (layers) further
    // Added graph label for title - made larger and bold
    graph [bgcolor="white", pad="0.5", fontname="Arial", label=<<b>Demeter Agent Architecture</b>>, fontsize=22, fontcolor=black, labelloc=t];
    node [fontname="Arial", fontsize=12, style="filled,rounded", color="{COLOR_BORDER}", fontcolor=black, penwidth=1]; // Increased node fontsize, rounded, black text
    edge [fontname="Arial", fontsize=11, color="{COLOR_EDGE}", fontcolor=black]; // Increased edge fontsize, black text

    // User Interaction Area
    node [shape=rect, fillcolor="{COLOR_USER}"];
    A [label=<<b>User via Chat Widget</b><br/>(index.html)>]; // Bold text using HTML

    // Compute Layer (App Runner, Lambda)
    subgraph cluster_Compute {{
        label = <<b>Compute Services</b>>; // Bold subgraph label
        labelloc=t; // Label at the top
        style="filled,rounded";
        color="#B0BEC540"; // Light gray background for subgraph
        penwidth=1;

        // App Runner Service
        node [shape=component, fillcolor="{COLOR_APP_RUNNER}", height=1.2]; // Component shape, taller
        B [label=<<b>AWS App Runner Service</b><br/>Consolidated Backend<br/>(app.py, bedrock_embeddings.py)<br/>Endpoints: /ask /search /rebuild /health>];

        // Lambda Functions
        node [shape=cds, fillcolor="{COLOR_LAMBDA}", height=1.0]; // Cylinder shape, taller
        E [label=<<b>Query Lambda</b><br/>(demeter_query_lambda.py)<br/>Bedrock Tool>];
        F [label=<<b>Rebuild Lambda</b><br/>(demeter_rebuild_embeddings_lambda.py)<br/>S3 Trigger>];
    }}

    // AI / ML Layer
    subgraph cluster_AI {{
        label = <<b>AI / ML</b>>;
        labelloc=t;
        style="filled,rounded";
        color="#D1C4E940"; // Lighter purple background
        penwidth=1;
        node [shape=tab, fillcolor="{COLOR_BEDROCK}"]; // Tab shape
        G [label=<<b>AWS Bedrock Agent</b><br/>(Handles Conversation Flow &amp; Tool Use)>]; // Escaped '&'
        H [label=<<b>AWS Titan Embeddings</b><br/>(Text-to-Vector Model)>];
    }}

    // Storage Layer
    subgraph cluster_Storage {{
        label = <<b>Data Layer</b>>;
        labelloc=t;
        style="filled,rounded";
        color="#C8E6C940"; // Lighter green background
        penwidth=1;
        node [fillcolor="{COLOR_S3}"];
        I [label=<<b>S3: Embeddings Store</b><br/>(Generated JSON Vector Files)>, shape=folder]; // Folder for stored data
        J [label=<<b>S3: Source Data Bucket</b><br/>(Uploaded CSV Files)>, shape=cylinder, peripheries=2]; // Cylinder with double border for bucket
    }}

    // Connections (Edges) - Using HTML for bold labels
    // Query Flow
    A -> B [label=<<b>1. User Query (Address/ZIP)</b><br/>POST /ask-agent>];
    B -> G [label=<<b>2. Invoke Agent</b><br/>(Query Text, SessionID)>];
    G -> E [label=<<b>3. Invoke Tool</b><br/>(Extracted ZIP Code)>];
    E -> B [label=<<b>4. Call Search API (ZIP)</b><br/>POST /search-data>];
    B -> H [label=<<b>5a. Generate Query Embedding</b><br/>(Input: ZIP Code Text)>];
    // Emphasize loading embeddings from S3 store
    B -> I [label=<<b>5b. Load Stored Embeddings</b><br/>(Input: Dataset Name)>, color="{COLOR_S3_EDGE}", penwidth=2, fontcolor="{COLOR_S3_EDGE}"];
    // Note: Steps 5a and 5b happen concurrently or sequentially within B's /search-data logic
    // Implicit return path: Search results flow back I -> B -> E -> G -> B -> A

    // Update Flow
    // Emphasize S3 event trigger
    J -> F [label=<<b>a. S3 Event: CSV Upload</b>>, style=dashed, arrowhead=open, color="{COLOR_S3_EDGE}", penwidth=2, fontcolor="{COLOR_S3_EDGE}"];
    F -> B [label=<<b>b. Call Rebuild API (Token)</b><br/>POST /rebuild-embeddings>];
    // Emphasize reading from S3 bucket
    B -> J [label=<<b>c. Read Source CSVs</b>>, color="{COLOR_S3_EDGE}", penwidth=2, fontcolor="{COLOR_S3_EDGE}"];
    B -> H [label=<<b>d. Generate Data Embeddings</b><br/>(Input: CSV Row Text)>];
    // Emphasize saving embeddings to S3 store
    B -> I [label=<<b>e. Save Embeddings</b><br/>(Output: JSON Files)>, color="{COLOR_S3_EDGE}", penwidth=2, fontcolor="{COLOR_S3_EDGE}"];

}}
'''

# ── Render PNG ────────────────────────────────────────────────────────────────
dst = Source(dot_graph, format='png').render(
    filename=os.path.expanduser('~/Desktop/demeter_agent_architecture'),
    view=False, cleanup=True
)
print("Diagram generated →", dst)