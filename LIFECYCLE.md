Lifecycle of an Work/Task

* Create/Refine work/subtasks from the interface
* Submit to persist details in a table
* Add a action to 'schedule' to publish the work item, & create a calendar item for the first subtask
    -> Set appropriate status for Work & subtask item.
    Work - Draft, Published, Completed
    Task - Published, Tracked, Completed
* Track calendar event (CE) statuses & update database details appropriately. (schedule overnight batch)
    -> When CE is marked completed, update Task as 'Completed' and create calendar event for subsequent event. If there's no more Tasks, mark Work as 'Completed'
    -> When CE is 'snoozed' or not actioned on that day, send out a follow-up to fetch an update on the status, which could either lead to completion (above flow), or pushed to a later date. When pushed to a later date, update the same to the calendar event as well. Track snooze actions as a count in the table.
    -> When the calendar event is updated directly, copy those changes to the table (due date, title, description, snooze counter - if moved to a later date, completion, deletion)
* Similarly broadcast clean-up or changes with the Work/Task items to the calendar event - deletion, due dates/title/description/status updates. (schedule overnight batch)

Notification interactions (via Slack)
* Seek confirmation with the user for the due dates before 'publishing' the Work
* Send out a reminder at the start of the day (0600 Hrs) calling out planned events for the day. 
* Send out confirmation when the user completes a Work item. Read the table records for that work, and call out good stats or things that could be improved
* Send out notification when a calendar event was created or when it's been updated. Group alerts into one message when there's multiple changes on a Work item - like when a subtask is "completed" & next is changed "Tracked" & a calendar event created for it, or when the final subtask is marked "completed" and then the Work is also changed "completed".
* Seek updates to a Work item, when it's been snoozed over 3 times whether it's still relevant or if it needs to be broken up differently.