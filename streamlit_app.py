
import streamlit as st
from generate import generate_subtasks
from reminder import ReminderAgent
import datetime

st.set_page_config(page_title="Task assist AI", page_icon="favicon.png")  # Set the browser tab title

st.title("Task assist AI")

task_description = st.text_input("Enter a new task:")
max_subtasks = st.number_input("Enter the maximum number of subtasks:", min_value=1, step=1, value=5)

if st.button("Generate Subtasks"):
    subtasks = generate_subtasks(task_description, max_subtasks=max_subtasks)
    st.session_state.subtasks = subtasks
    st.session_state.edit_mode = [False] * len(subtasks)

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
    for i, subtask in enumerate(st.session_state.subtasks):
        col1, col2, col3, col4, col5 = st.columns([5, 1, 1, 1, 1])
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
                st.rerun()
        with col4:
            if st.button("⬆️", key=f"up_{i}") and i > 0:
                st.session_state.subtasks[i], st.session_state.subtasks[i-1] = st.session_state.subtasks[i-1], st.session_state.subtasks[i]
                st.session_state.edit_mode[i], st.session_state.edit_mode[i-1] = st.session_state.edit_mode[i-1], st.session_state.edit_mode[i]
                st.rerun()
        with col5:
            if st.button("⬇️", key=f"down_{i}") and i < len(st.session_state.subtasks) - 1:
                st.session_state.subtasks[i], st.session_state.subtasks[i+1] = st.session_state.subtasks[i+1], st.session_state.subtasks[i]
                st.session_state.edit_mode[i], st.session_state.edit_mode[i+1] = st.session_state.edit_mode[i+1], st.session_state.edit_mode[i]
                st.rerun()


# Step 1: Capture due date for the work item
if 'subtasks' in st.session_state and st.session_state.get('subtasks'):
    due_date = st.date_input("Select due date for the work item:")
    if st.button("Save Subtasks and Schedule First Event"):
        # Step 2: Save subtasks (in session state for now)
        st.session_state.saved_subtasks = st.session_state.subtasks.copy()
        st.session_state.saved_due_date = due_date

        # Step 3: Calculate event date for first subtask
        num_subtasks = len(st.session_state.subtasks)
        if num_subtasks > 0:
            # Distribute subtasks evenly up to due date
            today = datetime.date.today()
            days_total = (due_date - today).days
            if days_total < num_subtasks:
                days_total = num_subtasks  # Avoid negative/zero division
            days_per_subtask = days_total // num_subtasks
            first_event_date = today + datetime.timedelta(days=days_per_subtask)
            first_event_datetime = datetime.datetime.combine(first_event_date, datetime.time(8, 0))
            # Use due date for last subtask if only one
            if num_subtasks == 1:
                first_event_datetime = datetime.datetime.combine(due_date, datetime.time(8, 0))

            # Step 4: Create calendar event for first subtask
            agent = ReminderAgent()
            first_subtask = st.session_state.subtasks[0]
            summary = first_subtask['description']
            start_time = first_event_datetime.isoformat()
            end_time = (first_event_datetime + datetime.timedelta(hours=1)).isoformat()
            try:
                event = agent.create_event(summary, start_time, end_time, description=f"Auto-scheduled by Task Assist. Priority: {first_subtask['priority']}")
                st.success(f"Calendar event created for first subtask: {summary}")
                st.write(f"Event link: {event.get('htmlLink')}")
            except Exception as e:
                st.error(f"Failed to create calendar event: {e}")
        else:
            st.warning("No subtasks to schedule.")
