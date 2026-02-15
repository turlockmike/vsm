#!/usr/bin/env python3
"""
Gmail Triage System — Cal Newport Deep Work Edition

Rule-based email classification and digest generation.
No LLM API calls — fast, free, token-efficient.
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple

try:
    from gmail_auth import get_gmail_service
except ImportError:
    from core.gmail_auth import get_gmail_service

# Path configuration
VSM_ROOT = Path(__file__).parent.parent
STATE_DIR = VSM_ROOT / 'state'
CONFIG_FILE = STATE_DIR / 'gmail_config.json'
TRIAGE_STATE_FILE = STATE_DIR / 'gmail_triage_state.json'

# Default configuration
DEFAULT_CONFIG = {
    "vip_contacts": [],
    "noise_domains": [
        "noreply@github.com",
        "notifications@github.com",
        "no-reply@github.com",
        "noreply@linkedin.com",
        "notifications@linkedin.com",
        "noreply@facebook.com",
        "notify@twitter.com",
        "notifications@twitter.com",
        "noreply@google.com",
        "noreply@medium.com",
        "newsletter@substack.com",
        "hello@substack.com",
        "noreply@youtube.com",
        "messages-noreply@linkedin.com",
        "jobalerts-noreply@linkedin.com",
        "no_reply@email.apple.com",
        "do-not-reply@slack.com",
        "feedback@slack.com",
        "no-reply@calendly.com",
        "calendar-notification@google.com",
        "notifications@reddit.com",
        "noreply@reddit.com",
        "automated@salesforce.com",
        "donotreply@salesforce.com",
    ],
    "noise_keywords": [
        "promotional",
        "newsletter",
        "marketing",
        "unsubscribe",
        "opt out",
        "manage preferences",
    ],
    "batch_times": ["09:00", "14:00", "17:00"],
    "auto_archive_noise": True,
    "auto_archive_fyi": False,
    "digest_email": None
}

# Gmail label names
LABELS = {
    "URGENT_IMPORTANT": "VSM/Urgent-Important",
    "IMPORTANT": "VSM/Important",
    "ACTIONABLE": "VSM/Actionable",
    "FYI": "VSM/FYI",
    "NOISE": "VSM/Noise"
}


def load_config():
    """Load or create configuration."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Merge with defaults for any missing keys
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    else:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save configuration."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def load_triage_state():
    """Load triage processing state."""
    if TRIAGE_STATE_FILE.exists():
        with open(TRIAGE_STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "last_scan": None,
        "processed_ids": [],
        "stats": {
            "total_processed": 0,
            "urgent": 0,
            "important": 0,
            "actionable": 0,
            "fyi": 0,
            "noise": 0
        }
    }


