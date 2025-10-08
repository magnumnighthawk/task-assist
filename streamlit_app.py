
import streamlit as st
from generate import generate_subtasks, revise_subtasks
from reminder import ReminderAgent
import datetime

st.set_page_config(page_title="Task assist AI", page_icon="favicon.png")  # Set the browser tab title

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
        subtasks = generate_subtasks(task_description, max_subtasks=max_subtasks)
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
        col1, col2, col3, col4, col5, col6 = st.columns([5, 1, 1, 1, 1, 2])
        with col1:
            if st.session_state.edit_mode[i]:
                new_subtask = st.text_input(f"Subtask {i+1}", value=subtask['description'], key=f"subtask_{i}")
                st.session_state.subtasks[i]['description'] = new_subtask
            else:
                priority_color = get_priority_color(subtask['priority'])
                st.markdown(
                    f"{subtask['description']} <span style='background-color:{priority_color}; padding: 2px 4px; border-radius: 4px; margin-left: 8px;'>{subtask['priority']}</span>",
                    unsafe_allow_html=True
                )
        with col2:
            if st.session_state.edit_mode[i]:
                if st.button("💾", key=f"save_{i}"):
                    st.session_state.edit_mode[i] = False
                    st.rerun()
                if st.button("❌", key=f"discard_{i}"):
                    st.session_state.edit_mode[i] = False
                    st.rerun()
            else:
                if st.button("✏️", key=f"edit_{i}"):
                    st.session_state.edit_mode[i] = True
                    st.rerun()
        with col3:
            if st.button("🗑️", key=f"delete_{i}"):
                st.session_state.subtasks.pop(i)
                st.session_state.edit_mode.pop(i)
                st.session_state.subtask_due_dates.pop(i)
                st.rerun()
        with col4:
            if st.button("⬆️", key=f"up_{i}") and i > 0:
                st.session_state.subtasks[i], st.session_state.subtasks[i-1] = st.session_state.subtasks[i-1], st.session_state.subtasks[i]
                st.session_state.edit_mode[i], st.session_state.edit_mode[i-1] = st.session_state.edit_mode[i-1], st.session_state.edit_mode[i]
                st.session_state.subtask_due_dates[i], st.session_state.subtask_due_dates[i-1] = st.session_state.subtask_due_dates[i-1], st.session_state.subtask_due_dates[i]
                st.rerun()
        with col5:
            if st.button("⬇️", key=f"down_{i}") and i < len(st.session_state.subtasks) - 1:
                st.session_state.subtasks[i], st.session_state.subtasks[i+1] = st.session_state.subtasks[i+1], st.session_state.subtasks[i]
                st.session_state.edit_mode[i], st.session_state.edit_mode[i+1] = st.session_state.edit_mode[i+1], st.session_state.edit_mode[i]
                st.session_state.subtask_due_dates[i], st.session_state.subtask_due_dates[i+1] = st.session_state.subtask_due_dates[i+1], st.session_state.subtask_due_dates[i]
                st.rerun()
        with col6:
            # Per-subtask due date input and schedule button
            due_date = st.date_input(f"Due date for subtask {i+1}", value=st.session_state.subtask_due_dates[i] or datetime.date.today(), key=f"due_date_{i}")
            st.session_state.subtask_due_dates[i] = due_date
            schedule_key = f"loading_schedule_{i}"
            if schedule_key not in st.session_state:
                st.session_state[schedule_key] = False
            if st.session_state[schedule_key]:
                with st.spinner("Scheduling event..."):
                    pass
            if st.button("Schedule", key=f"schedule_{i}"):
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

     # --- Revise Subtasks UI ---
    
    st.markdown("**Revise Subtasks**")
    feedback = st.text_area("Describe how you want to revise or break down the subtasks (specify which if needed):", key="revise_feedback")

    if 'loading_revise' not in st.session_state:
        st.session_state.loading_revise = False
    if st.session_state.loading_revise:
        with st.spinner("Revising subtasks..."):
            pass
    if st.button("Revise Subtasks"):
        st.session_state.loading_revise = True
        with st.spinner("Revising subtasks..."):
            revised = revise_subtasks(st.session_state.subtasks, feedback, max_subtasks=len(st.session_state.subtasks))
            print('REVISED SUBTASKS:', revised)
            st.session_state.subtasks = revised
            st.session_state.edit_mode = [False] * len(revised)
            st.session_state.subtask_due_dates = [None] * len(revised)
        st.success("Subtasks revised.")
        st.session_state.loading_revise = False
        # Instead of clearing st.session_state["revise_feedback"], rerun to reset the widget
        st.rerun()