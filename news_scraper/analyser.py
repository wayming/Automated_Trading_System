import os
import requests
import json
import re
from bs4 import BeautifulSoup

# === CONFIG ===
API_KEY = os.getenv("DEEPSEEK_API_KEY")
API_URL = "https://api.deepseek.com/v1/chat/completions"  # or the correct endpoint

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# === FUNCTIONS ===

def extract_article_info(file):
    with open(file, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    title_tag = soup.find('h1', class_='title-KX2tCBZq')
    title = title_tag.text.strip() if title_tag else "Title not found"

    content_div = soup.find('div', class_='body-KX2tCBZq')
    if content_div:
        paragraphs = content_div.find_all('p')
        content = "\n".join(p.get_text(strip=True) for p in paragraphs)
    else:
        content = "Content not found"

    return {
        "title": title,
        "content": content
    }

def send_to_deepseek(prompt_text):
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.7
    }

    response = requests.post(API_URL, headers=HEADERS, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        raise Exception(f"Request failed: {response.status_code} - {response.text}")

def extract_response_struct(response, delim='---'):
    # Create a regex pattern that matches lines with at least N hyphens
    delim_pattern = rf'^-{{{3},}}$'  # Matches lines with 3+ hyphens
    
    # Extract the content between delimiters
    pattern = rf'{delim_pattern}(.*?){delim_pattern}'
    match = re.search(pattern, response, re.DOTALL | re.MULTILINE)
    
    if not match:
        print(f"JSON block not found for response {response}")
        return None
    
    # Get the JSON text and clean it
    json_text = match.group(1).strip()
    
    # Remove single-line comments (lines starting with #)
    json_cleaned = re.sub(r'#.*', '', json_text)  # Remove everything after #
    json_cleaned = re.sub(r'//.*', '', json_cleaned)  # Remove everything after //
    json_cleaned = re.sub(r'^\s*#.*$', '', json_cleaned, flags=re.MULTILINE)  # Clean any remaining    

    # Parse the JSON
    try:
        return json.loads(json_cleaned)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}\nCleaned JSON:\n{json_cleaned}")
        return None

def run_pipeline(html_path, prompt_path):
    article = extract_article_info(html_path)

    with open(prompt_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    full_prompt = (
        f"{base_prompt}\n\n"
        f"---\n\n"
        f"Title: {article['title']}\n\n"
        f"Content:\n{article['content']}"
    )

    response = send_to_deepseek(full_prompt)

    # Extract structured response
    result = extract_response_struct(response)
    
    # Write raw response to .resp file
    output_dir = os.path.dirname(html_path)
    base_name = os.path.splitext(os.path.basename(html_path))[0]
    resp_path = os.path.join(output_dir, f"{base_name}.resp")
    
    with open(resp_path, "w", encoding="utf-8") as f:
        f.write(response)
    
    return result

# === RUN SCRIPT ===
def main():
    try:
        # Run the pipeline
        result = run_pipeline(
            "output/UBS_Adjusts_Price_Target_on_O'Reilly_Automotive_to_$1_580_From_$1_535__Maintains_Buy_Rating.html",
            "prompt.txt"
        )
        
        print("DeepSeek Response:\n")
        print(json.dumps(result, indent=2, ensure_ascii=False))  # Pretty print JSON
        
        # Check short term score if analysis exists
        if 'analysis' in result and 'short_term' in result['analysis']:
            try:
                # Extract numeric value from [+30] format
                score_str = result['analysis']['short_term']['score']
                score = int(re.search(r'[+-]?\d+', score_str).group())
                
                if score > 10:
                    print(f"\nPositive Signal for {result.get('stock_name', 'Unknown')}")
                    print(f"Short Term Score: {score}")
            except (ValueError, AttributeError, KeyError):
                print("\nCould not parse score value")
        else:
            print("\nNo short_term analysis available")
            
    except Exception as e:
        print(f"\nError in pipeline execution: {str(e)}")