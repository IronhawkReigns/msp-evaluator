import pandas as pd
from fastapi import UploadFile
from evaluator import evaluate_answer

EXPECTED_HEADERS = ["Domain", "설명", "Key Questions", "Present Lv.", "Interview Result"]


def evaluate_uploaded_excel(uploaded_file: UploadFile):
    results = {}
    excel_bytes = uploaded_file.file.read()
    excel_data = pd.ExcelFile(excel_bytes)

    for sheet_name in excel_data.sheet_names:
        df = pd.read_excel(excel_data, sheet_name=sheet_name, header=None)

        if df.shape[0] < 2 or df.shape[1] < 5:
            print(f"[DEBUG] Skipping sheet '{sheet_name}' — too small or malformed")
            continue

        # Check header row
        header = df.iloc[0].tolist()
        if header[:5] != EXPECTED_HEADERS:
            print(f"[DEBUG] Skipping sheet '{sheet_name}' — headers do not match")
            continue

        try:
            parsed = parse_excel_category_sheet(df)
            print(f"[DEBUG] Sheet: {sheet_name}")
            print(f"[DEBUG] Parsed: {parsed}")
        except Exception as e:
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
