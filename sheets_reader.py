import os
import json
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Load configs
INTERVIEW_SHEET_DOC_NAME = os.getenv("INTERVIEW_SHEET_DOC_NAME")
INTERVIEW_SHEET = os.getenv("INTERVIEW_SHEET_NAME")

# Authenticate and connect to Google Sheets
def connect_to_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json_str = os.getenv("GOOGLE_SHEET_CREDENTIALS_PATH")
    creds_dict = json.loads(creds_json_str)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# Read the interview sheet
def load_evaluation_data():
    client = connect_to_sheets()
    interview_sheet = client.open(INTERVIEW_SHEET_DOC_NAME)
    worksheet = interview_sheet.worksheet(INTERVIEW_SHEET)
    interview_records = worksheet.get_all_records()
    df_interview = pd.DataFrame(interview_records)
    df_interview["Key Questions"] = df_interview["Key Questions"].str.strip()
    return df_interview, worksheet

# Write back the score column
def update_scores_to_sheet(df, sheet):
    data_to_update = df.fillna("").values.tolist()
    header = df.columns.tolist()
    sheet.update([header] + data_to_update)