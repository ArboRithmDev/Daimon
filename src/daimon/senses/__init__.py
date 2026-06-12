"""Senses — the perception surfaces Daimon exposes over MCP.

Each sense is read-only and pull-driven: it answers a client request, it never
pushes or acts. The map of senses (locked in scoping):

    Vue            — screen snapshot (pixels). Sense #1, implemented.
    Touché passif  — full accessibility-tree snapshot. Stub.
    Touché actif   — probe a point/region of the a11y tree. Stub.
"""
