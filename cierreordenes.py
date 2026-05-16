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
            json={
                "chat_id": cid,
                "text": text
            },
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

        send_msg(cid, "📥 Leyendo Excel...")

        # =========================
        # LEER EXCEL
        # =========================
        df = pd.read_excel(
            archivo,
            engine="openpyxl"
        )

        # =========================
        # NORMALIZAR COLUMNAS
        # =========================
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.lower()
        )

        print("COLUMNAS:")
        print(df.columns.tolist())

        # =========================
        # COLUMNAS
        # =========================
        c_centro = "centro"
        c_inicio = "fecha de inicio extrema"
        c_fin = "fecha real de fin de la orden"
        c_texto = "texto breve"

        # =========================
        # VALIDAR COLUMNAS
        # =========================
        faltantes = []

        for c in [c_centro, c_inicio, c_fin]:

            if c not in df.columns:
                faltantes.append(c)

        if faltantes:

            send_msg(
                cid,
                f"❌ Faltan columnas:\n\n{', '.join(faltantes)}"
            )

            return

        # =========================
        # FECHAS
        # =========================
        send_msg(cid, "📅 Procesando fechas...")

        df[c_inicio] = pd.to_datetime(
            df[c_inicio],
            errors="coerce"
        )

        df[c_fin] = pd.to_datetime(
            df[c_fin],
            errors="coerce"
        )

        # =========================
        # LIMPIAR NULOS
        # =========================
        df = df.dropna(
            subset=[c_centro, c_inicio]
        )

        # =========================
        # FILTROS
        # =========================
        if c_texto in df.columns:

            df[c_texto] = (
                df[c_texto]
                .astype(str)
                .str.lower()
                .str.strip()
            )

            # excluir
            df = df[
                ~df[c_texto].str.startswith("insp. semanal")
            ]

            df = df[
                ~df[c_texto].str.startswith(
                    "rev. estructura y pintura trimestral"
                )
            ]

        # =========================
        # FECHA BASE
        # =========================
        df["fecha"] = df[c_inicio].dt.date

        # =========================
        # LANZADAS
        # =========================
        send_msg(cid, "📦 Calculando lanzadas...")

        lanzadas = (
            df.groupby([c_centro, "fecha"])
            .size()
            .reset_index(name="lanzadas")
        )

        # =========================
        # CERRADAS
        # =========================
        send_msg(cid, "✅ Calculando cerradas...")

        cerradas = df.dropna(subset=[c_fin])

        cerradas = (
            cerradas.groupby([c_centro, "fecha"])
            .size()
            .reset_index(name="cerradas")
        )

        # =========================
        # MERGE
        # =========================
        rep = pd.merge(
            lanzadas,
            cerradas,
            on=[c_centro, "fecha"],
            how="outer"
        )

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

        rep = rep.dropna(subset=["fecha"])

        # =========================
        # DEBUG
        # =========================
        print(rep.head())

        send_msg(
            cid,
            f"📊 Registros para dashboard: {len(rep)}"
        )

        # =========================
        # VALIDAR DATOS
        # =========================
        if len(rep) == 0:

            send_msg(
                cid,
                "❌ No hay datos para graficar"
            )

            return

        # =========================
        # REPORTE TEXTO
        # =========================
        msg = "📊 REPORTE DIARIO\n\n"

        centros = rep[c_centro].dropna().unique()

        msg += f"🏢 Centros detectados: {len(centros)}\n\n"

        for centro in centros:

            temp = rep[
                rep[c_centro] == centro
            ]

            total_l = temp["lanzadas"].sum()
            total_c = temp["cerradas"].sum()

            estado = "🟢 OK"

            if total_l - total_c > 3:
                estado = "🔴 ALTA CARGA"

            elif total_l - total_c > 0:
                estado = "🟡 MEDIA"

            msg += (
                f"🏢 {centro}\n"
                f"{estado}\n"
                f"📦 Lanzadas: {total_l}\n"
                f"✅ Cerradas: {total_c}\n\n"
            )

        send_msg(cid, msg)

        # =========================
        # DASHBOARD
        # =========================
        send_msg(cid, "📈 Generando dashboard...")

        centros = rep[c_centro].dropna().unique()

        if len(centros) == 0:

            send_msg(
                cid,
                "❌ No hay centros válidos"
            )

            return

        # =========================
        # SOLO 2 PAGINAS
        # =========================
        mid = max(
            1,
            math.ceil(len(centros) / 2)
        )

        paginas = [
            centros[:mid],
            centros[mid:]
        ]

        paginas = [
            p for p in paginas
            if len(p) > 0
        ]

        pagina = 1

        # =========================
        # LOOP PAGINAS
        # =========================
        for grupo in paginas:

            try:

                # limpiar memoria
                plt.close("all")
                plt.clf()

                cols = 2
                rows = math.ceil(
                    len(grupo) / cols
                )

                fig = plt.figure(
                    figsize=(14, rows * 4)
                )

                plt.style.use(
                    "seaborn-v0_8-whitegrid"
                )

                for i, centro in enumerate(grupo, 1):

                    temp = rep[
                        rep[c_centro] == centro
                    ].copy()

                    temp = temp.sort_values(
                        "fecha"
                    )

                    if len(temp) == 0:
                        continue

                    ax = plt.subplot(
                        rows,
                        cols,
                        i
                    )

                    ax.set_facecolor(
                        "#f7f9fc"
                    )

                    # =========================
                    # AZUL
                    # =========================
                    ax.plot(
                        temp["fecha"],
                        temp["lanzadas"],
                        marker="o",
                        linewidth=2.5,
                        color="#1f77b4",
                        label="Lanzadas"
                    )

                    # =========================
                    # VERDE
                    # =========================
                    ax.plot(
                        temp["fecha"],
                        temp["cerradas"],
                        marker="o",
                        linewidth=2.5,
                        color="#2ca02c",
                        label="Cerradas"
                    )

                    # =========================
                    # ETIQUETAS
                    # =========================
                    for x, y in zip(
                        temp["fecha"],
                        temp["lanzadas"]
                    ):

                        ax.text(
                            x,
                            y + 0.5,
                            str(y),
                            fontsize=7,
                            ha="center",
                            color="#1f77b4"
                        )

                    for x, y in zip(
                        temp["fecha"],
                        temp["cerradas"]
                    ):

                        ax.text(
                            x,
                            y - 0.9,
                            str(y),
                            fontsize=7,
                            ha="center",
                            color="#2ca02c",
                            bbox=dict(
                                facecolor="white",
                                edgecolor="none",
                                alpha=0.75,
                                boxstyle="round,pad=0.2"
                            )
                        )

                    ax.set_title(
                        f"📊 {centro}",
                        fontsize=11,
                        fontweight="bold"
                    )

                    ax.tick_params(
                        axis='x',
                        rotation=45
                    )

                    ax.grid(
                        True,
                        alpha=0.3
                    )

                    ax.legend()

                plt.tight_layout()

                img = f"dashboard_{pagina}.png"

                plt.savefig(
                    img,
                    dpi=150,
                    bbox_inches="tight"
                )

                plt.close()

                send_photo(cid, img)

                os.remove(img)

                pagina += 1

            except Exception as e:

                send_msg(
                    cid,
                    f"❌ Error gráfica página {pagina}: {e}"
                )

    except Exception as e:

        send_msg(
            cid,
            f"❌ ERROR GENERAL:\n{e}"
        )

