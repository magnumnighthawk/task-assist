import streamlit as st
from generate import generate_subtasks

st.title("AI-Powered Workflow Automation")

task_description = st.text_input("Enter a new task:")
if st.button("Generate Subtasks"):
    subtasks = generate_subtasks(task_description)
    st.write("Generated Subtasks:")
    for subtask in subtasks:
        st.write(f"{subtask}")

# Further UI elements for marking tasks complete and scheduling reminders can be added.
