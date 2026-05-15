import os
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# TOKEN DESDE RENDER
# =========================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("Falta TOKEN en Render")

URL = f"https://api.telegram.org/bot{TOKEN}"

# =========================
# ENVIAR MENSAJE
# =========================
def send_msg(cid, text):

    try:

        requests.post(
            f"{URL}/sendMessage",
            json={
                "chat_id": cid,
                "text": text
            },
            timeout=20
        )

    except Exception as e:

        print("ERROR MENSAJE:", e)

# =========================
# ENVIAR IMAGEN
# =========================
def send_photo(cid, path):

    try:

        with open(path, "rb") as img:

            requests.post(
                f"{URL}/sendPhoto",
                data={
                    "chat_id": cid
                },
                files={
                    "photo": img
                },
                timeout=60
            )

    except Exception as e:

        print("ERROR FOTO:", e)

# =========================
# PROCESAR EXCEL
# =========================
def procesar(cid, archivo):

    try:

        print("LEYENDO EXCEL...")

        # =========================
        # LEER EXCEL
        # =========================
        df = pd.read_excel(
            archivo,
            engine="openpyxl"
        )

        print("EXCEL OK")

        # limpiar columnas
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.lower()
        )

        print("COLUMNAS:", list(df.columns))

        # =========================
        # COLUMNAS REALES
        # =========================
        c_centro = "centro"
        c_inicio = "fecha de inicio extrema"
        c_fin = "fecha real de fin de la orden"

        # validar
        faltantes = []

        if c_centro not in df.columns:
            faltantes.append(c_centro)

        if c_inicio not in df.columns:
            faltantes.append(c_inicio)

        if c_fin not in df.columns:
            faltantes.append(c_fin)

        if faltantes:

            send_msg(
                cid,
                f"Faltan columnas:\n{faltantes}"
            )

            return

        # =========================
        # FECHAS
        # =========================
        df[c_inicio] = pd.to_datetime(
            df[c_inicio],
            errors="coerce"
        )

        df[c_fin] = pd.to_datetime(
            df[c_fin],
            errors="coerce"
        )

        # quitar nulos
        df = df.dropna(
            subset=[c_centro, c_inicio]
        )

        print("FILAS:", len(df))

        # =========================
        # DIAS
        # =========================
        df["dia_inicio"] = df[c_inicio].dt.date
        df["dia_fin"] = df[c_fin].dt.date

        # =========================
        # LANZADAS
        # =========================
        lanzadas = (
            df.groupby([c_centro, "dia_inicio"])
            .size()
            .reset_index(name="lanzadas")
        )

        # =========================
        # CERRADAS
        # =========================
        cerradas = (
            df.dropna(subset=[c_fin])
            .groupby([c_centro, "dia_fin"])
            .size()
            .reset_index(name="cerradas")
        )

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

        # numeros
        rep["lanzadas"] = (
            rep["lanzadas"]
            .fillna(0)
            .astype(int)
        )

        rep["cerradas"] = (
            rep["cerradas"]
            .fillna(0)
            .astype(int)
        )

        # fecha segura
        rep["fecha"] = (
            rep["dia_inicio"]
            .combine_first(rep["dia_fin"])
        )

        # quitar vacíos
        rep = rep.dropna(subset=["fecha"])

        print("REPORTE OK")

        # =========================
        # MENSAJE
        # =========================
        msg = "REPORTE DIARIO\n\n"

        for centro in rep[c_centro].dropna().unique():

            temp = rep[
                rep[c_centro] == centro
            ].copy()

            temp = temp.sort_values("fecha")

            msg += f"{centro}\n"

            for _, r in temp.iterrows():

                msg += (
                    f"{r['fecha']} | "
                    f"Lanzadas: {r['lanzadas']} | "
                    f"Cerradas: {r['cerradas']}\n"
                )

            msg += "\n"

            # =========================
            # GRAFICA
            # =========================
            plt.figure(figsize=(12, 5))

            plt.plot(
                temp["fecha"],
                temp["lanzadas"],
                marker="o",
                linewidth=2,
                label="Lanzadas"
            )

            plt.plot(
                temp["fecha"],
                temp["cerradas"],
                marker="o",
                linewidth=2,
                label="Cerradas"
            )

            plt.title(f"Ordenes - {centro}")

            plt.xlabel("Fecha")
            plt.ylabel("Cantidad")

            plt.xticks(rotation=45)

            plt.grid(True)

            plt.legend()

            plt.tight_layout()

            nombre = f"grafica_{centro}.png"

            plt.savefig(nombre)

            plt.close()

            print("GRAFICA OK:", nombre)

            # enviar gráfica
            send_photo(cid, nombre)

            # borrar
            if os.path.exists(nombre):
                os.remove(nombre)

        # telegram tiene limite
        if len(msg) > 3500:
            msg = msg[:3500]

        send_msg(cid, msg)

        print("MENSAJE ENVIADO")

    except Exception as e:

        print("ERROR PROCESAR:", e)

        send_msg(
            cid,
            f"ERROR:\n{e}"
        )

# =========================
# MAIN
# =========================
def main():

    print("BOT ACTIVO")

    offset = 0

    while True:

        try:

            r = requests.get(
                f"{URL}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": 30
                },
                timeout=40
            )

            data = r.json()

            for u in data.get("result", []):

                offset = u["update_id"] + 1

                m = u.get("message", {})

                cid = m.get("chat", {}).get("id")

                if not cid:
                    continue

                # =====================
                # START
                # =====================
                if m.get("text") == "/start":

                    send_msg(
                        cid,
                        "Envia tu Excel"
                    )

                # =====================
                # ARCHIVO
                # =====================
                if "document" in m:

                    send_msg(
                        cid,
                        "Procesando..."
                    )

                    print("DOCUMENTO RECIBIDO")

                    file_id = m["document"]["file_id"]

                    # =====================
                    # GET FILE
                    # =====================
                    info = requests.get(
                        f"{URL}/getFile",
                        params={
                            "file_id": file_id
                        },
                        timeout=30
                    ).json()

                    print("GETFILE OK")

                    file_path = info["result"]["file_path"]

                    file_url = (
                        f"https://api.telegram.org/file/bot"
                        f"{TOKEN}/{file_path}"
                    )

                    print("DESCARGANDO...")

                    archivo = requests.get(
                        file_url,
                        timeout=60
                    )

                    print("DESCARGA OK")

                    if archivo.status_code != 200:

                        send_msg(
                            cid,
                            "Error descargando archivo"
                        )

                        continue

                    local = "temp.xlsx"

                    with open(local, "wb") as f:
                        f.write(archivo.content)

                    print("ARCHIVO GUARDADO")

                    # procesar
                    procesar(cid, local)

                    # borrar excel
                    if os.path.exists(local):
                        os.remove(local)

        except Exception as e:

            print("ERROR LOOP:", e)

            time.sleep(5)

# =========================
# START
# =========================
if __name__ == "__main__":
    main()
