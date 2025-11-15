"""
스텔라큐브 데이터 분석 스크립트
유동인구 데이터가 있는지 확인
"""
import sys
from pathlib import Path
import csv

# 프로젝트 루트 경로
project_root = Path(__file__).parent.parent.parent
data_path = project_root / "2025-09-30-stellarcube" / "sscard" / "api_mrcno_202408-202504" / "api_mrcno_202408-202504"

def analyze_csv_structure(file_path):
    """CSV 파일 구조 분석"""
    print(f"\n{'='*80}")
    print(f"파일 분석: {file_path.name}")
    print(f"{'='*80}\n")
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        print(f"컬럼 수: {len(headers)}")
        print(f"컬럼 목록: {', '.join(headers[:10])}...")
        
        # 샘플 데이터 확인
        rows = []
        for i, row in enumerate(reader):
            if i < 3:
                rows.append(row)
            if i >= 100:  # 처음 100개 행만 확인
                break
        
        print(f"\n총 확인한 행 수: {i+1}")
        
        # 국립현대미술관 관련 데이터 찾기
        f.seek(0)
        reader = csv.DictReader(f)
        mmca_count = 0
        mmca_samples = []
        for row in reader:
            if '국립현대미술관' in row.get('mrc_snbd_nm', ''):
                mmca_count += 1
                if len(mmca_samples) < 3:
                    mmca_samples.append(row)
        
        print(f"\n국립현대미술관 관련 행 수: {mmca_count}")
        if mmca_samples:
            print("\n국립현대미술관 샘플 데이터:")
            for i, sample in enumerate(mmca_samples, 1):
                print(f"\n[{i}]")
                print(f"  cri_ym: {sample.get('cri_ym')}")
                print(f"  mrcno: {sample.get('mrcno')}")
                print(f"  cutr_facl_id: {sample.get('cutr_facl_id')}")
                print(f"  mrc_snbd_nm: {sample.get('mrc_snbd_nm')}")
                print(f"  pct_20_male: {sample.get('pct_20_male')}")
                print(f"  pct_30_male: {sample.get('pct_30_male')}")
                print(f"  foreign_rt: {sample.get('foreign_rt')}")

def check_for_population_count(file_path):
    """실제 유동인구 수치가 있는지 확인"""
    print(f"\n{'='*80}")
    print("유동인구 수치 확인")
    print(f"{'='*80}\n")
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # 숫자형 컬럼 찾기
        numeric_cols = []
        sample_row = next(reader)
        for key, value in sample_row.items():
            try:
                float(value)
                if 'pct' not in key.lower() and 'rt' not in key.lower():
                    numeric_cols.append(key)
            except:
                pass
        
        print(f"비율이 아닌 숫자형 컬럼: {numeric_cols}")
        
        # 행 수가 유동인구 수를 나타내는지 확인
        f.seek(0)
        reader = csv.DictReader(f)
        total_rows = sum(1 for _ in reader)
        print(f"\n전체 행 수: {total_rows}")
        print("(참고: 각 행은 하나의 거래/방문을 나타낼 수 있음)")

if __name__ == "__main__":
    csv_file = data_path / "tb_sscard_api_mrcno_202408.csv"
    
    if csv_file.exists():
        analyze_csv_structure(csv_file)
        check_for_population_count(csv_file)
    else:
        print(f"파일을 찾을 수 없습니다: {csv_file}")

