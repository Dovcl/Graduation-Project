// 시각화 페이지 메인 스크립트
// Leaflet 지도 및 Chart.js 시계열 차트 구현

// 전역 변수
let map = null;
let timeseriesChart = null;
let visualizationData = null;

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadVisualizationData();
});

// 이벤트 리스너 설정
function setupEventListeners() {
    // 탭 전환
    document.querySelectorAll('.viz-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            switchTab(tabName);
        });
    });

    // 채팅으로 돌아가기
    const backToChatBtn = document.getElementById('backToChatBtn');
    if (backToChatBtn) {
        backToChatBtn.addEventListener('click', () => {
            window.location.href = 'index.html';
        });
    }
}

// 탭 전환
function switchTab(tabName) {
    // 탭 버튼 활성화
    document.querySelectorAll('.viz-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // 패널 표시/숨김
    document.querySelectorAll('.viz-panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === `${tabName}Panel`);
    });

    // 탭별 초기화
    if (tabName === 'map' && !map) {
        initMap();
    } else if (tabName === 'map' && map) {
        // 지도 크기 조정 (탭 전환 시 필요)
        setTimeout(() => {
            map.invalidateSize();
        }, 100);
    } else if (tabName === 'timeseries' && !timeseriesChart) {
        initTimeseriesChart();
    }
}

// sessionStorage에서 시각화 데이터 로드
function loadVisualizationData() {
    const stored = sessionStorage.getItem('visualizationData');
    console.log('sessionStorage에서 로드 시도:', stored ? '데이터 있음' : '데이터 없음');
    
    if (stored) {
        try {
            visualizationData = JSON.parse(stored);
            console.log('시각화 데이터 파싱 완료:', visualizationData);
            console.log('map_points:', visualizationData.map_points);
            console.log('timeseries:', visualizationData.timeseries);
            console.log('query_context:', visualizationData.query_context);
            
            // 데이터 유효성 검사
            if (!visualizationData) {
                console.warn('시각화 데이터가 null입니다.');
                showNoDataMessage();
                return;
            }
            
            const hasMapPoints = visualizationData.map_points && visualizationData.map_points.length > 0;
            const hasTimeseries = visualizationData.timeseries && 
                                 (visualizationData.timeseries.labels && visualizationData.timeseries.labels.length > 0);
            
            console.log('데이터 유효성:', { hasMapPoints, hasTimeseries });
            
            if (!hasMapPoints && !hasTimeseries) {
                console.warn('시각화 데이터가 비어있습니다. (map_points와 timeseries 모두 없음)');
                showNoDataMessage();
                return;
            }
            
            renderVisualizations();
        } catch (e) {
            console.error('시각화 데이터 파싱 실패:', e);
            console.error('원본 데이터:', stored);
            showNoDataMessage();
        }
    } else {
        console.log('sessionStorage에 시각화 데이터가 없습니다.');
        console.log('채팅에서 예측 질문을 먼저 수행해주세요.');
        showNoDataMessage();
    }
}

// 시각화 데이터 렌더링
function renderVisualizations() {
    if (!visualizationData) {
        showNoDataMessage();
        return;
    }

    // 지도 렌더링
    if (visualizationData.map_points && visualizationData.map_points.length > 0) {
        renderMap();
    }

    // 시계열 차트 렌더링
    if (visualizationData.timeseries) {
        renderTimeseriesChart();
    }

    // 정보 업데이트
    updateVisualizationInfo();
}

// 지도 초기화 및 렌더링
function initMap() {
    // Leaflet 지도 생성 (한국 중심)
    map = L.map('mapContainer', {
        center: [36.5, 127.5],  // 한국 중심 좌표
        zoom: 8,
        zoomControl: true
    });

    // 타일 레이어 추가 (OpenStreetMap)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    // GeoJSON 레이어 로드
    loadGeoJSONLayers();
}

