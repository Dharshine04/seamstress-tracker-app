# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# === AUTH ===
creds_path = "seamstress_creds.json"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(creds_path, scopes=scope)
client = gspread.authorize(creds)

# === LOAD SHEETS ===
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/13DEtiPzOi3-lqKl6f3wehhO-urORH70atNWNEk28mzk")
plan_ws = sheet.worksheet("Production Plan")

# === PAGE CONFIG ===
st.set_page_config(page_title="Seamstress Planner", layout="wide")
st.title("🧵 Seamstress Production Planner")

menu = st.sidebar.radio("Navigation", ["📋 Task Table", "📊 Dashboard"])

# === TASK TABLE ===
if menu == "📋 Task Table":
    st.subheader("📌 Manage Production Tasks")
    df = pd.DataFrame(plan_ws.get_all_records())
    df.columns = df.columns.str.strip().str.title()

    required_columns = ['Task Name', 'Category', 'Quantity', 'Seamstress', 'Status', 'Priority', 
                        'Cost', 'Expected File Upload', 'Delivered File Upload', 'Timeline', 'Last Updated']

    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        st.error(f"❌ Missing columns in Google Sheet: {', '.join(missing_cols)}")
        st.stop()

    df["Last Updated"] = pd.to_datetime(df["Last Updated"], errors='coerce')

    # === ADD FORM ===
    with st.expander("➕ Add New Task"):
        with st.form("add_task_form"):
            col1, col2, col3 = st.columns(3)
            task = col1.text_input("Task Name")
            category = col2.selectbox("Category", ["Stitching", "Custom/Alteration", "Labelling"])
            qty = col3.number_input("Quantity", min_value=1)

            col4, col5, col6 = st.columns(3)
            seamstress = col4.text_input("Seamstress")
            status = col5.selectbox("Status", ["Working", "Done", "Stuck"])
            priority = col6.selectbox("Priority", ["Low", "Medium", "High"])

            cost = st.number_input("Cost ($)", min_value=0.0)
            exp_file = st.text_input("Expected File Link")
            del_file = st.text_input("Delivered File Link")
            due = st.date_input("Due Date")

            if st.form_submit_button("Add Task"):
                plan_ws.append_row([
                    task, category, qty, seamstress, status, priority,
                    cost, exp_file, del_file, str(due), datetime.today().strftime("%Y-%m-%d")
                ])
                st.success("✅ Task added.")
                st.experimental_rerun()

    # === FILTERS ===
    filter1 = st.multiselect("Filter by Status", df["Status"].unique())
    filter2 = st.multiselect("Filter by Category", df["Category"].unique())

    filtered_df = df.copy()
    if filter1:
        filtered_df = filtered_df[filtered_df["Status"].isin(filter1)]
    if filter2:
        filtered_df = filtered_df[filtered_df["Category"].isin(filter2)]

    st.markdown("### 📋 Editable Task Table")

    gb = GridOptionsBuilder.from_dataframe(filtered_df)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_default_column(editable=True, groupable=True)
    gb.configure_selection("single")
    gridOptions = gb.build()

    grid_response = AgGrid(
        filtered_df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.MANUAL,
        fit_columns_on_grid_load=True,
        height=400,
        width='100%',
        theme="material"
    )

    updated_df = grid_response["data"]
    selected_row = grid_response["selected_rows"]

    if selected_row:
        row_index = selected_row[0]['_selectedRowNodeInfo']['nodeRowIndex']
        row_number = df.index[df["Task Name"] == selected_row[0]["Task Name"]][0] + 2
        st.markdown("### ✏️ Selected Row Actions")
        col7, col8 = st.columns(2)
        if col7.button("Update Selected Task"):
            new_row = updated_df.iloc[row_index].tolist()
            new_row[-1] = datetime.today().strftime("%Y-%m-%d")  # Update last updated
            plan_ws.delete_row(row_number)
            plan_ws.insert_row(new_row, row_number)
            st.success("✅ Task updated.")
            st.experimental_rerun()
        if col8.button("Delete Selected Task"):
            plan_ws.delete_row(row_number)
            st.warning("🗑️ Task deleted.")
            st.experimental_rerun()

# === DASHBOARD ===
elif menu == "📊 Dashboard":
    st.subheader("📊 Task Summary Dashboard")
    df = pd.DataFrame(plan_ws.get_all_records())
    df.columns = df.columns.str.strip().str.title()

    if df.empty:
        st.info("No tasks found.")
    elif "Status" not in df.columns:
        st.error("❌ 'Status' column missing in the data.")
    else:
        st.write("### Summary")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Tasks", len(df))
        col2.metric("✅ Done", (df["Status"] == "Done").sum())
        col3.metric("🟡 Working", (df["Status"] == "Working").sum())
        col4.metric("🔴 Stuck", (df["Status"] == "Stuck").sum())

        df["Timeline"] = pd.to_datetime(df["Timeline"], errors="coerce")
        df["Due Date"] = df["Timeline"].dt.date

        st.plotly_chart(px.pie(df, names="Status", title="Tasks by Status"), use_container_width=True)
        st.plotly_chart(px.histogram(df, x="Due Date", color="Status", title="Tasks by Due Date"), use_container_width=True)
        st.plotly_chart(px.histogram(df, x="Seamstress", color="Status", title="Tasks by Seamstress"), use_container_width=True)

        overdue = df[df["Timeline"] < pd.Timestamp.today()]
        if not overdue.empty:
            st.write("### ⏰ Overdue Tasks")
            st.dataframe(overdue[["Task Name", "Seamstress", "Timeline", "Status"]])
