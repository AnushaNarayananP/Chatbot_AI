import html

import streamlit as st

from chatbot import BOT_NAME, DEFAULT_MODEL, SYSTEM_PROMPT, route_chat_request
from vision_handler import validate_image_url


APP_TITLE = "FriendlyBot"
STATUS_TEXT = "Online"


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def inject_styles():
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(circle at top, rgba(255,255,255,0.95), rgba(240,229,255,0.82) 40%, rgba(228,212,252,0.72) 65%, rgba(218,197,247,0.78)),
                    linear-gradient(180deg, #f8f3ff 0%, #ebddfb 100%);
            }

            .block-container {
                padding-top: 1.25rem;
                padding-bottom: 1.2rem;
                max-width: 860px;
            }

            h1.page-title {
                text-align: center;
                font-size: 2.1rem;
                font-weight: 700;
                color: #161327;
                margin-bottom: 1rem;
                letter-spacing: -0.02em;
            }

            .st-key-chat_box {
                max-width: 480px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.78);
                border: 1px solid rgba(255, 255, 255, 0.72);
                border-radius: 28px;
                backdrop-filter: blur(18px);
                box-shadow: 0 24px 70px rgba(93, 63, 140, 0.16);
                overflow: hidden;
                padding: 0 !important;
            }

            .st-key-chat_box > div {
                padding: 0 !important;
            }

            .chat-topbar {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 1rem 1rem 0.85rem 1rem;
                border-bottom: 1px solid rgba(122, 96, 167, 0.12);
                background: rgba(255, 255, 255, 0.62);
            }

            .brand-wrap {
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }

            .brand-icon {
                width: 36px;
                height: 36px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: linear-gradient(135deg, #7c3aed, #a855f7);
                color: white;
                font-size: 1rem;
                font-weight: 700;
                box-shadow: 0 10px 20px rgba(124, 58, 237, 0.25);
            }

            .brand-meta {
                display: flex;
                flex-direction: column;
                line-height: 1.15;
            }

            .brand-name {
                font-size: 1rem;
                font-weight: 700;
                color: #1f1636;
            }

            .brand-status {
                font-size: 0.8rem;
                color: #6b5d85;
                margin-top: 0.2rem;
            }

            .window-actions {
                color: #8c7aa9;
                font-size: 1rem;
                display: flex;
                gap: 0.65rem;
                align-items: center;
            }

            .date-row {
                text-align: center;
                font-size: 0.76rem;
                color: #8d7ca7;
                padding: 0.7rem 1rem 0.35rem 1rem;
            }

            .chat-history {
                height: 240px;
                overflow-y: auto;
                padding: 0.65rem 1rem 0.25rem 1rem;
                background: linear-gradient(180deg, rgba(255,255,255,0.52), rgba(250,245,255,0.7));
                scrollbar-width: thin;
                scrollbar-color: rgba(124, 58, 237, 0.45) transparent;
            }

            .chat-history::-webkit-scrollbar {
                width: 8px;
            }

            .chat-history::-webkit-scrollbar-track {
                background: transparent;
            }

            .chat-history::-webkit-scrollbar-thumb {
                background: rgba(124, 58, 237, 0.45);
                border-radius: 999px;
            }

            .message-row {
                display: flex;
                margin-bottom: 0.55rem;
            }

            .message-row.user {
                justify-content: flex-end;
            }

            .message-row.bot {
                justify-content: flex-start;
            }

            .message-bubble {
                max-width: 82%;
                padding: 0.8rem 1rem;
                border-radius: 18px;
                font-size: 0.97rem;
                line-height: 1.45;
                box-shadow: 0 8px 18px rgba(93, 63, 140, 0.08);
                word-wrap: break-word;
                white-space: pre-wrap;
            }

            .message-row.bot .message-bubble {
                background: #f4effd;
                color: #24183c;
                border-top-left-radius: 8px;
            }

            .message-row.user .message-bubble {
                background: linear-gradient(135deg, #7c3aed, #9333ea);
                color: white;
                border-top-right-radius: 8px;
            }

            .inner-pad {
                padding: 0.05rem 1rem 0.5rem 1rem;
            }

            .divider {
                height: 1px;
                background: rgba(122, 96, 167, 0.12);
                margin: 0;
            }

            .input-label {
                margin: 0.3rem 0 0.3rem 0;
                color: #3f3658;
                font-size: 0.9rem;
                font-weight: 600;
            }

            .stTextInput > div > div > input {
                border-radius: 999px;
                border: 1px solid rgba(141, 113, 189, 0.26);
                background: rgba(255, 255, 255, 0.88);
                padding: 8px 10px;
                font-size: 14px;
                height: 40px;
                box-shadow: 0 10px 26px rgba(93, 63, 140, 0.07);
            }

            .stTextInput > div {
                margin-bottom: 0 !important;
            }

            .stButton > button,
            .stFormSubmitButton > button {
                border-radius: 999px;
                border: none;
                background: linear-gradient(135deg, #7c3aed, #9333ea);
                color: white;
                font-weight: 600;
                padding: 0.62rem 1.1rem;
                box-shadow: 0 10px 22px rgba(124, 58, 237, 0.22);
            }

            .composer-row {
                margin-top: 0.1rem;
            }

            .stFormSubmitButton > button {
                min-width: 40px;
                width: 40px;
                height: 40px;
                padding: 0;
                border-radius: 999px;
                font-size: 1.05rem;
                font-weight: 700;
                line-height: 1;
            }

            .input-bar-shell {
                margin-top: 0.25rem;
                padding: 0.4rem 0.45rem;
                border: 1px solid rgba(141, 113, 189, 0.18);
                border-radius: 22px;
                background: rgba(255, 255, 255, 0.72);
                box-shadow: 0 10px 24px rgba(93, 63, 140, 0.08);
            }

            .stPopover > div > button {
                min-width: 40px;
                width: 40px;
                height: 40px;
                padding: 0;
                border-radius: 999px;
                border: 1px solid rgba(141, 113, 189, 0.14);
                background: rgba(124, 58, 237, 0.08);
                color: #6a35d4;
                box-shadow: none;
                font-size: 1rem;
                font-weight: 700;
            }

            .stPopover > div > button:hover {
                background: rgba(124, 58, 237, 0.14);
            }

            .composer-row div[data-testid="column"] {
                display: flex;
                align-items: center;
            }

            .composer-row div[data-testid="column"] > div {
                width: 100%;
            }

            .composer-input {
                width: 100%;
            }

            .composer-input div[data-baseweb="input"] {
                height: 40px;
                border-radius: 999px;
                overflow: hidden;
            }

            .composer-input input {
                height: 40px !important;
                padding-top: 0 !important;
                padding-bottom: 0 !important;
            }

            .preview-shell {
                display: flex;
                justify-content: center;
                margin: 0.15rem 0 0.55rem 0;
            }

            .preview-image {
                width: 160px;
                max-width: 100%;
                border-radius: 16px;
                border: 1px solid rgba(141, 113, 189, 0.16);
                box-shadow: 0 10px 26px rgba(93, 63, 140, 0.10);
            }

            .meta-note {
                margin: 0.3rem 0 0 0;
                color: #6e6188;
                font-size: 0.82rem;
                text-align: center;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "assistant",
                "content": (
                    f"Hello, I'm {BOT_NAME}. I'm here whenever you want to talk, "
                    "brainstorm, or ask for help."
                ),
            },
        ]
    if "model" not in st.session_state:
        st.session_state.model = DEFAULT_MODEL


def render_header():
    st.markdown(f"<h1 class='page-title'>{APP_TITLE}</h1>", unsafe_allow_html=True)


def _build_user_display_text(prompt, uploaded_image=None, image_url=None):
    cleaned_prompt = (prompt or "").strip()
    source_label = None
    if uploaded_image is not None:
        source_label = "Image uploaded"
    elif (image_url or "").strip():
        source_label = "Image URL attached"

    if cleaned_prompt and source_label:
        return f"{cleaned_prompt}\n[{source_label}]"
    if cleaned_prompt:
        return cleaned_prompt
    if source_label:
        return f"Please analyze this image.\n[{source_label}]"
    return ""


def render_chat_card():
    messages_html = []
    for message in st.session_state.messages:
        if message["role"] == "system":
            continue
        role_class = "user" if message["role"] == "user" else "bot"
        safe_content = html.escape(message["content"])
        messages_html.append(
            f'<div class="message-row {role_class}"><div class="message-bubble">{safe_content}</div></div>'
        )

    chat_html = (
        f'<div class="chat-topbar">'
        f'<div class="brand-wrap">'
        f'<div class="brand-icon">A</div>'
        f'<div class="brand-meta">'
        f'<div class="brand-name">{BOT_NAME}</div>'
        f'<div class="brand-status">{STATUS_TEXT}</div>'
        f'</div></div>'
        f'<div class="window-actions">'
        f'<span title="Refresh">&#8635;</span>'
        f'<span title="Minimize">&#215;</span>'
        f'</div></div>'
        f'<div class="divider"></div>'
        f'<div class="date-row">Conversation with {BOT_NAME}</div>'
        f'<div class="chat-history">{"".join(messages_html)}</div>'
    )
    st.markdown(chat_html, unsafe_allow_html=True)


def submit_message(prompt):
    cleaned_prompt = (prompt or "").strip()
    if not cleaned_prompt:
        return False

    return True


def render_input_area():
    st.markdown('<div class="divider"></div><div class="inner-pad">', unsafe_allow_html=True)
    st.markdown('<div class="input-label">You</div>', unsafe_allow_html=True)

    current_uploaded_image = st.session_state.get("vision_upload")
    current_image_url = st.session_state.get("image_url_input", "")

    validated_preview_url = ""
    preview_error = ""
    if current_image_url.strip():
        try:
            validated_preview_url = validate_image_url(current_image_url)
        except ValueError as error:
            preview_error = str(error)

    if current_uploaded_image is not None:
        preview_col_left, preview_col_center, preview_col_right = st.columns([1.3, 2, 1.3])
        with preview_col_center:
            st.markdown('<div class="preview-shell">', unsafe_allow_html=True)
            st.image(current_uploaded_image, width=160)
            st.markdown("</div>", unsafe_allow_html=True)
    elif validated_preview_url:
        preview_col_left, preview_col_center, preview_col_right = st.columns([1.3, 2, 1.3])
        with preview_col_center:
            st.markdown('<div class="preview-shell">', unsafe_allow_html=True)
            st.image(validated_preview_url, width=160)
            st.markdown("</div>", unsafe_allow_html=True)
    elif preview_error:
        st.warning(preview_error)

    with st.form("chat_input_form", clear_on_submit=True):
        st.markdown('<div class="input-bar-shell">', unsafe_allow_html=True)
        st.markdown('<div class="composer-row">', unsafe_allow_html=True)
        upload_col, url_col, input_col, send_col = st.columns(
            [0.8, 0.8, 4.5, 1.0],
            gap="small",
            vertical_alignment="center",
        )

        with upload_col:
            with st.popover("", help="Upload image", use_container_width=True):
                uploaded_image = st.file_uploader(
                    "Upload image",
                    type=["png", "jpg", "jpeg", "webp"],
                    accept_multiple_files=False,
                    key="vision_upload",
                    label_visibility="collapsed",
                )

        with url_col:
            with st.popover("🔗", help="Add image URL", use_container_width=True):
                image_url_value = st.text_input(
                    "Image URL",
                    key="image_url_input",
                    placeholder="Paste image URL...",
                    label_visibility="collapsed",
                )

        with input_col:
            st.markdown('<div class="composer-input">', unsafe_allow_html=True)
            prompt = st.text_input(
                "You",
                key="prompt_input",
                placeholder="Type your message...",
                label_visibility="collapsed",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with send_col:
            submitted = st.form_submit_button(
                "➤",
                use_container_width=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    uploaded_image = st.session_state.get("vision_upload")
    image_url_value = st.session_state.get("image_url_input", "")

    if submitted:
        prompt_for_routing = (prompt or "").strip()
        has_image = uploaded_image is not None or bool(image_url_value.strip())
        if not prompt_for_routing and not has_image:
            st.markdown(
                "<div class='preview-note'>Type a message or add an image before sending.</div>",
                unsafe_allow_html=True,
            )
        else:
            display_user_text = _build_user_display_text(
                prompt_for_routing,
                uploaded_image=uploaded_image,
                image_url=image_url_value,
            )
            result = route_chat_request(
                prompt_for_routing,
                uploaded_image=uploaded_image,
                image_url=image_url_value,
                messages=st.session_state.messages,
                model=st.session_state.model,
            )

            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": display_user_text,
                    "meta": {
                        "mode": result.get("mode"),
                        "source_type": result.get("meta", {}).get("source_type"),
                    },
                }
            )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result["reply"],
                    "meta": result.get("meta", {}),
                }
            )
        st.rerun()

    st.markdown(
        f"<div class='meta-note'>Current model: {st.session_state.model}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def main():
    inject_styles()
    initialize_state()
    render_header()
    outer_left, outer_center, outer_right = st.columns([1.2, 2.2, 1.2])
    with outer_center:
        with st.container(key="chat_box"):
            render_chat_card()
            render_input_area()


if __name__ == "__main__":
    main()
