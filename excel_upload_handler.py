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
            if answer.lower() == "nan" or not answer.strip():
                continue
            try:
                score = evaluate_answer(question, answer)
            except Exception as e:
                print(f"[ERROR] Failed to evaluate: {question[:20]} — {e}")
                score = f"Error: {str(e)}"

            sheet_results.append({
                "question": question,
                "answer": answer,
                "score": score,
                "group": item.get("group")
            })

        if sheet_results:
            results[sheet_name] = sheet_results

    summary_df = compute_category_scores_from_excel_data(results)
    return {
        "evaluated": results,
        "summary": summary_df.to_dict(orient="records")
    }


def evaluate_uploaded_excel(uploaded_file: UploadFile):
    excel_bytes = uploaded_file.file.read()
    result = parse_excel_category_sheets(excel_bytes)
    return {
        **result["evaluated"],
        "summary": result["summary"]
    }


def parse_excel_category_sheet(df: pd.DataFrame):
    parsed = []
    for _, row in df.iterrows():
        try:
            question = str(row[2]).strip()
            answer = str(row[4]).strip()
            group = str(row[1]).strip()
            if question.lower() == "key questions":
                continue  # Skip header
            if not question or not answer or question == "nan":
                continue
            parsed.append({
                "question": question,
                "answer": answer,
                "group": group
            })
        except Exception:
            continue
    return parsed

def compute_category_scores_from_excel_data(results_by_category):
    """Takes dict from upload-based evaluation and computes average score per category, group, and overall."""
    category_scores = {}
    group_scores = {}
    total_score = 0
    total_questions = 0

    for category, items in results_by_category.items():
        if category == "summary":
            continue
        if not isinstance(items, list):
            print(f"[WARNING] Skipping category '{category}' — expected list but got {type(items)}")
            continue

        filtered_items = [item for item in items if isinstance(item, dict) and "score" in item and isinstance(item["score"], int)]
        if not filtered_items:
            continue
        question_count = len(filtered_items)
        score_sum = sum(item["score"] for item in filtered_items)
        percentage = round(score_sum / (question_count * 5), 4)
        category_scores[category] = {
            "average": percentage,
            "count": question_count,
            "total": score_sum
        }
        total_score += score_sum
        total_questions += question_count

        # Track group scores within this category
        for item in filtered_items:
            group = item.get("group", "")
            if not group:
                continue
            key = (category, group)
            if key not in group_scores:
                group_scores[key] = {"score_sum": 0, "count": 0}
            group_scores[key]["score_sum"] += item["score"]
            group_scores[key]["count"] += 1

    total_max = total_questions * 5
    overall = round((total_score / total_max) * 100, 2) if total_max > 0 else 0.0

    summary = [{"Category": "총점", "Score": round(overall, 2), "Questions": total_questions}]
    for category, data in category_scores.items():
        summary.append({
            "Category": category,
            "Score": round(data['average'] * 100, 2),
            "Questions": data['count']
        })
    # Append group scores under each category
    for (category, group_name), data in group_scores.items():
        if not group_name or group_name.lower() == "nan":
            continue
        group_avg = data["score_sum"] / (data["count"] * 5)
        summary.append({
            "Category": group_name,
            "Score": round(group_avg * 100, 2),
            "Questions": data["count"]
        })

    return pd.DataFrame(summary)
