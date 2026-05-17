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
# PROCESO PRINCIPAL
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
        # FILTRO
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
        # PLAN VS REAL
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
        # FECHA
        # =========================
        zona = pytz.timezone("America/Mexico_City")
        fecha_revision = datetime.now(zona).strftime("%d-%m-%Y %H:%M")

        send_msg(cid, "📊 Generando dashboards...")

        # =========================
        # DASHBOARDS PRINCIPALES
        # =========================
        for grupo in paginas:

            plt.close("all")

            cols = 2
            rows = math.ceil(len(grupo) / cols)

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

                ax.plot(temp["fecha"], temp["lanzadas"], marker="o", color="#1f77b4", label="Plan")
                ax.plot(temp["fecha"], temp["cerradas"], marker="o", color="#2ca02c", label="Real")

                cant_atrasadas = len(atrasadas[atrasadas[c_centro] == centro])

                ax.text(0.02, 0.92, f"🔴 {cant_atrasadas}", transform=ax.transAxes, color="red")

                pct = round(cumplimiento[centro], 1)

                ax.text(0.98, 0.95, f"{pct}%", transform=ax.transAxes, ha="right")

                ax.set_title(f"{centro}")
                ax.legend()
                ax.grid(alpha=0.3)

            plt.tight_layout(rect=[0, 0, 1, 0.93])

            img = f"dashboard_{pagina}.png"

            plt.savefig(img, dpi=150, bbox_inches="tight")

            plt.close()

            send_photo(cid, img)

            os.remove(img)

            pagina += 1

        # =========================
        # 🔥 DASHBOARD EJECUTIVO DIRECCIÓN
        # =========================

        try:

            plt.close("all")

            total_ordenes = len(df)
            cerradas_total = len(df.dropna(subset=[c_fin]))
            atrasadas_total = len(atrasadas)
            abiertas_total = max(0, total_ordenes - cerradas_total)

            cumplimiento_global = round(
                (cerradas_total / total_ordenes * 100),
                1
            ) if total_ordenes > 0 else 0

            top_atrasos = (
                atrasadas.groupby(c_centro)
                .size()
                .sort_values(ascending=False)
                .head(5)
            )

            top_cierres = (
                df.dropna(subset=[c_fin])
                .groupby(c_centro)
                .size()
                .sort_values(ascending=False)
                .head(5)
            )

            fig = plt.figure(figsize=(18,10))

            fig.suptitle(
                "📊 DASHBOARD EJECUTIVO DIRECCIÓN",
                fontsize=20,
                fontweight="bold"
            )

            # DONUT
            ax1 = plt.subplot2grid((3,4), (0,0), rowspan=2)

            ax1.pie(
                [cerradas_total, atrasadas_total, abiertas_total],
                labels=["Cerradas", "Atrasadas", "Abiertas"],
                autopct='%1.1f%%',
                colors=["#16a34a", "#dc2626", "#2563eb"],
                wedgeprops=dict(width=0.45)
            )

            ax1.set_title("Estado General")

            # KPI
            ax2 = plt.subplot2grid((3,4), (0,1), colspan=3)
            ax2.axis("off")

            ax2.text(
                0.02,
                0.5,
                f"""
TOTAL: {total_ordenes}
CERRADAS: {cerradas_total}
ATRASADAS: {atrasadas_total}
ABIERTAS: {abiertas_total}
CUMPLIMIENTO: {cumplimiento_global}%
""",
                fontsize=16,
                fontweight="bold"
            )

            # ATRASOS
            ax3 = plt.subplot2grid((3,4), (1,1), colspan=3)

            if len(top_atrasos) > 0:
                ax3.barh(top_atrasos.index.astype(str), top_atrasos.values, color="#dc2626")
                ax3.set_title("Top Atrasos")

            else:
                ax3.text(0.5,0.5,"Sin atrasos",ha="center")
                ax3.axis("off")

            # CIERRES
            ax4 = plt.subplot2grid((3,4), (2,0), colspan=2)

            if len(top_cierres) > 0:
                ax4.bar(top_cierres.index.astype(str), top_cierres.values, color="#16a34a")
                ax4.set_title("Top Cierres")

            else:
                ax4.axis("off")

            # SEMAFORO
            ax5 = plt.subplot2grid((3,4), (2,2), colspan=2)
            ax5.axis("off")

            if cumplimiento_global >= 90:
                color = "#16a34a"
                estado = "EXCELENTE"
            elif cumplimiento_global >= 75:
                color = "#f59e0b"
                estado = "RIESGO"
            else:
                color = "#dc2626"
                estado = "CRÍTICO"

            ax5.text(0.5,0.6,f"{cumplimiento_global}%",ha="center",fontsize=40,color=color)
            ax5.text(0.5,0.25,estado,ha="center",fontsize=16)

            plt.tight_layout()

            img_exec = "dashboard_direccion.png"

            plt.savefig(img_exec, dpi=180, bbox_inches="tight")

            plt.close()

            send_photo(cid, img_exec)

            os.remove(img_exec)

        except Exception as e:
            print("ERROR DASH:", e)

    except Exception as e:
        send_msg(cid, f"❌ ERROR: {e}")
        print("ERROR:", e)

# =========================
# BOT LOOP
# =========================
def main():

    offset = 0

    print("🚀 BOT ACTIVO")

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

                    send_msg(cid, "⌛ Procesando...")

                    file_id = m["document"]["file_id"]

                    info = requests.get(f"{URL}/getFile", params={"file_id": file_id}).json()

                    file_path = info["result"]["file_path"]

                    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

                    file_data = requests.get(file_url, timeout=60)

                    with open("temp.xlsx", "wb") as f:
                        f.write(file_data.content)

                    procesar(cid, "temp.xlsx")

                    os.remove("temp.xlsx")

        except Exception as e:
            print("LOOP ERROR:", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
