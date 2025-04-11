import pandas as pd
import os
import chardet
from datetime import datetime, timedelta

def detect_encoding(file_path):
    with open(file_path, "rb") as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result["encoding"]

def process_attendance(input_folder, output_folder, session_start="09:00", session_end="11:00"):
    all_files = [f for f in os.listdir(input_folder) if f.endswith(".csv")]
    if not all_files:
        print("X No CSV files found in", input_folder)
        return

    monthly_csv = os.path.join(output_folder, "Monthly_Attendance.csv")

    if os.path.exists(monthly_csv):
        monthly_df = pd.read_csv(monthly_csv)
    else:
        monthly_df = pd.DataFrame(columns=["Full Name"])

    all_names = set(monthly_df["Full Name"]) if not monthly_df.empty else set()

    for file in all_files:
        file_path = os.path.join(input_folder, file)
        encoding_type = detect_encoding(file_path)

        try:
            daily_df = pd.read_csv(file_path, encoding=encoding_type, delimiter='\t')
        except Exception as e:
            print(f"X Error reading {file}: {e}")
            continue

        daily_df.columns = [col.strip().lower().replace(" ", "_") for col in daily_df.columns]

        required_columns = {"full_name", "user_action", "timestamp"}
        if not required_columns.issubset(set(daily_df.columns)):
            print(f"X Skipping {file}: Missing required columns. Found: {daily_df.columns}")
            continue

        daily_df["timestamp"] = pd.to_datetime(daily_df["timestamp"], errors="coerce")
        daily_df = daily_df.dropna(subset=["timestamp"])

        session_date = daily_df["timestamp"].dt.date.min()
        if pd.isna(session_date):
            print(f"X Skipping {file}: Unable to determine session date.")
            continue
        date_col = session_date.strftime("%Y-%m-%d")

        session_start_time = datetime.strptime(session_start, "%H:%M").time()
        session_end_time = datetime.strptime(session_end, "%H:%M").time()
        session_duration = (datetime.combine(datetime.today(), session_end_time) -
                            datetime.combine(datetime.today(), session_start_time)).total_seconds()
        required_duration = session_duration * 0.8  # 80% of session duration

        daily_attendance = {}
        user_times = {}

        for _, row in daily_df.iterrows():
            name = row["full_name"].strip()
            action = str(row["user_action"]).strip().lower()
            timestamp = row["timestamp"]

            if name not in user_times:
                user_times[name] = []
            user_times[name].append(timestamp)

        for name, times in user_times.items():
            times.sort()
            total_time = sum((times[i + 1] - times[i]).total_seconds()
                             for i in range(0, len(times) - 1, 2))  # Pair-wise session calculation

            daily_attendance[name] = "Y" if total_time >= required_duration else "N"

        all_names.update(daily_attendance.keys())
        daily_attendance_df = pd.DataFrame(list(daily_attendance.items()), columns=["Full Name", date_col])

        # Ensure consistent data types for 'Full Name' before merging
        monthly_df['Full Name'] = monthly_df['Full Name'].astype(str)
        daily_attendance_df['Full Name'] = daily_attendance_df['Full Name'].astype(str)

        if date_col in monthly_df.columns:
            for index, row in daily_attendance_df.iterrows():
                monthly_df.loc[monthly_df["Full Name"] == row["Full Name"], date_col] = row[date_col]
        else:
            monthly_df = monthly_df.merge(daily_attendance_df, on="Full Name", how="outer")

        print(f"✓ Processed: {file}")

    monthly_df = pd.DataFrame({"Full Name": sorted(all_names)}).merge(monthly_df, on="Full Name", how="left").fillna("")
    monthly_df.to_csv(monthly_csv, index=False)
    print(f"✓ Monthly attendance updated: {monthly_csv}")

if __name__ == "__main__":
    input_folder = "daily_attendance"
    output_folder = "."
    process_attendance(input_folder, output_folder)

