import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timezone
import random

# ── Config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="NativeCards",
    page_icon="🃏",
    layout="centered",
    initial_sidebar_state="collapsed",
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_client()

# ── CSS personalizado ────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { max-width: 720px; margin: auto; }
.nc-card {
    background: #EEEDFE;
    border: 1px solid #AFA9EC;
    border-radius: 14px;
    padding: 2rem 1.5rem;
    text-align: center;
    min-height: 160px;
    cursor: pointer;
    transition: box-shadow .2s;
    margin-bottom: .5rem;
}
.nc-card-back {
    background: #E1F5EE;
    border-color: #5DCAA5;
}
.nc-tag { font-size: .72rem; letter-spacing: .06em; color: #534AB7; text-transform: uppercase; margin-bottom: .5rem; }
.nc-tag-error { color: #993C1D; }
.nc-main { font-size: 1.3rem; font-weight: 600; color: #26215C; margin-bottom: .4rem; }
.nc-main-back { color: #04342C; }
.nc-sub { font-size: .9rem; color: #534AB7; }
.nc-sub-back { color: #085041; }
.nc-example { font-size: .82rem; color: #3C3489; margin-top: .7rem; font-style: italic; }
.nc-hint { font-size: .75rem; color: #888780; margin-top: .8rem; }
.nc-streak { background:#FAEEDA; border-radius:10px; padding:.5rem 1rem;
             display:inline-block; font-size:.9rem; color:#633806; font-weight:600; }
.tense-pill {
    background:#EEEDFE; border:1px solid #AFA9EC; border-radius:99px;
    padding:.3rem .9rem; font-size:.8rem; color:#3C3489; cursor:pointer;
    display:inline-block; margin:.2rem;
}
.tense-pill-done { background:#EAF3DE; border-color:#97C459; color:#3B6D11; }
</style>
""", unsafe_allow_html=True)


# ── Helpers de Supabase ──────────────────────────────────────
def get_or_create_nc_user(user):
    res = supabase.table("nc_users").select("*").eq("user_id", user.id).execute()
    if res.data:
        return res.data[0]
    new = supabase.table("nc_users").insert({
        "user_id": user.id,
        "display_name": user.email.split("@")[0],
        "email": user.email,
    }).execute()
    return new.data[0]


def load_cards(filter_type=None):
    q = supabase.table("nc_cards").select("*").eq("is_active", True)
    if filter_type and filter_type != "todas":
        q = q.eq("type", filter_type)
    return q.execute().data or []


def load_tenses():
    return supabase.table("nc_tenses").select("*").order("sort_order").execute().data or []


def get_progress(user_id):
    return supabase.table("nc_user_progress").select("*").eq("user_id", user_id).execute().data or []


def upsert_progress(user_id, card_id, known: bool):
    existing = supabase.table("nc_user_progress")\
        .select("*").eq("user_id", user_id).eq("card_id", card_id).execute().data
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        row = existing[0]
        supabase.table("nc_user_progress").update({
            "known": known,
            "times_seen": row["times_seen"] + 1,
            "times_correct": row["times_correct"] + (1 if known else 0),
            "last_seen_at": now,
        }).eq("id", row["id"]).execute()
    else:
        supabase.table("nc_user_progress").insert({
            "user_id": user_id,
            "card_id": card_id,
            "known": known,
            "times_seen": 1,
            "times_correct": 1 if known else 0,
            "last_seen_at": now,
        }).execute()


def save_session(user_id, reviewed, correct):
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("nc_sessions").insert({
        "user_id": user_id,
        "started_at": now,
        "ended_at": now,
        "cards_reviewed": reviewed,
        "correct_count": correct,
    }).execute()


def update_streak(nc_user):
    today = datetime.now(timezone.utc).date()
    last = nc_user.get("last_session_at")
    streak = nc_user.get("streak_days", 0)
    if last:
        last_date = datetime.fromisoformat(last).date()
        diff = (today - last_date).days
        if diff == 1:
            streak += 1
        elif diff > 1:
            streak = 1
    else:
        streak = 1
    supabase.table("nc_users").update({
        "streak_days": streak,
        "last_session_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", nc_user["user_id"]).execute()
    return streak


# ── Autenticación ────────────────────────────────────────────
def pantalla_login():
    st.markdown("## 🃏 NativeCards")
    st.markdown("Aprende inglés con tus propias expresiones y errores corregidos.")
    st.divider()

    tab_login, tab_register = st.tabs(["Iniciar sesión", "Registrarse"])

    with tab_login:
        email = st.text_input("Correo electrónico", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar", use_container_width=True, type="primary"):
            if not email or not password:
                st.warning("Ingresa tu correo y contraseña.")
                return
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["user"] = res.user
                st.session_state["session"] = res.session
                st.rerun()
            except Exception as e:
                st.error(f"Error al iniciar sesión: {e}")

    with tab_register:
        r_email = st.text_input("Correo electrónico", key="reg_email")
        r_pass  = st.text_input("Contraseña (mínimo 6 caracteres)", type="password", key="reg_pass")
        r_name  = st.text_input("Tu nombre", key="reg_name")
        if st.button("Crear cuenta", use_container_width=True):
            if not r_email or not r_pass or not r_name:
                st.warning("Completa todos los campos.")
                return
            try:
                res = supabase.auth.sign_up({"email": r_email, "password": r_pass})
                if res.user:
                    supabase.table("nc_users").insert({
                        "user_id": res.user.id,
                        "display_name": r_name,
                        "email": r_email,
                    }).execute()
                    st.success("¡Cuenta creada! Revisa tu correo para confirmar y luego inicia sesión.")
                else:
                    st.error("No se pudo crear la cuenta.")
            except Exception as e:
                st.error(f"Error: {e}")


# ── Módulo Flashcards ────────────────────────────────────────
def modulo_flashcards(user, nc_user):
    st.markdown("### 🃏 Flashcards")

    progress_data = get_progress(user.id)
    known_ids = {p["card_id"] for p in progress_data if p["known"]}
    total_seen = len(progress_data)

    col1, col2, col3 = st.columns(3)
    col1.metric("Tarjetas vistas", total_seen)
    col2.metric("Dominadas ✅", len(known_ids))
    col3.metric("Para repasar 🔁", sum(1 for p in progress_data if not p["known"]))

    st.divider()

    filtro = st.radio(
        "Mostrar:",
        ["todas", "native", "error"],
        format_func=lambda x: {"todas": "Todas", "native": "Expresiones nativas", "error": "Errores corregidos"}[x],
        horizontal=True,
        key="fc_filter",
    )

    cards = load_cards(filtro)
    if not cards:
        st.info("No hay tarjetas con ese filtro todavía.")
        return

    random.shuffle(cards)

    if "fc_index" not in st.session_state:
        st.session_state.fc_index = 0
        st.session_state.fc_flipped = False
        st.session_state.fc_correct = 0
        st.session_state.fc_reviewed = 0

    idx = st.session_state.fc_index % len(cards)
    card = cards[idx]

    progress_pct = int((idx / len(cards)) * 100)
    st.progress(progress_pct, text=f"Tarjeta {idx + 1} de {len(cards)}")

    tag_class = "nc-tag" if card["type"] == "native" else "nc-tag nc-tag-error"
    tag_label = "Expresión nativa" if card["type"] == "native" else "Error corregido"

    if not st.session_state.fc_flipped:
        st.markdown(f"""
        <div class="nc-card">
            <div class="{tag_class}">{tag_label}</div>
            <div class="nc-main">{card['front_text']}</div>
            <div class="nc-sub">{card.get('example_sentence', '¿Cómo lo dirías de forma más natural?')}</div>
            <div class="nc-hint">👆 Toca el botón para ver la respuesta</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Ver respuesta 👁", use_container_width=True):
            st.session_state.fc_flipped = True
            st.rerun()
    else:
        st.markdown(f"""
        <div class="nc-card nc-card-back">
            <div class="nc-tag" style="color:#0F6E56;">Respuesta</div>
            <div class="nc-main nc-main-back">{card['back_text']}</div>
            <div class="nc-sub nc-sub-back">{card.get('example_sentence', '')}</div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("❌ No lo sabía", use_container_width=True):
                upsert_progress(user.id, card["id"], False)
                st.session_state.fc_reviewed += 1
                st.session_state.fc_index += 1
                st.session_state.fc_flipped = False
                st.rerun()
        with c2:
            if st.button("⏭ Saltar", use_container_width=True):
                st.session_state.fc_index += 1
                st.session_state.fc_flipped = False
                st.rerun()
        with c3:
            if st.button("✅ Lo sabía", use_container_width=True, type="primary"):
                upsert_progress(user.id, card["id"], True)
                st.session_state.fc_reviewed += 1
                st.session_state.fc_correct += 1
                st.session_state.fc_index += 1
                st.session_state.fc_flipped = False
                st.rerun()

    if st.session_state.fc_reviewed > 0 and st.session_state.fc_reviewed % 5 == 0:
        save_session(user.id, st.session_state.fc_reviewed, st.session_state.fc_correct)
        update_streak(nc_user)


# ── Módulo Tiempos Verbales ──────────────────────────────────
def modulo_tiempos(user, nc_user):
    st.markdown("### 📖 Los 12 tiempos verbales")

    tenses = load_tenses()
    if not tenses:
        st.warning("No se encontraron tiempos verbales en la base de datos.")
        return

    progress_data = get_progress(user.id)
    tense_card_ids = {}
    for t in tenses:
        cards = supabase.table("nc_cards").select("id").eq("tense_id", t["id"]).execute().data or []
        tense_card_ids[t["id"]] = [c["id"] for c in cards]

    groups = {
        "simple": "Simples",
        "continuous": "Continuos",
        "perfect": "Perfectos",
        "perfect_continuous": "Perfecto continuo",
    }

    selected_tense = st.session_state.get("selected_tense", None)

    if selected_tense is None:
        for group_key, group_label in groups.items():
            st.markdown(f"**{group_label}**")
            group_tenses = [t for t in tenses if t["tense_group"] == group_key]
            cols = st.columns(2)
            for i, tense in enumerate(group_tenses):
                card_ids = tense_card_ids.get(tense["id"], [])
                known = sum(1 for p in progress_data if p["card_id"] in card_ids and p["known"])
                badge = f"✅ {known} dominadas" if known else "Pendiente"
                with cols[i % 2]:
                    with st.container(border=True):
                        st.markdown(f"**{tense['label_es']}**")
                        st.caption(f"_{tense.get('example_en', '')}_")
                        st.caption(f"📌 {tense.get('example_context_es', '')}")
                        st.markdown(f"`{tense.get('formula', '')}`")
                        if st.button(f"Practicar →", key=f"tense_{tense['id']}"):
                            st.session_state.selected_tense = tense
                            st.session_state.tense_flipped = False
                            st.session_state.tense_idx = 0
                            st.rerun()
    else:
        tense = selected_tense
        if st.button("← Volver a tiempos"):
            st.session_state.selected_tense = None
            st.rerun()

        st.markdown(f"#### {tense['label_es']}")
        st.markdown(f"**Fórmula:** `{tense.get('formula', '')}`")
        st.info(f"📌 {tense.get('example_context_es', '')}")

        cards = supabase.table("nc_cards").select("*").eq("tense_id", tense["id"]).execute().data or []

        if not cards:
            st.warning("Este tiempo aún no tiene tarjetas. Puedes agregarlas desde el Panel de administración.")
            st.markdown("**Ejemplo base:**")
            st.markdown(f"> _{tense.get('example_en', '')}_")
            return

        tidx = st.session_state.get("tense_idx", 0) % len(cards)
        card = cards[tidx]
        st.progress(int((tidx / len(cards)) * 100), text=f"Tarjeta {tidx + 1} de {len(cards)}")

        if not st.session_state.get("tense_flipped", False):
            st.markdown(f"""
            <div class="nc-card">
                <div class="nc-tag">Tiempo verbal</div>
                <div class="nc-main">{card['front_text']}</div>
                <div class="nc-hint">👆 Ver traducción / explicación</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Ver respuesta 👁", use_container_width=True, key="tense_flip"):
                st.session_state.tense_flipped = True
                st.rerun()
        else:
            st.markdown(f"""
            <div class="nc-card nc-card-back">
                <div class="nc-tag" style="color:#0F6E56;">Respuesta</div>
                <div class="nc-main nc-main-back">{card['back_text']}</div>
                <div class="nc-sub nc-sub-back">{card.get('example_sentence','')}</div>
            </div>
            """, unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("❌ Repasar", use_container_width=True, key="tense_wrong"):
                    upsert_progress(user.id, card["id"], False)
                    st.session_state.tense_idx = tidx + 1
                    st.session_state.tense_flipped = False
                    st.rerun()
            with c2:
                if st.button("✅ Dominada", use_container_width=True, type="primary", key="tense_right"):
                    upsert_progress(user.id, card["id"], True)
                    st.session_state.tense_idx = tidx + 1
                    st.session_state.tense_flipped = False
                    st.rerun()


# ── Módulo Progreso ──────────────────────────────────────────
def modulo_progreso(user, nc_user):
    st.markdown("### 📊 Mi progreso")

    streak = nc_user.get("streak_days", 0)
    st.markdown(f'<div class="nc-streak">🔥 {streak} día{"s" if streak != 1 else ""} de racha</div>', unsafe_allow_html=True)
    st.markdown("")

    progress_data = get_progress(user.id)
    total = len(progress_data)
    known = sum(1 for p in progress_data if p["known"])
    pct = int((known / total * 100)) if total else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Tarjetas vistas", total)
    col2.metric("Dominadas", known)
    col3.metric("Precisión", f"{pct}%")

    st.divider()
    st.markdown("**Distribución por tipo**")

    all_cards = load_cards()
    native_ids = {c["id"] for c in all_cards if c["type"] == "native"}
    error_ids  = {c["id"] for c in all_cards if c["type"] == "error"}

    seen_native  = sum(1 for p in progress_data if p["card_id"] in native_ids)
    seen_error   = sum(1 for p in progress_data if p["card_id"] in error_ids)

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**Expresiones nativas**")
            st.metric("Vistas", seen_native)
    with c2:
        with st.container(border=True):
            st.markdown("**Errores corregidos**")
            st.metric("Vistas", seen_error)

    st.divider()
    st.markdown("**Últimas sesiones**")
    sessions = supabase.table("nc_sessions").select("*")\
        .eq("user_id", user.id).order("started_at", desc=True).limit(5).execute().data or []

    if sessions:
        for s in sessions:
            fecha = s["started_at"][:10]
            pct_s = int(s["correct_count"] / s["cards_reviewed"] * 100) if s["cards_reviewed"] else 0
            st.markdown(f"- {fecha} — {s['cards_reviewed']} tarjetas · {pct_s}% aciertos")
    else:
        st.info("Aún no tienes sesiones registradas. ¡Practica para ver tu historial!")


# ── Módulo Perfil ────────────────────────────────────────────
def modulo_perfil(user, nc_user):
    st.markdown("### 👤 Mi perfil")

    with st.container(border=True):
        st.markdown(f"**{nc_user.get('display_name', 'Usuario')}**")
        st.caption(nc_user.get("email", ""))
        st.caption(f"Miembro desde: {nc_user.get('created_at', '')[:10]}")

    st.divider()
    st.markdown("**Actualizar nombre**")
    new_name = st.text_input("Nuevo nombre", value=nc_user.get("display_name", ""))
    if st.button("Guardar"):
        supabase.table("nc_users").update({"display_name": new_name})\
            .eq("user_id", user.id).execute()
        st.success("¡Nombre actualizado!")
        st.rerun()

    st.divider()
    if st.button("Cerrar sesión", type="secondary"):
        supabase.auth.sign_out()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ── App principal ────────────────────────────────────────────
def main():
    if "user" not in st.session_state:
        pantalla_login()
        return

    user = st.session_state["user"]
    nc_user = get_or_create_nc_user(user)

    nombre = nc_user.get("display_name", "Usuario")
    streak = nc_user.get("streak_days", 0)

    st.sidebar.markdown(f"👋 Hola, **{nombre}**")
    st.sidebar.markdown(f"🔥 Racha: **{streak} día{'s' if streak != 1 else ''}**")
    st.sidebar.divider()

    seccion = st.sidebar.radio(
        "Navegar",
        ["🃏 Flashcards", "📖 Tiempos verbales", "📊 Progreso", "👤 Perfil"],
    )

    if seccion == "🃏 Flashcards":
        modulo_flashcards(user, nc_user)
    elif seccion == "📖 Tiempos verbales":
        modulo_tiempos(user, nc_user)
    elif seccion == "📊 Progreso":
        modulo_progreso(user, nc_user)
    elif seccion == "👤 Perfil":
        modulo_perfil(user, nc_user)


if __name__ == "__main__":
    main()
