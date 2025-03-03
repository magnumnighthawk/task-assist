# Task Assist

Task Assist is an AI-powered workflow automation application designed to help you manage tasks and reminders with a multi-agent architecture. This project leverages Python, OpenAI, Langchain, Google Calendar API, and additional tools to provide a simple yet extensible solution for automating business workflows.

## Overview

Task Assist automates the process of breaking down high-level tasks, assigning them, verifying their completion, and scheduling reminders. The system is composed of four primary agents:

- **Task Generator Agent:** Uses NLP via OpenAI and Langchain to decompose tasks into actionable subtasks.
- **Execution Agent:** Manages the assignment and tracking of subtasks.
- **Verification Agent:** Confirms task completion through manual or automated checks.
- **Reminder Agent:** Integrates with Google Calendar to schedule task deadlines and reminders.

This modular design allows for a simple MVP that can be easily extended with more features in future iterations.

## Features

- **Task Decomposition:** Leverages OpenAI's API to break down complex tasks.
- **Task Assignment & Tracking:** Uses a simple execution module to manage task status.
- **Task Verification:** Provides a basic mechanism to confirm task completion.
- **Google Calendar Integration:** Schedules reminders and deadlines using the Google Calendar API.
- **User Interfaces:** Interact via terminal inputs or a simple UI built with Streamlit.
- **Local Development:** Designed to run on a MacBook using free-tier services and local resources.
- **Future Enhancements:** Plans to integrate vector databases (e.g., FAISS) for semantic search and enhanced data persistence.

## Tech Stack

- **Language:** Python
- **Libraries & Tools:**
  - `python-dotenv` for managing environment variables
  - `langchain-openai` for NLP and task decomposition
  - `langchain-community` for managing language model prompts and flows
  - `streamlit` for building a simple web-based UI
  - `google-api-python-client` and `google-auth` for Google Calendar integration
  - `faiss-cpu` (planned for future enhancements)
- **Optional Tools:**
  - Docker for containerization
  - SQLite or JSON files for local data persistence

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/task-assist.git
   cd task-assist
   ```

2. **Create and Activate a Virtual Environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install the Required Packages:**

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. **Environment Variables:**
   - Copy `.env.sample` to `.env` and update the API keys and other configurations as needed.

2. **Google Calendar Integration:**
   - Follow Google’s documentation to set up OAuth credentials.
   - Save your OAuth token as `token.pickle` in the project root directory.

## Usage

### Terminal-Based Interface

Run the main script to interact with Task Assist through the terminal:

```bash
python execute_and_verify.py
```

### Streamlit UI

For a web-based interface, run the following command:

```bash
streamlit run streamlit_app.py
```

## Future Enhancements

- **Vector Database Integration:** Use FAISS for advanced semantic search and task similarity matching.
- **Improved UI/UX:** Enhance the dashboard and user interface for a better experience.
- **Asynchronous Task Management:** Implement Celery or a similar framework for improved scalability.
- **Automated Verification:** Develop rule-based or ML-driven methods for task verification.

## Contributing

Contributions are welcome! Please fork the repository and submit pull requests with your changes. For significant modifications, open an issue to discuss your ideas beforehand.

Happy Task Managing with Task Assist!
