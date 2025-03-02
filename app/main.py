from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from . import crud, models, schemas, security
from .database import (
    engine, get_db, store_reset_token, 
    verify_reset_token, clear_reset_token
)
from jose import JWTError, jwt
import gradio as gr
import pandas as pd
import plotly.express as px
from .utils import (
    load_data,
    get_unique_branches,
    hybrid_probability_calculation,
    get_probability_interpretation
)
import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="JOSAA Predictor")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Email configuration
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")

def send_reset_email(email: str, reset_token: str):
    """Send password reset email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = email
        msg['Subject'] = "Password Reset Request"

        body = f"""
        You have requested to reset your password.
        Please use the following token to reset your password: {reset_token}
        
        This token will expire in 1 hour.
        
        If you did not request this reset, please ignore this email.
        """
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def create_gradio_interface():
    with gr.Blocks() as iface:
        # State variables
        is_logged_in = gr.State(False)
        current_user = gr.State(None)
        
        # Custom CSS
        custom_css = """
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        .error-message { color: red; margin-top: 10px; }
        .success-message { color: green; margin-top: 10px; }
        """
        gr.HTML(f"<style>{custom_css}</style>")

        # Login/Register/Reset Tabs
        with gr.Box(visible=True) as auth_block:
            with gr.Tabs() as tabs:
                # Login Tab
                with gr.TabItem("Login"):
                    login_username = gr.Textbox(label="Username")
                    login_password = gr.Textbox(label="Password", type="password")
                    login_button = gr.Button("Login")
                    login_message = gr.Markdown("")

                # Register Tab
                with gr.TabItem("Register"):
                    reg_email = gr.Textbox(label="Email")
                    reg_username = gr.Textbox(label="Username")
                    reg_password = gr.Textbox(label="Password", type="password")
                    reg_confirm_password = gr.Textbox(label="Confirm Password", type="password")
                    register_button = gr.Button("Register")
                    register_message = gr.Markdown("")

                # Password Reset Tab
                with gr.TabItem("Reset Password"):
                    # Request Reset
                    reset_email = gr.Textbox(label="Email")
                    request_reset_button = gr.Button("Request Reset")
                    reset_request_message = gr.Markdown("")

                    # Reset Password
                    with gr.Box(visible=False) as reset_box:
                        reset_token = gr.Textbox(label="Reset Token")
                        new_password = gr.Textbox(label="New Password", type="password")
                        confirm_new_password = gr.Textbox(label="Confirm New Password", type="password")
                        reset_password_button = gr.Button("Reset Password")
                        reset_message = gr.Markdown("")

        # Main interface (initially hidden)
        with gr.Box(visible=False) as main_block:
            gr.Markdown("""
            # 🎓 JOSAA College Preference List Generator
            ### Get personalized college recommendations with admission probability predictions
            """)

            # Your existing interface components...
            [Rest of your main interface code...]

        # Login function
        def login(username, password):
            try:
                db = next(get_db())
                user = crud.get_user(db, username=username)
                if user and security.verify_password(password, user.hashed_password):
                    crud.update_last_login(db, user)
                    return {
                        login_message: gr.update(value="Login successful!"),
                        auth_block: gr.update(visible=False),
                        main_block: gr.update(visible=True),
                        current_user: user.username
                    }
                return {
                    login_message: gr.update(value="Invalid username or password"),
                    auth_block: gr.update(visible=True),
                    main_block: gr.update(visible=False),
                    current_user: None
                }
            except Exception as e:
                return {
                    login_message: gr.update(value=f"Login error: {str(e)}"),
                    auth_block: gr.update(visible=True),
                    main_block: gr.update(visible=False),
                    current_user: None
                }

        # Register function
        def register(email, username, password, confirm_password):
            if password != confirm_password:
                return gr.update(value="Passwords do not match")
            try:
                db = next(get_db())
                if crud.get_user(db, username=username):
                    return gr.update(value="Username already exists")
                if crud.get_user_by_email(db, email=email):
                    return gr.update(value="Email already registered")
                
                user = schemas.UserCreate(
                    email=email,
                    username=username,
                    password=password
                )
                crud.create_user(db=db, user=user)
                return gr.update(value="Registration successful! Please login.")
            except Exception as e:
                return gr.update(value=f"Registration error: {str(e)}")

        # Request password reset function
        def request_reset(email):
            try:
                db = next(get_db())
                user = crud.get_user_by_email(db, email=email)
                if not user:
                    return gr.update(value="Email not found")
                
                reset_token = secrets.token_hex(16)
                store_reset_token(email, reset_token)
                
                if send_reset_email(email, reset_token):
                    return {
                        reset_request_message: gr.update(value="Reset instructions sent to your email"),
                        reset_box: gr.update(visible=True)
                    }
                return {
                    reset_request_message: gr.update(value="Error sending reset email"),
                    reset_box: gr.update(visible=False)
                }
            except Exception as e:
                return {
                    reset_request_message: gr.update(value=f"Reset request error: {str(e)}"),
                    reset_box: gr.update(visible=False)
                }

        # Reset password function
        def reset_password(email, token, new_password, confirm_new_password):
            if new_password != confirm_new_password:
                return gr.update(value="Passwords do not match")
            
            if not verify_reset_token(email, token):
                return gr.update(value="Invalid or expired reset token")
            
            try:
                db = next(get_db())
                user = crud.get_user_by_email(db, email=email)
                if not user:
                    return gr.update(value="User not found")
                
                crud.update_password(db, user, new_password)
                clear_reset_token(email)
                return gr.update(value="Password reset successful! Please login.")
            except Exception as e:
                return gr.update(value=f"Password reset error: {str(e)}")

        # Connect interface functions
        login_button.click(
            fn=login,
            inputs=[login_username, login_password],
            outputs=[login_message, auth_block, main_block, current_user]
        )

        register_button.click(
            fn=register,
            inputs=[reg_email, reg_username, reg_password, reg_confirm_password],
            outputs=register_message
        )

        request_reset_button.click(
            fn=request_reset,
            inputs=[reset_email],
            outputs=[reset_request_message, reset_box]
        )

        reset_password_button.click(
            fn=reset_password,
            inputs=[reset_email, reset_token, new_password, confirm_new_password],
            outputs=reset_message
        )

        return iface

# Create default admin user on startup
@app.on_event("startup")
async def startup_event():
    try:
        db = next(get_db())
        admin_user = crud.get_user(db, username="admin")
        if not admin_user:
            admin = schemas.UserCreate(
                email="admin@example.com",
                username="admin",
                password="admin123"  # Change this to a secure password
            )
            crud.create_user(db=db, user=admin)
            print("Default admin user created")
    except Exception as e:
        print(f"Error creating default admin: {e}")

# Mount Gradio app
app = gr.mount_gradio_app(app, create_gradio_interface(), path="/")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
