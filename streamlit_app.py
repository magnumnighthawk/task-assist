
import streamlit as st
import datetime
import uuid
import requests
from generate import generate_subtasks, revise_subtasks
from reminder import ReminderAgent
from db import create_work, get_db, get_all_works, get_tasks_by_work
from sqlalchemy.orm import Session

st.set_page_config(page_title="Task assist AI", page_icon="favicon.png")

# --- Page Navigation ---
page = st.sidebar.radio("Navigation", ["Task Generator", "View Work & Tasks"])

if page == "Task Generator":
    st.title("Task assist AI")
    task_description = st.text_input("Enter a new task:")
    max_subtasks = st.number_input("Enter the maximum number of subtasks:", min_value=1, step=1, value=5)

    if 'loading_generate' not in st.session_state:
        st.session_state.loading_generate = False
    if st.session_state.loading_generate:
        with st.spinner("Generating subtasks..."):
            pass
    if st.button("Generate Subtasks"):
        st.session_state.loading_generate = True
        with st.spinner("Generating subtasks..."):
            result = generate_subtasks(task_description, max_subtasks=max_subtasks)
            st.session_state.llm_work_name = result.get('work_name', task_description)
            st.session_state.llm_work_description = result.get('work_description', task_description)
            subtasks = result['subtasks']
            # Assign a unique uid to each subtask
            for sub in subtasks:
                if 'uid' not in sub:
                    sub['uid'] = str(uuid.uuid4())
            st.session_state.subtasks = subtasks
            st.session_state.edit_mode = [False] * len(subtasks)
            st.session_state.subtask_due_dates = [None] * len(subtasks)
        st.session_state.loading_generate = False
        st.rerun()


    def get_priority_color(priority):
        if priority == "High":
            return "red"
        elif priority == "Medium":
            return "orange"
        elif priority == "Low":
            return "green"
        return "gray"

    if 'subtasks' in st.session_state:
        st.write("Generated Subtasks:")

        # --- Subtasks List UI ---
        for i, subtask in enumerate(st.session_state.subtasks):
            # Ensure every subtask has a uid
            if 'uid' not in subtask:
                subtask['uid'] = str(uuid.uuid4())
            # --- Action Panel using st.columns for all actions ---
            col1, col_due, col_save, col_discard, col_edit, col_delete, col_up, col_down, col_sched = st.columns([5, 2, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 3])
            with col1:
                if st.session_state.edit_mode[i]:
                    new_subtask = st.text_input("Subtask", value=subtask['description'], key=f"subtask_{subtask['uid']}")
                    st.session_state.subtasks[i]['description'] = new_subtask
                else:
                    priority_color = get_priority_color(subtask['priority'])
                    st.markdown(
                        f"{subtask['description']} <span style='background-color:{priority_color}; padding: 2px 4px; border-radius: 4px; margin-left: 8px;'>{subtask['priority']}</span>",
                        unsafe_allow_html=True
                    )
            with col_due:
                st.markdown(f"<b>Due</b>", unsafe_allow_html=True)
                due_date = st.date_input(" ", value=st.session_state.subtask_due_dates[i] or datetime.date.today(), key=f"due_date_{subtask['uid']}")
                st.session_state.subtask_due_dates[i] = due_date
            with col_save:
                st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
                if st.session_state.edit_mode[i]:
                    if st.button("💾", key=f"save_{i}_{subtask['uid']}", help="Save"):
                        st.session_state.edit_mode[i] = False
                        st.rerun()
            with col_discard:
                st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
                if st.session_state.edit_mode[i]:
                    if st.button("❌", key=f"discard_{i}_{subtask['uid']}", help="Discard changes"):
                        st.session_state.edit_mode[i] = False
                        st.rerun()
            with col_edit:
                st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
                if not st.session_state.edit_mode[i]:
                    if st.button("✏️", key=f"edit_{i}_{subtask['uid']}", help="Edit"):
                        st.session_state.edit_mode[i] = True
                        st.rerun()
            with col_delete:
                st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"delete_{i}_{subtask['uid']}", help="Delete"):
                    st.session_state.subtasks.pop(i)
                    st.session_state.edit_mode.pop(i)
                    st.session_state.subtask_due_dates.pop(i)
                    st.rerun()
            with col_up:
                st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
                if st.button("⬆️", key=f"up_{i}_{subtask['uid']}", help="Move up") and i > 0:
                    st.session_state.subtasks[i], st.session_state.subtasks[i-1] = st.session_state.subtasks[i-1], st.session_state.subtasks[i]
                    st.session_state.edit_mode[i], st.session_state.edit_mode[i-1] = st.session_state.edit_mode[i-1], st.session_state.edit_mode[i]
                    st.session_state.subtask_due_dates[i], st.session_state.subtask_due_dates[i-1] = st.session_state.subtask_due_dates[i-1], st.session_state.subtask_due_dates[i]
                    st.rerun()
            with col_down:
                st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
                if st.button("⬇️", key=f"down_{i}_{subtask['uid']}", help="Move down") and i < len(st.session_state.subtasks) - 1:
                    st.session_state.subtasks[i], st.session_state.subtasks[i+1] = st.session_state.subtasks[i+1], st.session_state.subtasks[i]
                    st.session_state.edit_mode[i], st.session_state.edit_mode[i+1] = st.session_state.edit_mode[i+1], st.session_state.edit_mode[i]
                    st.session_state.subtask_due_dates[i], st.session_state.subtask_due_dates[i+1] = st.session_state.subtask_due_dates[i+1], st.session_state.subtask_due_dates[i]
                    st.rerun()
            with col_sched:
                st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
                schedule_key = f"loading_schedule_{i}_{subtask['uid']}"
                if schedule_key not in st.session_state:
                    st.session_state[schedule_key] = False
                if st.session_state[schedule_key]:
                    with st.spinner("Scheduling event..."):
                        pass
                if st.button("Add to Calendar", key=f"schedule_{i}_{subtask['uid']}", help="Add to Calendar"):
                    st.session_state[schedule_key] = True
                    with st.spinner("Scheduling event..."):
                        agent = ReminderAgent()
                        summary = subtask['description']
                        start_time = datetime.datetime.combine(due_date, datetime.time(8, 0)).isoformat()
                        end_time = (datetime.datetime.combine(due_date, datetime.time(8, 0)) + datetime.timedelta(hours=1)).isoformat()
                        try:
                            event = agent.create_event(summary, start_time, end_time, description=f"Auto-scheduled by Task Assist. Priority: {subtask['priority']}")
                            st.success(f"Calendar event created for subtask: {summary}")
                            st.write(f"Event link: {event.get('htmlLink')}")
                        except Exception as e:
                            st.error(f"Failed to create calendar event: {e}")
                    st.session_state[schedule_key] = False
                    st.rerun()

        with st.expander("Revise Subtasks", expanded=False):
            feedback = st.text_area("Describe how you want to revise or break down the subtasks (specify which if needed):", key="revise_feedback")
            if st.button("Revise Subtasks"):
                st.session_state.loading_revise = True
                with st.spinner("Revising subtasks..."):
                    revised_result = revise_subtasks(st.session_state.subtasks, feedback, max_subtasks=len(st.session_state.subtasks))
                    revised_subtasks = revised_result['subtasks']
                    # Assign a unique uid to each revised subtask if missing
                    for sub in revised_subtasks:
                        if 'uid' not in sub:
                            sub['uid'] = str(uuid.uuid4())
                    print('REVISED SUBTASKS:', revised_subtasks)
                    st.session_state.subtasks = revised_subtasks
                    st.session_state.edit_mode = [False] * len(revised_subtasks)
                    st.session_state.subtask_due_dates = [None] * len(revised_subtasks)
                st.success("Subtasks revised.")
                st.session_state.loading_revise = False
                st.rerun()

        # --- Submit to DB ---
        if st.button("Submit"):
            db_gen = get_db()
            db: Session = next(db_gen)
            work_title = st.session_state.get('llm_work_name', task_description) or "Untitled Work"
            work_desc = st.session_state.get('llm_work_description', task_description)
            tasks = []
            for i, subtask in enumerate(st.session_state.subtasks):
                due_date = st.session_state.subtask_due_dates[i] if 'subtask_due_dates' in st.session_state else None
                tasks.append({
                    "title": subtask["description"],
                    "status": "pending",
                    "due_date": due_date
                })
            work = create_work(db, title=work_title, description=work_desc, tasks=tasks)
            st.success(f"Work and tasks saved to database (Work ID: {work.id})")

        if 'loading_revise' not in st.session_state:
            st.session_state.loading_revise = False
        if st.session_state.loading_revise:
            with st.spinner("Revising subtasks..."):
                pass

