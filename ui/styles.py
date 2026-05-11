import streamlit as st


def inject_app_styles() -> None:
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            max-width: 1550px;
        }

        .app-header {
            padding: 0.45rem 0.85rem;
            border-radius: 12px;
            background: linear-gradient(135deg, #111827 0%, #1e293b 55%, #0f172a 100%);
            border: 1px solid #334155;
            margin-bottom: 0.45rem;
            box-shadow: 0 3px 10px rgba(0, 0, 0, 0.16);
        }
        
        .app-title {
            color: #f8fafc !important;
            font-size: 1.2rem;
            font-weight: 800;
            line-height: 1.05;
            margin-bottom: 0.1rem;
        }
        
        .app-subtitle {
            color: #cbd5e1 !important;
            font-size: 0.78rem;
        }

        .panel-title {
            font-weight: 750;
            font-size: 1.02rem;
            margin-bottom: 0.15rem;
        }

        .muted-text {
            color: #94a3b8;
            font-size: 0.84rem;
            margin-bottom: 0.45rem;
        }

        .status-pill {
            display: inline-block;
            padding: 0.18rem 0.58rem;
            border-radius: 999px;
            background: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
            font-size: 0.76rem;
            font-weight: 700;
        }

        .danger-pill {
            display: inline-block;
            padding: 0.18rem 0.58rem;
            border-radius: 999px;
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
            font-size: 0.76rem;
            font-weight: 700;
        }

        .neutral-pill {
            display: inline-block;
            padding: 0.18rem 0.58rem;
            border-radius: 999px;
            background: #e2e8f0;
            color: #334155;
            border: 1px solid #cbd5e1;
            font-size: 0.76rem;
            font-weight: 700;
        }

        div[data-testid="stExpander"] {
            border-radius: 12px;
        }

        .small-caption {
            color: #94a3b8;
            font-size: 0.8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def panel_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"<div class='panel-title'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(
            f"<div class='muted-text'>{subtitle}</div>",
            unsafe_allow_html=True,
        )


def status_pill(text: str, *, kind: str = "neutral") -> None:
    css_class = {
        "ok": "status-pill",
        "danger": "danger-pill",
        "neutral": "neutral-pill",
    }.get(kind, "neutral-pill")

    st.markdown(
        f"<span class='{css_class}'>{text}</span>",
        unsafe_allow_html=True,
    )