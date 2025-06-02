import pandas as pd
from fastapi import UploadFile
from evaluator import evaluate_answer
import io

EXPECTED_HEADERS = ["Domain", "설명", "Key Questions", "Present Lv.", "Interview Result"]


def parse_excel_category_sheets(excel_bytes: bytes):
    excel_data = pd.ExcelFile(io.BytesIO(excel_bytes))
    results = {}

    for sheet_name in excel_data.sheet_names:
        if "역량" not in sheet_name:
            print(f"[DEBUG] Skipping sheet '{sheet_name}' — name does not contain '역량'")
            continue

        df = pd.read_excel(excel_data, sheet_name=sheet_name, header=None)

        if df.shape[0] < 2 or df.shape[1] < 5:
            print(f"[DEBUG] Skipping sheet '{sheet_name}' — too small or malformed")
            continue

        try:
            parsed = parse_excel_category_sheet(df)
            print(f"[DEBUG] Sheet: {sheet_name}")
            print(f"[DEBUG] Parsed: {parsed}")
        except Exception as e:
            print(f"[DEBUG] Error parsing sheet '{sheet_name}': {e}")
            continue  # skip problematic sheet

        sheet_results = []
        for item in parsed:
            question = item.get("question")
            answer = item.get("answer")
            if not isinstance(question, str) or not isinstance(answer, str):
                continue
            try:
                score = evaluate_answer(question, answer)
            except Exception as e:
                score = f"Error: {str(e)}"

            sheet_results.append({
                "question": question,
                "answer": answer,
                "score": score
            })

        if sheet_results:
            results[sheet_name] = sheet_results

    return results


def evaluate_uploaded_excel(uploaded_file: UploadFile):
    excel_bytes = uploaded_file.file.read()
    return parse_excel_category_sheets(excel_bytes)


def parse_excel_category_sheet(df: pd.DataFrame):
    parsed = []
    for _, row in df.iterrows():
        try:
            question = str(row[2]).strip()
            answer = str(row[4]).strip()
            if question.lower() == "key questions":
                continue  # Skip header
            if not question or not answer or question == "nan":
                continue
            parsed.append({
                "question": question,
                "answer": answer
            })
        except Exception:
            continue
    return parsed

def compute_category_scores_from_excel_data(results_by_category):
    """Takes dict from upload-based evaluation and computes average score per category and overall."""
    category_scores = {}
    total_score = 0
    total_questions = 0

    for category, items in results_by_category.items():
        scores = [item['score'] for item in items if isinstance(item['score'], int)]
        if not scores:
            continue
        question_count = len(scores)
        score_sum = sum(scores)
        percentage = round(score_sum / (question_count * 5), 4)
        category_scores[category] = {
            "average": percentage,
            "count": question_count,
            "total": score_sum
        }
        total_score += score_sum
        total_questions += question_count

    total_max = total_questions * 5
    overall = round((total_score / total_max) * 100, 2) if total_max > 0 else 0.0

    summary = [["총점", f"{overall:.2f}", total_questions]]
    for category, data in category_scores.items():
        summary.append([category, f"{data['average'] * 100:.2f}", data['count']])

    return pd.DataFrame(summary, columns=["Category", "Score", "Questions"])
