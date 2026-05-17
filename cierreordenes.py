import os
import time
import math
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import pytz

# =========================
# TOKEN
# =========================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ Falta TOKEN en variables de entorno")
    raise SystemExit(1)

URL = f"https://api.telegram.org/bot{TOKEN}"

# =========================
# TELEGRAM
# =========================
def send_msg(cid, text):
    try:
        requests.post(
            f"{URL}/sendMessage",
            json={"chat_id": cid, "text": text},
            timeout=20
        )
    except Exception as e:
        print("MSG ERROR:", e)

def send_photo(cid, path):
    try:
        with open(path, "rb") as img:
            requests.post(
                f"{URL}/sendPhoto",
                data={"chat_id": cid},
                files={"photo": img},
                timeout=60
            )
    except Exception as e:
        print("PHOTO ERROR:", e)

# =========================
# PROCESO
# =========================
def procesar(cid, archivo):

    try:

        send_msg(cid, "📥 Leyendo archivo...")

        df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = df.columns.astype(str).str.strip().str.lower()

        c_centro = "centro"
        c_inicio = "fecha de inicio extrema"
        c_fin = "fecha real de fin de la orden"
        c_texto = "texto breve"
        c_status = "status del sistema"

        # =========================
        # FECHAS
        # =========================
        df[c_inicio] = pd.to_datetime(df[c_inicio], errors="coerce")
        df[c_fin] = pd.to_datetime(df[c_fin], errors="coerce")

        df = df.dropna(subset=[c_centro, c_inicio])

        # =========================
        # FILTRO SOLO TRIMESTRALES FUERA
        # =========================
        if c_texto in df.columns:

            df[c_texto] = df[c_texto].astype(str).str.lower().str.strip()

            df = df[
                ~df[c_texto].str.startswith(
                    "rev. estructura y pintura trimestral"
                )
            ]

        # =========================
        # FECHAS BASE
        # =========================
        df["dia_inicio"] = df[c_inicio].dt.date
        df["dia_fin"] = df[c_fin].dt.date

        # =========================
        # PLAN / REAL
        # =========================
        lanzadas = df.groupby([c_centro, "dia_inicio"]).size().reset_index(name="lanzadas")

        cerradas = (
            df.dropna(subset=[c_fin])
            .groupby([c_centro, "dia_fin"])
            .size()
            .reset_index(name="cerradas")
        )

        rep = pd.merge(
            lanzadas,
            cerradas,
            left_on=[c_centro, "dia_inicio"],
            right_on=[c_centro, "dia_fin"],
            how="outer"
        )

        rep["lanzadas"] = rep["lanzadas"].fillna(0).astype(int)
        rep["cerradas"] = rep["cerradas"].fillna(0).astype(int)

        rep["fecha"] = rep["dia_inicio"].combine_first(rep["dia_fin"])

        rep = rep.dropna(subset=["fecha"])

        # =========================
        # ATRASADAS
        # =========================
        hoy = pd.Timestamp.now().date()

        limite = hoy - pd.Timedelta(days=1)

        atrasadas = df[
            (df[c_status].astype(str).str.strip().str.upper() == "LIB. KKMP NLIQ")
            &
            (df["dia_inicio"] <= limite)
        ]

        # =========================
        # KPI CUMPLIMIENTO
        # =========================
        cumplimiento = {}

        centros = rep[c_centro].dropna().unique()

        centros = list(dict.fromkeys(centros))

        if len(centros) == 0:
            send_msg(cid, "❌ Sin datos")
            return

        for centro in centros:

            total_plan = len(
                df[
                    (df[c_centro] == centro)
                    &
                    (df["dia_inicio"] <= limite)
                ]
            )

            total_real = len(
                df[
                    (df[c_centro] == centro)
                    &
                    (df["dia_fin"] <= limite)
                ]
            )

            cumplimiento[centro] = (
                (total_real / total_plan * 100)
                if total_plan > 0 else 0
            )

        # =========================
        # PAGINAS
        # =========================
        paginas = [centros]

        pagina = 1

        # =========================
        # ZONA HORARIA
        # =========================
        zona = pytz.timezone("America/Mexico_City")

        fecha_revision = datetime.now(zona).strftime("%d-%m-%Y %H:%M")

        send_msg(cid, "📊 Generando dashboards...")

        # =========================
        # GRAFICAS OPERATIVAS
        # =========================
        for grupo in paginas:

            plt.close("all")

            cols = 2
            rows = math.ceil(len(grupo) / cols)

            plt.style.use("seaborn-v0_8-whitegrid")

            fig = plt.figure(figsize=(14, rows * 4))

            fig.suptitle(
                f"Dashboard Ejecutivo SAP | Actualización: {fecha_revision}",
                fontsize=15,
                fontweight="bold"
            )

            for i, centro in enumerate(grupo, 1):

                temp = rep[rep[c_centro] == centro].copy()

                temp = temp.sort_values("fecha")

                ax = plt.subplot(rows, cols, i)

                ax.set_facecolor("#f7f9fc")

                # PLAN
                ax.plot(
                    temp["fecha"],
                    temp["lanzadas"],
                    marker="o",
                    linewidth=2.5,
                    color="#1f77b4",
                    label="Plan"
                )

                # REAL
                ax.plot(
                    temp["fecha"],
                    temp["cerradas"],
                    marker="o",
                    linewidth=2.5,
                    color="#2ca02c",
                    label="Real"
                )

                # NUMEROS PLAN
                for x, y in zip(temp["fecha"], temp["lanzadas"]):

                    ax.text(
                        x,
                        y + 0.5,
                        str(y),
                        fontsize=7,
                        ha="center",
                        color="#1f77b4"
                    )

                # NUMEROS REAL
                for x, y in zip(temp["fecha"], temp["cerradas"]):

                    ax.text(
                        x,
                        y - 0.9,
                        str(y),
                        fontsize=7,
                        ha="center",
                        color="#2ca02c"
                    )

                # ATRASADAS
                cant_atrasadas = len(
                    atrasadas[
                        atrasadas[c_centro] == centro
                    ]
                )

                ax.text(
                    0.02,
                    0.92,
                    f"🔴 Atrasadas: {cant_atrasadas}",
                    transform=ax.transAxes,
                    fontsize=10,
                    color="red",
                    fontweight="bold",
                    bbox=dict(
                        facecolor="white",
                        alpha=0.85,
                        edgecolor="red"
                    )
                )

                # KPI
                pct = round(cumplimiento[centro], 1)

                ax.text(
                    0.98,
                    0.95,
                    f"📈 Cumplimiento: {pct}%",
                    transform=ax.transAxes,
                    fontsize=9,
                    ha="right",
                    va="top",
                    bbox=dict(
                        facecolor="white",
                        alpha=0.85
                    )
                )

                ax.set_title(
                    f"📊 Plan vs Real - {centro}",
                    fontsize=11,
                    fontweight="bold"
                )

                ax.tick_params(
                    axis='x',
                    rotation=45
                )

                ax.grid(True, alpha=0.3)

                ax.legend()

            plt.tight_layout(rect=[0, 0, 1, 0.93])

            img = f"dashboard_{pagina}.png"

            plt.savefig(
                img,
                dpi=150,
                bbox_inches="tight"
            )

            plt.close()

            send_photo(cid, img)

            os.remove(img)

            pagina += 1

        # =========================
        # DASHBOARD DIRECTIVO
        # =========================
        plt.close("all")

        fig2, axs = plt.subplots(2, 2, figsize=(14, 10))

        fig2.patch.set_facecolor("#111111")

        fig2.suptitle(
            "📊 Dashboard Ejecutivo Dirección",
            fontsize=20,
            fontweight="bold",
            color="white"
        )

        total_ot = len(df)

        total_cerradas = len(df.dropna(subset=[c_fin]))

        total_atrasadas = len(atrasadas)

        cumpl_global = round(
            (total_cerradas / total_ot) * 100,
            1
        ) if total_ot > 0 else 0

        # =========================
        # PIE
        # =========================
        axs[0, 0].pie(
            [total_cerradas, total_ot - total_cerradas],
            labels=["Cerradas", "Pendientes"],
            autopct='%1.1f%%',
            colors=["#2ecc71", "#e74c3c"],
            textprops={
                'color': "white",
                'fontsize': 11
            }
        )

        axs[0, 0].set_title(
            "Estado OT",
            color="white",
            fontsize=14,
            fontweight="bold"
        )

        # =========================
        # ATRASADAS
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

        axs[0, 1].tick_params(axis='x', rotation=20, colors='white')
        axs[0, 1].tick_params(axis='y', colors='white')

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

        axs[1, 1].tick_params(axis='x', colors='white')
        axs[1, 1].tick_params(axis='y', colors='white')

        # =========================
        # ESTILO GENERAL
        # =========================
        for ax in axs.flat:

            ax.set_facecolor("#1c1c1c")

            for spine in ax.spines.values():
                spine.set_color("white")

        plt.tight_layout(rect=[0, 0, 1, 0.95])

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

    except Exception as e:

        send_msg(cid, f"❌ ERROR: {e}")

        print("ERROR:", e)

# =========================
# BOT LOOP
# =========================
def main():

    offset = 0

    print("🚀 BOT EJECUTIVO ACTIVO")

    while True:

        try:

            r = requests.get(
                f"{URL}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": 30
                },
                timeout=40
            )

            data = r.json()

            for u in data.get("result", []):

                offset = u["update_id"] + 1

                m = u.get("message", {})

                cid = m.get("chat", {}).get("id")

                if not cid:
                    continue

                if m.get("text") == "/start":

                    send_msg(
                        cid,
                        "📊 Envía tu Excel SAP"
                    )

                if "document" in m:

                    send_msg(
                        cid,
                        "⌛ Procesando archivo..."
                    )

                    file_id = m["document"]["file_id"]

                    info = requests.get(
                        f"{URL}/getFile",
                        params={"file_id": file_id}
                    ).json()

                    file_path = info["result"]["file_path"]

                    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

                    file_data = requests.get(
                        file_url,
                        timeout=60
                    )

                    local = "temp.xlsx"

                    with open(local, "wb") as f:
                        f.write(file_data.content)

                    procesar(cid, local)

                    os.remove(local)

        except Exception as e:

            print("LOOP ERROR:", e)

            time.sleep(3)

if __name__ == "__main__":
    main()
