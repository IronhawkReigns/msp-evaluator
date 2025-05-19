import os
import signal
import time
from sheets_reader import load_evaluation_data, update_scores_to_sheet, create_and_write_summary_sheet
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
