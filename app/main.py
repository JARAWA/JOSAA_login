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

            with gr.Row():
                with gr.Column(scale=1, min_width=300):
                    college_type = gr.Dropdown(
                        choices=["ALL", "IIT", "NIT", "IIIT", "GFTI"],
                        label="Select College Type",
                        value="ALL"
                    )
                    
                    jee_rank = gr.Number(
                        label="Enter your JEE Main Rank (OPEN-CRL, Others-Category Rank)",
                        minimum=1
                    )
                    
                    category = gr.Dropdown(
                        choices=["All", "OPEN", "OBC-NCL", "OBC-NCL (PwD)", "EWS", "EWS (PwD)",
                                "SC", "SC (PwD)", "ST", "ST (PwD)"],
                        label="Select Category"
                    )

                with gr.Column(scale=1, min_width=300):
                    preferred_branch = gr.Dropdown(
                        choices=get_unique_branches(),
                        label="Select Preferred Branch"
                    )
                    round_no = gr.Dropdown(
                        choices=["1", "2", "3", "4", "5", "6"],
                        label="Select Round"
                    )
                    min_prob = gr.Slider(
                        minimum=0,
                        maximum=100,
                        value=30,
                        step=5,
                        label="Minimum Admission Probability (%)"
                    )

            def update_rank_label(college_type_value):
                if college_type_value == "IIT":
                    return gr.update(label="Enter your JEE Advanced Rank (OPEN-CRL, Others-Category Rank)")
                return gr.update(label="Enter your JEE Main Rank (OPEN-CRL, Others-Category Rank)")

            college_type.change(
                fn=update_rank_label,
                inputs=college_type,
                outputs=jee_rank
            )

            with gr.Row():
                submit_btn = gr.Button("🔍 Generate Preferences")
                download_btn = gr.Button("📥 Download Excel")

            output_table = gr.Dataframe(
                headers=[
                    "Preference",
                    "Institute",
                    "College Type",
                    "Location",
                    "Branch",
                    "Opening Rank",
                    "Closing Rank",
                    "Admission Probability (%)",
                    "Admission Chances"
                ],
                label="College Preferences"
            )

            prob_plot = gr.Plot(label="Probability Distribution")
            excel_output = gr.File(label="Download Excel File")

            submit_btn.click(
                fn=predict_preferences,
                inputs=[jee_rank, category, college_type, preferred_branch, round_no, min_prob],
                outputs=[output_table, excel_output, prob_plot]
            )

            download_btn.click(
                fn=lambda x: x,
                inputs=[excel_output],
                outputs=[excel_output]
            )

            # Logout button
            logout_btn = gr.Button("Logout")

            def logout():
                return {
                    auth_block: gr.update(visible=True),
                    main_block: gr.update(visible=False),
                    current_user: None
                }

            logout_btn.click(
                fn=logout,
                inputs=[],
                outputs=[auth_block, main_block, current_user]
            )

            gr.Markdown("""
            ### 📚 How to use this tool:
            1. First, select the type of college (IIT/NIT/IIIT/GFTI)
            2. Enter your rank:
               - For IITs: Enter your JEE Advanced rank
               - For NITs/IIITs/GFTIs: Enter your JEE Main rank
               - For OPEN category: Enter CRL (Common Rank List) rank
               - For other categories: Enter your category rank
            3. Select your category (OPEN/OBC-NCL/SC/ST/EWS)
            4. Select your preferred branch (optional)
            5. Choose the counselling round
            6. Set minimum admission probability threshold
            7. Click on "Generate Preferences"
            8. Use the Download Excel button to save the results
            """)

            gr.Markdown("""
            ### ⚠️ Disclaimer:
            - This tool provides suggestions based on previous year's cutoff data
            - The admission probabilities are estimates based on historical data
            - The actual cutoffs and admission chances may vary in the current year
            - This is not an official JOSAA tool and should be used only for reference
            - Please verify all information from the official JOSAA website
            - The developers are not responsible for any decisions made based on this tool
            """)

        # Connect login/register/reset functions
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

# Mount Gradio app
app = gr.mount_gradio_app(app, create_gradio_interface(), path="/")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