elif page == "View Work & Tasks":
    st.title("Work & Tasks List")
    db_gen = get_db()
    db: Session = next(db_gen)
    works = get_all_works(db)
    if not works:
        st.info("No Work items found.")
    else:
        for work in works:
            with st.expander(f"{work.title} (ID: {work.id})", expanded=False):
                st.write(f"**Description:** {work.description}")
                st.write(f"**Created:** {work.created_at}")
                # Edit Work title/desc
                edit_title = st.text_input("Edit Title", value=work.title, key=f"edit_title_{work.id}")
                edit_desc = st.text_area("Edit Description", value=work.description, key=f"edit_desc_{work.id}")
                if st.button("Save Changes", key=f"save_work_{work.id}"):
                    work.title = edit_title
                    work.description = edit_desc
                    db.commit()
                    st.success("Work updated.")
                if st.button("Delete Work", key=f"delete_work_{work.id}"):
                    db.delete(work)
                    db.commit()
                    st.warning("Work deleted.")
                    st.rerun()
                # Notify button for Slack integration
                if st.button("Notify", key=f"notify_work_{work.id}"):
                    import requests
                    # Use internal Flask address (supervisor runs Flask on 9000)
                    api_url = f"http://127.0.0.1:9000/api/notify-work/{work.id}"
                    try:
                        response = requests.post(api_url)
                        try:
                            data = response.json()
                        except Exception:
                            data = None
                        if response.status_code == 200:
                            st.success("Slack interactive notification sent!")
                        elif data and 'message' in data:
                            st.error(f"Failed to send notification: {data['message']}")
                        else:
                            st.error(f"Failed to send notification. Status: {response.status_code}. Response: {response.text}")
                    except Exception as e:
                        st.error(f"Error calling notify API: {e}")

                # List Tasks
                tasks = get_tasks_by_work(db, work.id)
                if not tasks:
                    st.write("No tasks for this work.")
                else:
                    for task in tasks:
                        col1, col2, col3, col4 = st.columns([4, 2, 2, 3])
                        with col1:
                            edit_task_title = st.text_input("Task", value=task.title, key=f"task_title_{task.id}")
                            with col2:
                                edit_task_status = st.selectbox("Status", ["pending", "done"], index=0 if task.status=="pending" else 1, key=f"task_status_{task.id}")
                        with col3:
                            # Show due date if available
                            if task.due_date:
                                st.markdown(f"<b>Due date:</b> {task.due_date.strftime('%Y-%m-%d')}", unsafe_allow_html=True)
                            else:
                                st.markdown("<b>Due date:</b> -", unsafe_allow_html=True)
                        with col4:
                            if st.button("Save", key=f"save_task_{task.id}"):
                                task.title = edit_task_title
                                task.status = edit_task_status
                                db.commit()
                                st.success("Task updated.")
                            if st.button("Delete", key=f"delete_task_{task.id}"):
                                db.delete(task)
                                db.commit()
                                st.warning("Task deleted.")
                                st.rerun()
