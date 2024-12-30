import imaplib
import email
import os
import re
import os
import requests
import logging
import smtplib
from email.header import decode_header
from email.utils import parsedate_to_datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Seafile API credentials
SEAFILE_URL = "https://custom.seafile.com"  # Change to your Seafile server URL
SEAFILE_USERNAME = "seafile_username"  # Change to your Seafile User
SEAFILE_PASSWORD = os.environ['SEAFILE_PASSWORD'] 
REPO_ID = os.environ["REPO_ID"]

# Your email credentials
EMAIL = "username@gmail.com"
PASSWORD = os.environ['EMAIL_PASSWORD']

# Email configuration for sending reports
REPORT_SENDER = "sender@email.com"
REPORT_RECEIVER = "receiver@email.com"
SMTP_SERVER = "SMTP_PASSWORD"
SMTP_PORT = 587
SMTP_USERNAME = "STMP_USER"
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]

# Configure logging to a file
LOG_FILE = "fetch_attachments.txt"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def send_report(processed_count):
    try:
        subject = f"Fetch Attachments Report - {processed_count} Emails Processed"
        body = f"The script processed {processed_count} emails. See the attached log file for details."
        
        msg = MIMEMultipart()
        msg["From"] = REPORT_SENDER
        msg["To"] = REPORT_RECEIVER
        msg["Subject"] = subject
        
        msg.attach(MIMEText(body, "plain"))
        
        with open(LOG_FILE, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(LOG_FILE)}"
        )
        msg.attach(part)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(REPORT_SENDER, REPORT_RECEIVER, msg.as_string())
        
        logging.info(f"Report sent to {REPORT_RECEIVER}.")
    except Exception as e:
        logging.error(f"Failed to send report: {e}")

def connect_to_gmail():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL, PASSWORD)
        logging.info("Connected to Gmail.")
        return mail
    except Exception as e:
        logging.error(f"Failed to connect to Gmail: {e}")
        raise

def add_label(mail, email_id, label):
    try:
        mail.store(email_id, '+X-GM-LABELS', label)
        logging.info(f"Label '{label}' added to email ID {email_id}.")
    except Exception as e:
        logging.error(f"Failed to add label: {e}")

def has_label(mail, email_id, label):
    try:
        status, response = mail.fetch(email_id, '(X-GM-LABELS)')
        if status != "OK":
            logging.warning(f"Failed to fetch labels for email ID: {email_id}")
            return False
        for response_part in response:
            if isinstance(response_part, bytes):
                labels_data = response_part.decode('utf-8')
                return label in labels_data
    except Exception as e:
        logging.error(f"Failed to check label: {e}")
        return False

def get_seafile_token():
    login_data = {'username': SEAFILE_USERNAME, 'password': SEAFILE_PASSWORD}
    try:
        response = requests.post(f"{SEAFILE_URL}/api2/auth-token/", data=login_data)
        if response.status_code == 200:
            logging.info("Generated Seafile token successfully.")
            return response.json().get('token')
        logging.error("Failed to generate Seafile token.")
        return None
    except Exception as e:
        logging.error(f"Error generating Seafile token: {e}")
        return None

def generate_upload_link(token, path):
    headers = {'Authorization': f'Token {token}'}
    url = f"{SEAFILE_URL}/api2/repos/{REPO_ID}/upload-link/?p={path}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            logging.info(f"Generated upload link for path {path}.")
            return response.text.strip().strip('"')
        logging.error(f"Failed to generate upload link: {response.status_code}")
        return None
    except Exception as e:
        logging.error(f"Error generating upload link: {e}")
        return None

def upload_file(token, file_path):
    try:
        with open(file_path, "rb") as f:

            # Determine directory based on filename content.
            # Directories should already be created.

            if "policy" in file_path.lower():
                upload_link = generate_upload_link(token, f"%2fPolicy%2f")
                files = {"file": f, "filename": os.path.basename(file_path), "parent_dir": (None, "/Policy"), "replace": (None, "0")}
            elif "invoice" in file_path.lower():
                upload_link = generate_upload_link(token, f"%2finvoice%2f")
                files = {"file": f, "filename": os.path.basename(file_path), "parent_dir": (None, "/Invoice"), "replace": (None, "0")}
            else:
                upload_link = generate_upload_link(token, f"%2f")
                files = {"file": f, "filename": os.path.basename(file_path), "parent_dir": (None, "/"), "replace": (None, "0")}

            if not upload_link:
                logging.error("Upload link could not be generated.")
                return False

            response = requests.post(upload_link, files=files)
            if response.status_code == 200:
                logging.info(f"Uploaded file {file_path} successfully.")
                return True
            logging.error(f"Failed to upload file: {file_path} - Status Code: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"Failed to upload file: {e}")
        return False

# folder is from where you want to pull the emails.
# processed_label will be the label the email will be marked with once it has been analyzed. Make sure the label exists in Gmail.
def fetch_attachments(folder="Inbox", processed_label="Processed"):
    mail = connect_to_gmail()
    mail.select(folder)

    status, messages = mail.search(None, 'ALL')
    if status != "OK":
        logging.warning("No messages found!")
        return

    token = get_seafile_token()
    if not token:
        return

    processed_count = 0

    for num in messages[0].split():
        try:
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                logging.error(f"Failed to fetch message {num}")
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")

                    sanitized_subject = re.sub(r'[<>:"/\\|?*]', '_', subject or "No_Subject")
                    if has_label(mail, num, processed_label):
                        logging.info(f"Email '{sanitized_subject}' already processed. Skipping.")
                        continue

                    for part in msg.walk():
                        if part.get_content_disposition() == "attachment":
                            filename = part.get_filename()
                            if filename and filename.endswith(".pdf"):
                                file_path = os.path.join("/tmp", filename)
                                with open(file_path, "wb") as f:
                                    f.write(part.get_payload(decode=True))
                                upload_file(token, file_path)
                                os.remove(file_path)

                    logging.info(f"Marking email '{sanitized_subject}' as processed.")
                    add_label(mail, num, processed_label)
                    processed_count += 1
        except Exception as e:
            logging.error(f"Error processing email ID {num}: {e}")

    mail.logout()
    send_report(processed_count)
    os.remove("fetch_attachments.txt")


if __name__ == "__main__":
    fetch_attachments()
