import imaplib
import email
from email.header import decode_header
import re
import time
from typing import Optional

class IMAPVerificationParser:
    """
    Polls an IMAP mailbox for automated Craigslist confirmation/activation links.
    """
    def __init__(self, host: str, user: str, password: str, port: int = 993):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def _extract_body_text(self, msg: email.message.Message) -> str:
        """Extracts text/plain or text/html payload from multipart MIME emails."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type in ("text/plain", "text/html") and "attachment" not in content_disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body += payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
        return body

    def poll_for_link(
        self,
        sender_domain: str = "craigslist.org",
        link_regex_pattern: str = r"https://post\.craigslist\.org/k/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+",
        timeout_seconds: int = 120,
        poll_interval_seconds: int = 6
    ) -> Optional[str]:
        """
        Continuously polls the inbox until a matching verification URL is found or timeout occurs.
        """
        regex = re.compile(link_regex_pattern)
        start_time = time.time()

        print(f"[IMAP] Connecting to {self.host} for user {self.user}...")

        while time.time() - start_time < timeout_seconds:
            client: Optional[imaplib.IMAP4_SSL] = None
            try:
                client = imaplib.IMAP4_SSL(self.host, self.port)
                client.login(self.user, self.password)
                client.select("INBOX")

                # Search unread messages from craigslist
                search_query = f'(UNSEEN FROM "{sender_domain}")'
                status, data = client.search(None, search_query)

                if status == "OK" and data[0]:
                    email_ids = data[0].split()
                    latest_id = email_ids[-1]

                    res, msg_data = client.fetch(latest_id, "(RFC822)")
                    if res == "OK":
                        for part in msg_data:
                            if isinstance(part, tuple):
                                raw_email = part[1]
                                msg = email.message_from_bytes(raw_email)
                                body_content = self._extract_body_text(msg)

                                match = regex.search(body_content)
                                if match:
                                    found_url = match.group(0)
                                    print(f"[IMAP] Verification link identified: {found_url}")
                                    return found_url

            except Exception as e:
                print(f"[IMAP] Notice during polling cycle: {e}")
            finally:
                if client:
                    try:
                        client.close()
                        client.logout()
                    except Exception:
                        pass

            time.sleep(poll_interval_seconds)

        print("[IMAP] Polling finished without locating verification email.")
        return None

# Backward compatibility alias
EmailVerifier = IMAPVerificationParser
