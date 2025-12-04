# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from model import run_pipeline, PipelineResult  # 기존 코드 파일명
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
import boto3
import json
import time
from datetime import datetime
from decimal import Decimal
from auth import get_current_user_sub
from database import get_db, User
from model import run_pipeline, PipelineResult
import uuid

dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
route_table = dynamodb.Table('inha-capstone-11-nosql')

def float_to_decimal(data):
    return json.loads(json.dumps(data), parse_float=Decimal)
app = FastAPI(title="Safe Routing API")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

load_dotenv()

class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    hour: str = "now"


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/calculate-route")
def calculate_route(
        req: RouteRequest
        # sub: str = Depends(get_current_user_sub),  <-- [주석 처리] 토큰 검증 안 함
        # db: Session = Depends(get_db)              <-- [주석 처리] DB 연결 안 함
):
    # ---------------------------------------------------------
    # [테스트 모드] 인증 로직 우회 및 매직 넘버 설정
    # ---------------------------------------------------------

    # user = db.query(User).filter(User.sub == sub).first() <-- [주석 처리]
    # if not user:
    #     raise HTTPException(status_code=404, detail="User not found in RDS")

    internal_user_id = 99999

    print(f"⚠️ [TEST MODE] 인증 없이 테스트 ID({internal_user_id})로 실행합니다.")

    # ---------------------------------------------------------

    try:
        # 4. 경로 계산 (기존 로직)
        result: PipelineResult = run_pipeline(
            start_lat=req.start_lat,
            start_lon=req.start_lon,
            end_lat=req.end_lat,
            end_lon=req.end_lon,
            hour=req.hour,
            app_key=os.getenv("TMAP_APP_KEY"),
            cctv_path="./cctv_data.xlsx",
            model_path="./edge_pref_model_dataset.json"
        )

        response_data = {
            "base_route": result.base_route,
            "rerouted": result.rerouted,
            "base_weight": result.base_weight,
            "rerouted_weight": result.rerouted_weight
        }

        # 5. DynamoDB에 저장
        item = {
            "route_id": str(uuid.uuid4()),
            "user_id": str(internal_user_id),  # Partition Key (99999가 들어감)
            "timestamp": int(time.time()),  # Sort Key
            "created_at": datetime.now().isoformat(),
            "start_point": {"lat": Decimal(str(req.start_lat)), "lon": Decimal(str(req.start_lon))},
            "end_point": {"lat": Decimal(str(req.end_lat)), "lon": Decimal(str(req.end_lon))},
            "route_data": float_to_decimal(response_data)  # 경로 데이터 저장
        }

        route_table.put_item(Item=item)

        return response_data

    except Exception as e:
        logger.error(f"Error processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))