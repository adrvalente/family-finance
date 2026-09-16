
import bcrypt
import streamlit as st
from db import get_user_by_username, log_action, update_last_login, update_password

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False

def init_session():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None

def login(username, password):
    user = get_user_by_username(username.strip())

    if not user or not verify_password(password, user["password_hash"]):
        return False, "Utilizador ou palavra-passe inválidos."

    if not user["is_active"]:
        return False, "Esta conta encontra-se desativada."

    st.session_state.authenticated = True
    st.session_state.user = {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "email": user["email"],
        "role": user["role"],
        "must_change_password": bool(user["must_change_password"]),
        "household_id": user["household_id"],
        "household_name": user["household_name"],
    }

    update_last_login(user["id"])
    log_action(user["id"], "login", "user", user["id"], "Login efetuado")
    return True, None

def logout():
    user = st.session_state.get("user")
    if user:
        try:
            log_action(user["id"], "logout", "user", user["id"], "Logout efetuado")
        except Exception:
            pass
    st.session_state.authenticated = False
    st.session_state.user = None

def require_login():
    if not st.session_state.get("authenticated"):
        st.warning("É necessário iniciar sessão.")
        st.stop()

def is_admin():
    u = st.session_state.get("user")
    return bool(u and u.get("role")=="admin")

def require_admin():
    require_login()
    if not is_admin():
        st.error("Esta área está reservada ao administrador.")
        st.stop()

def change_password(user_id, current_password, new_password):
    user = get_user_by_username(st.session_state.user["username"])

    if not user or not verify_password(current_password,user["password_hash"]):
        return False, "A palavra-passe atual está incorreta."

    if len(new_password) < 8:
        return False, "A nova palavra-passe deve ter pelo menos 8 caracteres."

    update_password(user_id, hash_password(new_password))
    st.session_state.user["must_change_password"] = False
    log_action(user_id,"password_change","user",user_id,"Palavra-passe alterada")
    return True, "Palavra-passe alterada com sucesso."
