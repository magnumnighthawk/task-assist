import streamlit as st
from generate import generate_subtasks

st.set_page_config(page_title="Task assist AI")  # Set the browser tab title

st.title("Task assist AI")

task_description = st.text_input("Enter a new task:")
max_subtasks = st.number_input("Enter the maximum number of subtasks:", min_value=1, step=1, value=5)

if st.button("Generate Subtasks"):
    subtasks = generate_subtasks(task_description, max_subtasks=max_subtasks)
    st.session_state.subtasks = subtasks
    st.session_state.edit_mode = [False] * len(subtasks)

if 'subtasks' in st.session_state:
    st.write("Generated Subtasks:")
    for i, subtask in enumerate(st.session_state.subtasks):
        col1, col2, col3, col4, col5 = st.columns([5, 1, 1, 1, 1])
        with col1:
            if st.session_state.edit_mode[i]:
                new_subtask = st.text_input(f"Subtask {i+1}", value=subtask, key=f"subtask_{i}")
                st.session_state.subtasks[i] = new_subtask
            else:
                st.write(f"{subtask}")
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

if st.button("Submit"):
    st.write("Subtasks submitted!")
