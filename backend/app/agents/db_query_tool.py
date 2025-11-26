from typing import List, Dict, Optional, Any
from sqlalchemy import text, Table, MetaData, select, and_, or_, desc, asc
from sqlalchemy.orm import Session
import json


class DBQueryTool:
    """동적 DB 쿼리를 위한 도구 클래스"""
    
    def __init__(self, db: Session):
        self.db = db
        self.metadata = MetaData()
    
    def query(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        search_column: Optional[str] = None,
        search_value: Optional[str] = None,
        range_column: Optional[str] = None,
        range_start: Optional[Any] = None,
        range_end: Optional[Any] = None,
        order_by: Optional[str] = None,
        order_direction: str = "desc",
        limit: int = 100
    ) -> List[Dict]:
        """
        통합 쿼리 함수 (필터링 + LIKE 검색 + 범위 조건)
        
        Args:
            table_name: 조회할 테이블명
            columns: 조회할 컬럼 리스트 (None이면 전체)
            filters: 정확히 일치하는 필터 조건 (예: {"category": "박물관"})
            search_column: LIKE 검색할 컬럼명
            search_value: LIKE 검색 키워드
            range_column: 범위 조건 컬럼명
            range_start: 범위 시작값
            range_end: 범위 종료값
            order_by: 정렬 기준 컬럼명
            order_direction: 정렬 방향 ("asc" 또는 "desc")
            limit: 최대 조회 개수
        
        Returns:
            조회된 데이터 리스트 (딕셔너리 형태)
        """
        try:
            table = Table(table_name, self.metadata, autoload_with=self.db.bind)
            
            # 조회할 컬럼 선택
            if columns:
                select_cols = [table.c[col] for col in columns if col in table.c]
            else:
                select_cols = [table]
            
            query = select(*select_cols)
            
            # 조건 리스트
            conditions = []
            
            # 1. 정확한 일치 필터
            if filters:
                for key, value in filters.items():
                    if key in table.c:
                        # 배열인 경우 첫 번째 값만 사용 (LLM이 잘못 전달하는 경우 대응)
                        if isinstance(value, list) and len(value) > 0:
                            value = value[0]
                        conditions.append(table.c[key] == value)
            
            # 2. LIKE 검색 조건
            if search_column and search_value and search_column in table.c:
                conditions.append(table.c[search_column].ilike(f"%{search_value}%"))
            
            # 3. 범위 조건
            if range_column and range_column in table.c:
                if range_start is not None:
                    conditions.append(table.c[range_column] >= range_start)
                if range_end is not None:
                    conditions.append(table.c[range_column] <= range_end)
            
            # 조건 적용
            if conditions:
                query = query.where(and_(*conditions))
            
            # 정렬
            if order_by and order_by in table.c:
                if order_direction.lower() == "asc":
                    query = query.order_by(asc(table.c[order_by]))
                else:
                    query = query.order_by(desc(table.c[order_by]))
            
            # LIMIT
            query = query.limit(limit)
            
            # 실행
            result = self.db.execute(query)
            rows = result.fetchall()
            
            return [dict(row._mapping) for row in rows]
            
        except Exception as e:
            return [{"error": f"쿼리 실행 오류: {str(e)}"}]
    
    def aggregate_query(
        self,
        table_name: str,
        group_by_column: str,
        aggregate_column: str,
        aggregate_function: str = "count"
    ) -> List[Dict]:
        """
        집계 쿼리 (COUNT, SUM, AVG 등)
        
        Args:
            table_name: 조회할 테이블명
            group_by_column: 그룹화할 컬럼명
            aggregate_column: 집계할 컬럼명
            aggregate_function: 집계 함수 ("count", "sum", "avg", "max", "min")
        
        Returns:
            집계 결과 리스트
        """
        try:
            function_map = {
                "count": "COUNT",
                "sum": "SUM",
                "avg": "AVG",
                "max": "MAX",
                "min": "MIN"
            }
            
            func = function_map.get(aggregate_function.lower(), "COUNT")
            
            query = text(f"""
                SELECT {group_by_column}, {func}({aggregate_column}) as aggregate_value
                FROM {table_name}
                GROUP BY {group_by_column}
                ORDER BY aggregate_value DESC
            """)
            
            result = self.db.execute(query)
            rows = result.fetchall()
            
            return [
                {
                    group_by_column: row[0],
                    "aggregate_value": row[1]
                }
                for row in rows
            ]
            
        except Exception as e:
            return [{"error": f"집계 쿼리 실행 오류: {str(e)}"}]
    
    def raw_query(self, sql: str) -> List[Dict]:
        """
        Raw SQL 실행 (고급 사용자용)
        
        Args:
            sql: 실행할 SQL 쿼리
        
        Returns:
            쿼리 결과
        """
        try:
            result = self.db.execute(text(sql))
            rows = result.fetchall()
            
            if rows:
                columns = result.keys()
                return [dict(zip(columns, row)) for row in rows]
            
            return []
            
        except Exception as e:
            return [{"error": f"Raw SQL 실행 오류: {str(e)}"}]


