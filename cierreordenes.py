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
# PROCESAR EXCEL
# =========================
def procesar(cid, archivo):

    try:

        df = pd.read_excel(archivo, engine="openpyxl")

        # normalizar columnas
        df.columns = df.columns.astype(str).str.strip().str.lower()

        # =========================
        # COLUMNAS
        # =========================
        c_centro = "centro"
        c_inicio = "fecha de inicio extrema"
        c_fin = "fecha real de fin de la orden"
        c_status = "status del sistema"
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
        # DÍA
        # =========================
        df["dia"] = df[c_inicio].dt.date

        # =========================
        # LANZADAS
        # =========================
        lanzadas = df.groupby([c_centro, "dia"]).size().reset_index(name="lanzadas")

        # =========================
        # CERRADAS
        # =========================
        cerradas_df = df.dropna(subset=[c_fin])
        cerradas = cerradas_df.groupby([c_centro, "dia"]).size().reset_index(name="cerradas")

        # =========================
        # ATRASADAS (STATUS CORRECTO)
        # =========================
        abiertas = df[df[c_status] == "LIB. KKMP NLIQ"]
        abiertas = abiertas.groupby([c_centro, "dia"]).size().reset_index(name="atrasadas")

        # =========================
        # MERGE
        # =========================
        rep = pd.merge(lanzadas, cerradas, on=[c_centro, "dia"], how="outer")
        rep = pd.merge(rep, abiertas, on=[c_centro, "dia"], how="outer")

        rep = rep.fillna(0)

        rep["lanzadas"] = rep["lanzadas"].astype(int)
        rep["cerradas"] = rep["cerradas"].astype(int)
        rep["atrasadas"] = rep["atrasadas"].astype(int)

        # =========================
        # MENSAJE
        # =========================
        msg = "📊 REPORTE DIARIO\n\n"

        for centro in rep[c_centro].unique():

            temp = rep[rep[c_centro] == centro].copy()
            temp = temp.sort_values("dia")

            msg += f"🏢 {centro}\n\n"

            for _, r in temp.iterrows():

                msg += (
                    f"📅 {r['dia']}\n"
                    f"📦 Lanzadas: {r['lanzadas']}\n"
                    f"✅ Cerradas: {r['cerradas']}\n"
                    f"🔴 Atrasadas: {r['atrasadas']}\n\n"
                )

        send_msg(cid, msg)

        # =========================
        # DASHBOARD 2 PÁGINAS (SIN DUPLICAR)
        # =========================
        centros = rep[c_centro].unique()
        mid = math.ceil(len(centros) / 2)

        paginas = [centros[:mid], centros[mid:]]

        pagina = 1

        for grupo in paginas:

            rows = math.ceil(len(grupo) / 2)

            plt.style.use("seaborn-v0_8-whitegrid")
            plt.figure(figsize=(14, rows * 4))

            for i, centro in enumerate(grupo, 1):

                temp = rep[rep[c_centro] == centro].copy()
                temp = temp.sort_values("dia")

                ax = plt.subplot(rows, 2, i)
                ax.set_facecolor("#f7f9fc")

                # =========================
                # LÍNEAS
                # =========================
                ax.plot(temp["dia"], temp["lanzadas"],
                        marker="o", color="#1f77b4", linewidth=2.5, label="Lanzadas")

                ax.plot(temp["dia"], temp["cerradas"],
                        marker="o", color="#2ca02c", linewidth=2.5, label="Cerradas")

                ax.plot(temp["dia"], temp["atrasadas"],
                        marker="o", color="red", linewidth=2.5, label="Atrasadas")

                # =========================
                # ETIQUETAS ROJAS (ATRASADAS)
                # =========================
                for x, y in zip(temp["dia"], temp["atrasadas"]):

                    if y > 0:
                        ax.text(
                            x,
                            y + 0.4,
                            str(y),
                            fontsize=8,
                            ha="center",
                            color="red",
                            bbox=dict(facecolor="white", alpha=0.7, boxstyle="round")
                        )

                ax.set_title(f"📊 Dashboard - {centro}", fontweight="bold")
                ax.tick_params(axis='x', rotation=45)
                ax.grid(alpha=0.3)
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
    print("🚀 BOT FINAL ACTIVO")

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
            time.sleep(5)

if __name__ == "__main__":
    main()
