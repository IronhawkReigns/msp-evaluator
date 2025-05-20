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

    # Compute and write category summary with weighted average
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
    interview_sheet = client.open("Test")
    worksheet = interview_sheet.worksheet("데이터 요약")
    
    combined_rows = []
    for sheet_name, df_summary in all_summaries.items():
        for idx, row in df_summary.iterrows():
            label = row['Category'] if 'Category' in row else None
            score = row['Score (%)'] if 'Score (%)' in row else None
            if label is not None and score is not None:
                combined_rows.append([label, score])
    
    # Define updated row mappings for each label (row number = 1-based index)
    row_mapping = {
        "AI 전문 인력 구성": 3,
        "프로젝트 경험 및 성공 사례": 4,
        "지속적인 교육 및 학습": 5,
        "프로젝트 관리 및 커뮤니케이션": 6,
        "AI 윤리 및 책임 의식": 7,
        "AI 기술 연구 능력": 10,
        "AI 모델 개발 능력": 11,
        "AI 플랫폼 및 인프라 구축 능력": 12,
        "데이터 처리 및 분석 능력": 13,
        "AI 기술의 융합 및 활용 능력": 14,
        "AI 기술의 특허 및 인증 보유 현황": 15,
        "다양성 및 전문성": 18,
        "안정성": 19,
        "확장성 및 유연성": 20,
        "사용자 편의성": 21,
        "보안성": 22,
        "기술 지원 및 유지보수": 23,
        "차별성 및 경쟁력": 24,
        "개발 로드맵 및 향후 계획": 25,
        "총점": 27,
        "인적역량 총점": 28,
        "AI기술역량 총점": 29,
        "솔루션 역량 총점": 30
    }

    cell_updates = []
    for row in combined_rows:
        if isinstance(row, list) and len(row) == 2:
            label, score = str(row[0]).strip(), str(row[1]).strip()
            if label in row_mapping:
                row_num = row_mapping[label]
                cell_updates.append({
                    "range": f"B{row_num}",
                    "values": [[score]]
                })

    # Section-level 평균 계산 (revised to use actual Present Lv. scores from each sheet's df)
    import pandas as pd
    section_mappings = {
        "인적역량 총점": ["AI 전문 인력 구성", "프로젝트 경험 및 성공 사례", "지속적인 교육 및 학습", "프로젝트 관리 및 커뮤니케이션", "AI 윤리 및 책임 의식"],
        "AI기술역량 총점": ["AI 기술 연구 능력", "AI 모델 개발 능력", "AI 플랫폼 및 인프라 구축 능력", "데이터 처리 및 분석 능력", "AI 기술의 융합 및 활용 능력", "AI 기술의 특허 및 인증 보유 현황"],
        "솔루션 역량 총점": ["다양성 및 전문성", "안정성", "확장성 및 유연성", "사용자 편의성", "보안성", "기술 지원 및 유지보수", "차별성 및 경쟁력", "개발 로드맵 및 향후 계획"]
    }

    for sheet_name, df_summary in all_summaries.items():
        df_full, _ = load_evaluation_data(sheet_name=sheet_name)
        df_full['설명'] = df_full['설명'].replace('', pd.NA).ffill()
        df_full['Present Lv.'] = pd.to_numeric(df_full['Present Lv.'], errors='coerce')
        for section_label, subcategories in section_mappings.items():
            section_rows = df_full[df_full['설명'].isin(subcategories) & df_full['Present Lv.'].notna()]
            if not section_rows.empty:
                total = section_rows['Present Lv.'].sum()
                count = len(section_rows)
                percentage = round((total / (count * 5)) * 100, 2)
                row_num = row_mapping[section_label]
                cell_updates.append({
                    "range": f"B{row_num}",
                    "values": [[f"{percentage:.2f}%"]]
                })

    # Update overall total score
    total_rows = []
    for sheet_name in all_summaries:
        df_full, _ = load_evaluation_data(sheet_name=sheet_name)
        df_full['Present Lv.'] = pd.to_numeric(df_full['Present Lv.'], errors='coerce')
        total_rows.append(df_full[df_full['Present Lv.'].notna()])

    if total_rows:
        all_valid = pd.concat(total_rows)
        total_score = all_valid['Present Lv.'].sum()
        total_count = len(all_valid)
        if total_count > 0:
            overall_percentage = round((total_score / (total_count * 5)) * 100, 2)
            cell_updates.append({
                "range": "B27",
                "values": [[f"{overall_percentage:.2f}%"]]
            })

    if cell_updates:
        worksheet.batch_update(cell_updates)

write_combined_summary(all_summaries)