def query_cultural_facility_data(
    table_name: str,
    search_column: Optional[str] = None,
    search_value: Optional[str] = None,
    columns: Optional[List[str]] = None,
    limit: int = 50,
    db: Session = None
) -> str:
    """
    데이터베이스 검색 함수 (LIKE 검색 지원)
    
    Args:
        table_name: 테이블명
        search_column: 검색할 컬럼명
        search_value: 검색값 (LIKE 검색으로 동작)
        columns: 조회할 컬럼 리스트 (None이면 전체)
        limit: 최대 조회 개수
        db: 데이터베이스 세션
    
    Returns:
        JSON 문자열 형태의 조회 결과
    """
    tool = DBQueryTool(db)
    
    result = tool.query(
        table_name=table_name,
        columns=columns,
        search_column=search_column,
        search_value=search_value,
        limit=limit
    )
    
    return json.dumps(result, ensure_ascii=False, default=str, indent=2)


def query_with_filters(
    table_name: str,
    filters: Dict[str, Any],
    columns: Optional[List[str]] = None,
    order_by: Optional[str] = None,
    limit: int = 50,
    db: Session = None
) -> str:
    """
    여러 조건으로 데이터를 필터링하여 조회
    
    Args:
        table_name: 테이블명
        filters: 필터 조건 딕셔너리 (예: {"category": "박물관", "year": 2024})
        columns: 조회할 컬럼 리스트
        order_by: 정렬 기준 컬럼
        limit: 최대 조회 개수
        db: 데이터베이스 세션
    
    Returns:
        JSON 문자열 형태의 조회 결과
    """
    tool = DBQueryTool(db)
    
    result = tool.query(
        table_name=table_name,
        columns=columns,
        filters=filters,
        order_by=order_by,
        limit=limit
    )
    
    return json.dumps(result, ensure_ascii=False, default=str, indent=2)


def query_with_range_and_search(
    table_name: str,
    search_column: Optional[str] = None,
    search_value: Optional[str] = None,
    range_column: Optional[str] = None,
    range_start: Optional[Any] = None,
    range_end: Optional[Any] = None,
    columns: Optional[List[str]] = None,
    order_by: Optional[str] = None,
    order_direction: str = "desc",
    limit: int = 100,
    db: Session = None
) -> str:
    """
    범위 조건 + 검색 조건을 동시에 적용하는 범용 쿼리
    
    Args:
        table_name: 테이블명
        search_column: LIKE 검색할 컬럼명
        search_value: LIKE 검색값
        range_column: 범위 조건 컬럼명 (예: year, created_at)
        range_start: 범위 시작값
        range_end: 범위 종료값 (None이면 range_start와 동일)
        columns: 조회할 컬럼 리스트
        order_by: 정렬 기준 컬럼
        order_direction: 정렬 방향
        limit: 최대 조회 개수
        db: 데이터베이스 세션
    
    Returns:
        JSON 문자열 형태의 조회 결과
    """
    tool = DBQueryTool(db)
    
    result = tool.query(
        table_name=table_name,
        columns=columns,
        search_column=search_column,
        search_value=search_value,
        range_column=range_column,
        range_start=range_start,
        range_end=range_end,
        order_by=order_by,
        order_direction=order_direction,
        limit=limit
    )
    
    return json.dumps(result, ensure_ascii=False, default=str, indent=2)


def get_aggregate_statistics(
    table_name: str,
    group_by: str,
    aggregate_column: str = "id",
    aggregate_function: str = "count",
    db: Session = None
) -> str:
    """
    집계 통계 조회
    
    Args:
        table_name: 테이블명
        group_by: 그룹화 기준 컬럼
        aggregate_column: 집계할 컬럼
        aggregate_function: 집계 함수 (count, sum, avg, max, min)
        db: 데이터베이스 세션
    
    Returns:
        JSON 문자열 형태의 집계 결과
    """
    tool = DBQueryTool(db)
    
    result = tool.aggregate_query(
        table_name=table_name,
        group_by_column=group_by,
        aggregate_column=aggregate_column,
        aggregate_function=aggregate_function
    )
    
    return json.dumps(result, ensure_ascii=False, default=str, indent=2)

