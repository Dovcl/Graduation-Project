"""
녹조-수질 지점 매칭 테이블을 DB에 저장하는 스크립트
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 설정
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

# .env 파일 로드
from dotenv import load_dotenv
env_path = project_root / "backend" / ".env"
load_dotenv(env_path)

from sqlalchemy import text, Column, Integer, String, Float
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db, Base, engine


# 매칭 테이블 모델 정의
class LocationMapping(Base):
    """녹조-수질 지점 매칭 테이블"""
    __tablename__ = "location_mapping"

    id = Column(Integer, primary_key=True, index=True)
    algae_location = Column(String(100), nullable=False, unique=True, index=True)  # 녹조 지점 (cyanohab)
    wq_location = Column(String(100), nullable=False, index=True)  # 수질 지점 (WQ_TOTAL)
    region = Column(String(50))  # 수계 (한강, 금강, 낙동강, 영산강)
    latitude = Column(Float)  # 수질 지점 위도
    longitude = Column(Float)  # 수질 지점 경도


def main():
    print("="*60)
    print("녹조-수질 지점 매칭 테이블 생성")
    print("="*60)

    # 테이블 생성
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # 기존 데이터 삭제
        db.execute(text("DELETE FROM location_mapping"))
        db.commit()
        print("기존 매칭 데이터 삭제 완료")

        # 최종 매칭 테이블 (확정)
        mappings = [
            # 한강 수계
            {"algae": "한강_이천", "wq": "강천", "region": "한강", "lat": 37.272528, "lon": 127.686917},
            {"algae": "강천보_강천", "wq": "강천", "region": "한강", "lat": 37.272528, "lon": 127.686917},
            {"algae": "여주보_대신", "wq": "대신", "region": "한강", "lat": 37.322444, "lon": 127.613250},
            {"algae": "이포보_이포", "wq": "이포", "region": "한강", "lat": 37.398083, "lon": 127.541389},
            {"algae": "한강_미사대교", "wq": "구의", "region": "한강", "lat": 37.539900, "lon": 127.115800},
            {"algae": "한강_강동대교", "wq": "구의", "region": "한강", "lat": 37.539900, "lon": 127.115800},
            {"algae": "한강_광진교", "wq": "구의", "region": "한강", "lat": 37.539900, "lon": 127.115800},
            {"algae": "한강_잠실철교", "wq": "구의", "region": "한강", "lat": 37.539900, "lon": 127.115800},
            {"algae": "한강_성수대교", "wq": "노량진", "region": "한강", "lat": 37.515000, "lon": 126.960800},
            {"algae": "한강_한남대교", "wq": "노량진", "region": "한강", "lat": 37.515000, "lon": 126.960800},
            {"algae": "한강_한강대교", "wq": "노량진", "region": "한강", "lat": 37.515000, "lon": 126.960800},
            {"algae": "한강_마포대교", "wq": "노량진", "region": "한강", "lat": 37.515000, "lon": 126.960800},
            {"algae": "한강_성산대교", "wq": "노량진", "region": "한강", "lat": 37.515000, "lon": 126.960800},
            {"algae": "팔당호_댐앞", "wq": "팔당댐2", "region": "한강", "lat": 37.521042, "lon": 127.285281},
            {"algae": "팔당호_부용사앞", "wq": "팔당댐3", "region": "한강", "lat": 37.526428, "lon": 127.367633},
            {"algae": "팔당호_삼봉", "wq": "삼봉리", "region": "한강", "lat": 37.594167, "lon": 127.341306},
            {"algae": "충주호_댐앞", "wq": "충주댐1", "region": "한강", "lat": 37.000700, "lon": 127.996497},

            # 금강 수계
            {"algae": "세종보_연기", "wq": "연기", "region": "금강", "lat": 36.477981, "lon": 127.270967},
            {"algae": "공주보_금강", "wq": "금강", "region": "금강", "lat": 36.485278, "lon": 127.100039},
            {"algae": "백제보_부여", "wq": "부여", "region": "금강", "lat": 36.318061, "lon": 126.938331},
            {"algae": "대청호_문의", "wq": "대청댐3", "region": "금강", "lat": 36.512000, "lon": 127.506611},
            {"algae": "대청호_추동", "wq": "대청댐1", "region": "금강", "lat": 36.371111, "lon": 127.495556},
            {"algae": "대청호_회남", "wq": "대청댐5", "region": "금강", "lat": 36.433111, "lon": 127.552583},

            # 영산강 수계
            {"algae": "승촌보_광산", "wq": "광산", "region": "영산강", "lat": 35.101667, "lon": 126.776136},
            {"algae": "죽산보_죽산", "wq": "죽산", "region": "영산강", "lat": 35.001667, "lon": 126.632778},

            # 낙동강 수계
            {"algae": "상주보_도남", "wq": "도남", "region": "낙동강", "lat": 36.430861, "lon": 128.251442},
            {"algae": "낙단보_낙단", "wq": "낙단", "region": "낙동강", "lat": 36.357822, "lon": 128.307767},
            {"algae": "구미보_선산", "wq": "선산", "region": "낙동강", "lat": 36.233919, "lon": 128.347911},
            {"algae": "낙동강_해평", "wq": "강정", "region": "낙동강", "lat": 36.191700, "lon": 128.366600},
            {"algae": "칠곡보_칠곡", "wq": "칠곡", "region": "낙동강", "lat": 36.018556, "lon": 128.397822},
            {"algae": "강정고령보_다사", "wq": "성주", "region": "낙동강", "lat": 35.878500, "lon": 128.391200},
            {"algae": "낙동강_강정·고령", "wq": "다사", "region": "낙동강", "lat": 35.842731, "lon": 128.456936},
            {"algae": "달성보_논공", "wq": "논공", "region": "낙동강", "lat": 35.735806, "lon": 128.414022},
            {"algae": "합천창녕보_덕곡", "wq": "덕곡", "region": "낙동강", "lat": 35.593367, "lon": 128.355500},
            {"algae": "낙동강_칠서", "wq": "남지", "region": "낙동강", "lat": 35.402200, "lon": 128.473700},
            {"algae": "창녕함안보_함안", "wq": "함안", "region": "낙동강", "lat": 35.380631, "lon": 128.548783},
            {"algae": "낙동강_물금·매리", "wq": "물금", "region": "낙동강", "lat": 35.315300, "lon": 128.972200},
            {"algae": "진양호_내동", "wq": "남강댐1", "region": "낙동강", "lat": 35.168000, "lon": 128.031639},
            {"algae": "진양호_판문", "wq": "남강댐1", "region": "낙동강", "lat": 35.168000, "lon": 128.031639},
        ]

        # 데이터 삽입
        for m in mappings:
            mapping = LocationMapping(
                algae_location=m["algae"],
                wq_location=m["wq"],
                region=m["region"],
                latitude=m["lat"],
                longitude=m["lon"]
            )
            db.add(mapping)

        db.commit()
        print(f"\n✓ {len(mappings)}개 매칭 데이터 저장 완료")

        # 결과 확인
        print("\n" + "="*60)
        print("[저장된 매칭 테이블]")
        print("="*60)

        result = db.execute(text("""
            SELECT region, algae_location, wq_location
            FROM location_mapping
            ORDER BY region, algae_location
        """))

        current_region = None
        for row in result:
            if row.region != current_region:
                current_region = row.region
                print(f"\n[{current_region}]")
            print(f"  {row.algae_location:<25} → {row.wq_location}")

        print(f"\n✅ 완료!")

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    main()
