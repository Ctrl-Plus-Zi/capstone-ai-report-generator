import requests
import json

BASE_URL = "http://localhost:8000"

def test_advanced_report():
    url = f"{BASE_URL}/report/advanced"
    
    payload = {
        "organization_name": "국립중앙박물관",
        "report_topic": "2030 세대의 관람객 유입을 위한 이벤트 기획",
        "questions": [
            "국립중앙박물관의 최근 전시 정보를 조사해주세요.",
            "박물관의 대표 소장품을 조사해주세요.",
            "2030 세대의 관람객 유입을 위한 이벤트 기획에 대해 분석해주세요."
        ]
    }
    
    print("Sending request to advanced report API...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        
        print("=" * 80)
        print("Response received successfully!")
        print("=" * 80)
        print()
        print(f"Report ID: {result['id']}")
        print(f"Organization: {result['organization_name']}")
        print(f"Topic: {result['report_topic']}")
        print()
        print("-" * 80)
        print("Research Sources:")
        print("-" * 80)
        for i, source in enumerate(result['research_sources'], 1):
            print(f"{i}. {source}")
        print()
        print("-" * 80)
        print("Analysis Summary:")
        print("-" * 80)
        print(result['analysis_summary'])
        print()
        print("-" * 80)
        print("Final Report:")
        print("-" * 80)
        print(result['final_report'])
        print()
        print("=" * 80)
        print(f"Generated at: {result['generated_at']}")
        print("=" * 80)
        
    except requests.exceptions.Timeout:
        print("Error: Request timed out (max 300 seconds)")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")


if __name__ == "__main__":
    test_advanced_report()

