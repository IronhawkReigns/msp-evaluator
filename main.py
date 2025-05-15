from sheets_reader import load_evaluation_data, update_scores_to_sheet
from evaluator import evaluate_answer
import time

if __name__ == "__main__":
    df, sheet = load_evaluation_data()
    scores = []
    for idx, row in df.iterrows():
        question = row["Key Questions"]
        answer = row["설명"]
        score = evaluate_answer(question, answer)
        print(f"{idx+1}. {question} → Score: {score}")
        scores.append(score)
        time.sleep(2.5)

    df["Score"] = scores
    update_scores_to_sheet(df, sheet)