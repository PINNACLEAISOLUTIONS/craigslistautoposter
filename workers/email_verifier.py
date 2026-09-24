import imaplib
import email
import re
import time
from typing import Optional

class EmailVerifier:
    """
    Automated email verification listener based on alex1115alex/CraigslistBot.
    Polls IMAP inbox for Craigslist confirmation emails and extracts posting verification links.
    """
    def __init__(self, imap_server: str, email_user: str, email_pass: str):
        self.imap_server = imap_server
        self.email_user = email_user
        self.email_pass = email_pass

    def fetch_verification_link(self, max_wait_seconds: int = 120, poll_interval: int = 5) -> Optional[str]:
        """
        Polls IMAP inbox for unread Craigslist confirmation email and returns verification link.
        """
        start_time = time.time()
        print(f"[EmailVerifier] Polling {self.email_user} for Craigslist verification email...")

        link_regex = re.compile(r'https://post\.craigslist\.org/k/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+')

        while time.time() - start_time < max_wait_seconds:
            try:
                mail = imaplib.IMAP4_SSL(self.imap_server)
                mail.login(self.email_user, self.email_pass)
                mail.select("inbox")

                # Search recent emails from craigslist
                status, messages = mail.search(None, '(UNSEEN FROM "craigslist.org")')
                if status == "OK" and messages[0]:
                    email_ids = messages[0].split()
                    latest_id = email_ids[-1]

                    status, msg_data = mail.fetch(latest_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() in ("text/plain", "text/html"):
                                        body += part.get_payload(decode=True).decode(errors="ignore")
                            else:
                                body = msg.get_payload(decode=True).decode(errors="ignore")

                            match = link_regex.search(body)
                            if match:
                                verification_url = match.group(0)
                                print(f"[EmailVerifier] Found verification link: {verification_url}")
                                mail.logout()
                                return verification_url

                mail.logout()
            except Exception as e:
                print(f"[EmailVerifier] Polling error: {e}")

            time.sleep(poll_interval)

        print("[EmailVerifier] Timed out waiting for verification email.")
        return None
