
import streamlit as st
import sqlite3
from datetime import datetime, timedelta
from line_bot import send_line

st.title("Study Coach")

conn = sqlite3.connect("study.db")
cursor = conn.cursor()

st.header("今日の勉強記録")

subject = st.selectbox("教科", ["数学", "英語", "国語", "理科", "社会", "その他"])
category = st.text_input("カテゴリー（例：微分、長文）")

understand_level = st.slider("理解度", 1, 5, 3)
focus_level = st.slider("集中度", 1, 5, 3)
study_time = st.number_input(
    "勉強時間（分）", min_value=1, max_value=600, value=30, step=5
)

if st.button("保存する"):
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    cursor.execute("""
        INSERT INTO study_log 
        (datetime, subject, category, minutes, understand_level, focus_level)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (today, subject, category, study_time, understand_level, focus_level))

    log_id = cursor.lastrowid

    review_days = 1 if understand_level >= 4 else 3
    review_count = 1 if understand_level >= 4 else 3

    for i in range(review_count):
        review_date = (
            datetime.now() + timedelta(days=review_days * (i + 1))
        ).strftime("%Y-%m-%d %H:%M")

        cursor.execute("""
            INSERT INTO review_log (log_id, review_datetime)
            VALUES (?, ?)
        """, (log_id, review_date))

    conn.commit()
    st.success("勉強記録が保存されました！")

conn.close()

import pandas as pd
st.header("今週の勉強時間（教科別）")

conn = sqlite3.connect("study.db")
df = pd.read_sql_query("""
    SELECT subject, SUM(CAST(minutes AS INTEGER)) AS total_minutes
    FROM study_log
    WHERE datetime >= datetime('now', '-7 days')
    GROUP BY subject
""", conn)  
conn.close()
if not df.empty:
    st.bar_chart(df.set_index('subject'))
else:
    st.write("過去1週間の勉強記録はありません。")

st.header("曜日別　勉強時間")
conn = sqlite3.connect("study.db")
df_day =pd.read_sql_query("""
    SELECT 
        strftime('%w', datetime) AS weekday,
        SUM(CAST(minutes AS INTEGER)) AS total_minutes
    FROM study_log
    WHERE datetime >= datetime('now', '-7 days')
    GROUP BY weekday
""", conn)
conn.close()

weekday_map = {
    '0': '日曜日',
    '1': '月曜日',
    '2': '火曜日',
    '3': '水曜日',
    '4': '木曜日',
    '5': '金曜日',
    '6': '土曜日'
}

df_day['weekday'] = df_day['weekday'].map(weekday_map)

df_day = df_day.set_index('weekday').reindex([
    '月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日'
]).fillna(0)

st.bar_chart(df_day)

st.header("今日の復習予定")
conn = sqlite3.connect("study.db")
df_review = pd.read_sql_query("""
    SELECT  s.subject, s.category, r.review_datetime
    FROM review_log r 
    JOIN study_log s ON r.log_id = s.id
    WHERE date(r.review_datetime) = date('now') 
    ORDER BY r.review_datetime
""", conn)
conn.close()

if not df_review.empty:
    for _, row in df_review.iterrows():
        st.write(f"- {row['review_datetime']}: {row['subject']} - {row['category']}")
    

else:
    st.write("今日の復習予定はありません！")


if st.button("今日の復習をLINEに送る"):
    conn = sqlite3.connect("study.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            r.review_datetime,
            s.subject,
            s.category
        FROM review_log r
        JOIN study_log s ON r.log_id = s.id
        WHERE date(r.review_datetime) = date('now')
        ORDER BY r.review_datetime
    """)
    results = cursor.fetchall()
    conn.close()

    if results:
        msg ="[今日の復習予定]\n"
        for dt, subject,category in results:
            msg += f"\n{dt}\n-{subject}({category})"
        
        send_line(msg)
        st.success("LINEに送信しました！")
    
    else:
        st.info("今日は復習予定がありません")

