import os
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# 🔐 TOKEN (DESDE RENDER)
# =========================
TOKEN = os.environ.get("8685699623:AAGmHb1eYQft27I03YLN2yjvWRolOTQFg7I")

if not TOKEN:
    raise Exception("❌ Falta la variable de entorno TOKEN en Render")

URL = f"https://api.telegram.org/bot{TOKEN}"
# =========================
# ENVIAR MENSAJE
# =========================
def send_msg(cid, text):
    try:
        requests.post(
            f"{URL}/sendMessage",
            json={"chat_id": cid, "text": text, "parse_mode": "Markdown"},
            timeout=15,
            proxies={"http": None, "https": None}
        )
    except Exception as e:
        print("Error msg:", e)

# =========================
# ENVIAR DOCUMENTO
# =========================
def send_doc(cid, path):
    try:
        with open(path, "rb") as f:
            requests.post(
                f"{URL}/sendDocument",
                data={"chat_id": cid},
                files={"document": f},
                timeout=30,
                proxies={"http": None, "https": None}
            )
    except Exception as e:
        print("Error doc:", e)

# =========================
# PROCESAR EXCEL
# =========================
def procesar(cid, file_path):

    df = pd.read_excel(file_path, engine="openpyxl")

    df.columns = [str(c).strip().lower() for c in df.columns]

    # detectar columnas
    c_centro = next((c for c in df.columns if "centro" in c), None)
    c_inicio = next((c for c in df.columns if "inicio" in c or "plan" in c), None)
    c_fin = next((c for c in df.columns if "fin" in c or "real" in c or "cierre" in c), None)

    if not (c_centro and c_inicio and c_fin):
        send_msg(cid, f"❌ Faltan columnas: {list(df.columns)}")
        return

    df[c_inicio] = pd.to_datetime(df[c_inicio], errors="coerce")
    df[c_fin] = pd.to_datetime(df[c_fin], errors="coerce")

    df = df.dropna(subset=[c_centro, c_inicio])

    df["dia_inicio"] = df[c_inicio].dt.date
    df["dia_fin"] = df[c_fin].dt.date

    lanzadas = df.groupby([c_centro, "dia_inicio"]).size().reset_index(name="lanzadas")

    cerradas = df.dropna(subset=[c_fin])
    cerradas = cerradas.groupby([c_centro, "dia_fin"]).size().reset_index(name="cerradas")

    rep = pd.merge(
        lanzadas,
        cerradas,
        left_on=[c_centro, "dia_inicio"],
        right_on=[c_centro, "dia_fin"],
        how="outer"
    ).fillna(0)

    rep["lanzadas"] = rep["lanzadas"].astype(int)
    rep["cerradas"] = rep["cerradas"].astype(int)

    rep["fecha"] = rep["dia_inicio"].fillna(rep["dia_fin"])

    msg = "📊 *REPORTE DIARIO*\n\n"

    for centro in rep[c_centro].unique():
        temp = rep[rep[c_centro] == centro].sort_values("fecha")

        msg += f"🏢 *{centro}*\n"

        for _, r in temp.iterrows():
            msg += (
                f"📅 {r['fecha']}\n"
                f"📦 Lanzadas: {r['lanzadas']}\n"
                f"✅ Cerradas: {r['cerradas']}\n\n"
            )

    send_msg(cid, msg)

# =========================
# BOT LOOP
# =========================
def main():
    print("🤖 BOT ACTIVO")

    offset = 0

    while True:
        try:
            r = requests.get(
                f"{URL}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=40,
                proxies={"http": None, "https": None}
            )

            data = r.json()

            for u in data.get("result", []):

                offset = u["update_id"] + 1
                m = u.get("message", {})
                cid = m.get("chat", {}).get("id")

                if not cid:
                    continue

                if "document" in m:
                    send_msg(cid, "⌛ Procesando archivo...")

                    file_id = m["document"]["file_id"]

                    file_info = requests.get(
                        f"{URL}/getFile",
                        params={"file_id": file_id}
                    ).json()

                    file_path = file_info["result"]["file_path"]

                    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

                    file_data = requests.get(file_url)

                    local = "temp.xlsx"

                    with open(local, "wb") as f:
                        f.write(file_data.content)

                    procesar(cid, local)

                    os.remove(local)

                elif m.get("text") == "/start":
                    send_msg(cid, "📊 Envía tu Excel con órdenes")

        except Exception as e:
            print("Error loop:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
