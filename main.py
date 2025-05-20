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

        # Skip if there's no interview result
        if interview_result == "":
            print(f"Skipping row {idx+1} (no interview result)", flush=True)
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
    
    cell_updates = []

    combined_rows = []
    for sheet_name, df_summary in all_summaries.items():
        for idx, row in df_summary.iterrows():
            label = row['Category'] if 'Category' in row else None
            score = row['Score (%)'] if 'Score (%)' in row else None
            if label is not None and score is not None:
                combined_rows.append([label, score])
    
    # Define updated row mappings for each label (row number = 1-based index)
    row_mapping = {
        "총점": 2,
        "인적역량 총점": 4,
        "AI 전문 인력 구성": 5,
        "프로젝트 경험 및 성공 사례": 6,
        "지속적인 교육 및 학습": 7,
        "프로젝트 관리 및 커뮤니케이션": 8,
        "AI 윤리 및 책임 의식": 9,
        "AI기술역량 총점": 11,
        "AI 기술 연구 능력": 12,
        "AI 모델 개발 능력": 13,
        "AI 플랫폼 및 인프라 구축 능력": 14,
        "데이터 처리 및 분석 능력": 15,
        "AI 기술의 융합 및 활용 능력": 16,
        "AI 기술의 특허 및 인증 보유 현황": 17,
        "솔루션 역량 총점": 19,
        "다양성 및 전문성": 20,
        "안정성": 21,
        "확장성 및 유연성": 22,
        "사용자 편의성": 23,
        "보안성": 24,
        "기술 지원 및 유지보수": 25,
        "차별성 및 경쟁력": 26,
        "개발 로드맵 및 향후 계획": 27
    }

    for row in combined_rows:
        if isinstance(row, list) and len(row) == 2:
            label, score = str(row[0]), str(row[1])
            if label in row_mapping:
                row_num = row_mapping[label]
                cell_updates.append({
                    "range": f"B{row_num}",
                    "values": [[score]]
                })
            else:
                print(f"[WARNING] Label '{label}' not in hardcoded row mapping.")

    # Section-level 평균 계산
    sections = {
        "인적역량 총점": [5, 6, 7, 8, 9],
        "AI기술역량 총점": [12, 13, 14, 15, 16, 17],
        "솔루션 역량 총점": [20, 21, 22, 23, 24, 25, 26, 27]
    }
    section_rows = {"인적역량 총점": 4, "AI기술역량 총점": 11, "솔루션 역량 총점": 19}

    for sheet_name, df_summary in all_summaries.items():
        for section, member_rows in sections.items():
            section_labels = [label for label, row in row_mapping.items() if row in member_rows]
            filtered_df = df_summary[df_summary["Category"].isin(section_labels)]
            if not filtered_df.empty:
                scores = filtered_df["Score (%)"].str.replace("%", "").astype(float)
                weights = filtered_df["Questions"].astype(float)
                if weights.sum() > 0:
                    weighted_avg = round((scores * weights).sum() / weights.sum(), 2)
                    cell_updates.append({
                        "range": f"B{section_rows[section]}",
                        "values": [[f"{weighted_avg:.2f}%"]]
                    })

    # Ensure display rows under each section header remain visually separated with a blank line
    cell_updates.append({"range": "B3", "values": [[""]]})
    cell_updates.append({"range": "B10", "values": [[""]]})
    cell_updates.append({"range": "B18", "values": [[""]]})

    if cell_updates:
        worksheet.batch_update(cell_updates)

write_combined_summary(all_summaries)
