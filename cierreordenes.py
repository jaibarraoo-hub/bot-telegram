import os
import time
import math
import requests
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# TOKEN
# =========================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("Falta TOKEN en Render")

URL = f"https://api.telegram.org/bot{TOKEN}"

# =========================
# MENSAJES
# =========================
def send_msg(cid, text):
    try:
        requests.post(
            f"{URL}/sendMessage",
            json={"chat_id": cid, "text": text},
            timeout=20
        )
    except Exception as e:
        print("ERROR MSG:", e)

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
        print("ERROR PHOTO:", e)

# =========================
# PROCESAR
# =========================
def procesar(cid, archivo):

    try:

        df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = (
            df.columns.astype(str)
            .str.strip()
            .str.lower()
        )

        c_centro = "centro"
        c_inicio = "fecha de inicio extrema"
        c_fin = "fecha real de fin de la orden"
        c_texto = "texto breve"

        # =========================
        # FECHAS
        # =========================
        df[c_inicio] = pd.to_datetime(df[c_inicio], errors="coerce")
        df[c_fin] = pd.to_datetime(df[c_fin], errors="coerce")

        df = df.dropna(subset=[c_centro, c_inicio])

        # =========================
        # FILTROS
        # =========================
        if c_texto in df.columns:

            df[c_texto] = df[c_texto].astype(str).str.lower().str.strip()

            df = df[~df[c_texto].str.startswith("insp. semanal")]
            df = df[~df[c_texto].str.startswith("rev. estructura y pintura trimestral")]

        # =========================
        # FECHA BASE
        # =========================
        df["fecha"] = df[c_inicio].dt.date

        # =========================
        # LANZADAS
        # =========================
        lanzadas = df.groupby([c_centro, "fecha"]).size().reset_index(name="lanzadas")

        # =========================
        # CERRADAS
        # =========================
        cerradas = df.dropna(subset=[c_fin])
        cerradas = cerradas.groupby([c_centro, "fecha"]).size().reset_index(name="cerradas")

        # =========================
        # MERGE
        # =========================
        rep = pd.merge(lanzadas, cerradas, on=[c_centro, "fecha"], how="outer")

        rep["lanzadas"] = rep["lanzadas"].fillna(0).astype(int)
        rep["cerradas"] = rep["cerradas"].fillna(0).astype(int)

        rep = rep.dropna(subset=["fecha"])

        # =========================
        # REPORTE TEXTO
        # =========================
        msg = "📊 REPORTE DIARIO\n\n"

        for centro in rep[c_centro].unique():

            temp = rep[rep[c_centro] == centro]

            total_l = temp["lanzadas"].sum()
            total_c = temp["cerradas"].sum()

            estado = "🟢 OK"
            if total_l - total_c > 3:
                estado = "🔴 ALTA CARGA"
            elif total_l - total_c > 0:
                estado = "🟡 MEDIA"

            msg += f"🏢 {centro}\n"
            msg += f"{estado}\n"
            msg += f"📦 Lanzadas: {total_l}\n"
            msg += f"✅ Cerradas: {total_c}\n\n"

        send_msg(cid, msg)

        # =========================
        # DASHBOARD (SOLO 2 HOJAS FIJAS)
        # =========================

        centros = rep[c_centro].dropna().unique()

        # 🔥 FORZAR EXACTAMENTE 2 GRUPOS
        mid = math.ceil(len(centros) / 2)

        paginas = [
            centros[:mid],
            centros[mid:]  # SOLO 2 HOJAS
        ]

        pagina = 1

        for grupo in paginas:

            # 🔥 LIMPIEZA TOTAL DE GRAFICOS
            plt.close("all")
            plt.figure()

            cols = 2
            rows = math.ceil(len(grupo) / cols)

            plt.style.use("seaborn-v0_8-whitegrid")
            plt.figure(figsize=(14, rows * 4))

            for i, centro in enumerate(grupo, 1):

                temp = rep[rep[c_centro] == centro].copy()
                temp = temp.sort_values("fecha")

                ax = plt.subplot(rows, cols, i)
                ax.set_facecolor("#f7f9fc")

                # 🔵 LANZADAS
                ax.plot(
                    temp["fecha"],
                    temp["lanzadas"],
                    marker="o",
                    linewidth=2.5,
                    color="#1f77b4",
                    label="Lanzadas"
                )

                # 🟢 CERRADAS
                ax.plot(
                    temp["fecha"],
                    temp["cerradas"],
                    marker="o",
                    linewidth=2.5,
                    color="#2ca02c",
                    label="Cerradas"
                )

                ax.set_title(f"📊 {centro}")
                ax.tick_params(axis='x', rotation=45)
                ax.grid(True, alpha=0.3)
                ax.legend()

            plt.tight_layout()

            img = f"dashboard_{pagina}.png"
            plt.savefig(img, dpi=150)
            plt.close()

            send_photo(cid, img)
            os.remove(img)

            pagina += 1

    except Exception as e:
        send_msg(cid, f"❌ ERROR: {e}")

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
            ).json()

            for u in r.get("result", []):

                offset = u["update_id"] + 1

                m = u.get("message", {})
                cid = m.get("chat", {}).get("id")

                if m.get("text") == "/start":
                    send_msg(cid, "📊 Envía tu Excel")

                if "document" in m:

                    send_msg(cid, "⌛ Procesando archivo...")

                    file_id = m["document"]["file_id"]

                    info = requests.get(
                        f"{URL}/getFile",
                        params={"file_id": file_id}
                    ).json()

                    file_path = info["result"]["file_path"]

                    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

                    data = requests.get(file_url, timeout=60)

                    with open("temp.xlsx", "wb") as f:
                        f.write(data.content)

                    procesar(cid, "temp.xlsx")

                    os.remove("temp.xlsx")

        except Exception as e:
            print("LOOP ERROR:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
