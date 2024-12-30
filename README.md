I created a simple python script to sync Gmail attachments to Seafile. The script does the following

1. Pulls emails from Gmail from a specific folder (currently it is Inbox, you can change it)
2. Then if the email has a pdf attachment it will upload it to Seafile
3. Then it will mark the email with a label as "Processed" (you can change it) so that next time it skips that email.
4. Once the script is completed, it will send an email with the logs.

**NOTE**: it pulls passwords and repo id from environment variables so you might need to add them.

Requirements:
- App password from Gmail
- Seafile Creds and Repo id
- SMTP Details
