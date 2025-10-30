Lifecycle of an Work/Task

1. Create/Refine work/subtasks from the interface

CREATE:
* Specify a brief description of what needs to be achieved, & get the tool to break it down to smaller maneagable sub-tasks. The user input can optionally include some form of indication with respect to "when they expect to finish the work", or "what's challenging about it", or "how smaller they expect to broken down", etc & the tool is expected to respond appropriately with (no. of tasks, due dates)

notes:
* This step needs to be aware of the current date/time to forecast the due dates

REFINE:
* The user can refine generated subtasks in a number of ways. They can change the order, assign/update any pre-defined attributes like due dates, priority, etc or pass a feedback to generate tasks differently

2. SUBMIT to persist details in a table, and initiate a chain of events in the system

SUBMISSION:
* should presist all of the details of work item
* should start the chain of events - 
    > get confirmation on the due-dates & other details via Slack notification. wait for a set time & publish otherwise on no reponse
    > add first sub-task as calendar event
    > schedule actions to "check user progress", "changes made to the calendar event - postpone, marked complete, snooze"

3. Publish the work item, & create a calendar event (CE) for the first subtask
    -> Set appropriate status for Work & subtask item.
    Work - Draft, Published, Completed
    Task - Published, Tracked, Completed

4. Track CE statuses & update database details appropriately. (schedule overnight batch)
    -> When CE is marked completed, update Task as 'Completed' and create CE for subsequent event. If there's no more Tasks, mark Work as 'Completed'
    -> When CE is 'snoozed' or not actioned on that day, send out a follow-up to fetch an update on the status, which could either lead to completion (above flow), or pushed to a later date. And when pushed to a later date, update CE. Track snooze actions as a count in the table.
    -> When the CE is updated directly, copy those changes to the table (due date, title, description, snooze counter - if moved to a later date, completion, deletion)

5. Similarly broadcast clean-up or changes with the Work/Task items to the calendar event - deletion, due dates/title/description/status updates. (schedule overnight batch)

Notification interactions (via Slack)
* Seek confirmation with the user for the due dates before 'publishing' the Work
* Send out a reminder at the start of the day (0600 Hrs) calling out planned events for the day. 
* Send out confirmation when the user completes a Work item. Read the table records for that work, and call out good stats or things that could be improved
* Send out notification when a calendar event was created or when it's been updated. Group alerts into one message when there's multiple changes on a Work item - like when a subtask is "completed" & next is changed "Tracked" & a calendar event created for it, or when the final subtask is marked "completed" and then the Work is also changed "completed".
* Seek updates to a Work item, when it's been snoozed over 3 times whether it's still relevant or if it needs to be broken up differently.