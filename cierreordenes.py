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
# PROCESAR
# =========================
def procesar(cid, archivo):

    try:

        df = pd.read_excel(archivo, engine="openpyxl")

        df.columns = df.columns.astype(str).str.strip().str.lower()

        c_centro = "centro"
        c_inicio = "fecha de inicio extrema"
        c_fin = "fecha real de fin de la orden"
        c_status = "status del sistema"

        # =========================
        # FECHAS
        # =========================
        df[c_inicio] = pd.to_datetime(df[c_inicio], errors="coerce")
        df[c_fin] = pd.to_datetime(df[c_fin], errors="coerce")

        df = df.dropna(subset=[c_centro, c_inicio])

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
        # ATRASADAS (SOLO TEXTO)
        # =========================
        abiertas = df[df[c_status] == "LIB. KKMP NLIQ"]
        atrasadas_por_centro = abiertas.groupby(c_centro).size().reset_index(name="atrasadas")

        # =========================
        # MERGE SOLO PARA GRAFICA
        # =========================
        rep = pd.merge(lanzadas, cerradas, on=[c_centro, "dia"], how="outer")
        rep = rep.fillna(0)

        rep["lanzadas"] = rep["lanzadas"].astype(int)
        rep["cerradas"] = rep["cerradas"].astype(int)

        # =========================
        # MENSAJE
        # =========================
        msg = "📊 REPORTE DIARIO\n\n"

        for c in rep[c_centro].unique():

            msg += f"🏢 {c}\n"

            lanz = lanzadas[lanzadas[c_centro] == c]["lanzadas"].sum()
            cerr = cerradas[cerradas[c_centro] == c]["cerradas"].sum()

            atr = atrasadas_por_centro[atrasadas_por_centro[c_centro] == c]

            atr_val = int(atr["atrasadas"].values[0]) if not atr.empty else 0

            msg += (
                f"📦 Lanzadas: {lanz}\n"
                f"✅ Cerradas: {cerr}\n"
                f"🔴 Atrasadas (total): {atr_val}\n\n"
            )

        send_msg(cid, msg)

        # =========================
        # GRAFICA (SOLO AZUL Y VERDE)
        # =========================
        centros = rep[c_centro].unique()
        mid = math.ceil(len(centros) / 2)

        paginas = [centros[:mid], centros[mid:]]

        page = 1

        for grupo in paginas:

            plt.style.use("seaborn-v0_8-whitegrid")
            rows = math.ceil(len(grupo) / 2)
            plt.figure(figsize=(14, rows * 4))

            for i, c in enumerate(grupo, 1):

                t = rep[rep[c_centro] == c].copy()

                ax = plt.subplot(rows, 2, i)

                # 🔵 LANZADAS
                ax.plot(t["dia"], t["lanzadas"], color="blue", marker="o", label="Lanzadas")

                # 🟢 CERRADAS
                ax.plot(t["dia"], t["cerradas"], color="green", marker="o", label="Cerradas")

                ax.set_title(c)
                ax.tick_params(axis="x", rotation=45)
                ax.grid(True, alpha=0.3)
                ax.legend()

            plt.tight_layout()

            img = f"dash_{page}.png"
            plt.savefig(img, dpi=150)
            plt.close()

            send_photo(cid, img)
            os.remove(img)

            page += 1

    except Exception as e:
        send_msg(cid, f"❌ ERROR: {e}")

# =========================
# LOOP
# =========================
def main():

    offset = 0

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

                if "document" in m:

                    file_id = m["document"]["file_id"]

                    info = requests.get(
                        f"{URL}/getFile",
                        params={"file_id": file_id}
                    ).json()

                    path = info["result"]["file_path"]

                    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{path}"

                    data = requests.get(file_url)

                    with open("temp.xlsx", "wb") as f:
                        f.write(data.content)

                    procesar(cid, "temp.xlsx")

                    os.remove("temp.xlsx")

        except Exception as e:
            print("LOOP ERROR:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
