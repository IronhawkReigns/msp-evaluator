import pandas as pd
from fastapi import UploadFile
from evaluator import evaluate_answer
from utils import fix_korean_encoding
import io

EXPECTED_HEADERS = ["Domain", "설명", "Key Questions", "Present Lv.", "Interview Result"]


def parse_excel_category_sheets(excel_bytes: bytes):
    excel_data = pd.ExcelFile(io.BytesIO(excel_bytes))
    results = {}

    print(f"[DEBUG] Found sheets: {excel_data.sheet_names}")

    for sheet_name in excel_data.sheet_names:
        if "역량" not in sheet_name:
            print(f"[DEBUG] Skipping sheet '{sheet_name}' — name does not contain '역량'")
            continue

        print(f"[DEBUG] Processing sheet: {sheet_name}")
        
        try:
            # Read with explicit encoding handling
            df = pd.read_excel(excel_data, sheet_name=sheet_name, header=None)
            
            # Ensure all text data is properly encoded
            for col in df.columns:
                if df[col].dtype == 'object':  # String columns
                    df[col] = df[col].astype(str).apply(lambda x: fix_korean_encoding(x) if pd.notna(x) else "")
            
        except Exception as e:
            print(f"[ERROR] Failed to read sheet '{sheet_name}': {e}")
            continue

        if df.shape[0] < 2 or df.shape[1] < 5:
            print(f"[DEBUG] Skipping sheet '{sheet_name}' — too small: {df.shape}")
            continue

        try:
            parsed = parse_excel_category_sheet_fixed(df, sheet_name)
            print(f"[DEBUG] Sheet '{sheet_name}' parsed {len(parsed)} items")
            
            if not parsed:
                print(f"[WARNING] No items parsed from sheet '{sheet_name}'")
                continue
                
        except Exception as e:
            print(f"[ERROR] Error parsing sheet '{sheet_name}': {e}")
            continue

        # Evaluate each parsed item
        sheet_results = []
        for item in parsed:
            question = item.get("question", "")
            answer = item.get("answer", "")
            group = item.get("group", "")
            
            if not question or not answer or not question.strip() or not answer.strip():
                continue
                
            try:
                score = evaluate_answer(question, answer)
                print(f"[DEBUG] Evaluated '{question[:30]}...' -> Score: {score}")
            except Exception as e:
                print(f"[ERROR] Failed to evaluate question '{question[:30]}...': {e}")
                score = 3  # Default middle score instead of error

            sheet_results.append({
                "question": question,
                "answer": answer,
                "score": score,
                "group": group or sheet_name  # Use sheet name as fallback group
            })

        if sheet_results:
            results[sheet_name] = sheet_results
            print(f"[SUCCESS] Sheet '{sheet_name}' added with {len(sheet_results)} evaluated items")

    print(f"[DEBUG] Final results keys: {list(results.keys())}")
    
    if not results:
        print("[WARNING] No results generated from any sheet!")
        return {
            "evaluated": {},
            "summary": []
        }

    try:
        summary_df = compute_category_scores_from_excel_data(results)
        return {
            "evaluated": results,
            "summary": summary_df.to_dict(orient="records")
        }
    except Exception as e:
        print(f"[ERROR] Failed to compute summary: {e}")
        return {
            "evaluated": results,
            "summary": []
        }

def generate_summary_for_evaluation(results_by_category: dict) -> dict:
    return summarize_answers_for_subcategories(results_by_category)


def evaluate_uploaded_excel(uploaded_file: UploadFile):
    excel_bytes = uploaded_file.file.read()
    result = parse_excel_category_sheets(excel_bytes)
    return {
        **result["evaluated"],
        "summary": result["summary"],
        # Removed answer_summaries from return
        # "answer_summaries": result["answer_summaries"]
    }