# =========================
# LOOP BOT
# =========================
def main():

    offset = 0

    print("🚀 BOT ACTIVO")

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

                offset = (
                    u["update_id"] + 1
                )

                m = u.get("message", {})

                cid = (
                    m.get("chat", {})
                    .get("id")
                )

                if not cid:
                    continue

                # =========================
                # START
                # =========================
                if m.get("text") == "/start":

                    send_msg(
                        cid,
                        "📊 Envía tu Excel SAP"
                    )

                # =========================
                # ARCHIVO
                # =========================
                if "document" in m:

                    send_msg(
                        cid,
                        "⌛ Procesando archivo..."
                    )

                    file_id = (
                        m["document"]["file_id"]
                    )

                    info = requests.get(
                        f"{URL}/getFile",
                        params={
                            "file_id": file_id
                        }
                    ).json()

                    file_path = (
                        info["result"]["file_path"]
                    )

                    file_url = (
                        f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
                    )

                    data_file = requests.get(
                        file_url,
                        timeout=60
                    )

                    local = "temp.xlsx"

                    with open(local, "wb") as f:
                        f.write(data_file.content)

                    procesar(cid, local)

                    os.remove(local)

        except Exception as e:

            print("LOOP ERROR:", e)

            time.sleep(5)

if __name__ == "__main__":
    main()
