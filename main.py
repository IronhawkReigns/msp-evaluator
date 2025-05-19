import os
import signal
import time
from sheets_reader import load_evaluation_data, update_scores_to_sheet, create_and_write_summary_sheet, write_combined_summary, connect_to_sheets
from evaluator import evaluate_answer, append_category_scores_to_sheet

class TimeoutException(Exception):
    pass

def handler(signum, frame):
    raise TimeoutException("Timed out")

signal.signal(signal.SIGALRM, handler)

target_sheets = os.getenv("TARGET_SHEET_NAMES", "Test").split(",")

all_summaries = {}

for sheet_name in target_sheets:
    sheet_name = sheet_name.strip()
    print(f"\nProcessing sheet: {sheet_name}", flush=True)
    df, sheet = load_evaluation_data(sheet_name=sheet_name)
    scores = []

    for idx, row in df.iterrows():
        interview_result = str(row.get("Interview Result", "")).strip()
        current_level = str(row.get("Present Lv.", "")).strip()

        # Skip if there's no interview result, or already evaluated
        if interview_result == "" or current_level not in {"", "nan", "NaN"}:
            print(f"Skipping row {idx+1} (no new input or already scored)", flush=True)
            scores.append(current_level)
            continue

        question = row["Key Questions"]
        answer = interview_result
        print(f"Evaluating row {idx+1}", flush=True)
        try:
            signal.alarm(60)
            score = evaluate_answer(question, answer)
            signal.alarm(0)
            print(f"Done row {idx+1} → {score}", flush=True)
        except TimeoutException:
            print(f"Timeout for row {idx+1}", flush=True)
            score = "Timeout"
        except Exception as e:
            print(f"Exception at row {idx+1}: {e}", flush=True)
            score = "Error"
        scores.append(score)

    df["Present Lv."] = scores
    update_scores_to_sheet(df, sheet)

    # Compute and write category summary
    df_summary = append_category_scores_to_sheet(df)
    all_summaries[sheet_name] = df_summary
    print(f"[DEBUG] {sheet_name} → Summary shape: {df_summary.shape}")


# After the loop, before write_combined_summary
print("[DEBUG] Writing combined summary:")
for sheet, df in all_summaries.items():
    print(f" - {sheet}: {df.shape}")

def write_combined_summary(all_summaries):
    # Assuming this function writes combined summaries to a Google Sheet
    # Here is the updated logic for updating existing category labels in column A
    
    # This is a placeholder for sheet access, replace with actual sheet object
    client = connect_to_sheets()
    interview_sheet = client.open(INTERVIEW_SHEET_DOC_NAME)
    worksheet = interview_sheet.worksheet(sheet_name)
    
    combined_rows = []
    for sheet_name, df_summary in all_summaries.items():
        for idx, row in df_summary.iterrows():
            label = row['Category'] if 'Category' in row else None
            score = row['Score'] if 'Score' in row else None
            if label is not None and score is not None:
                combined_rows.append([label, score])
    
    # Pull all existing values from the worksheet
    existing_data = worksheet.get_all_values()

    # Create a map of row index for each category label in column A
    label_to_row = {row[0]: idx + 1 for idx, row in enumerate(existing_data) if row and row[0]}

    # Sanitize combined_rows and update column B values in place
    for row in combined_rows:
        if isinstance(row, list) and len(row) == 2:
            label, score = str(row[0]), str(row[1])
            if label in label_to_row:
                cell_address = f"B{label_to_row[label]}"
                worksheet.update(cell_address, [[score]])
            else:
                print(f"[WARNING] Label '{label}' not found in sheet. Skipping.")
        else:
            print(f"[WARNING] Malformed row skipped: {row}")

write_combined_summary(all_summaries)
