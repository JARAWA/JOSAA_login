from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from datetime import timedelta
from sqlalchemy.orm import Session
from . import crud, models, schemas, security
from .database import engine, get_db
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

# Health check endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Service is running"}

@app.get("/health/data")
async def check_data():
    try:
        df = load_data()
        if df is not None:
            return {
                "status": "healthy",
                "rows": len(df),
                "columns": list(df.columns),
                "sample_data": df.head(1).to_dict('records')
            }
        return {
            "status": "error",
            "message": "Failed to load data"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

# Prediction function
def predict_preferences(jee_rank, category, college_type, preferred_branch, round_no, min_prob):
    try:
        df = load_data()
        if df is None:
            return pd.DataFrame({"Error": ["Failed to load data"]}), None, None

        # Preprocess data
        df["Category"] = df["Category"].str.lower()
        df["Academic Program Name"] = df["Academic Program Name"].str.lower()
        df["College Type"] = df["College Type"].str.upper()
        
        category = category.lower()
        preferred_branch = preferred_branch.lower()
        college_type = college_type.upper()

        # Apply filters
        if category != "all":
            df = df[df["Category"] == category]
        if college_type != "ALL":
            df = df[df["College Type"] == college_type]
        if preferred_branch != "all":
            df = df[df["Academic Program Name"] == preferred_branch]
        df = df[df["Round"] == str(round_no)]

        if df.empty:
            return pd.DataFrame({"Message": ["No colleges found matching your criteria"]}), None, None

        # Generate college lists
        top_10 = df[
            (df["Opening Rank"] >= jee_rank - 200) &
            (df["Opening Rank"] <= jee_rank)
        ].head(10)

        next_20 = df[
            (df["Opening Rank"] <= jee_rank) &
            (df["Closing Rank"] >= jee_rank)
        ].head(20)

        last_20 = df[
            (df["Closing Rank"] >= jee_rank) &
            (df["Closing Rank"] <= jee_rank + 200)
        ].head(20)

        # Combine results
        final_list = pd.concat([top_10, next_20, last_20]).drop_duplicates()
        
        # Calculate probabilities
        final_list['Admission Probability (%)'] = final_list.apply(
            lambda x: hybrid_probability_calculation(jee_rank, x['Opening Rank'], x['Closing Rank']),
            axis=1
        )

        final_list['Admission Chances'] = final_list['Admission Probability (%)'].apply(get_probability_interpretation)
        
        # Filter and sort
        final_list = final_list[final_list['Admission Probability (%)'] >= min_prob]
        final_list = final_list.sort_values('Admission Probability (%)', ascending=False)
        final_list['Preference_Order'] = range(1, len(final_list) + 1)

        # Prepare final result
        result = final_list[[
            'Preference_Order',
            'Institute',
            'College Type',
            'Location',
            'Academic Program Name',
            'Opening Rank',
            'Closing Rank',
            'Admission Probability (%)',
            'Admission Chances'
        ]].rename(columns={
            'Preference_Order': 'Preference',
            'Academic Program Name': 'Branch'
        })

        # Create visualization
        fig = px.histogram(
            result,
            x='Admission Probability (%)',
            title='Distribution of Admission Probabilities',
            nbins=20,
            color_discrete_sequence=['#3366cc']
        )
        fig.update_layout(
            xaxis_title="Admission Probability (%)",
            yaxis_title="Number of Colleges",
            showlegend=False,
            title_x=0.5
        )

        return result, None, fig

    except Exception as e:
        print(f"Error in predict_preferences: {e}")
        return pd.DataFrame({"Error": [str(e)]}), None, None

# Create Gradio interface
def create_gradio_interface():
    with gr.Blocks() as iface:
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

        return iface

# Mount Gradio app
app = gr.mount_gradio_app(app, create_gradio_interface(), path="/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
