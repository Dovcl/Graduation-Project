"""
Shapefile을 GeoJSON으로 변환하는 스크립트
유역 경계선과 하천망을 GeoJSON 형식으로 변환하여 프론트엔드에서 사용
"""
import geopandas as gpd
from pathlib import Path
import json

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent
SHAPEFILE_DIR = PROJECT_ROOT.parent / "졸논. 녹조예측 주단위" / "Data" / "visualization"
OUTPUT_DIR = PROJECT_ROOT / "frontend" / "static" / "data"

# 출력 디렉토리 생성
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def convert_watershed_to_geojson():
    """유역 경계선 Shapefile을 GeoJSON으로 변환"""
    print("🔄 유역 경계선 변환 중...")
    
    # 주요 유역 경계선 (WKMBBSN.shp - 중소유역)
    watershed_path = SHAPEFILE_DIR / "수자원단위지도_KRF" / "WKMBBSN.shp"
    
    if not watershed_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {watershed_path}")
        return False
    
    try:
        # Shapefile 읽기
        gdf = gpd.read_file(watershed_path)
        
        # 좌표계 확인 및 변환 (EPSG:4326 = WGS84 위경도)
        if gdf.crs is None:
            print("⚠️ 좌표계 정보가 없습니다. EPSG:4326로 가정합니다.")
            gdf.set_crs("EPSG:4326", inplace=True)
        elif gdf.crs.to_string() != "EPSG:4326":
            print(f"🔄 좌표계 변환 중: {gdf.crs} → EPSG:4326")
            gdf = gdf.to_crs("EPSG:4326")
        
        # 지오메트리 단순화 (파일 크기 줄이기)
        # tolerance: 작을수록 정확하지만 파일 크기가 큼 (0.001 = 약 100m)
        print("📐 지오메트리 단순화 중...")
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.001, preserve_topology=True)
        
        # GeoJSON으로 저장
        output_path = OUTPUT_DIR / "watershed.geojson"
        gdf.to_file(output_path, driver="GeoJSON")
        
        file_size = output_path.stat().st_size / (1024 * 1024)  # MB
        print(f"✅ 유역 경계선 변환 완료: {output_path} ({file_size:.2f} MB)")
        print(f"   - 레코드 수: {len(gdf)}")
        return True
    
    except Exception as e:
        print(f"❌ 유역 경계선 변환 실패: {e}")
        return False


def convert_rivers_to_geojson():
    """하천망 Shapefile을 GeoJSON으로 변환"""
    print("\n🔄 하천망 변환 중...")
    
    # 하천 파일들 (국가 및 지방하천)
    river_files = [
        ("W_NATL.shp", "국가 및 지방하천/W_NATL.shp"),  # 국가하천
        ("W_FRST.shp", "국가 및 지방하천/W_FRST.shp"),  # 1급 하천
        ("W_SCND.shp", "국가 및 지방하천/W_SCND.shp"),  # 2급 하천
    ]
    
    all_rivers = []
    
    for filename, rel_path in river_files:
        river_path = SHAPEFILE_DIR / rel_path
        
        if not river_path.exists():
            print(f"⚠️ 파일을 찾을 수 없습니다: {river_path}")
            continue
        
        try:
            # Shapefile 읽기
            gdf = gpd.read_file(river_path)
            
            # 좌표계 변환
            if gdf.crs is None:
                gdf.set_crs("EPSG:4326", inplace=True)
            elif gdf.crs.to_string() != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            
            # 지오메트리 단순화 (하천은 더 작은 tolerance 사용)
            gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.0005, preserve_topology=True)
            
            # 타입 정보 추가
            river_type = filename.replace(".shp", "").replace("W_", "")
            gdf['river_type'] = river_type
            
            all_rivers.append(gdf)
            print(f"   ✓ {filename} 로드 완료 ({len(gdf)} 레코드)")
        
        except Exception as e:
            print(f"   ❌ {filename} 변환 실패: {e}")
    
    if not all_rivers:
        print("❌ 하천 파일을 찾을 수 없습니다.")
        return False
    
    # 모든 하천 병합
    print("🔗 하천 데이터 병합 중...")
    merged_rivers = gpd.GeoDataFrame(gpd.pd.concat(all_rivers, ignore_index=True))
    
    # GeoJSON으로 저장
    output_path = OUTPUT_DIR / "rivers.geojson"
    merged_rivers.to_file(output_path, driver="GeoJSON")
    
    file_size = output_path.stat().st_size / (1024 * 1024)  # MB
    print(f"✅ 하천망 변환 완료: {output_path} ({file_size:.2f} MB)")
    print(f"   - 총 레코드 수: {len(merged_rivers)}")
    return True


def main():
    """메인 함수"""
    print("=" * 60)
    print("Shapefile → GeoJSON 변환 스크립트")
    print("=" * 60)
    
    # 유역 경계선 변환
    watershed_success = convert_watershed_to_geojson()
    
    # 하천망 변환
    rivers_success = convert_rivers_to_geojson()
    
    print("\n" + "=" * 60)
    if watershed_success and rivers_success:
        print("✅ 모든 변환 완료!")
        print(f"\n출력 디렉토리: {OUTPUT_DIR}")
        print("   - watershed.geojson (유역 경계선)")
        print("   - rivers.geojson (하천망)")
    else:
        print("⚠️ 일부 변환 실패")
    print("=" * 60)


if __name__ == "__main__":
    main()

