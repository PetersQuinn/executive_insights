import email
from email import policy

def parse_email_status(file_path):
    with open(file_path, 'rb') as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    text = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                text += part.get_payload(decode=True).decode(errors='ignore')
    else:
        text = msg.get_payload(decode=True).decode(errors='ignore')
    return {
        "parsed": {},
        "raw_text": text
    }