// GeoJSON 레이어 로드
async function loadGeoJSONLayers() {
    try {
        // 유역 경계선 로드
        const watershedResponse = await fetch('/static/data/watershed.geojson');
        if (watershedResponse.ok) {
            const watershedData = await watershedResponse.json();
            L.geoJSON(watershedData, {
                style: {
                    fillColor: '#888',
                    fillOpacity: 0.1,
                    color: '#666',
                    weight: 1
                }
            }).addTo(map);
        }

        // 하천망 로드
        const riversResponse = await fetch('/static/data/rivers.geojson');
        if (riversResponse.ok) {
            const riversData = await riversResponse.json();
            L.geoJSON(riversData, {
                style: {
                    color: '#4A90E2',
                    weight: 1,
                    opacity: 0.6
                }
            }).addTo(map);
        }
    } catch (e) {
        console.warn('GeoJSON 로드 실패 (정적 파일이 없을 수 있음):', e);
    }
}

// 지도에 예측 포인트 렌더링
function renderMap() {
    if (!map) {
        initMap();
    }

    // 기존 마커 제거
    map.eachLayer(layer => {
        if (layer instanceof L.CircleMarker || layer instanceof L.Marker) {
            map.removeLayer(layer);
        }
    });

    const mapPoints = visualizationData.map_points || [];
    if (mapPoints.length === 0) {
        console.warn('지도 포인트 데이터가 없습니다.');
        return;
    }
    
    console.log('지도 포인트 렌더링:', mapPoints);

    // 값 범위 계산 (컬러바용)
    const values = mapPoints.map(p => p.value).filter(v => v !== null && v !== undefined);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);

    // 컬러바 생성
    renderColorbar(minValue, maxValue);

    // 설명 표시
    const mapPointDesc = document.getElementById('mapPointDescription');
    if (mapPointDesc) {
        mapPointDesc.style.display = 'inline';
    }

    // 포인트 추가
    mapPoints.forEach(point => {
        if (!point.lat || !point.lng) {
            console.warn('좌표가 없는 포인트:', point);
            return;
        }

        const color = getColorByValue(point.value, minValue, maxValue);
        const radius = 10;  // 크기 증가

        const marker = L.circleMarker([point.lat, point.lng], {
            radius: radius,
            fillColor: color,
            color: '#fff',
            weight: 2,
            fillOpacity: 0.9
        }).addTo(map);

        // 팝업 추가
        const popupContent = `
            <div class="map-popup">
                <strong>${point.name || point.site_id}</strong><br>
                <hr style="margin: 0.5rem 0;">
                <strong>예측값:</strong><br>
                ${visualizationData.query_context?.variable || '유해남조류 세포수'}: 
                ${point.value !== null && point.value !== undefined ? point.value.toFixed(2) : 'N/A'} 
                ${visualizationData.query_context?.unit || 'cells/㎖'}
            </div>
        `;
        marker.bindPopup(popupContent);
        
        // 마커 클릭 시 팝업 자동 열기
        marker.openPopup();

        // 지도 범위 조정
        if (mapPoints.length === 1) {
            map.setView([point.lat, point.lng], 11);  // 줌 레벨 증가
        } else {
            const bounds = L.latLngBounds(mapPoints.map(p => [p.lat, p.lng]));
            map.fitBounds(bounds, { padding: [50, 50] });
        }
    });
}

// 값에 따른 색상 계산 (Viridis 색상 스케일)
function getColorByValue(value, minValue, maxValue) {
    if (value === null || value === undefined) return '#999';
    
    // 정규화 (0-1)
    const normalized = (value - minValue) / (maxValue - minValue);
    
    // Viridis 색상 스케일 (간단한 버전)
    // 실제로는 더 정교한 색상 스케일 사용 가능
    if (normalized < 0.25) {
        return '#440154';  // 어두운 보라
    } else if (normalized < 0.5) {
        return '#31688e';  // 파랑
    } else if (normalized < 0.75) {
        return '#35b779';  // 초록
    } else {
        return '#fde725';  // 노랑
    }
}

