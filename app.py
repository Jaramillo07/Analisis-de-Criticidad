import streamlit as st
import pandas as pd
import io

st.set_page_config(
    page_title="Asset Criticality Analysis",
    page_icon="⚙️",
    layout="wide"
)

# ── Estilos ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }
    .main, .stApp { background-color: #f1f5f9; }
    .block-container { padding-top: 1.5rem; max-width: 1200px; }

    /* Header banner */
    .app-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 55%, #3b82f6 100%);
        border-radius: 14px;
        padding: 26px 32px;
        margin-bottom: 8px;
        box-shadow: 0 10px 30px rgba(30,58,95,0.25);
    }
    .app-header h1 {
        color: #ffffff; font-size: 1.9rem; font-weight: 800; margin: 0;
        letter-spacing: -0.5px;
    }
    .app-header p {
        color: #cbd5e1; font-size: 0.9rem; margin: 6px 0 0 0; font-weight: 400;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0; padding: 8px 16px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3a5f !important; color: #ffffff !important;
    }

    /* Section subheaders */
    h2, h3 { color: #1e293b; font-weight: 700; }

    /* Priority pills */
    .priority-p1 { background-color: #fee2e2; border-left: 5px solid #ef4444; padding: 8px 12px; border-radius: 6px; font-weight: 700; color: #7f1d1d; }
    .priority-p2 { background-color: #ffedd5; border-left: 5px solid #f97316; padding: 8px 12px; border-radius: 6px; font-weight: 700; color: #7c2d12; }
    .priority-p3 { background-color: #fef9c3; border-left: 5px solid #eab308; padding: 8px 12px; border-radius: 6px; font-weight: 700; color: #713f12; }
    .priority-p4 { background-color: #dcfce7; border-left: 5px solid #22c55e; padding: 8px 12px; border-radius: 6px; font-weight: 700; color: #14532d; }

    /* Score box */
    .score-box {
        background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%);
        color: white; padding: 20px; border-radius: 12px; text-align: center;
        box-shadow: 0 6px 18px rgba(30,58,95,0.20);
    }
    .score-number { font-size: 2.6rem; font-weight: 800; color: #93c5fd; line-height: 1.1; }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
        padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    div[data-testid="stMetricValue"] { font-weight: 800; color: #1e3a5f; }

    /* Buttons */
    .stButton > button { border-radius: 8px; font-weight: 600; }
    .stDownloadButton > button { border-radius: 8px; font-weight: 600; }

    /* Expanders */
    .streamlit-expanderHeader { font-weight: 600; }

    /* Footer */
    .app-footer {
        text-align: center; padding: 18px; margin-top: 8px;
        color: #64748b; font-size: 0.85rem;
    }
    .app-footer strong { color: #1e3a5f; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES Y METODOLOGÍA
# ══════════════════════════════════════════════════════════════════════════════
# Escala no lineal por nivel (nivel 5 = peor, penaliza fuerte los extremos)
SCORE_MAP = {1: 1, 2: 4, 3: 7, 4: 10, 5: 20}
# La criticidad es el PRODUCTO de los cuatro criterios (no la suma).
MAX_SCORE = 20 * 20 * 20 * 20  # 160,000 (los 4 criterios en nivel 5)

CRITERIA_LABELS = {
    "obsolescence": "Obsolescencia de refacciones eléctricas",
    "capacity":     "Impacto en capacidad de producción (PPR %)",
    "redirection":  "Posibilidad de redirigir producción",
    "stops":        "Paros significativos últimos 12 meses",
}

CRITERIA_LEVELS = {
    "obsolescence": [
        "Nivel 1 — <10% refacciones obsoletas",
        "Nivel 2 — 10–25% obsoletas",
        "Nivel 3 — 25–50% obsoletas",
        "Nivel 4 — 50–75% obsoletas",
        "Nivel 5 — >75% obsoletas / sin soporte",
    ],
    "capacity": [
        "Nivel 1 — <10% del volumen total",
        "Nivel 2 — 10–25% del volumen",
        "Nivel 3 — 25–50% del volumen",
        "Nivel 4 — 50–75% del volumen",
        "Nivel 5 — >75% / único en línea de proceso",
    ],
    "redirection": [
        "Nivel 1 — 100% redirigible sin impacto",
        "Nivel 2 — >75% redirigible",
        "Nivel 3 — 25–75% redirigible con impacto parcial",
        "Nivel 4 — <25% redirigible, impacto alto",
        "Nivel 5 — Sin posibilidad de redirección",
    ],
    "stops": [
        "Nivel 1 — 0 paros sobre el tiempo permitido",
        "Nivel 2 — 1–2 paros significativos",
        "Nivel 3 — 3–5 paros significativos",
        "Nivel 4 — 6–10 paros significativos",
        "Nivel 5 — >10 paros significativos",
    ],
}

# ── Aging (EJE INDEPENDIENTE — no entra en el score de criticidad) ────────────
# El envejecimiento es contexto para decisiones de inversión (CAPEX),
# no un criterio de criticidad. Se combina edad + nivel tecnológico.
AGE_LEVELS = {
    1: "0–5 años",
    2: "5–10 años",
    3: "10–15 años",
    4: "15–20 años",
    5: ">20 años",
}
TECH_LEVELS = {
    1: "Vigente — tecnología actual, con soporte",
    2: "En transición — soporte limitado",
    3: "Descontinuado — refacciones escasas",
    4: "Obsoleto — sin soporte del fabricante",
    5: "Sin refacciones — fin de vida total",
}
# Aging score independiente: producto edad × tecnología (escala no lineal).
AGE_SCORE_MAP = {1: 1, 2: 4, 3: 7, 4: 10, 5: 20}


def stops_to_level(n):
    """Convierte el número real de paros significativos (dato duro de mtto) a nivel 1-5."""
    try:
        n = int(n)
    except (ValueError, TypeError):
        return None
    if n <= 0:
        return 1
    elif n <= 2:
        return 2
    elif n <= 5:
        return 3
    elif n <= 10:
        return 4
    else:
        return 5


AGING_MAX = 20 * 20  # 400

def calc_aging(age_lvl, tech_lvl):
    """Aging score independiente (0 = no evaluado). Contexto para decisiones CAPEX."""
    if not age_lvl or not tech_lvl:
        return 0, "No evaluado"
    score = AGE_SCORE_MAP[age_lvl] * AGE_SCORE_MAP[tech_lvl]
    if score >= 100:
        band = "Envejecimiento alto — candidato a reemplazo (CAPEX)"
    elif score >= 28:
        band = "Envejecimiento medio — vigilar"
    else:
        band = "Envejecimiento bajo — equipo vigente"
    return score, band


# Matriz de prioridad: capacity (1-5) × redirection (1-5) → P1/P2/P3/P4
def get_priority(capacity_lvl, redirection_lvl, is_bottleneck):
    if capacity_lvl >= 4 and redirection_lvl >= 4:
        priority = "P1"
    elif capacity_lvl >= 3 and redirection_lvl >= 3:
        priority = "P2"
    elif capacity_lvl >= 2 or redirection_lvl >= 3:
        priority = "P3"
    else:
        priority = "P4"
    if is_bottleneck and priority in ("P3", "P4"):
        priority = "P2"
    return priority


import math

def calc_score(obs, cap, red, stp):
    # Criticidad = producto de los cuatro criterios (escala no lineal).
    return SCORE_MAP[obs] * SCORE_MAP[cap] * SCORE_MAP[red] * SCORE_MAP[stp]

def score_pct(score):
    """Normaliza el score (producto, 1..160,000) a 0-100% en escala logarítmica.
    Necesario porque el producto es exponencial: un % lineal aplastaría todo."""
    if not score or score <= 1:
        return 0.0
    return round(math.log(score) / math.log(MAX_SCORE) * 100, 1)


def priority_badge(p):
    colors = {"P1": "#ef4444", "P2": "#f97316", "P3": "#eab308", "P4": "#22c55e"}
    labels = {"P1": "P1 — Crítico", "P2": "P2 — Alto", "P3": "P3 — Medio", "P4": "P4 — Bajo"}
    c = colors.get(p, "#94a3b8")
    l = labels.get(p, p)
    return f'<span style="background:{c};color:white;padding:3px 10px;border-radius:20px;font-weight:700;font-size:13px">{l}</span>'


def is_complete(a):
    """Un activo está listo para rankear si tiene los 3 criterios manuales evaluados."""
    return all(a.get(k) for k in ("obs_lvl", "cap_lvl", "red_lvl"))


def recompute(a):
    """Recalcula score/prioridad/aging de un activo si está completo."""
    if is_complete(a):
        a["Score"] = calc_score(a["obs_lvl"], a["cap_lvl"], a["red_lvl"], a["stp_lvl"])
        a["Prioridad"] = get_priority(a["cap_lvl"], a["red_lvl"], a["bottleneck"])
        a["Estado"] = "Evaluado"
    else:
        a["Score"] = None
        a["Prioridad"] = None
        a["Estado"] = "Pendiente de evaluar"
    a["AgingScore"], a["AgingEV"] = calc_aging(a.get("age_lvl"), a.get("tech_lvl"))
    return a


# ── Plantilla Excel descargable ───────────────────────────────────────────────
def build_template():
    """Genera la plantilla Excel: datos que mantenimiento tiene a la mano."""
    datos = pd.DataFrame({
        "Equipo": ["Compresor de aire #3", "Banda transportadora L4", ""],
        "Área / Línea": ["Servicios auxiliares", "Línea 4 — Ensamble", ""],
        "Descripción": ["Suministro de aire comprimido a planta", "Traslado de producto entre estaciones", ""],
        "Paros significativos (12 meses)": [4, 0, ""],
    })

    instrucciones = pd.DataFrame({
        "CÓMO LLENAR ESTA PLANTILLA": [
            "1. Llena UNA FILA por cada activo o grupo de activos.",
            "2. Solo captura los datos que mantenimiento tiene a la mano:",
            "   • Equipo: nombre o tag del activo.",
            "   • Área / Línea: dónde opera.",
            "   • Descripción: función del equipo en el proceso.",
            "   • Paros significativos (12 meses): NÚMERO de paros que superaron",
            "     el tiempo máximo permitido sin impacto en los últimos 12 meses.",
            "",
            "3. NO captures aquí obsolescencia, capacidad, redirección ni aging.",
            "   Esos criterios se evalúan MANUAL en la app, con operaciones e",
            "   ingeniería industrial, porque son criterio de negocio.",
            "",
            "4. Los activos entran a la app como 'Pendiente de evaluar' y NO",
            "   aparecen en el ranking hasta que completes los 3 criterios manuales.",
            "",
            "REFERENCIA — Nivel de paros que asigna la app automáticamente:",
            "   0 paros = Nivel 1 | 1–2 = Nivel 2 | 3–5 = Nivel 3 | 6–10 = Nivel 4 | >10 = Nivel 5",
        ]
    })

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        datos.to_excel(writer, index=False, sheet_name="Activos")
        instrucciones.to_excel(writer, index=False, sheet_name="Instrucciones")

        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        wb = writer.book
        header_fill = PatternFill("solid", fgColor="1E3A5F")
        header_font = Font(color="FFFFFF", bold=True, size=11, name="Calibri")
        title_font = Font(color="1E3A5F", bold=True, size=12, name="Calibri")
        thin = Side(style="thin", color="D0D7DE")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        # Hoja Activos
        ws = writer.sheets["Activos"]
        widths = {"A": 30, "B": 26, "C": 42, "D": 30}
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=4):
            for cell in row:
                cell.border = border
                cell.alignment = Alignment(vertical="center")
        ws.freeze_panes = "A2"

        # Hoja Instrucciones
        wi = writer.sheets["Instrucciones"]
        wi.column_dimensions["A"].width = 78
        wi["A1"].fill = header_fill
        wi["A1"].font = header_font
        wi["A1"].alignment = Alignment(horizontal="left", vertical="center")
        for r in range(2, wi.max_row + 1):
            wi.cell(row=r, column=1).font = title_font if wi.cell(row=r, column=1).value and wi.cell(row=r, column=1).value.startswith("REFERENCIA") else Font(size=10, name="Calibri", color="334155")

    buffer.seek(0)
    return buffer


# ══════════════════════════════════════════════════════════════════════════════
# ESTADO DE SESIÓN
# ══════════════════════════════════════════════════════════════════════════════
if "assets" not in st.session_state:
    st.session_state.assets = []


def add_asset(record):
    st.session_state.assets.append(recompute(record))


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <h1>⚙️ Análisis de Criticidad de Activos</h1>
    <p>Criticidad = Obsolescencia × Capacidad × Redirección × Paros&nbsp;&nbsp;·&nbsp;&nbsp;Aging como eje independiente&nbsp;&nbsp;·&nbsp;&nbsp;Alineado a ISO 55000</p>
</div>
""", unsafe_allow_html=True)
st.write("")

tab_bulk, tab_eval, tab_manual, tab_results, tab_export = st.tabs([
    "📤 Carga masiva",
    "📝 Evaluar activos",
    "➕ Alta manual",
    "📊 Resultados",
    "📥 Exportar",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB — CARGA MASIVA
# ══════════════════════════════════════════════════════════════════════════════
with tab_bulk:
    st.subheader("1. Descarga la plantilla")
    st.caption("Llénala solo con los datos que mantenimiento tiene a la mano: listado de activos y número de paros significativos.")
    st.download_button(
        label="📄 Descargar plantilla Excel",
        data=build_template(),
        file_name="plantilla_criticidad_activos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

    st.divider()
    st.subheader("2. Sube tu plantilla llena")
    up = st.file_uploader("Archivo Excel (.xlsx)", type=["xlsx"], key="bulk_uploader")

    if up is not None:
        try:
            df_in = pd.read_excel(up, sheet_name="Activos")
        except Exception:
            # Si la hoja no se llama "Activos", tomar la primera
            df_in = pd.read_excel(up)

        # Normaliza nombres de columna esperados
        cols = {c.strip().lower(): c for c in df_in.columns}
        def find_col(*keys):
            for k in keys:
                for low, orig in cols.items():
                    if k in low:
                        return orig
            return None

        c_eq = find_col("equipo")
        c_ar = find_col("área", "area", "línea", "linea")
        c_de = find_col("descrip")
        c_pa = find_col("paro")

        if not c_eq or not c_pa:
            st.error("La plantilla debe tener al menos las columnas 'Equipo' y 'Paros significativos'. Descarga la plantilla y úsala como base.")
        else:
            df_prev = df_in[[c for c in [c_eq, c_ar, c_de, c_pa] if c]].copy()
            df_prev = df_prev[df_prev[c_eq].notna() & (df_prev[c_eq].astype(str).str.strip() != "")]
            st.markdown("**Vista previa de lo que se va a cargar:**")
            st.dataframe(df_prev, use_container_width=True)

            if st.button("➕ Cargar estos activos", type="primary"):
                existentes = {a["Equipo"] for a in st.session_state.assets}
                added, skipped, bad_stops = 0, 0, 0
                for _, r in df_prev.iterrows():
                    name = str(r[c_eq]).strip()
                    if name in existentes:
                        skipped += 1
                        continue
                    lvl = stops_to_level(r[c_pa]) if c_pa else None
                    if lvl is None:
                        bad_stops += 1
                        lvl = 1  # default conservador; se puede ajustar en Evaluar
                    add_asset({
                        "Equipo": name,
                        "Área": str(r[c_ar]).strip() if c_ar and pd.notna(r[c_ar]) else "",
                        "Descripción": str(r[c_de]).strip() if c_de and pd.notna(r[c_de]) else "",
                        "bottleneck": False,
                        "obs_lvl": None,
                        "cap_lvl": None,
                        "red_lvl": None,
                        "stp_lvl": lvl,
                        "Paros (n)": int(r[c_pa]) if c_pa and pd.notna(r[c_pa]) and str(r[c_pa]).strip() != "" else 0,
                        "age_lvl": None,
                        "tech_lvl": None,
                        "Plan de acción": "",
                    })
                    existentes.add(name)
                    added += 1
                msg = f"✅ {added} activos cargados como **Pendiente de evaluar**."
                if skipped:
                    msg += f" {skipped} omitidos (nombre duplicado)."
                if bad_stops:
                    msg += f" ⚠️ {bad_stops} filas con paros no numéricos → nivel 1 por defecto (ajústalo en Evaluar)."
                st.success(msg)
                st.info("Ahora ve a **Evaluar activos** para completar obsolescencia, capacidad, redirección y (opcional) aging.")

    # Estado actual
    if st.session_state.assets:
        n_pend = sum(1 for a in st.session_state.assets if a["Estado"] == "Pendiente de evaluar")
        n_eval = sum(1 for a in st.session_state.assets if a["Estado"] == "Evaluado")
        st.divider()
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Total activos", len(st.session_state.assets))
        cc2.metric("⏳ Pendientes", n_pend)
        cc3.metric("✅ Evaluados", n_eval)

# ══════════════════════════════════════════════════════════════════════════════
# TAB — EVALUAR ACTIVOS
# ══════════════════════════════════════════════════════════════════════════════
with tab_eval:
    if not st.session_state.assets:
        st.info("No hay activos cargados. Usa **Carga masiva** o **Alta manual** primero.")
    else:
        nombres = [a["Equipo"] for a in st.session_state.assets]
        sel = st.selectbox("Selecciona el activo a evaluar", options=nombres)
        a = next(x for x in st.session_state.assets if x["Equipo"] == sel)

        estado = a["Estado"]
        badge = "🟢 Evaluado" if estado == "Evaluado" else "⏳ Pendiente de evaluar"
        st.markdown(f"**Estado:** {badge}  |  **Paros (12m):** {a.get('Paros (n)', 0)} → Nivel {a['stp_lvl']}")
        st.divider()

        st.subheader("Criterios de criticidad (evaluación manual con negocio)")
        col_a, col_b = st.columns(2)
        with col_a:
            obs = st.selectbox(
                f"1. {CRITERIA_LABELS['obsolescence']}",
                options=[None, 1, 2, 3, 4, 5],
                index=([None, 1, 2, 3, 4, 5].index(a["obs_lvl"]) if a["obs_lvl"] in [1,2,3,4,5] else 0),
                format_func=lambda x: "— sin evaluar —" if x is None else CRITERIA_LEVELS["obsolescence"][x-1],
                key=f"obs_{sel}",
            )
            cap = st.selectbox(
                f"2. {CRITERIA_LABELS['capacity']}",
                options=[None, 1, 2, 3, 4, 5],
                index=([None, 1, 2, 3, 4, 5].index(a["cap_lvl"]) if a["cap_lvl"] in [1,2,3,4,5] else 0),
                format_func=lambda x: "— sin evaluar —" if x is None else CRITERIA_LEVELS["capacity"][x-1],
                key=f"cap_{sel}",
            )
        with col_b:
            red = st.selectbox(
                f"3. {CRITERIA_LABELS['redirection']}",
                options=[None, 1, 2, 3, 4, 5],
                index=([None, 1, 2, 3, 4, 5].index(a["red_lvl"]) if a["red_lvl"] in [1,2,3,4,5] else 0),
                format_func=lambda x: "— sin evaluar —" if x is None else CRITERIA_LEVELS["redirection"][x-1],
                key=f"red_{sel}",
            )
            stp = st.selectbox(
                f"4. {CRITERIA_LABELS['stops']} (viene del histórico, ajustable)",
                options=[1, 2, 3, 4, 5],
                index=(a["stp_lvl"] - 1) if a["stp_lvl"] in [1,2,3,4,5] else 0,
                format_func=lambda x: CRITERIA_LEVELS["stops"][x-1],
                key=f"stp_{sel}",
            )
        bott = st.checkbox(
            "⚠️ Es cuello de botella",
            value=a.get("bottleneck", False),
            help="Si es bottleneck, sube automáticamente a Prioridad 2 como mínimo",
            key=f"bott_{sel}",
        )

        st.divider()
        st.subheader("Aging — envejecimiento (opcional, eje independiente)")
        st.caption("No afecta el score de criticidad. Es contexto para decisiones de inversión (CAPEX).")
        usar_aging = st.checkbox("Evaluar aging de este equipo", value=bool(a.get("age_lvl")), key=f"useaging_{sel}")
        age = tech = None
        if usar_aging:
            col_ag1, col_ag2 = st.columns(2)
            with col_ag1:
                age = st.selectbox(
                    "Edad del equipo",
                    options=[1, 2, 3, 4, 5],
                    index=(a["age_lvl"] - 1) if a.get("age_lvl") else 0,
                    format_func=lambda x: AGE_LEVELS[x],
                    key=f"age_{sel}",
                )
            with col_ag2:
                tech = st.selectbox(
                    "Nivel tecnológico / obsolescencia",
                    options=[1, 2, 3, 4, 5],
                    index=(a["tech_lvl"] - 1) if a.get("tech_lvl") else 0,
                    format_func=lambda x: TECH_LEVELS[x],
                    key=f"tech_{sel}",
                )
            ag_prev, ev_prev = calc_aging(age, tech)
            st.markdown(f"**Aging score:** {ag_prev}  →  **{ev_prev}**")

        st.divider()
        plan = st.text_area(
            "Plan de acción / Reducer (opcional)",
            value=a.get("Plan de acción", ""),
            placeholder="Ej: Aumentar stock de variadores críticos, plan de contingencia con operaciones, capacitación en reparación rápida...",
            key=f"plan_{sel}",
        )

        # Preview
        if all(v in [1,2,3,4,5] for v in (obs, cap, red)):
            sc = calc_score(obs, cap, red, stp)
            pr = get_priority(cap, red, bott)
            colp1, colp2 = st.columns(2)
            with colp1:
                st.markdown(f"""
                <div class="score-box">
                    <div style="font-size:13px;color:#94a3b8;margin-bottom:4px">Índice de criticidad</div>
                    <div class="score-number">{score_pct(sc)}%</div>
                    <div style="font-size:12px;color:#cbd5e1;margin-top:4px">Score crudo: {sc:,}</div>
                </div>
                """, unsafe_allow_html=True)
            with colp2:
                st.markdown("**Prioridad calculada**")
                st.markdown(priority_badge(pr), unsafe_allow_html=True)
                if bott:
                    st.caption("⚠️ Ajustado por bottleneck")
        else:
            st.warning("Completa los 3 criterios de criticidad para calcular el score.")

        if st.button("💾 Guardar evaluación", type="primary", key=f"save_{sel}"):
            a["obs_lvl"] = obs
            a["cap_lvl"] = cap
            a["red_lvl"] = red
            a["stp_lvl"] = stp
            a["bottleneck"] = bott
            a["age_lvl"] = age if usar_aging else None
            a["tech_lvl"] = tech if usar_aging else None
            a["Plan de acción"] = plan.strip()
            recompute(a)
            st.success(f"✅ Evaluación de **{sel}** guardada. Estado: **{a['Estado']}**")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB — ALTA MANUAL (equipo individual completo)
# ══════════════════════════════════════════════════════════════════════════════
with tab_manual:
    st.subheader("Alta manual de un equipo")
    col1, col2 = st.columns(2)
    with col1:
        asset_name = st.text_input("Nombre del equipo / grupo", placeholder="Ej: Compresor de aire #3")
        area = st.text_input("Área / Línea", placeholder="Ej: Línea 4 — Ensamble")
        n_stops = st.number_input("Paros significativos (12 meses)", min_value=0, step=1, value=0,
                                  help="Número de paros que superaron el tiempo máximo permitido")
    with col2:
        description = st.text_area("Descripción breve", placeholder="Función del equipo en el proceso", height=100)
        is_bottleneck_m = st.checkbox("⚠️ Es cuello de botella", key="bott_manual")

    st.divider()
    st.subheader("Evaluación de criterios")
    st.caption("Nivel 1 (mejor) al 5 (peor). Escala no lineal — nivel 5 penaliza fuerte.")
    col_a, col_b = st.columns(2)
    with col_a:
        obs_m = st.selectbox(f"1. {CRITERIA_LABELS['obsolescence']}", options=[1,2,3,4,5],
                             format_func=lambda x: CRITERIA_LEVELS["obsolescence"][x-1], key="obs_manual")
        cap_m = st.selectbox(f"2. {CRITERIA_LABELS['capacity']}", options=[1,2,3,4,5],
                             format_func=lambda x: CRITERIA_LEVELS["capacity"][x-1], key="cap_manual")
    with col_b:
        red_m = st.selectbox(f"3. {CRITERIA_LABELS['redirection']}", options=[1,2,3,4,5],
                             format_func=lambda x: CRITERIA_LEVELS["redirection"][x-1], key="red_manual")
        stp_m = stops_to_level(n_stops)
        st.info(f"Paros: {n_stops} → **Nivel {stp_m}** ({CRITERIA_LEVELS['stops'][stp_m-1]})")

    # Aging opcional
    st.divider()
    st.subheader("Aging (opcional, eje independiente)")
    usar_aging_m = st.checkbox("Evaluar aging", key="useaging_manual")
    age_m = tech_m = None
    if usar_aging_m:
        col_ag1, col_ag2 = st.columns(2)
        with col_ag1:
            age_m = st.selectbox("Edad", options=[1,2,3,4,5], format_func=lambda x: AGE_LEVELS[x], key="age_manual")
        with col_ag2:
            tech_m = st.selectbox("Nivel tecnológico", options=[1,2,3,4,5], format_func=lambda x: TECH_LEVELS[x], key="tech_manual")

    score_preview = calc_score(obs_m, cap_m, red_m, stp_m)
    priority_preview = get_priority(cap_m, red_m, is_bottleneck_m)

    st.divider()
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.markdown(f"""
        <div class="score-box">
            <div style="font-size:13px;color:#94a3b8;margin-bottom:4px">Índice de criticidad</div>
            <div class="score-number">{score_pct(score_preview)}%</div>
            <div style="font-size:12px;color:#cbd5e1;margin-top:4px">Score crudo: {score_preview:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_s2:
        st.markdown("**Prioridad calculada**")
        st.markdown(priority_badge(priority_preview), unsafe_allow_html=True)
        if is_bottleneck_m:
            st.caption("⚠️ Ajustado por bottleneck")
    with col_s3:
        st.metric("Índice de criticidad", f"{score_pct(score_preview)}%")
        st.caption(f"Score crudo: {score_preview:,}")

    st.divider()
    action_plan = st.text_area("Plan de acción / Reducer (opcional)",
                               placeholder="Acciones para reducir la criticidad...", height=90, key="plan_manual")

    if st.button("✅ Agregar equipo", type="primary", key="add_manual"):
        if not asset_name.strip():
            st.error("El nombre del equipo es obligatorio.")
        elif asset_name.strip() in {x["Equipo"] for x in st.session_state.assets}:
            st.error("Ya existe un equipo con ese nombre.")
        else:
            add_asset({
                "Equipo": asset_name.strip(),
                "Área": area.strip(),
                "Descripción": description.strip(),
                "bottleneck": is_bottleneck_m,
                "obs_lvl": obs_m,
                "cap_lvl": cap_m,
                "red_lvl": red_m,
                "stp_lvl": stp_m,
                "Paros (n)": int(n_stops),
                "age_lvl": age_m if usar_aging_m else None,
                "tech_lvl": tech_m if usar_aging_m else None,
                "Plan de acción": action_plan.strip(),
            })
            st.success(f"✅ **{asset_name}** agregado. Score: **{score_preview:,}** | Prioridad: **{priority_preview}**")

# ══════════════════════════════════════════════════════════════════════════════
# TAB — RESULTADOS
# ══════════════════════════════════════════════════════════════════════════════
with tab_results:
    if not st.session_state.assets:
        st.info("Aún no hay activos. Usa **Carga masiva** o **Alta manual**.")
    else:
        evaluados = [a for a in st.session_state.assets if a["Estado"] == "Evaluado"]
        pendientes = [a for a in st.session_state.assets if a["Estado"] == "Pendiente de evaluar"]

        st.subheader("Resumen")
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Total", len(st.session_state.assets))
        k2.metric("⏳ Pendientes", len(pendientes))
        k3.metric("🔴 P1", sum(1 for a in evaluados if a["Prioridad"] == "P1"))
        k4.metric("🟠 P2", sum(1 for a in evaluados if a["Prioridad"] == "P2"))
        k5.metric("🟡 P3", sum(1 for a in evaluados if a["Prioridad"] == "P3"))
        k6.metric("🟢 P4", sum(1 for a in evaluados if a["Prioridad"] == "P4"))

        if pendientes:
            st.warning(f"⏳ {len(pendientes)} activo(s) pendientes de evaluar — no aparecen en el ranking hasta completar los 3 criterios: " +
                       ", ".join(a["Equipo"] for a in pendientes))

        st.divider()
        st.subheader("Ranking de criticidad (solo evaluados)")

        if not evaluados:
            st.info("Ningún activo evaluado todavía. Ve a **Evaluar activos**.")
        else:
            df = pd.DataFrame(evaluados).sort_values("Score", ascending=False).reset_index(drop=True)
            df.index += 1
            for i, row in df.iterrows():
                p = row["Prioridad"]
                aging_txt = f"  |  Aging: {row['AgingEV']}" if row["AgingScore"] else ""
                with st.expander(f"#{i}  {row['Equipo']}  —  Índice: {score_pct(row['Score'])}%  |  {p}{aging_txt}", expanded=(p == "P1")):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"**Área:** {row['Área']}")
                        st.markdown(f"**Descripción:** {row['Descripción']}")
                        st.markdown(f"**Bottleneck:** {'Sí' if row['bottleneck'] else 'No'}")
                    with c2:
                        st.markdown("**Criterios (factores):**")
                        fo, fc, fr, fs = SCORE_MAP[row["obs_lvl"]], SCORE_MAP[row["cap_lvl"]], SCORE_MAP[row["red_lvl"]], SCORE_MAP[row["stp_lvl"]]
                        st.write(f"• Obsolescencia: N{row['obs_lvl']} → ×{fo}")
                        st.write(f"• Capacidad PPR: N{row['cap_lvl']} → ×{fc}")
                        st.write(f"• Redirección: N{row['red_lvl']} → ×{fr}")
                        st.write(f"• Paros ({row.get('Paros (n)',0)}): N{row['stp_lvl']} → ×{fs}")
                        st.caption(f"{fo} × {fc} × {fr} × {fs} = **{row['Score']:,}**")
                    with c3:
                        st.markdown(f"**Índice de criticidad:** {score_pct(row['Score'])}%")
                        st.caption(f"Score crudo: {row['Score']:,}")
                        st.markdown(priority_badge(p), unsafe_allow_html=True)
                        if row["AgingScore"]:
                            st.markdown(f"**Aging:** {row['AgingEV']}")
                        if row["Plan de acción"]:
                            st.markdown("**Plan de acción:**")
                            st.info(row["Plan de acción"])

        # Gestionar
        st.divider()
        st.subheader("Gestionar activos")
        colg1, colg2 = st.columns(2)
        with colg1:
            equipo_del = st.selectbox("Eliminar activo", options=[a["Equipo"] for a in st.session_state.assets])
            if st.button("🗑️ Eliminar", type="secondary"):
                st.session_state.assets = [a for a in st.session_state.assets if a["Equipo"] != equipo_del]
                st.success(f"Activo **{equipo_del}** eliminado.")
                st.rerun()
        with colg2:
            st.write("")
            st.write("")
            if st.button("🧹 Borrar todo", type="secondary"):
                st.session_state.assets = []
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB — EXPORTAR
# ══════════════════════════════════════════════════════════════════════════════
with tab_export:
    if not st.session_state.assets:
        st.info("Agrega activos primero para poder exportar.")
    else:
        rows = []
        for a in st.session_state.assets:
            rows.append({
                "Equipo": a["Equipo"],
                "Área": a["Área"],
                "Descripción": a["Descripción"],
                "Estado": a["Estado"],
                "Bottleneck": "Sí" if a["bottleneck"] else "No",
                "Obsolescencia (lvl)": a["obs_lvl"],
                "Capacidad PPR (lvl)": a["cap_lvl"],
                "Redirección (lvl)": a["red_lvl"],
                "Paros (n)": a.get("Paros (n)", 0),
                "Paros (lvl)": a["stp_lvl"],
                "Score criticidad": a["Score"],
                "Prioridad": a["Prioridad"],
                "Índice criticidad (%)": score_pct(a["Score"]) if a["Score"] else "",
                "Aging score": a["AgingScore"] if a["AgingScore"] else "",
                "Aging (banda)": a["AgingEV"] if a["AgingScore"] else "",
                "Plan de acción": a["Plan de acción"],
            })
        df_export = pd.DataFrame(rows)
        # Ordena: evaluados por score desc, pendientes al final
        df_export["_ord"] = df_export["Score criticidad"].fillna(-1)
        df_export = df_export.sort_values("_ord", ascending=False).drop(columns="_ord").reset_index(drop=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Criticidad")
        buffer.seek(0)

        st.download_button(
            label="📥 Descargar resultados (Excel)",
            data=buffer,
            file_name="analisis_criticidad_resultados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
        st.divider()
        st.dataframe(df_export, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown("""
<div class="app-footer">
    <strong>Jesús Jaramillo</strong> — Reliability Management<br>
    Herramienta de análisis de criticidad de activos · Alineado a ISO 55000
</div>
""", unsafe_allow_html=True)
