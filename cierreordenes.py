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
        cerradas = df.dropna(subset=[c_fin]).groupby([c_centro, "dia_fin"]).size().reset_index(name="cerradas")

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
        # ATRASADAS (LIB KKMP NLIQ)
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

        for centro in centros:

            total_plan = len(df[(df[c_centro] == centro) & (df["dia_inicio"] <= limite)])
            total_real = len(df[(df[c_centro] == centro) & (df["dia_fin"] <= limite)])

            cumplimiento[centro] = (total_real / total_plan * 100) if total_plan > 0 else 0

        if len(centros) == 0:
            send_msg(cid, "❌ Sin datos")
            return

        # =========================
        # PAGINAS
        # =========================
        mid = max(1, math.ceil(len(centros) / 2))
        paginas = [centros[:mid], centros[mid:]]

        pagina = 1

        # =========================
        # ZONA HORARIA
        # =========================
        zona = pytz.timezone("America/Mexico_City")
        fecha_revision = datetime.now(zona).strftime("%d-%m-%Y %H:%M")

        send_msg(cid, "📊 Generando dashboards...")

        # =========================
        # GRAFICAS
        # =========================
        for grupo in paginas:

            plt.close("all")

            cols = 2
            rows = math.ceil(len(grupo) / cols)

            plt.style.use("seaborn-v0_8-whitegrid")
            fig = plt.figure(figsize=(14, rows * 4))

            # ENCABEZADO
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
                ax.plot(temp["fecha"], temp["lanzadas"], marker="o", linewidth=2.5, color="#1f77b4", label="Plan")

                # REAL
                ax.plot(temp["fecha"], temp["cerradas"], marker="o", linewidth=2.5, color="#2ca02c", label="Real")

                # NUMEROS
                for x, y in zip(temp["fecha"], temp["lanzadas"]):
                    ax.text(x, y + 0.5, str(y), fontsize=7, ha="center", color="#1f77b4")

                for x, y in zip(temp["fecha"], temp["cerradas"]):
                    ax.text(x, y - 0.9, str(y), fontsize=7, ha="center", color="#2ca02c")

                # ATRASADAS
                cant_atrasadas = len(atrasadas[atrasadas[c_centro] == centro])

                ax.text(
                    0.02,
                    0.92,
                    f"🔴 Atrasadas: {cant_atrasadas}",
                    transform=ax.transAxes,
                    fontsize=10,
                    color="red",
                    fontweight="bold",
                    bbox=dict(facecolor="white", alpha=0.85, edgecolor="red")
                )

                # CUMPLIMIENTO
                pct = round(cumplimiento[centro], 1)

                ax.text(
                    0.98,
                    0.95,
                    f"📈 Cumplimiento: {pct}%",
                    transform=ax.transAxes,
                    fontsize=9,
                    ha="right",
                    va="top",
                    bbox=dict(facecolor="white", alpha=0.85)
                )

                ax.set_title(f"📊 Plan vs Real - {centro}", fontsize=11, fontweight="bold")
                ax.tick_params(axis='x', rotation=45)
                ax.grid(True, alpha=0.3)
                ax.legend()

            plt.tight_layout(rect=[0, 0, 1, 0.93])

            img = f"dashboard_{pagina}.png"
            plt.savefig(img, dpi=150, bbox_inches="tight")
            plt.close()

            send_photo(cid, img)
            os.remove(img)

            pagina += 1

    except Exception as e:
        send_msg(cid, f"❌ ERROR: {e}")
        print("ERROR:", e)

# =========================
# BOT LOOP
# =========================
def main():

    offset = 0
    print("🚀 BOT EJECUTIVO RENDER SAFE ACTIVO")

    while True:

        try:

            r = requests.get(
                f"{URL}/getUpdates",
                params={"offset": offset, "timeout": 30},
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
                    send_msg(cid, "📊 Envía tu Excel SAP")

                if "document" in m:

                    send_msg(cid, "⌛ Procesando archivo...")

                    file_id = m["document"]["file_id"]

                    info = requests.get(
                        f"{URL}/getFile",
                        params={"file_id": file_id}
                    ).json()

                    file_path = info["result"]["file_path"]

                    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

                    file_data = requests.get(file_url, timeout=60)

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
