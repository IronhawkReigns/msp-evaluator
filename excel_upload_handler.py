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
            if answer.lower() == "nan" or not answer.strip():
                print(f"[DEBUG] Skipping empty answer for question '{question}' in group '{item.get('group')}' of sheet '{sheet_name}'")
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
    # New: generate answer summaries for subcategories
    answer_summaries = summarize_answers_for_subcategories(results)
    return {
        "evaluated": results,
        "summary": summary_df.to_dict(orient="records"),
        "answer_summaries": answer_summaries
    }


def evaluate_uploaded_excel(uploaded_file: UploadFile):
    excel_bytes = uploaded_file.file.read()
    result = parse_excel_category_sheets(excel_bytes)
    return {
        **result["evaluated"],
        "summary": result["summary"],
        "answer_summaries": result["answer_summaries"]
    }


def parse_excel_category_sheet(df: pd.DataFrame):
    parsed = []
    last_group = None
    for _, row in df.iterrows():
        try:
            question = str(row[2]).strip()
            answer = str(row[4]).strip()
            group = str(row[1]).strip()
            if group.lower() in ["", "nan"]:
                group = last_group
            else:
                last_group = group
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

        # Track group scores within this category, nested by category
        for item in filtered_items:
            group = item.get("group", "").strip()
            if not group or group.lower() == "nan":
                continue
            if category not in group_scores:
                group_scores[category] = {}
            if group not in group_scores[category]:
                group_scores[category][group] = {"score_sum": 0, "count": 0}
            group_scores[category][group]["score_sum"] += item["score"]
            group_scores[category][group]["count"] += 1

    total_max = total_questions * 5
    overall = round((total_score / total_max) * 100, 2) if total_max > 0 else 0.0

    summary = [{"Category": "총점", "Score": round(overall, 2), "Questions": total_questions}]
    for category, data in category_scores.items():
        summary.append({
            "Category": category,
            "Score": round(data['average'] * 100, 2),
            "Questions": data['count']
        })
    # Append group scores under each category (nested)
    for category, groups in group_scores.items():
        for group_name, data in groups.items():
            group_avg = data["score_sum"] / (data["count"] * 5)
            summary.append({
                "Category": group_name,
                "Score": round(group_avg * 100, 2),
                "Questions": data["count"]
            })

    return pd.DataFrame(summary)


def summarize_answers_for_subcategories(results_by_category: dict) -> dict:
    import os
    import uuid
    import json

    CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")
    CLOVA_HOST = "https://clovastudio.stream.ntruss.com"
    model_path = "/testapp/v3/chat-completions/HCX-005"

    class CompletionExecutor:
        def __init__(self, host, api_key, request_id):
            self._host = host
            self._api_key = api_key
            self._request_id = request_id

        def execute(self, completion_request):
            import requests
            headers = {
                'Authorization': self._api_key,
                'X-NCP-CLOVASTUDIO-REQUEST-ID': self._request_id,
                'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'text/event-stream'
            }
            response_text = ""
            with requests.post(self._host + model_path,
                               headers=headers, json=completion_request, stream=True) as r:
                for line in r.iter_lines():
                    if line:
                        decoded_line = line.decode("utf-8")
                        if decoded_line.startswith("data: "):
                            data_json_str = decoded_line[6:]
                            if data_json_str == "[DONE]":
                                break
                            try:
                                data_json = json.loads(data_json_str)
                                if 'choices' in data_json:
                                    content_part = data_json['choices'][0]['delta'].get('content', '')
                                    response_text += content_part
                            except Exception:
                                continue
            return response_text.strip()

    summaries = {}

    for category, items in results_by_category.items():
        if not isinstance(items, list):
            continue
        group_to_answers = {}
        for item in items:
            group = item.get("group", "기타").strip() or "기타"
            answer = item.get("answer", "").strip()
            if not answer:
                continue
            group_to_answers.setdefault(group, []).append(answer)

        summaries[category] = {}
        for group, answers in group_to_answers.items():
            if not answers:
                continue
            combined_text = "\n".join(answers[:5])
            prompt = (
                f"다음은 {category}의 하위 그룹 '{group}'에 대한 답변들임.\n"
                f"이 답변들을 요약하여 정확하고 명확한 한 문장으로 작성할 것.\n"
                f"중복된 내용 없이, 핵심만 간결하게 포함하며, 문장은 '~함' 형태로 작성할 것.\n"
                f"요약은 반드시 한 문장이어야 하며, 군더더기 없이 명확하게 표현되어야 함.\n"
                f"답변들:\n{combined_text}\n"
                f"요약:"
            )

            request_id = f"msp-evaluator-{uuid.uuid4()}"
            executor = CompletionExecutor(
                host=CLOVA_HOST,
                api_key=f"Bearer {CLOVA_API_KEY}",
                request_id=request_id
            )
            completion_request = {
                "messages": [
                    {"role": "system", "content": "답변을 명확하고 간결하게 한 문장으로 요약해 주세요."},
                    {"role": "user", "content": prompt}
                ],
                "topP": 0.8,
                "topK": 0,
                "maxTokens": 60,
                "temperature": 0.3,
                "repetitionPenalty": 1.1,
                "stop": [],
                "includeAiFilters": True,
                "seed": 0
            }

            try:
                summary = executor.execute(completion_request)
                print(f"[DEBUG] Summary for category '{category}', group '{group}': {summary}")
            except Exception as e:
                error_message = str(e)
                print(f"[ERROR] Summarization failed for category '{category}', group '{group}': {error_message}")
                summary = f"요약 실패: {error_message}"

            summaries[category][group] = summary

    return summaries
