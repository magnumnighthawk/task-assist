import streamlit as st
from generate import generate_subtasks

st.title("AI-Powered Workflow Automation")

task_description = st.text_input("Enter a new task:")
if st.button("Generate Subtasks"):
    subtasks = generate_subtasks(task_description)
    st.write("Generated Subtasks:")
    for idx, subtask in enumerate(subtasks):
        st.write(f"{idx+1}. {subtask}")

# Further UI elements for marking tasks complete and scheduling reminders can be added.
