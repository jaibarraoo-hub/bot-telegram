import requests
import os
import time
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# 🔧 FIX PROXY (IMPORTANTE)
# =========================
import os
os.environ["NO_PROXY"] = "api.telegram.org"

# =========================
# CONFIG
# =========================
TOKEN = "TU_TOKEN_NUEVO"
URL = f"https://api.telegram.org/bot{TOKEN}"

# =========================
# REQUEST SEGURO
# =========================
def safe_get(url, **kwargs):
    for i in range(3):  # reintentos
        try:
            return requests.get(
                url,
                timeout=30,
                proxies={"http": None, "https": None},
                **kwargs
            )
        except Exception as e:
            print(f"⚠️ Retry {i+1}: {e}")
            time.sleep(2)
    return None

# =========================
def send_msg(cid, text):
    try:
        requests.post(
            f"{URL}/sendMessage",
            json={"chat_id": cid, "text": text},
            timeout=10,
            proxies={"http": None, "https": None}
        )
    except Exception as e:
        print(f"❌ Error msg: {e}")

# =========================
def send_doc(cid, path):
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                requests.post(
                    f"{URL}/sendDocument",
                    data={"chat_id": cid},
                    files={"document": f},
                    timeout=30,
                    proxies={"http": None, "https": None}
                )
    except Exception as e:
        print(f"❌ Error doc: {e}")

# =========================
# PROCESAR EXCEL
# =========================
def procesar(cid, path):

    try:
        df = pd.read_excel(path, engine="openpyxl")

        df.columns = [str(c).strip().lower() for c in df.columns]

        # =========================
        # CENTRO
        # =========================
        col_centro = next((c for c in df.columns if "centro" in c), None)

        if not col_centro:
            send_msg(cid, "❌ No se encontró columna 'centro'")
            return

        df = df[[col_centro]].dropna()

        resumen = df[col_centro].value_counts().reset_index()
        resumen.columns = ["Centro", "Cantidad"]

        # =========================
        # GRAFICA
        # =========================
        plt.figure(figsize=(12,6))
        plt.bar(resumen["Centro"], resumen["Cantidad"], color="blue")
        plt.xticks(rotation=45, ha="right")
        plt.title("Reporte por Centro")
        plt.tight_layout()

        pdf = "reporte.pdf"
        plt.savefig(pdf)
        plt.close()

        send_doc(cid, pdf)
        send_msg(cid, "📊 Reporte generado correctamente")

    except Exception as e:
        send_msg(cid, f"⚠️ Error procesando archivo: {e}")

# =========================
# MAIN LOOP ESTABLE
# =========================
def main():

    print("🤖 BOT ESTABLE INICIADO")

    offset = 0

    while True:

        try:

            r = safe_get(
                f"{URL}/getUpdates",
                params={"offset": offset, "timeout": 30}
            )

            if r is None:
                continue

            data = r.json()

            for u in data.get("result", []):

                offset = u["update_id"] + 1

                m = u.get("message", {})
                cid = m.get("chat", {}).get("id")

                if not cid:
                    continue

                # =====================
                # DOCUMENTO
                # =====================
                if "document" in m:

                    send_msg(cid, "⌛ Procesando archivo...")

                    file_id = m["document"]["file_id"]

                    file_info = safe_get(
                        f"{URL}/getFile",
                        params={"file_id": file_id}
                    )

                    if file_info is None:
                        send_msg(cid, "❌ Error obteniendo archivo")
                        continue

                    file_path = file_info.json()["result"]["file_path"]

                    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

                    file_data = safe_get(file_url)

                    if file_data is None:
                        send_msg(cid, "❌ Error descargando archivo")
                        continue

                    local = "temp.xlsx"

                    with open(local, "wb") as f:
                        f.write(file_data.content)

                    procesar(cid, local)

                    if os.path.exists(local):
                        os.remove(local)

                # =====================
                # START
                # =====================
                elif m.get("text") == "/start":
                    send_msg(cid, "📊 Envíame un Excel con columna 'centro'")

        except Exception as e:
            print(f"⚠️ LOOP ERROR: {e}")
            time.sleep(3)

# =========================
if __name__ == "__main__":
    main()