def parse_excel_category_sheet(df: pd.DataFrame):
    parsed = []
    last_valid_group = None
    
    print(f"[DEBUG] Processing sheet with {df.shape[0]} rows and {df.shape[1]} columns")
    
    for idx, row in df.iterrows():
        try:
            # Debug: print first few rows to understand structure
            if idx < 5:
                print(f"[DEBUG] Row {idx}: {row.tolist()}")
            
            # Extract data from expected columns
            question = str(row.iloc[2]).strip() if len(row) > 2 else ""  # Column C (index 2)
            answer = str(row.iloc[4]).strip() if len(row) > 4 else ""    # Column E (index 4)
            raw_group = str(row.iloc[1]).strip() if len(row) > 1 else "" # Column B (index 1)

            # Skip header rows
            if question.lower() in ["key questions", "질문", "문항"] or "key question" in question.lower():
                print(f"[DEBUG] Skipping header row {idx}: {question}")
                continue
                
            # Skip empty or invalid questions/answers
            if not question or not answer or question.lower() == "nan" or answer.lower() == "nan":
                if idx < 10:  # Only log first 10 for debugging
                    print(f"[DEBUG] Skipping empty row {idx}: question='{question}', answer='{answer}'")
                continue

            # Group handling with better logic
            if raw_group and raw_group.lower() not in ["", "nan", "none"]:
                # This is a new group
                group = raw_group
                last_valid_group = group
                print(f"[DEBUG] Found new group at row {idx}: '{group}'")
            else:
                # Use the last valid group
                group = last_valid_group
                if idx < 10:  # Only log first 10 for debugging
                    print(f"[DEBUG] Using last valid group at row {idx}: '{group}'")

            # Only add if we have valid data
            if question and answer and question != "nan" and answer != "nan":
                parsed_item = {
                    "question": question,
                    "answer": answer,
                    "group": group if group else "미분류"  # Use "미분류" instead of None
                }
                parsed.append(parsed_item)
                
                if len(parsed) <= 10:  # Log first 10 parsed items
                    print(f"[DEBUG] Parsed item {len(parsed)}: {parsed_item}")
                    
        except Exception as e:
            print(f"[ERROR] Error processing row {idx}: {e}")
            continue
    
    print(f"[DEBUG] Total parsed items: {len(parsed)}")
    
    # Group summary for debugging
    groups_found = {}
    for item in parsed:
        group = item.get("group", "None")
        groups_found[group] = groups_found.get(group, 0) + 1
    
    print(f"[DEBUG] Groups found: {groups_found}")
    
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


# New helper function for summarizing answers per group
def summarize_answers_for_subcategories(results_by_category: dict) -> dict:
    from openai import OpenAI
    import os

    CLOVA_API_KEY = os.getenv("CLOVA_API_KEY_OPENAI")
    API_URL = "https://clovastudio.stream.ntruss.com/v1/openai"
    client = OpenAI(api_key=CLOVA_API_KEY, base_url=API_URL)
    model = "HCX-005"

    summaries = {}

    for category, items in results_by_category.items():
        if not isinstance(items, list):
            continue
        # Group answers by 'group', reusing last_valid_group logic as in parse_excel_category_sheet
        group_to_answers = {}
        last_valid_group = None
        for item in items:
            raw_group = item.get("group")
            if isinstance(raw_group, str) and raw_group.strip().lower() not in ["", "nan"]:
                group = raw_group.strip()
                last_valid_group = group
            else:
                group = last_valid_group if 'last_valid_group' in locals() and last_valid_group else None

            if not group:
                continue  # skip if still no valid group

            answer = item.get("answer", "").strip()
            if not answer:
                continue
            group_to_answers.setdefault(group, []).append(answer)

        summaries[category] = {}
        for group, answers in group_to_answers.items():
            if not answers:
                continue  # skip empty answer groups
            combined_text = "\n".join(answers[:5])  # limit to first 5 answers
            print(f"[DEBUG] Category: {category}, Group: {group}")
            print(f"[DEBUG] Answer count: {len(answers)}")
            print(f"[DEBUG] Combined Text:\n{combined_text}")
            prompt = (
                f"다음은 '{category}'의 하위 그룹 '{group}'에 대한 인터뷰 요약 답변들임.\n"
                f"이 답변들을 바탕으로, 핵심 내용을 정확하고 명확하게 한 문장으로 요약하시오.\n\n"
                f"반드시 아래 조건을 따르시오:\n"
                f"1. 요약은 하나의 문장으로만 작성할 것 (문장 두 개 이상 금지). 다만 문장은 반드시 끝낼 것.\n"
                f"2. '~함'으로 끝나는 서술형 종결어미를 사용할 것 (예: ~중임, ~함, ~추진 중임 등).\n"
                f"3. 군더더기 없이 핵심 내용만 요약할 것. 수식어나 배경 설명은 배제할 것.\n"
                f"4. 각 답변의 공통된 핵심을 뽑고, 유사 내용은 중복하지 말 것.\n\n"
                f"예시:\n"
                f"답변들: ['LLM을 기반으로 다양한 서비스를 개발함', 'STT와 OCR 기술을 이용한 솔루션이 있음']\n"
                f"요약: 다양한 생성형 AI 기술을 이용한 서비스 개발 경험을 보유함.\n\n"
                f"답변들:\n{combined_text}\n"
                f"요약:"
            )
            try:
                print(f"[DEBUG] Prompt for category '{category}', group '{group}':\n{prompt}")
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "답변을 명확하고 간결하게 한 문장으로 요약해 주세요."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=60,
                )
                summary = response.choices[0].message.content.strip()
                print(f"[DEBUG] Summary for category '{category}', group '{group}': {summary}")
            except Exception as e:
                error_message = str(e)
                if "429" in error_message or "rate limit" in error_message.lower():
                    summary = "요약 실패: API 요청 제한 초과 또는 기타 오류 발생"
                else:
                    summary = f"요약 실패: {error_message}"
                print(f"[ERROR] Summarization failed for category '{category}', group '{group}': {error_message}")

            summaries[category][group] = summary

    return summaries

