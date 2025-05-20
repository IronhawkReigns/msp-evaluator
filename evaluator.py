def append_category_scores_to_sheet(sheet_df, use_weighted_average=False):
    sheet_df['설명'] = sheet_df['설명'].replace('', pd.NA).ffill()
    sheet_df['Present Lv.'] = pd.to_numeric(sheet_df['Present Lv.'], errors='coerce')
    valid_rows = sheet_df[sheet_df['Key Questions'].notna() & sheet_df['Present Lv.'].notna()].copy()

    grouped = valid_rows.groupby('설명', sort=False)

    category_scores = {}
    question_counts = {}

    for category, group in grouped:
        score_sum = group['Present Lv.'].sum()
        question_count = len(group)
        max_score = question_count * 5
        percentage = round(score_sum / max_score, 4) if max_score > 0 else 0.0
        category_scores[category] = percentage
        question_counts[category] = question_count

    if use_weighted_average:
        total_score = valid_rows['Present Lv.'].sum()
        question_count = len(valid_rows)
        max_score = question_count * 5
        avg_score = round((total_score / max_score) * 100, 2) if max_score > 0 else 0.0
    else:
        total_weight = sum(question_counts.values())
        weighted_sum = sum(score * question_counts[cat] for cat, score in category_scores.items())
        avg_score = round((weighted_sum / total_weight) * 100, 2) if total_weight > 0 else 0.0

    summary_rows = [["총점", f"{avg_score:.2f}%", sum(question_counts.values())]]
    for category, score in category_scores.items():
        summary_rows.append([category, f"{score * 100:.2f}%", question_counts[category]])

    summary_df = pd.DataFrame(summary_rows, columns=["Category", "Score (%)", "Questions"])
    return summary_df
