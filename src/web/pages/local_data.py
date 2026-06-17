from pathlib import Path

import pandas as pd
import streamlit as st


def render_local_data_page():
    st.title("🗂️ Dados locais")

    st.write(
        "Aqui vamos acompanhar os arquivos locais usados pelo Margin Miner."
    )

    paths = [
        "storage/selic/daily_selic.parquet",
        "storage/benchmarks/IBOV/history.parquet",
        "storage/benchmarks/IFIX/history.parquet",
        "storage/fundamentus/latest.parquet",
        "storage/rankings/latest.parquet",
        "storage/valuations/valuations.sqlite",
    ]

    rows = []

    for p in paths:
        path = Path(p)

        rows.append(
            {
                "arquivo": p,
                "existe": path.exists(),
                "tamanho_kb": round(path.stat().st_size / 1024, 2)
                if path.exists()
                else None,
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )