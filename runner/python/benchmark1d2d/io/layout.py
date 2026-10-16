"""Map coordinates for a network that has none (the suite's generated SWMM and EPANET files).

Each node is placed at its longest distance along the links from the network's
upstream ends (nodes no link flows into), so a line of pipes is drawn as a
straight line at its true lengths; nodes at the same distance are spread
across, and independent parts of the network are stacked. The same rule as
the site's network viewer, written into the files so that they also open as a
map in EPA SWMM and EPANET.
"""

from __future__ import annotations


def layout(nodes: list[str], links: list[tuple[str, str, float | None]]) -> dict[str, tuple[float, float]]:
    lens = sorted(float(L) for _, _, L in links if L and L > 0)
    unit = lens[len(lens) // 2] if lens else 1.0
    out: dict[str, list] = {n: [] for n in nodes}
    inc = {n: 0 for n in nodes}
    adj: dict[str, list] = {n: [] for n in nodes}
    for a, b, L in links:
        if a not in out or b not in out:
            continue
        out[a].append((b, float(L) if L and L > 0 else unit))
        inc[b] += 1
        adj[a].append(b)
        adj[b].append(a)
    seen: dict[str, int] = {}
    comps: list[list[str]] = []
    for n in nodes:
        if n in seen:
            continue
        stack, comp = [n], []
        seen[n] = len(comps)
        while stack:
            u = stack.pop()
            comp.append(u)
            for w in adj[u]:
                if w not in seen:
                    seen[w] = len(comps)
                    stack.append(w)
        comps.append(comp)
    xy: dict[str, tuple[float, float]] = {}
    y0 = 0.0
    for comp in comps:
        dist = {u: (0.0 if inc[u] == 0 else float("-inf")) for u in comp}
        if all(v == float("-inf") for v in dist.values()):
            dist[comp[0]] = 0.0
        for _ in range(len(comp)):
            changed = False
            for u in comp:
                if dist[u] == float("-inf"):
                    continue
                for w, L in out[u]:
                    if dist[u] + L > dist[w] + 1e-9:
                        dist[w] = dist[u] + L
                        changed = True
            if not changed:
                break
        groups: dict[int, list[str]] = {}
        for u in comp:
            d = dist[u] if dist[u] != float("-inf") else 0.0
            dist[u] = d
            groups.setdefault(round(d / (unit * 0.25)), []).append(u)
        width = 1
        for g in groups.values():
            for i, u in enumerate(g):
                xy[u] = (round(dist[u], 6), round(y0 - (i - (len(g) - 1) / 2) * unit * 0.6, 6))
            width = max(width, len(g))
        y0 -= width * unit * 0.6 + unit * 0.8
    return xy


def coordinates_section(xy: dict[str, tuple[float, float]]) -> list[str]:
    return ["", "[COORDINATES]", ";;Node X-Coord Y-Coord"] + [f"{n} {x:.3f} {y:.3f}" for n, (x, y) in xy.items()]
