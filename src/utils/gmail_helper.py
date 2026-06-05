"""
Gmail Helper - Monitor inbox for responses, detect interviews, offers, rejections
Uses Gmail API for automatic response tracking
"""

import logging
import base64
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import settings

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


class GmailHelper:
    """Monitor Gmail for job responses"""

    def __init__(self, credentials_file: str = "credentials/gmail_credentials.json"):
        self.service = None
        self.credentials_file = credentials_file
        self.response_indicators = {
            "interview": [
                "interview",
                "schedule",
                "call with",
                "speaking with",
                "moving forward",
                "next step",
            ],
            "offer": [
                "offer",
                "congratulations",
                "we're happy",
                "excited to extend",
                "start date",
            ],
            "rejection": [
                "reject",
                "not moving forward",
                "unsuccessful",
                "other candidate",
                "not the right fit",
                "appreciate your interest",
            ],
        }

    def authenticate(self) -> bool:
        """Authenticate with Gmail API"""

        try:
            creds = None
            import os
            import json

            # If credentials file missing but settings exist, create it
            if not os.path.exists(self.credentials_file) and settings.google_client_id:
                logger.info("Generating credentials file from environment variables...")
                os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
                creds_dict = {
                    "installed": {
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": ["http://localhost"]
                    }
                }
                with open(self.credentials_file, 'w') as f:
                    json.dump(creds_dict, f)

            # Try to load existing token
            token_file = "credentials/token.json"
            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file, SCOPES)

            # If no valid credentials, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_file):
                        raise Exception(f"Missing {self.credentials_file} and no environment variables set")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())

            # Build service
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("✅ Gmail authenticated")
            return True

        except Exception as e:
            logger.error(f"Error authenticating Gmail: {e}")
            return False

    def get_recent_emails(
        self,
        days: int = 7,
        from_addresses: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent emails from last N days

        Args:
            days: Number of days to look back
            from_addresses: Filter by sender addresses

        Returns:
            List of emails with parsed content
        """

        try:
            if not self.service:
                return []

            # Build query
            after_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y/%m/%d")
            query = f"after:{after_date}"

            if from_addresses:
                from_query = " OR ".join([f'from:{addr}' for addr in from_addresses])
                query += f" ({from_query})"

            # Get message IDs
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=50,
            ).execute()

            messages = results.get('messages', [])
            parsed_emails = []

            # Parse each message
            for msg in messages:
                parsed = self._parse_message(msg['id'])
                if parsed:
                    parsed_emails.append(parsed)

            logger.info(f"✅ Retrieved {len(parsed_emails)} recent emails")
            return parsed_emails

        except Exception as e:
            logger.error(f"Error getting recent emails: {e}")
            return []

    def detect_response_type(self, email_content: str) -> Optional[str]:
        """
        Detect if email is interview, offer, or rejection

        Returns: 'interview', 'offer', 'rejection', or None
        """

        content_lower = email_content.lower()

        # Check for keywords
        for response_type, keywords in self.response_indicators.items():
            if any(keyword in content_lower for keyword in keywords):
                return response_type

        return None

    def extract_recruiter_email(self, msg_id: str) -> Optional[str]:
        """Extract recruiter email address from message"""

        try:
            if not self.service:
                return None

            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='metadata',
                metadataHeaders=['From', 'Reply-To'],
            ).execute()

            headers = message['payload'].get('headers', [])

            for header in headers:
                if header['name'] in ['From', 'Reply-To']:
                    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                    match = re.search(email_pattern, header['value'])
                    if match:
                        return match.group(0)

            return None

        except Exception as e:
            logger.error(f"Error extracting recruiter email: {e}")
            return None

    def mark_as_processed(self, msg_id: str) -> bool:
        """Mark email as processed (add label)"""

        try:
            if not self.service:
                return False

            # Create label if not exists
            labels = self.service.users().labels().list(userId='me').execute()
            label_id = None

            for label in labels.get('labels', []):
                if label['name'] == 'JobApplications/Processed':
                    label_id = label['id']
                    break

            if not label_id:
                # Create new label
                label_body = {
                    'name': 'JobApplications/Processed',
                    'labelListVisibility': 'labelShow',
                    'messageListVisibility': 'show',
                }
                result = self.service.users().labels().create(
                    userId='me',
                    body=label_body,
                ).execute()
                label_id = result['id']

            # Apply label
            self.service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'addLabelIds': [label_id]},
            ).execute()

            return True

        except Exception as e:
            logger.error(f"Error marking email as processed: {e}")
            return False

    def _parse_message(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Parse individual email message"""

        try:
            if not self.service:
                return None

            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full',
            ).execute()

            # Extract headers
            headers = message['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            from_addr = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

            # Extract body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode()
                        break
            elif 'body' in message['payload']:
                body = base64.urlsafe_b64decode(
                    message['payload']['body'].get('data', '')
                ).decode()

            # Detect response type
            response_type = self.detect_response_type(body or subject)

            return {
                "message_id": msg_id,
                "subject": subject,
                "from": from_addr,
                "date": date,
                "body_preview": (body or "")[:200],
                "response_type": response_type,
            }

        except Exception as e:
            logger.error(f"Error parsing message {msg_id}: {e}")
            return None


# Singleton
gmail_helper = GmailHelper()