def save_triage_state(state):
    """Save triage processing state."""
    with open(TRIAGE_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_or_create_label(service, label_name):
    """Get label ID by name, creating if it doesn't exist."""
    # List existing labels
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    # Check if label exists
    for label in labels:
        if label['name'] == label_name:
            return label['id']

    # Create label
    label_object = {
        'name': label_name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show'
    }
    created = service.users().labels().create(userId='me', body=label_object).execute()
    return created['id']


def extract_email_address(email_str):
    """Extract email address from 'Name <email@domain.com>' format."""
    match = re.search(r'<(.+?)>', email_str)
    if match:
        return match.group(1).lower()
    return email_str.lower()


def get_domain(email):
    """Extract domain from email address."""
    if '@' in email:
        return email.split('@')[1].lower()
    return ''


def is_noise(msg_data, config):
    """Detect if email is noise (automated notifications, marketing)."""
    headers = {h['name'].lower(): h['value'] for h in msg_data['payload']['headers']}

    # Get sender
    from_addr = headers.get('from', '')
    sender_email = extract_email_address(from_addr)
    sender_domain = get_domain(sender_email)

    # Get body snippet
    snippet = msg_data.get('snippet', '').lower()

    # Check for noise signals
    noise_signals = [
        # No-reply addresses
        'noreply' in sender_email or 'no-reply' in sender_email or 'do-not-reply' in sender_email,
        'donotreply' in sender_email or 'no_reply' in sender_email,

        # Known noise domains
        sender_email in config['noise_domains'],
        any(sender_email.endswith('@' + domain.split('@')[1]) for domain in config['noise_domains'] if '@' in domain),

        # Unsubscribe header
        'list-unsubscribe' in headers,

        # Marketing keywords in snippet
        any(keyword in snippet for keyword in config['noise_keywords']),

        # Automated categories
        'CATEGORY_PROMOTIONS' in msg_data.get('labelIds', []),
        'CATEGORY_UPDATES' in msg_data.get('labelIds', []),
        'CATEGORY_FORUMS' in msg_data.get('labelIds', []),
    ]

    return any(noise_signals)


def is_fyi(msg_data, headers):
    """Detect if email is FYI (informational only)."""
    to_header = headers.get('to', '').lower()
    cc_header = headers.get('cc', '').lower()
    subject = headers.get('subject', '').lower()

    # Note: Getting actual user email is complex, so we use heuristics
    # User is likely CC'd if CC header exists and TO header has multiple recipients
    user_is_ccd = cc_header and '@' in cc_header

    fyi_signals = [
        user_is_ccd,
        'fyi' in subject,
        subject.startswith('re: re: re:'),  # Deep in thread
    ]

    return any(fyi_signals)


def is_urgent(msg_data, headers, config):
    """Detect urgent/important emails."""
    from_addr = headers.get('from', '')
    sender_email = extract_email_address(from_addr)
    subject = headers.get('subject', '').lower()
    snippet = msg_data.get('snippet', '').lower()

    # Check if from VIP
    is_vip = sender_email in config['vip_contacts']

    urgent_signals = [
        is_vip,
        'urgent' in subject and not is_noise(msg_data, config),
        'asap' in subject,
        'important' in subject and is_vip,
        # Reply to thread user started (has 'Re:' and 'In-Reply-To' header)
        subject.startswith('re:') and 'in-reply-to' in headers,
    ]

    return any(urgent_signals)


def is_important(msg_data, headers, config):
    """Detect important but not urgent emails."""
    from_addr = headers.get('from', '')
    sender_email = extract_email_address(from_addr)
    to_header = headers.get('to', '').lower()
    snippet = msg_data.get('snippet', '').lower()

    # Direct recipient (not CC'd)
    is_direct_recipient = to_header and not headers.get('cc')

    # Has a question
    has_question = '?' in snippet

    # Not automated
    not_automated = not is_noise(msg_data, config)

    # From a real person (heuristic: not in noise domains and not noreply)
    from_real_person = not any([
        'noreply' in sender_email,
        'no-reply' in sender_email,
        sender_email in config['noise_domains']
    ])

    important_signals = [
        is_direct_recipient and from_real_person and not_automated,
        has_question and from_real_person,
        'proposal' in snippet,
        'feedback' in snippet and from_real_person,
    ]

    return any(important_signals)


def classify_email(msg_data, config):
    """
    Classify email using rule-based logic.
    Returns: (category, confidence)
    """
    headers = {h['name'].lower(): h['value'] for h in msg_data['payload']['headers']}

    # Check in priority order
    if is_noise(msg_data, config):
        return 'NOISE', 0.9

    if is_fyi(msg_data, headers):
        return 'FYI', 0.7

    if is_urgent(msg_data, headers, config):
        return 'URGENT_IMPORTANT', 0.8

    if is_important(msg_data, headers, config):
        return 'IMPORTANT', 0.7

    # Default: actionable
    return 'ACTIONABLE', 0.6


def parse_email(msg_data):
    """Parse email data into structured format."""
    headers = {h['name'].lower(): h['value'] for h in msg_data['payload']['headers']}

    return {
        'id': msg_data['id'],
        'thread_id': msg_data['threadId'],
        'from': headers.get('from', 'Unknown'),
        'to': headers.get('to', ''),
        'subject': headers.get('subject', '(no subject)'),
        'date': headers.get('date', ''),
        'snippet': msg_data.get('snippet', '')[:150],
        'labels': msg_data.get('labelIds', [])
    }


def apply_label_and_archive(service, msg_id, category, config):
    """Apply category label and optionally archive."""
    label_name = LABELS.get(category)
    if not label_name:
        return

    # Get or create label
    label_id = get_or_create_label(service, label_name)

    # Apply label
    service.users().messages().modify(
        userId='me',
        id=msg_id,
        body={'addLabelIds': [label_id]}
    ).execute()

    # Archive if configured
    should_archive = (
        (category == 'NOISE' and config['auto_archive_noise']) or
        (category == 'FYI' and config['auto_archive_fyi'])
    )

    if should_archive:
        service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={'removeLabelIds': ['INBOX']}
        ).execute()


