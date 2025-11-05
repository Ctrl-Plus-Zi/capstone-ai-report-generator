import json, os
import re 

def load_api_registry():
    with open("api_configs.json", "r", encoding="utf-8") as f:
        configs = json.load(f)

    return configs


def xml_to_dict(root, fields, filter_rules):
    dict = []
    for item in root.findall('.//item'):
        # 조건식 확인 
        result = {}

        for field in fields:
            result[field] = item.findtext(f'.//{field}') if item.findtext(f'.//{field}') else None
        
        if filter_field(result, filter_rules):
            dict.append(result)

    return dict


def filter_field(result, filter_rules):
    flag = False
    if filter_rules is None:
        return flag

    for filter_rule in filter_rules:

        field = filter_rule["field"]
        operator = filter_rule["operator"]
        value = filter_rule["value"]

        if operator == "==":
            if result[field] == value:
                flag = True

        elif operator == "!=":
            if result[field] != value:
                flag = True

        elif operator == "substring":
            if result[field] is None:
                continue
            else:
                if re.search(value, result[field]):
                    flag = True
    return flag

############################3

import requests
import xml.etree.ElementTree as ET
from pprint import pprint
from bs4 import BeautifulSoup

# API 레지스트리 로드
api_registry  = load_api_registry()

test_api_name = "KCISA_CCA_145"  #"KCISA_CCA_145"

config = api_registry[test_api_name]
f_rules = config["filter_rules"].copy()
f_rules[0]["value"] = "www.museum.go.kr"

response = requests.get(config["base_url"], params=config["default_params"])
root = ET.fromstring(response.text)

# 결과 코드 및 메시지
result_code = root.findtext('.//resultCode')
result_msg = root.findtext('.//resultMsg')
print("resultCode:", result_code)
print("resultMsg:", result_msg)


result_data = xml_to_dict(root, config["fields"], f_rules)
pprint(result_data)

'''
# KCISA API 기본 URL
url = "https://api.kcisa.kr/openapi/API_CCA_145/request"

# 요청 파라미터
params = {
    'serviceKey': "6f086938-b508-4d8c-9a89-5fe89d5de126",  
    'numOfRows': "100",
    'pageNo': "1"
}

#print(params)

# 요청 전송
response = requests.get(url, params=params)

# 상태 코드 확인
print("Status:", response.status_code)

# XML 파싱
#print(response.text)
root = ET.fromstring(response.text)
#print(root)

# 결과 코드 및 메시지
result_code = root.findtext('.//resultCode')
result_msg = root.findtext('.//resultMsg')
print("resultCode:", result_code)
print("resultMsg:", result_msg)

target_lst = []

# 아이템 반복
for item in root.findall('.//item'):
    url = item.findtext('URL')
    if "www.museum.go.kr" in url:
        html_desc = item.findtext('DESCRIPTION')
        soup = BeautifulSoup(html_desc, 'html.parser')

        target_lst.append({
            "related_organ": item.findtext('CNTC_INSTT_NM'),
            "title": item.findtext('TITLE'),
            "desc": soup.get_text(" ", strip=True),
            "period": item.findtext('PERIOD'),
            "notice": item.findtext('TABLE_OF_CONTENTS'),
            "url": item.findtext('URL')
        })

pprint(target_lst)
'''