"""Schematic coordinates for generated network files."""

from __future__ import annotations

from benchmark1d2d.io.layout import coordinates_section, layout


def test_chain_is_a_straight_line_at_true_lengths():
    xy = layout(["A", "B", "C"], [("A", "B", 50.0), ("B", "C", 30.0)])
    assert xy == {"A": (0.0, 0.0), "B": (50.0, 0.0), "C": (80.0, 0.0)}


def test_branches_spread_and_lines_stack():
    xy = layout(["R", "1", "2", "X", "Y"], [("R", "1", 10.0), ("R", "2", 10.0), ("X", "Y", 10.0)])
    assert xy["1"][0] == xy["2"][0] == 10.0 and xy["1"][1] != xy["2"][1]
    assert xy["X"][1] < min(xy["1"][1], xy["2"][1])  # the second line sits below the first


def test_every_node_gets_a_row():
    xy = layout(["A", "B", "lone"], [("A", "B", None)])
    lines = coordinates_section(xy)
    assert lines[1] == "[COORDINATES]" and len(lines) == 3 + 3
