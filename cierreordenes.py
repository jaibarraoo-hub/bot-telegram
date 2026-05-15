import os
import time
import requests
import pandas as pd

# =========================
# 🔐 TOKEN DESDE RENDER
# =========================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("❌ TOKEN no encontrado en Render")

URL = f"https://api.telegram.org/bot{TOKEN}"

# =========================
# MENSAJES
# =========================
def send_msg(cid, text):
    try:
        requests.post(
            f"{URL}/sendMessage",
            json={
                "chat_id": cid,
                "text": text,
                "parse_mode": "Markdown"
            },
            timeout=15,
            proxies={"http": None, "https": None}
        )
    except Exception as e:
        print("Error send_msg:", e)

# =========================
# PROCESAR EXCEL
# =========================
def procesar(cid, file_path):
    try:
        print("📥 Leyendo Excel...")

        df = pd.read_excel(file_path, engine="openpyxl")

        print("📊 Columnas originales:", df.columns)

        # limpiar columnas
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.lower()
        )

        print("📊 Columnas limpias:", df.columns)

        # =========================
        # COLUMNAS REALES
        # =========================
        c_centro = "centro"
        c_inicio = "fecha de inicio extrema"
        c_fin = "fecha real de fin de la orden"

        # validar
        if c_centro not in df.columns or c_inicio not in df.columns or c_fin not in df.columns:
            send_msg(cid, "❌ Columnas no coinciden:\n\n" + str(list(df.columns)))
            return

        # =========================
        # FECHAS
        # =========================
        df[c_inicio] = pd.to_datetime(df[c_inicio], errors="coerce")
        df[c_fin] = pd.to_datetime(df[c_fin], errors="coerce")

        df = df.dropna(subset=[c_centro, c_inicio])

        # =========================
        # DÍAS
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
        # UNIR SIN ROMPER TIPOS
        # =========================
        rep = pd.merge(
            lanzadas,
            cerradas,
            left_on=[c_centro, "dia_inicio"],
            right_on=[c_centro, "dia_fin"],
            how="outer"
        )

        # valores numéricos seguros
        rep["lanzadas"] = rep["lanzadas"].fillna(0).astype(int)
        rep["cerradas"] = rep["cerradas"].fillna(0).astype(int)

        # fecha segura (SIN 0, SIN int)
        rep["fecha"] = rep["dia_inicio"].combine_first(rep["dia_fin"])

        # =========================
        # MENSAJE FINAL
        # =========================
        msg = "📊 *REPORTE DIARIO POR TIENDA*\n\n"

        for centro in rep[c_centro].unique():
            temp = rep[rep[c_centro] == centro].copy()

            # ordenar seguro (solo fechas válidas)
            temp = temp.sort_values("fecha")

            msg += f"🏢 *{centro}*\n"

            for _, r in temp.iterrows():
                msg += (
                    f"📅 {r['fecha']}\n"
                    f"📦 Lanzadas: {r['lanzadas']}\n"
                    f"✅ Cerradas: {r['cerradas']}\n\n"
                )

        send_msg(cid, msg)

        print("✅ PROCESO TERMINADO OK")

    except Exception as e:
        print("❌ ERROR:", e)
        send_msg(cid, f"❌ Error interno: {e}")

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

                if m.get("text") == "/start":
                    send_msg(cid, "📊 Envíame tu Excel con órdenes")

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

        except Exception as e:
            print("❌ LOOP ERROR:", e)
            time.sleep(5)

if __name__ == "__main__":
    main()