def parse_excel_category_sheet_fixed(df: pd.DataFrame, sheet_name: str):
    """Enhanced parser with better group extraction and encoding handling"""
    parsed = []
    current_group = sheet_name  # Use sheet name as default group
    
    print(f"[DEBUG] Processing sheet '{sheet_name}' with {df.shape[0]} rows")
    
    for idx, row in df.iterrows():
        try:
            # Get values safely
            question = str(row.iloc[2]).strip() if len(row) > 2 else ""
            answer = str(row.iloc[4]).strip() if len(row) > 4 else ""
            group_cell = str(row.iloc[1]).strip() if len(row) > 1 else ""
            
            # Fix encoding for all text
            question = fix_korean_encoding(question)
            answer = fix_korean_encoding(answer)
            group_cell = fix_korean_encoding(group_cell)
            
            # Debug first few rows
            if idx < 5:
                print(f"[DEBUG] Row {idx}: question='{question[:30]}...', answer='{answer[:30]}...', group='{group_cell}'")
            
            # Skip header rows
            if any(header in question.lower() for header in ["key questions", "질문", "문항", "항목"]):
                print(f"[DEBUG] Skipping header row {idx}: {question}")
                continue
                
            # Skip empty or invalid rows
            if not question or not answer or question.lower() in ["nan", ""] or answer.lower() in ["nan", ""]:
                continue
            
            # Determine group
            if group_cell and group_cell.lower() not in ["nan", "", "none"]:
                # Found a new group
                current_group = group_cell
                print(f"[DEBUG] New group found at row {idx}: '{current_group}'")
            
            # Use current group (either from cell or carried forward)
            group = current_group
            
            parsed_item = {
                "question": question,
                "answer": answer,
                "group": group
            }
            parsed.append(parsed_item)
            
            if len(parsed) <= 10:  # Log first 10
                print(f"[DEBUG] Parsed item {len(parsed)}: group='{group}', question='{question[:30]}...'")
                    
        except Exception as e:
            print(f"[ERROR] Error processing row {idx}: {e}")
            continue
    
    print(f"[DEBUG] Total parsed items from '{sheet_name}': {len(parsed)}")
    
    # Summary of groups found
    groups_found = {}
    for item in parsed:
        group = item.get("group", "None")
        groups_found[group] = groups_found.get(group, 0) + 1
    
    print(f"[DEBUG] Groups found in '{sheet_name}': {groups_found}")
    
    return parsed
