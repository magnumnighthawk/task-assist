
import streamlit as st
import datetime
import uuid
import requests
import threading
import logging
from generate import generate_subtasks, revise_subtasks
from reminder import ReminderAgent
from db import create_work, get_db, get_all_works, get_tasks_by_work
from sqlalchemy.orm import Session


# --- Custom CSS for modern look ---
st.set_page_config(page_title="Task Assist AI", page_icon="favicon.png")
st.markdown(
    """
    <style>
    html, body, [class*="css"]  {
        font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
        background-color: #f7f9fa;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 900px;
    }
    h1, h2, h3, h4 {
        font-weight: 700;
        color: #1a202c;
        letter-spacing: -1px;
    }
    .stButton>button {
        background: linear-gradient(90deg, #4f8cff 0%, #38b2ac 100%);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1.2rem;
        font-weight: 600;
        transition: box-shadow 0.2s;
        box-shadow: 0 2px 8px rgba(80,120,200,0.07);
    }
    .stButton>button:hover {
        box-shadow: 0 4px 16px rgba(80,120,200,0.15);
        background: linear-gradient(90deg, #38b2ac 0%, #4f8cff 100%);
    }
    .stTextInput>div>div>input {
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        padding: 0.4rem 0.8rem;
    }
    .stDateInput>div>input {
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        padding: 0.4rem 0.8rem;
    }
    .stSelectbox>div>div>div {
        border-radius: 6px;
        border: 1px solid #cbd5e1;
    }
    .stMarkdown h2 {
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .priority-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.9em;
        font-weight: 600;
        margin-left: 8px;
    }
    .priority-high { background: #ff4d4f; color: white; }
    .priority-medium { background: #ffb020; color: #222; }
    .priority-low { background: #38b2ac; color: white; }
    .status-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.95em;
        font-weight: 600;
        margin-left: 8px;
    }
    .status-draft { background: #cbd5e1; color: #222; }
    .status-published { background: #4f8cff; color: white; }
    .status-completed { background: #38b2ac; color: white; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Page Navigation ---
page = st.sidebar.radio("Navigation", ["Task Generator", "View Work & Tasks"])

if page == "Task Generator":
    st.markdown("<h1>Task Assist AI</h1>", unsafe_allow_html=True)
    task_description = st.text_input("Enter a new task:", help="Describe the high-level task you want to break down.")
    max_subtasks = st.number_input("Maximum subtasks:", min_value=1, step=1, value=5, help="How many subtasks should be generated?")

    if 'loading_generate' not in st.session_state:
        st.session_state.loading_generate = False
    if st.session_state.loading_generate:
        with st.spinner("Generating subtasks..."):
            pass
    if st.button("Generate Subtasks", help="Use AI to break down your task into actionable subtasks."):
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


    def get_priority_class(priority):
        if priority == "High":
            return "priority-badge priority-high"
        elif priority == "Medium":
            return "priority-badge priority-medium"
        elif priority == "Low":
            return "priority-badge priority-low"
        return "priority-badge"

    if 'subtasks' in st.session_state:
        st.write("Generated Subtasks:")

        # --- Subtasks List UI ---
        for i, subtask in enumerate(st.session_state.subtasks):
            # Ensure every subtask has a uid
            if 'uid' not in subtask:
                subtask['uid'] = str(uuid.uuid4())
            col1, col_due, col_save, col_discard, col_edit, col_delete, col_up, col_down, col_sched = st.columns([5, 3, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 3])
            with col1:
                if st.session_state.edit_mode[i]:
                    new_subtask = st.text_input("Subtask", value=subtask['description'], key=f"subtask_{subtask['uid']}")
                    st.session_state.subtasks[i]['description'] = new_subtask
                else:
                    priority_class = get_priority_class(subtask['priority'])
                    st.markdown(
                        f"<span style='font-size:1.1em;font-weight:500'>{subtask['description']}</span> "
                        f"<span class='{priority_class}'>{subtask['priority']}</span>",
                        unsafe_allow_html=True
                    )
            with col_due:
                due_date = st.date_input("Due date", value=st.session_state.subtask_due_dates[i] or datetime.date.today(), key=f"due_date_{subtask['uid']}", help="When should this subtask be completed?")
                st.session_state.subtask_due_dates[i] = due_date
            # Action icon columns
            with col_save:
                if st.session_state.edit_mode[i]:
                    if st.button("💾", key=f"save_{i}_{subtask['uid']}", help="Save changes to this subtask."):
                        st.session_state.edit_mode[i] = False
                        st.rerun()
            with col_discard:
                if st.session_state.edit_mode[i]:
                    if st.button("❌", key=f"discard_{i}_{subtask['uid']}", help="Discard changes to this subtask."):
                        st.session_state.edit_mode[i] = False
                        st.rerun()
            with col_edit:
                if not st.session_state.edit_mode[i]:
                    if st.button("✏️", key=f"edit_{i}_{subtask['uid']}", help="Edit this subtask."):
                        st.session_state.edit_mode[i] = True
                        st.rerun()
            with col_delete:
                if st.button("🗑️", key=f"delete_{i}_{subtask['uid']}", help="Delete this subtask."):
                    st.session_state.subtasks.pop(i)
                    st.session_state.edit_mode.pop(i)
                    st.session_state.subtask_due_dates.pop(i)
                    st.rerun()
            with col_up:
                if st.button("⬆️", key=f"up_{i}_{subtask['uid']}", help="Move this subtask up") and i > 0:
                    st.session_state.subtasks[i], st.session_state.subtasks[i-1] = st.session_state.subtasks[i-1], st.session_state.subtasks[i]
                    st.session_state.edit_mode[i], st.session_state.edit_mode[i-1] = st.session_state.edit_mode[i-1], st.session_state.edit_mode[i]
                    st.session_state.subtask_due_dates[i], st.session_state.subtask_due_dates[i-1] = st.session_state.subtask_due_dates[i-1], st.session_state.subtask_due_dates[i]
                    st.rerun()
            with col_down:
                if st.button("⬇️", key=f"down_{i}_{subtask['uid']}", help="Move this subtask down") and i < len(st.session_state.subtasks) - 1:
                    st.session_state.subtasks[i], st.session_state.subtasks[i+1] = st.session_state.subtasks[i+1], st.session_state.subtasks[i]
                    st.session_state.edit_mode[i], st.session_state.edit_mode[i+1] = st.session_state.edit_mode[i+1], st.session_state.edit_mode[i]
                    st.session_state.subtask_due_dates[i], st.session_state.subtask_due_dates[i+1] = st.session_state.subtask_due_dates[i+1], st.session_state.subtask_due_dates[i]
                    st.rerun()
            with col_sched:
                schedule_key = f"loading_schedule_{i}_{subtask['uid']}"
                if schedule_key not in st.session_state:
                    st.session_state[schedule_key] = False
                if st.session_state[schedule_key]:
                    with st.spinner("Scheduling event..."):
                        pass
                if st.button("Add to Calendar", key=f"schedule_{i}_{subtask['uid']}", help="Schedule this subtask as a Google Calendar event."):
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

    # Show only when generated subtasks exist
    if 'subtasks' in st.session_state and st.session_state.subtasks:
        with st.expander("Revise Subtasks", expanded=False):
                feedback = st.text_area("Describe how you want to revise or break down the subtasks (specify which if needed):", key="revise_feedback", help="Give feedback to improve or split subtasks.")
                if st.button("Revise Subtasks", help="Use AI to revise the generated subtasks."):
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
    if st.button("Submit", help="Save this work and its subtasks to the database."):
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
    st.markdown("<h1>Work & Tasks List</h1>", unsafe_allow_html=True)
    db_gen = get_db()
    db: Session = next(db_gen)
    works = get_all_works(db)
    if not works:
        st.info("No Work items found.")
    else:
        for work in works:
            with st.expander(f"{work.title} (ID: {work.id})", expanded=False):
                # Status indicator
                status_class = {
                    "Draft": "status-badge status-draft",
                    "Published": "status-badge status-published",
                    "Completed": "status-badge status-completed"
                }.get(work.status, "status-badge")
                st.markdown(f"<b>Status:</b> <span class='{status_class}'>{work.status}</span>", unsafe_allow_html=True)
                st.write(f"**Description:** {work.description}")
                st.caption(f"Created: {work.created_at}")
                # Edit Work title/desc
                edit_title = st.text_input("Edit Title", value=work.title, key=f"edit_title_{work.id}", help="Edit the work title.")
                edit_desc = st.text_area("Edit Description", value=work.description, key=f"edit_desc_{work.id}", help="Edit the work description.")
                # ACTION: Group action buttons together more closely
                if st.button("Save Changes", key=f"save_work_{work.id}", help="Save changes to this work."):
                    work.title = edit_title
                    work.description = edit_desc
                    db.commit()
                    st.success("Work updated.")
                if st.button("Delete Work", key=f"delete_work_{work.id}", help="Delete this work and all its tasks."):
                    db.delete(work)
                    db.commit()
                    st.warning("Work deleted.")
                    st.rerun()
                # Publish button only for Draft work
                if work.status == "Draft":
                    if st.button("Publish", key=f"publish_work_{work.id}", help="Publish this work and notify via Slack/Calendar."):
                        from db import publish_work, get_tasks_by_work
                        publish_work(db, work.id)
                        db.commit()

                        # Use a background thread to perform calendar event creation and Slack notification
                        def _async_publish(work_id, work_title):
                            logger = logging.getLogger('streamlit_publish')
                            logger.info(f"Async publish worker started for work {work_id}")
                            try:
                                # Check connectivity and auth before instantiating ReminderAgent
                                db_gen = get_db()
                                db_thread = next(db_gen)
                                try:
                                    import os
                                    from db import get_tasks_by_work, get_work, update_task_status
                                    # Check Google connectivity helper (may not exist in older versions)
                                    try:
                                        from reminder import _check_google_connectivity
                                        connectivity_ok = _check_google_connectivity()
                                    except Exception:
                                        connectivity_ok = True
                                    agent = None
                                    if connectivity_ok:
                                        try:
                                            agent = ReminderAgent()
                                        except Exception as e:
                                            # Likely missing credentials/token; log and proceed to send Slack only
                                            logger.warning(f"Google Calendar agent not available: {e}")
                                            agent = None
                                    else:
                                        logger.warning('Skipping calendar API calls due to failed connectivity check')

                                    tasks = get_tasks_by_work(db_thread, work_id)
                                    if not tasks:
                                        logger.info(f"Publish: no tasks to schedule for work {work_id}")
                                    else:
                                        first = True
                                        for t in tasks:
                                            try:
                                                if first:
                                                    # Mark first task as Tracked
                                                    update_task_status(db_thread, t.id, 'Tracked')
                                                    # Diagnostic logging
                                                    try:
                                                        token_exists = os.path.exists('token.pickle')
                                                        creds_exists = os.path.exists('credentials.json')
                                                    except Exception:
                                                        token_exists = False
                                                        creds_exists = False
                                                    logger.info(f"Publish: creating calendar event for task {t.id} (title: {t.title}) - due_date={t.due_date} calendar_event_id={t.calendar_event_id} token_exists={token_exists} creds_exists={creds_exists}")
                                                    if agent:
                                                        try:
                                                            ev = agent.create_event_for_task(t, work_title)
                                                            if ev:
                                                                logger.info(f"Publish: created event for task {t.id}: id={ev.get('id')} link={ev.get('htmlLink')}")
                                                            else:
                                                                logger.warning(f"Publish: create_event_for_task returned None for task {t.id}")
                                                        except Exception:
                                                            logger.exception(f"Failed to create calendar event for published work task {t.id}")
                                                    else:
                                                        # Agent not available; skip calendar creation but log clearly
                                                        logger.info(f"Publish: skipped calendar creation for task {t.id} due to unavailable Google agent or connectivity issues")
                                                    first = False
                                                else:
                                                    # Ensure others are marked Published
                                                    update_task_status(db_thread, t.id, 'Published')
                                            except Exception:
                                                logger.exception(f"Failed to process published task {t.id}")

                                    # Re-fetch work and tasks from DB so notification reflects updates
                                    try:
                                        work_obj = get_work(db_thread, work_id)
                                        # Diagnostic: show final task states
                                        final_tasks = get_tasks_by_work(db_thread, work_id)
                                        logger.info(f"Publish: final task states for work {work_id}: {[{'id': tt.id, 'status': tt.status, 'calendar_event_id': tt.calendar_event_id} for tt in final_tasks]}")
                                        if work_obj:
                                            try:
                                                if agent:
                                                    agent.send_publish_notification(work_obj)
                                                else:
                                                    # Fallback: send publish notification directly using slack helper
                                                    try:
                                                        from slack_interactive import send_publish_work_notification
                                                        import os
                                                        slack_url = os.getenv('SLACK_WEBHOOK_URL')
                                                        send_publish_work_notification(work_obj, slack_url)
                                                    except Exception:
                                                        logger.exception('Failed to send fallback publish Slack notification')
                                                logger.info(f"Publish: sent Slack notification for work {work_id}")
                                            except Exception:
                                                logger.exception(f"Failed to send publish notification for work {work_id}")
                                    except Exception:
                                        logger.exception(f"Failed while preparing publish notification for work {work_id}")
                                finally:
                                    db_thread.close()
                            except Exception as e:
                                logger.exception(f"Async publish worker error for work {work_id}: {e}")

                        try:
                            threading.Thread(target=_async_publish, args=(work.id, work.title), daemon=True).start()
                        except Exception as e:
                            print(f"Failed to schedule async publish worker: {e}")

                        st.success("Work published. Calendar event creation and notifications are running in background.")
                # Notify button for Slack integration
                if st.button("Notify", key=f"notify_work_{work.id}", help="Send a Slack notification for this work."):
                    import requests
                    import os
                    # Use FLASK_API_URL env var if set, else default to local or docker port
                    flask_api_base = os.environ.get("FLASK_API_URL")
                    if not flask_api_base:
                        # Default: 5050 for local, 9000 for Docker (can be improved with more checks)
                        flask_api_base = "http://127.0.0.1:5050" if os.environ.get("ENV", "local") == "local" else "http://127.0.0.1:9000"
                    api_url = f"{flask_api_base}/api/notify-work/{work.id}"
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
                        col1, col2, col3, col4 = st.columns([4, 3, 2, 1])
                        with col1:
                            edit_task_title = st.text_input("Task", value=task.title, key=f"task_title_{task.id}", help="Edit the task title.")
                        with col2:
                            status_options = ["Published", "Tracked", "Completed"]
                            status_index = status_options.index(task.status) if task.status in status_options else 0
                            edit_task_status = st.selectbox("Status", status_options, index=status_index, key=f"task_status_{task.id}", help="Update the task status.")
                        with col3:
                            if task.due_date:
                                edit_task_due_date = st.date_input("Due date", value=task.due_date, key=f"task_due_date_{task.id}", help="Edit the task due date.")
                            else:
                                edit_task_due_date = None
                                st.markdown("<b>Due date:</b> -", unsafe_allow_html=True)
                        with col4:
                            save_col, delete_col = st.columns([1,1])
                            with save_col:
                                if st.button("💾", key=f"save_task_{task.id}", help="Save changes to this task."):
                                    task.title = edit_task_title
                                    task.status = edit_task_status
                                    if edit_task_due_date is not None:
                                        task.due_date = edit_task_due_date
                                    db.commit()
                                    # Schedule calendar sync in background so Streamlit UI doesn't block on network/OAuth
                                    def _async_sync_calendar(task_id, work_title, status):
                                        # Worker will fetch a fresh DB session and task object, then perform calendar operations
                                        def _worker():
                                            try:
                                                from db import get_db, Task
                                                db_gen2 = get_db()
                                                db2 = next(db_gen2)
                                                try:
                                                    t = db2.query(Task).filter(Task.id == task_id).first()
                                                finally:
                                                    db2.close()
                                                if not t:
                                                    print(f"Async calendar sync: task {task_id} not found")
                                                    return
                                                agent = ReminderAgent()
                                                # If existing event, update it
                                                if t.calendar_event_id:
                                                    updated_data = {
                                                        'summary': f"{work_title}: {t.title}",
                                                        'description': getattr(t, 'description', None),
                                                    }
                                                    if t.due_date:
                                                        updated_data['start'] = {'dateTime': t.due_date.isoformat(), 'timeZone': 'Europe/London'}
                                                        updated_data['end'] = {'dateTime': (t.due_date + datetime.timedelta(hours=1)).isoformat(), 'timeZone': 'Europe/London'}
                                                    updated_data = {k: v for k, v in updated_data.items() if v is not None}
                                                    try:
                                                        agent.update_event(t.calendar_event_id, updated_data)
                                                    except Exception as e:
                                                        # If the event was deleted or not found remotely, create a new event and persist its id
                                                        err_str = str(e).lower()
                                                        print(f"Failed to update calendar event for task {task_id}: {e}")
                                                        if 'notfound' in err_str or '404' in err_str or 'not found' in err_str:
                                                            try:
                                                                new_ev = agent.create_event_for_task(t, work_title)
                                                                print(f"Recreated calendar event for task {task_id}: {new_ev.get('id')}")
                                                            except Exception as e2:
                                                                print(f"Failed to recreate calendar event for task {task_id}: {e2}")
                                                else:
                                                    # If status indicates it should be tracked, create an event
                                                    if status == 'Tracked' or (t.due_date and status == 'Published'):
                                                        try:
                                                            agent.create_event_for_task(t, work_title)
                                                        except Exception as e:
                                                            print(f"Failed to create calendar event for task {task_id}: {e}")
                                            except Exception as e:
                                                print(f"Async calendar sync failed for task {task_id}: {e}")
                                        threading.Thread(target=_worker, daemon=True).start()

                                    try:
                                        _async_sync_calendar(task.id, work.title, task.status)
                                    except Exception as e:
                                        print(f"Failed to start async calendar sync thread: {e}")
                                    # Immediately notify user; calendar work happens in background
                                    st.success("Task updated. Calendar sync scheduled in background.")
                            with delete_col:
                                if st.button("🗑️", key=f"delete_task_{task.id}", help="Delete this task."):
                                    # If task has a calendar event, delete it first
                                    try:
                                        if task.calendar_event_id:
                                            agent = ReminderAgent()
                                            agent.delete_event(task.calendar_event_id)
                                    except Exception as e:
                                        st.warning(f"Failed to delete calendar event: {e}")
                                    db.delete(task)
                                    db.commit()
                                    st.warning("Task deleted.")
                                    st.rerun()