// 컬러바 렌더링
function renderColorbar(minValue, maxValue) {
    const legend = document.getElementById('colorbarLegend');
    if (!legend) return;

    const steps = 10;
    const stepSize = (maxValue - minValue) / steps;
    
    let html = '<div class="colorbar-title">유해남조류 세포수 (cells/㎖)</div>';
    html += '<div class="colorbar-gradient">';
    
    for (let i = 0; i <= steps; i++) {
        const value = minValue + (stepSize * i);
        const color = getColorByValue(value, minValue, maxValue);
        html += `<div class="colorbar-step" style="background-color: ${color}"></div>`;
    }
    
    html += '</div>';
    html += `<div class="colorbar-labels">
        <span>${minValue.toFixed(0)}</span>
        <span>${maxValue.toFixed(0)}</span>
    </div>`;
    
    legend.innerHTML = html;
}

// 시계열 차트 초기화 및 렌더링
function initTimeseriesChart() {
    const ctx = document.getElementById('timeseriesChart');
    if (!ctx) return;

    timeseriesChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: []
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: '날짜'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: '유해남조류 세포수 (cells/㎖)'
                    }
                }
            }
        }
    });
}

function renderTimeseriesChart() {
    if (!timeseriesChart) {
        initTimeseriesChart();
    }

    const timeseries = visualizationData.timeseries;
    if (!timeseries) {
        console.warn('시계열 데이터가 없습니다.');
        return;
    }

    console.log('시계열 데이터:', timeseries);

    // 날짜 포맷팅 (YYYY-MM-DD → MM/DD)
    const labels = timeseries.labels.map(dateStr => {
        try {
            const date = new Date(dateStr);
            if (isNaN(date.getTime())) {
                // ISO 형식이 아닐 경우 그대로 사용
                return dateStr.split('T')[0].substring(5).replace('-', '/');
            }
            return `${date.getMonth() + 1}/${date.getDate()}`;
        } catch (e) {
            return dateStr;
        }
    });

    // 관측값과 예측값 필터링 (null 제거하지 않고 그대로 사용)
    const observedData = timeseries.observed || [];
    const predictedData = timeseries.predicted || [];

    console.log('관측값 개수:', observedData.filter(v => v !== null && v !== undefined).length);
    console.log('예측값 개수:', predictedData.filter(v => v !== null && v !== undefined).length);

    timeseriesChart.data.labels = labels;
    timeseriesChart.data.datasets = [
        {
            label: '관측값',
            data: observedData,
            borderColor: '#4A90E2',
            backgroundColor: 'rgba(74, 144, 226, 0.1)',
            tension: 0.4,
            pointRadius: 3,
            pointHoverRadius: 5,
            spanGaps: false  // null 값 사이의 선 연결 안 함
        },
        {
            label: '예측값',
            data: predictedData,
            borderColor: '#F5A623',
            backgroundColor: 'rgba(245, 166, 35, 0.1)',
            borderDash: [5, 5],
            tension: 0.4,
            pointRadius: 4,
            pointHoverRadius: 6,
            pointStyle: 'circle',
            spanGaps: false
        }
    ];

    timeseriesChart.update();
}

// 시각화 정보 업데이트
function updateVisualizationInfo() {
    const queryContext = visualizationData.query_context;
    if (!queryContext) {
        console.warn('쿼리 컨텍스트가 없습니다.');
        return;
    }

    // 지도 정보
    const mapLocation = document.getElementById('mapLocation');
    const mapDate = document.getElementById('mapDate');
    if (mapLocation) mapLocation.textContent = queryContext.site_name || queryContext.site_id || '-';
    if (mapDate) {
        const period = queryContext.period || {};
        // 날짜 포맷팅 (YYYY-MM-DD -> YYYY/MM/DD)
        const endDate = period.end || '';
        if (endDate) {
            const formatted = endDate.split('T')[0].replace(/-/g, '/');
            mapDate.textContent = formatted;
        } else {
            mapDate.textContent = '-';
        }
    }

    // 시계열 정보
    const timeseriesLocation = document.getElementById('timeseriesLocation');
    if (timeseriesLocation) {
        timeseriesLocation.textContent = queryContext.site_name || queryContext.site_id || '-';
    }
}

// 데이터 없음 메시지 표시
function showNoDataMessage() {
    const noDataMessage = document.getElementById('noDataMessage');
    const vizContent = document.querySelector('.viz-content');
    
    if (noDataMessage) noDataMessage.style.display = 'block';
    if (vizContent) vizContent.style.display = 'none';
}

