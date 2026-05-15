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
# MENSAJE
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

# =========================
# FOTO
# =========================
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
# PROCESAR EXCEL
# =========================
def procesar(cid, archivo):

    try:

        df = pd.read_excel(archivo, engine="openpyxl")

        # normalizar columnas
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.lower()
        )

        # =========================
        # COLUMNAS
        # =========================
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
        # DIAS
        # =========================
        df["dia_inicio"] = df[c_inicio].dt.date
        df["dia_fin"] = df[c_fin].dt.date

        # =========================
        # LANZADAS
        # =========================
        lanzadas = df.groupby([c_centro, "dia_inicio"]).size().reset_index(name="lanzadas")

        # =========================
        # CERRADAS
        # =========================
        cerradas = df.dropna(subset=[c_fin])
        cerradas = cerradas.groupby([c_centro, "dia_fin"]).size().reset_index(name="cerradas")

        # =========================
        # MERGE
        # =========================
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
        # MENSAJE
        # =========================
        msg = "📊 REPORTE DIARIO\n\n"

        centros = rep[c_centro].dropna().unique()

        msg += f"Total centros: {len(centros)}\n\n"

        for centro in centros:

            temp = rep[rep[c_centro] == centro].copy()
            temp = temp.sort_values("fecha")

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
        # 📊 DASHBOARD 2 HOJAS
        # =========================
        centros = rep[c_centro].dropna().unique()

        mid = math.ceil(len(centros) / 2)

        paginas = [
            centros[:mid],
            centros[mid:]
        ]

        pagina = 1

        for grupo in paginas:

            cols = 2
            rows = math.ceil(len(grupo) / cols)

            plt.figure(figsize=(14, rows * 4))

            for i, centro in enumerate(grupo, 1):

                temp = rep[rep[c_centro] == centro].copy()
                temp = temp.sort_values("fecha")

                plt.subplot(rows, cols, i)

                plt.plot(temp["fecha"], temp["lanzadas"], marker="o", label="Lanzadas")
                plt.plot(temp["fecha"], temp["cerradas"], marker="o", label="Cerradas")

                # etiquetas
                for x, y in zip(temp["fecha"], temp["lanzadas"]):
                    plt.text(x, y, str(y), fontsize=7, ha="center", va="bottom")

                for x, y in zip(temp["fecha"], temp["cerradas"]):
                    plt.text(x, y, str(y), fontsize=7, ha="center", va="top")

                plt.title(centro)
                plt.xticks(rotation=45)
                plt.grid(True)
                plt.legend()

            plt.tight_layout()

            img = f"dashboard_{pagina}.png"

            plt.savefig(img)
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
    print("BOT DASHBOARD 2 HOJAS ACTIVO")

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
