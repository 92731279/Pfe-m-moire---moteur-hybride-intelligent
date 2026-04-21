import re
import pdfplumber
import pandas as pd
from typing import List, Dict, Any

from src.pipeline import run_pipeline

def extract_messages_from_pdf(pdf_path: str) -> List[str]:
    # Extract all text
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
                
    # Split text into SWIFT messages
    # A new message starts with :50K:, :50F:, :59:, or :59F:
    pattern = re.compile(r'(:(?:50K|50F|59K|59F|59):)', re.IGNORECASE)
    parts = pattern.split(text)
    
    messages = []
    # parts[0] is anything before the first tag
    for i in range(1, len(parts), 2):
        tag = parts[i]
        content = parts[i+1]
        msg = f"{tag}{content}".strip()
        if msg:
            # clean up multiple newlines that might cause issues if they aren't part of the msg
            messages.append(msg)
            
    return messages

def evaluate_messages(messages: List[str]) -> pd.DataFrame:
    results = []
    for i, raw_msg in enumerate(messages):
        msg_id = f"MSG_{i+1:03d}"
        print(f"Processing {msg_id} / {len(messages)}...")
        
        try:
            result, logger = run_pipeline(raw_msg, message_id=msg_id)
            meta = result.meta
            
            # Count valid lines contextually
            valid_address_lines = sum(1 for av in getattr(result, 'address_validation', []) if av.get('contextual_valid'))
            total_address_lines = len(getattr(result, 'address_lines', []))
            
            # SLM Fallback check using your e3 condition (usually confidence < 0.85)
            # You can also use needs_slm_fallback logic here if accessible
            needs_ia = meta.parse_confidence < 0.85
            
            row = {
                "ID": msg_id,
                "Type": result.field_type,
                "Party Name": " ".join(result.name) if getattr(result, "name", None) else "",
                "Confidence": meta.parse_confidence,
                "Country": getattr(result.country_town, "country", "") if getattr(result, "country_town", None) else "",
                "Town": getattr(result.country_town, "town", "") if getattr(result, "country_town", None) else "",
                "Addr Lines Valid": f"{valid_address_lines}/{total_address_lines}",
                "Needs AI (Ambiguous)": "YES" if needs_ia else "NO",
                "Warnings": " | ".join(meta.warnings),
                "Raw SWIFT": raw_msg
            }
            results.append(row)
        except Exception as e:
            print(f"Error on {msg_id}: {e}")
            results.append({
                "ID": msg_id,
                "Type": "ERROR",
                "Party Name": "",
                "Confidence": 0.0,
                "Country": "",
                "Town": "",
                "Addr Lines Valid": "0/0",
                "Needs AI (Ambiguous)": "ERROR",
                "Warnings": str(e),
                "Raw SWIFT": raw_msg
            })
            
    return pd.DataFrame(results)

if __name__ == "__main__":
    pdf_path = "data/des msgs reelles.pdf"
    print(f"Reading {pdf_path}...")
    msgs = extract_messages_from_pdf(pdf_path)
    print(f"Found {len(msgs)} messages.")
    
    df = evaluate_messages(msgs)
    
    # Analyze
    total = len(df)
    perfect = len(df[df["Confidence"] >= 0.85])
    ambiguous = total - perfect
    
    print("\n--- BENCHMARK RESULTS ---")
    print(f"Total Messages: {total}")
    print(f"Perfect Parse (>= 85%): {perfect} ({perfect/total * 100:.1f}%)")
    print(f"Sent to AI (< 85%): {ambiguous} ({ambiguous/total * 100:.1f}%)")
    
    out_path = "data/outputs/benchmark_report.xlsx"
    df.to_excel(out_path, index=False)
    print(f"\nReport generated at: {out_path}")
