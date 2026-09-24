#!/usr/bin/env python3
"""Generate the Station B (close-interaction) lab-layout figure.

Matches the visual language of the seated Station A figure
(`lab-layout.png` / `lab-layout.svg`, Matplotlib v3.11). Does **not**
overwrite those files.

Usage (from repo root or this directory):

    python docs/figures/generate_lab_layout_close_interact.py

Outputs:

    docs/figures/lab-layout-close-interact.png
    docs/figures/lab-layout-close-interact.svg
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

# Same palette / type as docs/figures/lab-layout.png
PAINT = "#2c5f8a"
RGB = "#1a6fb5"
RGB_EDGE = "#0d3d66"
THERMAL = "#b33a3a"
THERMAL_EDGE = "#6b1a1a"
VERITY = "#c45c26"
INK = "#333333"
MUTED = "#666666"
GHOST = "#8a9299"
BG = "#fafafa"
GRID = "#b0b0b0"

OUT_DIR = Path(__file__).resolve().parent


def _style_ax(ax) -> None:
    ax.set_facecolor("white")
    ax.grid(True, linestyle=(0, (1, 1.65)), color=GRID, alpha=0.4, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color("black")


def _dim_arrow(ax, x1, y1, x2, y2, text, *, color=INK, fs=7.5, text_off=(0.0, 0.07), ha="center"):
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="<->", color=color, lw=1.05),
        zorder=6,
    )
    ax.text(
        (x1 + x2) / 2 + text_off[0],
        (y1 + y2) / 2 + text_off[1],
        text,
        ha=ha,
        va="center",
        fontsize=fs,
        color=color,
        zorder=6,
    )


def _dual_cameras(ax, x, y, *, scale=1.0, z=6, alpha=1.0):
    """RGB + PI 450i boxes on a short rigid bar (side elevation)."""
    w, h = 0.058 * scale, 0.040 * scale
    gap = 0.006
    ax.add_patch(
        Rectangle(
            (x - 0.018, y - 0.014),
            2 * w + gap + 0.036,
            0.014,
            facecolor="#3a3a3a",
            edgecolor="#222222",
            lw=0.6,
            alpha=alpha,
            zorder=z,
        )
    )
    ax.add_patch(
        Rectangle(
            (x, y),
            w,
            h,
            facecolor=RGB,
            edgecolor=RGB_EDGE,
            lw=0.7,
            alpha=alpha,
            zorder=z + 1,
        )
    )
    ax.add_patch(
        Rectangle(
            (x + w + gap, y),
            w,
            h,
            facecolor=THERMAL,
            edgecolor=THERMAL_EDGE,
            lw=0.7,
            alpha=alpha,
            zorder=z + 1,
        )
    )
    return x + w / 2, y + h * 0.4


def draw_side_elevation(ax) -> None:
    _style_ax(ax)
    ax.set_xlim(-0.52, 2.10)
    ax.set_ylim(-0.06, 2.42)
    ax.set_aspect("equal")
    ax.set_xlabel("Distance from painting plane (m)")
    ax.set_ylabel("Height above floor (m)")
    ax.set_title("Side elevation (close-interaction subject)", fontsize=11, pad=10)
    ax.set_xticks([0.0, 0.5, 1.0, 1.5, 2.0])
    ax.set_yticks([0.0, 0.5, 1.0, 1.5, 2.0])

    paint_bottom, paint_h = 1.00, 0.90
    paint_top = paint_bottom + paint_h
    paint_center = paint_bottom + paint_h / 2.0

    # Canvas plane
    ax.add_patch(
        Rectangle(
            (-0.016, paint_bottom),
            0.032,
            paint_h,
            facecolor=PAINT,
            edgecolor=PAINT,
            lw=0.6,
            zorder=3,
        )
    )
    ax.text(
        -0.07,
        paint_center,
        "Painting  70×90 cm",
        color=PAINT,
        fontsize=7.4,
        ha="right",
        va="center",
        rotation=90,
    )
    ax.text(0.06, 0.94, "lower edge ≈ 1.00 m", fontsize=6.8, color=PAINT, ha="left", va="top")

    # Station B: wall plate / easel-back + short rigid riser (not a floor-to-ceiling pole)
    plate_x = -0.20
    ax.add_patch(
        Rectangle(
            (plate_x, 1.68),
            0.09,
            0.28,
            facecolor="#7a7a7a",
            edgecolor="#444444",
            lw=0.7,
            zorder=3,
        )
    )
    ax.add_patch(
        Rectangle((plate_x - 0.02, 0.00), 0.10, 0.035, facecolor="#555555", edgecolor="#333333", lw=0.5, zorder=2)
    )
    ax.plot([plate_x + 0.03, plate_x + 0.03], [0.035, 0.22], color="#888888", lw=1.6, zorder=2)
    ax.plot([plate_x + 0.045, plate_x + 0.045], [1.88, 2.00], color="#333333", lw=2.8, zorder=4)
    ax.plot([plate_x + 0.045, 0.16], [2.00, 2.00], color="#222222", lw=3.0, solid_capstyle="butt", zorder=5)
    cam_lens = _dual_cameras(ax, 0.02, 2.005, scale=1.25, z=7)

    ax.text(
        0.22,
        2.28,
        "RGB + PI 450i dual bar",
        fontsize=8,
        color=INK,
        ha="left",
    )
    ax.text(
        0.22,
        2.18,
        "peek over top · co-mounted · QR plate on bar",
        fontsize=7,
        color=MUTED,
        ha="left",
    )
    ax.text(
        -0.48,
        1.58,
        "Station B mount\nwall plate / easel-back\n+ short rigid riser\n(no floppy boom)",
        fontsize=6.5,
        color=MUTED,
        ha="left",
        va="top",
        linespacing=1.25,
    )

    # Standing / leaning subject — two legs + filled torso (not a stick-A)
    left_x, right_x = 0.47, 0.57
    hip_y, shoulder_y = 0.90, 1.34
    head = (0.48, 1.58)
    ax.plot([left_x, left_x], [0.0, hip_y], color=INK, lw=2.3, zorder=4)
    ax.plot([right_x, right_x], [0.0, hip_y], color=INK, lw=2.3, zorder=4)
    ax.plot([left_x, right_x], [hip_y, hip_y], color=INK, lw=2.0, zorder=4)
    ax.add_patch(
        Rectangle(
            (0.445, hip_y),
            0.15,
            shoulder_y - hip_y,
            facecolor="#ececec",
            edgecolor=INK,
            lw=1.5,
            zorder=4,
        )
    )
    ax.add_patch(Circle(head, 0.095, fill=False, edgecolor=INK, lw=2.0, zorder=5))
    ax.plot([0.50, head[0]], [shoulder_y, head[1] - 0.095], color=INK, lw=1.7, zorder=4)
    hand_near = (0.055, 1.48)
    hand_far = (0.10, 1.26)
    ax.plot([0.445, 0.24, hand_near[0]], [1.28, 1.34, hand_near[1]], color=INK, lw=2.0, zorder=5)
    ax.plot([0.445, 0.26, hand_far[0]], [1.20, 1.16, hand_far[1]], color=INK, lw=1.6, alpha=0.85, zorder=4)
    ax.add_patch(Circle(hand_near, 0.026, facecolor=INK, edgecolor=INK, zorder=6))
    ax.add_patch(Circle(hand_far, 0.022, facecolor=INK, edgecolor=INK, alpha=0.85, zorder=5))
    ax.annotate(
        "hand(s) over\npainting surface",
        xy=hand_near,
        xytext=(0.78, 1.20),
        fontsize=7.2,
        color=INK,
        arrowprops=dict(arrowstyle="->", color=INK, lw=0.8),
        linespacing=1.2,
    )
    ax.text(0.72, 0.36, "Subject (standing / leaning)", fontsize=8, color=INK, ha="left")
    ax.text(0.72, 0.24, "close to canvas", fontsize=7, color=MUTED, ha="left")

    # Verity
    ax.add_patch(Rectangle((0.42, 1.22), 0.042, 0.032, facecolor=VERITY, edgecolor=VERITY, zorder=6))
    ax.annotate(
        "Verity Sense\n(arm PPG)",
        xy=(0.44, 1.23),
        xytext=(0.78, 0.86),
        fontsize=7,
        color=VERITY,
        arrowprops=dict(arrowstyle="->", color=VERITY, lw=0.7),
    )

    # Look-down axis (≈38°)
    ax.annotate(
        "",
        xy=head,
        xytext=cam_lens,
        arrowprops=dict(arrowstyle="->", color=RGB, lw=1.35),
        zorder=5,
    )
    ax.text(0.20, 1.90, "look-down ≈ 30–45°", fontsize=7.4, color=RGB, ha="left")
    ax.text(0.20, 1.80, "camera → face ≈ 0.4–0.8 m", fontsize=7.4, color=RGB, ha="left")

    # Gaze to painting (same dashed language as seated figure)
    ax.plot(
        [head[0] - 0.09, 0.016],
        [head[1] - 0.02, paint_center],
        linestyle="--",
        color="#5a8f4a",
        lw=1.0,
        zorder=3,
    )
    ax.text(0.12, 1.58, "gaze → painting", fontsize=6.8, color="#5a8f4a")

    _dim_arrow(
        ax,
        0.02,
        0.52,
        0.52,
        0.52,
        "subject close to canvas",
        fs=7.2,
        text_off=(0.58, 0.00),
        ha="left",
    )

    # Floor marks (subject B + Station B)
    ax.plot([-0.22, -0.10], [0.0, 0.0], color=VERITY, lw=3.4, solid_capstyle="butt", zorder=5)
    ax.plot([0.45, 0.60], [0.0, 0.0], color=VERITY, lw=3.4, solid_capstyle="butt", zorder=5)
    ax.plot(-0.16, 0.0, marker="s", color=VERITY, markersize=4.5, zorder=6)
    ax.plot(0.52, 0.0, marker="s", color=VERITY, markersize=4.5, zorder=6)
    ax.text(-0.16, 0.08, "floor marks\n(Station B)", fontsize=6.3, color=VERITY, ha="center", va="bottom")
    ax.text(0.52, 0.08, "floor marks\n(subject B)", fontsize=6.3, color=VERITY, ha="center", va="bottom")

    # QR move note (do not draw Station A hardware on top of the close subject)
    ax.annotate(
        "",
        xy=(0.10, 2.00),
        xytext=(1.15, 1.55),
        arrowprops=dict(
            arrowstyle="->",
            color=GHOST,
            lw=1.15,
            linestyle="dashed",
            connectionstyle="arc3,rad=0.12",
        ),
        zorder=3,
    )
    ax.add_patch(
        FancyBboxPatch(
            (1.12, 1.38),
            0.90,
            0.34,
            boxstyle="round,pad=0.02,rounding_size=0.03",
            facecolor="white",
            edgecolor="#cccccc",
            lw=0.8,
            zorder=6,
        )
    )
    ax.text(
        1.16,
        1.62,
        "QR move from Station A\n"
        "(seated frontal; lab-layout.png)\n"
        "Carry the whole dual bar — do not\n"
        "loosen cameras on the bar.",
        fontsize=6.8,
        color=MUTED,
        ha="left",
        va="top",
        zorder=7,
        linespacing=1.25,
    )

    ax.add_patch(
        FancyBboxPatch(
            (1.12, 1.95),
            0.90,
            0.22,
            boxstyle="round,pad=0.02,rounding_size=0.03",
            facecolor="#fff8f8",
            edgecolor="#e0c8c8",
            lw=0.8,
            zorder=6,
        )
    )
    ax.text(
        1.16,
        2.12,
        "Facial thermal ROIs\n(not canvas IR)",
        fontsize=7.2,
        color=THERMAL,
        ha="left",
        va="top",
        zorder=7,
    )


def draw_plan_view(ax) -> None:
    _style_ax(ax)
    ax.set_xlim(-0.52, 2.10)
    ax.set_ylim(-1.05, 1.10)
    ax.set_aspect("equal")
    ax.set_xlabel("Distance from painting plane (m)")
    ax.set_ylabel("Lateral (m)")
    ax.set_title("Plan view (from above)", fontsize=11, pad=10)
    ax.set_xticks([0.0, 0.5, 1.0, 1.5, 2.0])

    half_w = 0.35
    ax.plot([0, 0], [-half_w, half_w], color=PAINT, lw=5.5, solid_capstyle="butt", zorder=3)
    ax.text(-0.06, 0.55, "Painting", color=PAINT, fontsize=7.5, ha="right")
    ax.text(-0.06, 0.44, "width 0.70 m", color=PAINT, fontsize=6.8, ha="right")

    # Station B mount behind the canvas; cameras peek over the top edge
    ax.add_patch(
        Rectangle(
            (-0.20, -0.09),
            0.12,
            0.18,
            facecolor="#888888",
            edgecolor="#555555",
            lw=0.7,
            zorder=2,
        )
    )
    ax.plot(0.04, 0.028, marker="s", color=RGB, markersize=8, markeredgecolor=RGB_EDGE, zorder=6)
    ax.plot(0.04, -0.028, marker="s", color=THERMAL, markersize=8, markeredgecolor=THERMAL_EDGE, zorder=6)
    ax.text(-0.22, -0.28, "Station B\nmount", fontsize=7, color=MUTED, ha="center")
    ax.text(0.12, 0.16, "RGB + thermal\npeek over top", fontsize=7, color=INK, ha="left")

    # Subject + hands
    subj = (0.48, 0.0)
    ax.add_patch(Circle(subj, 0.125, fill=False, edgecolor=INK, lw=1.7, zorder=4))
    ax.plot(*subj, marker="o", color=INK, markersize=4, zorder=5)
    ax.plot(0.07, 0.055, marker="o", color=INK, markersize=5.5, zorder=5)
    ax.plot(0.09, -0.05, marker="o", color=INK, markersize=5, zorder=5)
    ax.plot([0.07, subj[0]], [0.055, 0.035], color=INK, lw=1.15, zorder=3)
    ax.plot([0.09, subj[0]], [-0.05, -0.03], color=INK, lw=1.0, zorder=3, alpha=0.85)
    ax.text(0.68, -0.38, "Subject standing\n/ leaning close", fontsize=8, color=INK, ha="left")
    ax.text(0.07, 0.14, "hands", fontsize=6.6, color=INK)

    # Floor marks at both stations / subject
    for xm in (-0.13, 0.48):
        ax.plot([xm, xm], [-0.20, -0.155], color=VERITY, lw=2.3, zorder=4)
        ax.plot([xm, xm], [0.155, 0.20], color=VERITY, lw=2.3, zorder=4)
    ax.text(1.92, 0.0, "floor\nmarks", fontsize=7, color=VERITY, ha="left", va="center")

    _dim_arrow(ax, 0.0, -0.58, 0.48, -0.58, "subject close to canvas", fs=7.3, text_off=(0.20, -0.10))
    _dim_arrow(
        ax,
        0.04,
        0.62,
        0.48,
        0.62,
        "≈ 0.4–0.8 m to face",
        color=RGB,
        fs=7.4,
        text_off=(0.55, 0.0),
        ha="left",
    )

    # Ghost Station A offset so it does not sit on the close subject
    ax.plot(0.60, 0.42, marker="s", color=RGB, markersize=6, alpha=0.40, zorder=2)
    ax.plot(0.66, 0.42, marker="s", color=THERMAL, markersize=6, alpha=0.40, zorder=2)
    ax.text(0.72, 0.42, "Station A (ghost; bar moved here)", fontsize=6.5, color=GHOST, ha="left", va="center")
    ax.annotate(
        "",
        xy=(0.06, 0.06),
        xytext=(0.60, 0.40),
        arrowprops=dict(arrowstyle="->", color=GHOST, lw=1.0, linestyle="dashed"),
        zorder=2,
    )

    ax.add_patch(
        FancyBboxPatch(
            (1.12, 0.52),
            0.92,
            0.50,
            boxstyle="round,pad=0.02,rounding_size=0.03",
            facecolor="white",
            edgecolor="#cccccc",
            lw=0.8,
            zorder=6,
        )
    )
    ax.text(
        1.16,
        0.98,
        "Same PI 450i + Blackfly bar\n"
        "as Station A; QR dock only.\n"
        "IR lens: face-sharp at 0.4–0.8 m.\n"
        "Two marked stations — do not\n"
        "cover both phases from one spot.",
        fontsize=7.0,
        color=INK,
        ha="left",
        va="top",
        zorder=7,
        linespacing=1.28,
    )

    legend_handles = [
        Line2D([0], [0], color=PAINT, lw=4, label="Painting"),
        Line2D([0], [0], marker="s", color=RGB, lw=0, markersize=7, label="RGB (Blackfly S)"),
        Line2D([0], [0], marker="s", color=THERMAL, lw=0, markersize=7, label="Thermal (PI 450i)"),
        Line2D([0], [0], marker="s", color=VERITY, lw=0, markersize=7, label="Verity / floor marks"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower right",
        fontsize=7,
        framealpha=0.95,
        edgecolor="#cccccc",
        fancybox=True,
    )


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": BG,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.labelsize": 9,
        }
    )

    fig, (ax_side, ax_plan) = plt.subplots(
        1,
        2,
        figsize=(12.93, 6.53),
        gridspec_kw={"wspace": 0.22},
    )
    draw_side_elevation(ax_side)
    draw_plan_view(ax_plan)

    fig.suptitle(
        "quantum-platform — sample lab layout (close interaction, provisional geometry)",
        fontsize=12.5,
        fontweight="bold",
        y=0.98,
    )
    fig.text(
        0.5,
        0.012,
        "Station B only: dual IR+RGB bar behind / above the painting, looking down at the face. "
        "Seated viewing is Station A (lab-layout.png). Verify distances in the room.",
        ha="center",
        va="bottom",
        fontsize=8,
        color=MUTED,
    )

    fig.subplots_adjust(left=0.065, right=0.985, top=0.88, bottom=0.11)
    png = OUT_DIR / "lab-layout-close-interact.png"
    svg = OUT_DIR / "lab-layout-close-interact.svg"
    fig.savefig(png, dpi=160)
    fig.savefig(svg)
    plt.close(fig)
    print(f"wrote {png}")
    print(f"wrote {svg}")


if __name__ == "__main__":
    main()
