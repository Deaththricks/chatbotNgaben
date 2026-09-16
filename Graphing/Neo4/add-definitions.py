import json

def merge_data():
    # 1. Load your existing relations
    with open('relation_results_ngaben.normalized.json', 'r', encoding='utf-8') as f:
        existing_data = json.load(f)

    # 2. Load the 132 definitions
    with open('definitions.json', 'r', encoding='utf-8') as f:
        definitions = json.load(f)

    # 3. Format each definition into a LITERAL row and append it
    for item in definitions:
        literal_row = {
            "subject": item["name"],
            "subject_label": "Entity",
            "relation": "DEFINISI",
            "object": item["definition"],
            "object_type": "LITERAL",
            "source": "manual_injection"
        }
        existing_data.append(literal_row)

    # 4. Save everything to a brand new file so your original is untouched
    with open('relation_results_combined.json', 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=4, ensure_ascii=False)

    print(f"Success. Added {len(definitions)} definitions. Total rows: {len(existing_data)}.")

if __name__ == "__main__":
    merge_data()