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
def load_evaluation_data(sheet_name=None):
    client = connect_to_sheets()
    interview_sheet = client.open(INTERVIEW_SHEET_DOC_NAME)
    worksheet = interview_sheet.worksheet(sheet_name or INTERVIEW_SHEET)
    interview_records = worksheet.get_all_records()
    df_interview = pd.DataFrame(interview_records)
    df_interview["Key Questions"] = df_interview["Key Questions"].str.strip()
    return df_interview, worksheet

# Write back the score column
def update_scores_to_sheet(df, sheet):
    data_to_update = df.fillna("").values.tolist()
    header = df.columns.tolist()
    sheet.update([header] + data_to_update)


# Write only the Score (%) column to an existing "데이터 요약" sheet
def create_and_write_summary_sheet(df_summary, new_sheet_name="데이터 요약"):
    client = connect_to_sheets()
    interview_sheet = client.open(INTERVIEW_SHEET_DOC_NAME)

    try:
        worksheet = interview_sheet.worksheet(new_sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = interview_sheet.add_worksheet(title=new_sheet_name, rows="100", cols="5")

        # Clean and simplify the summary DataFrame before writing
    df_summary = df_summary.rename(columns={
        "Key Questions": "Category",
        "Present Lv.": "Score (%)"
    })[["Score (%)"]]

    # Prepare list of scores
    score_values = df_summary["Score (%)"].fillna("").tolist()

    # Compute 총점 (average of all category scores)
    numeric_scores = [
        float(str(score).replace('%', '')) for score in score_values
        if str(score).replace('%', '').replace('.', '').isdigit()
    ]
    total_score = round(sum(numeric_scores) / len(numeric_scores), 2) if numeric_scores else 0.0
    score_values.insert(0, f"{total_score:.2f}%")  # insert at top

    # Write to column B starting from B2 (row 2)
    cell_range = f"B2:B{len(score_values) + 1}"
    worksheet.update(cell_range, [[v] for v in score_values])


# Combine summaries from multiple sheets into a unified summary sheet
def write_combined_summary(summary_dict, sheet_name="데이터 요약"):
    client = connect_to_sheets()
    interview_sheet = client.open(INTERVIEW_SHEET_DOC_NAME)

    try:
        worksheet = interview_sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = interview_sheet.add_worksheet(title=sheet_name, rows="100", cols="5")

    combined_rows = [["Category", "Score (%)"]]
    total_scores = []

    for sheet_title, df_summary in summary_dict.items():
        if not df_summary.empty:
            # Add section-level summary
            section_score = df_summary.iloc[0, 0]
            combined_rows.append([f"{sheet_title} 총점", section_score])
            try:
                total_scores.append(float(str(section_score).replace('%', '')))
            except ValueError:
                pass

            # Add each category score under this section
            for idx in range(1, len(df_summary)):
                combined_rows.append(df_summary.iloc[idx].tolist())

    # Insert overall average score at the top
    if total_scores:
        avg_score = round(sum(total_scores) / len(total_scores), 2)
        combined_rows.insert(1, ["총점", f"{avg_score:.2f}%"])

    # Write to the sheet
    worksheet.update(f"A1:B{len(combined_rows)}", combined_rows)

    # Bold the headers
    try:
        from gspread_formatting import CellFormat, TextFormat, format_cell_range
        bold_format = CellFormat(textFormat=TextFormat(bold=True))
        format_cell_range(worksheet, "A1:B2", bold_format)
    except Exception as e:
        print(f"Could not apply formatting: {e}")
