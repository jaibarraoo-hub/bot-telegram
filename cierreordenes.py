# =========================
# DASHBOARD DIRECTIVO
# =========================
plt.close("all")

fig2, axs = plt.subplots(
    2,
    2,
    figsize=(14, 10)
)

fig2.patch.set_facecolor("#111111")

fig2.suptitle(
    "📊 Dashboard Ejecutivo Dirección",
    fontsize=20,
    fontweight="bold",
    color="white"
)

total_ot = len(df)

total_cerradas = len(
    df.dropna(subset=[c_fin])
)

total_atrasadas = len(atrasadas)

cumpl_global = round(
    (total_cerradas / total_ot) * 100,
    1
) if total_ot > 0 else 0

# =========================
# DONUT EJECUTIVO 3D
# =========================
porc_atrasadas = round(
    (total_atrasadas / total_ot) * 100,
    1
) if total_ot > 0 else 0

sizes = [
    total_atrasadas,
    total_ot - total_atrasadas
]

colors = [
    "#ff3b30",
    "#2ecc71"
]

wedges, texts = axs[0, 0].pie(
    sizes,
    startangle=90,
    colors=colors,
    shadow=True,
    wedgeprops=dict(
        width=0.42,
        edgecolor="#111111",
        linewidth=2
    )
)

# TEXTO CENTRAL
axs[0, 0].text(
    0,
    0.08,
    f"{porc_atrasadas}%",
    ha='center',
    va='center',
    fontsize=28,
    color="white",
    fontweight='bold'
)

axs[0, 0].text(
    0,
    -0.18,
    "OT ATRASADAS",
    ha='center',
    va='center',
    fontsize=11,
    color="#cccccc",
    fontweight='bold'
)

axs[0, 0].set_title(
    "Indicador Ejecutivo",
    color="white",
    fontsize=15,
    fontweight="bold"
)

# =========================
# TOP ATRASADAS
# =========================
atr_centro = (
    atrasadas
    .groupby(c_centro)
    .size()
    .sort_values(ascending=False)
    .head(5)
)

axs[0, 1].bar(
    atr_centro.index.astype(str),
    atr_centro.values,
    color="#ff4d4d"
)

axs[0, 1].set_title(
    "Top Atrasadas",
    color="white",
    fontsize=14,
    fontweight="bold"
)

axs[0, 1].tick_params(
    axis='x',
    rotation=20,
    colors='white'
)

axs[0, 1].tick_params(
    axis='y',
    colors='white'
)

# =========================
# KPI TEXTO
# =========================
axs[1, 0].axis("off")

texto = f"""
OT Totales: {total_ot}

OT Cerradas: {total_cerradas}

OT Atrasadas: {total_atrasadas}

Cumplimiento Global:
{cumpl_global}%
"""

axs[1, 0].text(
    0.05,
    0.5,
    texto,
    fontsize=18,
    color="white",
    fontweight="bold",
    va="center"
)

# =========================
# TOP CIERRES
# =========================
cierres = (
    df.dropna(subset=[c_fin])
    .groupby(c_centro)
    .size()
    .sort_values(ascending=False)
    .head(5)
)

axs[1, 1].barh(
    cierres.index.astype(str),
    cierres.values,
    color="#3498db"
)

axs[1, 1].set_title(
    "Top Cierres",
    color="white",
    fontsize=14,
    fontweight="bold"
)

axs[1, 1].tick_params(
    axis='x',
    colors='white'
)

axs[1, 1].tick_params(
    axis='y',
    colors='white'
)

# =========================
# ESTILO GENERAL
# =========================
for ax in axs.flat:

    ax.set_facecolor("#1c1c1c")

    for spine in ax.spines.values():
        spine.set_color("white")

plt.tight_layout(
    rect=[0, 0, 1, 0.95]
)

img2 = "dashboard_directivo.png"

plt.savefig(
    img2,
    dpi=180,
    bbox_inches="tight",
    facecolor=fig2.get_facecolor()
)

plt.close()

send_photo(cid, img2)

os.remove(img2)