st.header("今日やるべき復習（理解度が低い順）")

conn = sqlite3.connect("study.db")
df_review = pd.read_sql_query("""
    SELECT  
        s.subject,
        s.category,
        s.understand_level,
        r.review_datetime
    FROM review_log r 
    JOIN study_log s ON r.log_id = s.id
    WHERE date(r.review_datetime) = date('now')
    ORDER BY s.understand_level ASC, r.review_datetime
""", conn)
conn.close()

conn = sqlite3.connect("study.db")
df_today = pd.read_sql_query("""
    SELECT  
        s.subject,
        s.category,
        s.understand_level,
        r.review_datetime
    FROM review_log r 
    JOIN study_log s ON r.log_id = s.id
    WHERE date(r.review_datetime) = date('now') AND r.done = 0
    ORDER BY s.understand_level ASC, r.review_datetime
""", conn)
conn.close()

if not df_today.empty:
    for _, row in df_today.iterrows():
        if row["understand_level"] <= 2:
            st.error(
                f"最優先復習\n"
                f"{row['subject']}（{row['category']}）\n"
                f"理解度: {row['understand_level']} / 5\n"
                f"{row['review_datetime']}"
            )
        else:
            st.info(
                f"{row['subject']}（{row['category']}）\n"
                f"理解度: {row['understand_level']} / 5\n"
                f"{row['review_datetime']}"
            )
else:
    st.success("今日の未完了復習はありません！")

st.header("今日やるべき復習（チェック可能）")

conn = sqlite3.connect("study.db")
df_review = pd.read_sql_query("""
    SELECT  
        r.id AS review_id,
        s.subject,
        s.category,
        s.understand_level,
        r.review_datetime,
        r.done
    FROM review_log r 
    JOIN study_log s ON r.log_id = s.id
    WHERE date(r.review_datetime) = date('now')
    ORDER BY s.understand_level ASC, r.review_datetime
""", conn)

if not df_review.empty:
    for _, row in df_review.iterrows():
        col1, col2 = st.columns([0.1, 0.9])
        done = col1.checkbox("", value=row['done'], key=row['review_id'])
        if done != row['done']:
            # チェックボックスの変更があったら DB を更新
            cursor = conn.cursor()
            cursor.execute("UPDATE review_log SET done = ? WHERE id = ?", (1 if done else 0, row['review_id']))
            conn.commit()
        
        col2.markdown(
            f"**{row['subject']}（{row['category']}）**  \n"
            f"理解度: {row['understand_level']} / 5  \n"
            f"{row['review_datetime']}"
        )
else:
    st.success("今日やるべき復習はありません！")

conn.close()


st.header("データリセット")

if st.button("すべての勉強データを削除"):
    conn = sqlite3.connect("study.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM study_log")
    cursor.execute("DELETE FROM review_log")
    conn.commit()
    conn.close()
    st.warning("すべてのデータを削除しました！")

if not df_review.empty:
    for _, row in df_review.iterrows():
        if row["understand_level"] <= 2:
            st.error(
                f"最優先復習\n"
                f"{row['subject']}（{row['category']}）\n"
                f"理解度: {row['understand_level']} / 5\n"
                f"{row['review_datetime']}"
            )
        else:
            st.info(
                f"{row['subject']}（{row['category']}）\n"
                f"理解度: {row['understand_level']} / 5\n"
                f"{row['review_datetime']}"
            )
else:
    st.success("今日やるべき復習はありません！")



st.header("⚠ データ管理")

confirm = st.checkbox("本当にすべての勉強記録を削除する（元に戻せません）")

if confirm:
    if st.button("⚠ すべての記録をリセット"):
        conn = sqlite3.connect("study.db")
        cursor = conn.cursor()

        cursor.execute("DELETE FROM review_log")
        cursor.execute("DELETE FROM study_log")

        conn.commit()
        conn.close()

        st.success("すべての記録をリセットしました")
else:
    st.info("チェックを入れるとリセットボタンが有効になります")
