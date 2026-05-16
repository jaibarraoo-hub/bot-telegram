import os
import time
import math
import requests
import pandas as pd
import matplotlib.pyplot as plt

TOKEN = os.getenv("TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}"

# =========================
# TELEGRAM
# =========================
def send_msg(cid, text):
    requests.post(f"{URL}/sendMessage",
                  json={"chat_id": cid, "text": text})

def send_photo(cid, path):
    with open(path, "rb") as f:
        requests.post(f"{URL}/sendPhoto",
                      data={"chat_id": cid},
                      files={"photo": f})

# =========================
# PROCESAR
# =========================
def procesar(cid, archivo):

    df = pd.read_excel(archivo, engine="openpyxl")
    df.columns = df.columns.str.strip().str.lower()

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
    # 🔥 SOLO HASTA HOY
    # =========================
    hoy = pd.Timestamp.today().date()
    df = df[df["dia"] <= hoy]

    # =========================
    # LANZADAS (AZUL)
    # =========================
    lanzadas = df.groupby([c_centro, "dia"]).size().reset_index(name="lanzadas")

    # =========================
    # CERRADAS (VERDE)
    # =========================
    cerradas_df = df.dropna(subset=[c_fin])
    cerradas = cerradas_df.groupby([c_centro, "dia"]).size().reset_index(name="cerradas")

    # =========================
    # ATRASADAS (ROJO - SOLO HOY HACIA ATRÁS)
    # =========================
    abiertas = df[df[c_status] == "LIB. KKMP NLIQ"]
    abiertas = abiertas.groupby([c_centro, "dia"]).size().reset_index(name="atrasadas")

    # =========================
    # MERGE SEGURO
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
    msg = "📊 REPORTE\n\n"

    for c in rep[c_centro].unique():

        t = rep[rep[c_centro] == c].sort_values("dia")

        msg += f"🏢 {c}\n"

        for _, r in t.iterrows():
            msg += f"{r['dia']} | L:{r['lanzadas']} C:{r['cerradas']} 🔴{r['atrasadas']}\n"

        msg += "\n"

    send_msg(cid, msg)

    # =========================
    # GRAFICA
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

            t = rep[rep[c_centro] == c].sort_values("dia")

            ax = plt.subplot(rows, 2, i)

            # 🔵 AZUL
            ax.plot(t["dia"], t["lanzadas"], color="blue", marker="o", label="Lanzadas")

            # 🟢 VERDE
            ax.plot(t["dia"], t["cerradas"], color="green", marker="o", label="Cerradas")

            # 🔴 ROJO (solo hasta hoy ya filtrado)
            ax.plot(t["dia"], t["atrasadas"], color="red", marker="o", label="Atrasadas")

            ax.set_title(c)
            ax.tick_params(axis="x", rotation=45)
            ax.legend()
            ax.grid(True, alpha=0.3)

        plt.tight_layout()

        name = f"dash_{page}.png"
        plt.savefig(name, dpi=150)
        plt.close()

        send_photo(cid, name)
        os.remove(name)

        page += 1

# =========================
# LOOP
# =========================
def main():

    offset = 0

    while True:

        r = requests.get(f"{URL}/getUpdates",
                         params={"offset": offset, "timeout": 30}).json()

        for u in r.get("result", []):

            offset = u["update_id"] + 1

            m = u.get("message", {})
            cid = m.get("chat", {}).get("id")

            if "document" in m:

                fid = m["document"]["file_id"]

                info = requests.get(f"{URL}/getFile",
                                    params={"file_id": fid}).json()

                path = info["result"]["file_path"]

                file_url = f"https://api.telegram.org/file/bot{TOKEN}/{path}"

                data = requests.get(file_url)

                with open("temp.xlsx", "wb") as f:
                    f.write(data.content)

                procesar(cid, "temp.xlsx")

                os.remove("temp.xlsx")

if __name__ == "__main__":
    main()
