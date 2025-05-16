from sheets_reader import load_evaluation_data, update_scores_to_sheet
from evaluator import evaluate_answer
import time

if __name__ == "__main__":
    df, sheet = load_evaluation_data()
    scores = []

    for idx, row in df.iterrows():
        interview_result = str(row.get("Interview Result", "")).strip()
        current_level = str(row.get("Present Lv.", "")).strip()

        # Skip if there's no interview result, or already evaluated
        if interview_result == "":
            print(f"Skipping row {idx+1} due to empty 'Interview Result'")
            scores.append(current_level)
            continue

        if current_level not in {"", "nan", "NaN"}:
            print(f"Skipping row {idx+1} (already scored)")
            scores.append(current_level)
            continue

        question = row["Key Questions"]
        answer = interview_result
        score = evaluate_answer(question, answer)
        print(f"{idx+1}. {question} → Score: {score}")
        scores.append(score)

    df["Present Lv."] = scores
    update_scores_to_sheet(df, sheet)
