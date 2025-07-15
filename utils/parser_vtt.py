import webvtt

def parse_vtt_status(file_path):
    text = "\n".join([caption.text for caption in webvtt.read(file_path)])
    return {
        "parsed": {},
        "raw_text": text
    }
