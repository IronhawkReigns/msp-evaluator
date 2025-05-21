import os
import json
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Load configs
GOOGLE_SHEET_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEET_CREDENTIALS_JSON")
INTERVIEW_SHEET_DOC_NAME = os.getenv("INTERVIEW_SHEET_DOC_NAME")
INTERVIEW_SHEET = os.getenv("INTERVIEW_SHEET_NAME")

# Authenticate and connect to Google Sheets
def connect_to_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    return client

# Read the interview sheet
def load_evaluation_data():
    client = connect_to_sheets()
    interview_sheet = client.open(INTERVIEW_SHEET_DOC_NAME)

    fixed_tabs = ["인적역량", "AI기술역량", "솔루션 역량"]
    combined_df = pd.DataFrame()

    for tab in fixed_tabs:
        worksheet = interview_sheet.worksheet(tab)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        df["Key Questions"] = df["Key Questions"].str.strip()
        combined_df = pd.concat([combined_df, df], ignore_index=True)

    return combined_df, None

# Write back the score column
def update_scores_to_sheet(df, sheet):
    data_to_update = df.fillna("").values.tolist()
    header = df.columns.tolist()
    sheet.update([header] + data_to_update)


# Function to extract company data from a sheet by MSP name
def get_company_data_from_sheet(msp_name: str):
    df, _ = load_evaluation_data()
    data = {}

    for _, row in df.iterrows():
        question = row.get("Key Questions")
        answer = row.get("Interview Result")
        score = row.get("Present Lv.")

        if pd.isna(question) or pd.isna(answer):
            continue

        data[question.strip()] = {
            "answer": str(answer).strip(),
            "score": int(score) if not pd.isna(score) else None
        }

    return data

def get_summary_scores(msp_name: str):
    client = connect_to_sheets()
    sheet = client.open(INTERVIEW_SHEET_DOC_NAME).worksheet("데이터 요약")
    records = sheet.get_all_records()

    summary = {
        "total_score": None,
        "human_score": None,
        "ai_score": None,
        "solution_score": None
    }

    for row in records:
        label = row.get("Key Questions") or row.get("항목")
        score = row.get("Score (%)") or row.get("Present Lv.") or row.get("점수")
        if label == "총점":
            summary["total_score"] = score
        elif label == "인적역량 총점":
            summary["human_score"] = score
        elif label == "AI기술역량 총점":
            summary["ai_score"] = score
        elif label == "솔루션 역량 총점":
            summary["solution_score"] = score

    return summary