def scan_and_classify(service, config, max_results=50):
    """Scan inbox and classify unread emails."""
    # Get unread messages
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        q='is:unread',
        maxResults=max_results
    ).execute()

    messages = results.get('messages', [])

    if not messages:
        return []

    classified = []
    state = load_triage_state()

    for msg in messages:
        # Skip if already processed
        if msg['id'] in state['processed_ids']:
            continue

        # Get full message data
        msg_data = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()

        # Classify
        category, confidence = classify_email(msg_data, config)

        # Parse
        parsed = parse_email(msg_data)
        parsed['category'] = category
        parsed['confidence'] = confidence

        # Apply label and archive
        apply_label_and_archive(service, msg['id'], category, config)

        classified.append(parsed)

        # Update state
        state['processed_ids'].append(msg['id'])
        state['stats']['total_processed'] += 1
        state['stats'][category.lower()] += 1

    # Keep only last 1000 processed IDs to prevent unbounded growth
    state['processed_ids'] = state['processed_ids'][-1000:]
    state['last_scan'] = datetime.now().isoformat()
    save_triage_state(state)

    return classified


def generate_digest(classified_emails):
    """Generate a formatted digest of classified emails."""
    # Group by category
    by_category = defaultdict(list)
    for email in classified_emails:
        by_category[email['category']].append(email)

    # Build digest
    lines = []
    lines.append("=" * 70)
    lines.append(f"VSM Email Digest — {datetime.now().strftime('%b %d, %Y')}")
    lines.append("=" * 70)

    total = len(classified_emails)
    urgent = len(by_category['URGENT_IMPORTANT'])
    important = len(by_category['IMPORTANT'])
    actionable = len(by_category['ACTIONABLE'])
    fyi = len(by_category['FYI'])
    noise = len(by_category['NOISE'])

    lines.append(f"Total: {total} emails | {urgent} urgent | {important} important | {actionable} actionable | {fyi} fyi | {noise} noise")
    lines.append("")

    # Urgent section
    if by_category['URGENT_IMPORTANT']:
        lines.append("🔴 URGENT ({})".format(len(by_category['URGENT_IMPORTANT'])))
        for i, email in enumerate(by_category['URGENT_IMPORTANT'], 1):
            from_name = email['from'].split('<')[0].strip()
            lines.append(f"  {i}. [{from_name}] {email['subject']}")
        lines.append("")

    # Important section
    if by_category['IMPORTANT']:
        lines.append("🟡 IMPORTANT ({})".format(len(by_category['IMPORTANT'])))
        for i, email in enumerate(by_category['IMPORTANT'], 1):
            from_name = email['from'].split('<')[0].strip()
            subject = email['subject'][:60]
            lines.append(f"  {i}. [{from_name}] {subject}")
        lines.append("")

    # Actionable section
    if by_category['ACTIONABLE']:
        lines.append("📋 ACTIONABLE ({})".format(len(by_category['ACTIONABLE'])))
        for i, email in enumerate(by_category['ACTIONABLE'], 1):
            from_name = email['from'].split('<')[0].strip()
            subject = email['subject'][:60]
            lines.append(f"  {i}. [{from_name}] {subject}")
        lines.append("")

    # FYI section
    if by_category['FYI']:
        lines.append("📁 FYI (auto-archived: {})".format(len(by_category['FYI'])))
        sender_counts = defaultdict(int)
        for email in by_category['FYI']:
            from_addr = extract_email_address(email['from'])
            sender_counts[from_addr] += 1
        for sender, count in sorted(sender_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  - {sender}: {count} emails")
        lines.append("")

    # Noise section
    if by_category['NOISE']:
        lines.append("🗑️  NOISE (auto-archived: {})".format(len(by_category['NOISE'])))
        sender_counts = defaultdict(int)
        for email in by_category['NOISE']:
            from_addr = extract_email_address(email['from'])
            sender_counts[from_addr] += 1
        for sender, count in sorted(sender_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  - {sender}: {count} emails")
        lines.append("")

    # Suggestions
    if by_category['NOISE']:
        lines.append("💡 Suggestions:")
        sender_counts = defaultdict(int)
        for email in by_category['NOISE']:
            from_addr = extract_email_address(email['from'])
            sender_counts[from_addr] += 1

        # Find high-volume senders
        for sender, count in sorted(sender_counts.items(), key=lambda x: -x[1])[:3]:
            if count >= 3:
                lines.append(f"  - Consider filtering '{sender}' ({count} emails this scan)")

    lines.append("=" * 70)

    return "\n".join(lines)


def cmd_scan(args):
    """Scan inbox and classify emails."""
    try:
        config = load_config()
        service = get_gmail_service()

        print("Scanning inbox for unread emails...")
        classified = scan_and_classify(service, config, max_results=100)

        if not classified:
            print("No new unread emails to process.")
            return 0

        print(f"\nProcessed {len(classified)} emails:")
        by_category = defaultdict(int)
        for email in classified:
            by_category[email['category']] += 1

        for category in ['URGENT_IMPORTANT', 'IMPORTANT', 'ACTIONABLE', 'FYI', 'NOISE']:
            count = by_category[category]
            if count > 0:
                print(f"  {category}: {count}")

        print("\nDone! Run 'vsm email digest' to see the full digest.")
        return 0

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("\nRun 'vsm email setup' first to configure Gmail access.")
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_digest(args):
    """Generate and print daily digest."""
    try:
        config = load_config()
        service = get_gmail_service()

        # Scan first to get latest
        classified = scan_and_classify(service, config, max_results=100)

        if not classified:
            print("No new emails since last scan.")

            # Check state for recent activity
            state = load_triage_state()
            if state['last_scan']:
                print(f"Last scan: {state['last_scan']}")
                print(f"Total processed: {state['stats']['total_processed']}")
            return 0

        # Generate digest
        digest = generate_digest(classified)
        print(digest)

        return 0

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("\nRun 'vsm email setup' first to configure Gmail access.")
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_setup(args):
    """Run Gmail OAuth setup."""
    from gmail_auth import setup_oauth
    success = setup_oauth()
    return 0 if success else 1


def main():
    if len(sys.argv) < 2:
        print("Usage: gmail_triage.py <scan|digest|setup>")
        return 1

    command = sys.argv[1]

    if command == 'scan':
        return cmd_scan(None)
    elif command == 'digest':
        return cmd_digest(None)
    elif command == 'setup':
        return cmd_setup(None)
    else:
        print(f"Unknown command: {command}")
        print("Usage: gmail_triage.py <scan|digest|setup>")
        return 1


if __name__ == '__main__':
    sys.exit(main())
