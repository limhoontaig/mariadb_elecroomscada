# excel_report.py
import shutil
import sys
import os
import zipfile
import re
from datetime import datetime, timedelta
import openpyxl
# 💡 핵심 개선: 이제 복잡한 내부 SQL 처리는 전부 db_manager가 대행합니다.
import db_manager

TEMPLATE_NAME = "template_전기실_운영일지.xlsx"
TEMPLATE_IN_APPDATA = os.path.join(db_manager.DB_DIR, TEMPLATE_NAME)

def get_bundle_template_path(relative_path):
    """PyInstaller 및 일반 개발 환경 경로 추적"""
    try:
        base_path = sys._MEIPASS
        return os.path.join(base_path, relative_path)
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

def ensure_excel_template():
    """템플릿 자동 무결성 점검"""
    if not os.path.exists(TEMPLATE_IN_APPDATA):
        bundled_template = get_bundle_template_path(TEMPLATE_NAME)
        if os.path.exists(bundled_template):
            if not os.path.exists(db_manager.DB_DIR):
                os.makedirs(db_manager.DB_DIR)
            shutil.copy(bundled_template, TEMPLATE_IN_APPDATA)
            print("✅ 엑셀 템플릿 파일이 가상 공간에 준비되었습니다.")

# 초기 구동 보장
ensure_excel_template()

def clean_external_links_physically(file_path):
    """엑셀 내부 외부 링크 오염 파편 청소 엔진"""
    temp_file_path = file_path + ".tmp"
    try:
        with zipfile.ZipFile(file_path, 'r') as zin:
            with zipfile.ZipFile(temp_file_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    filename = item.filename
                    if "externalLinks/" in filename: continue
                    if filename == "xl/_rels/workbook.xml.rels":
                        data = zin.read(filename).decode('utf-8')
                        data_clean = re.sub(r'<Relationship[^>]*Type="[^"]*externalLink"[^>]*/>', '', data)
                        zout.writestr(filename, data_clean.encode('utf-8'))
                        continue
                    if filename == "xl/workbook.xml":
                        data = zin.read(filename).decode('utf-8')
                        data_clean = re.sub(r'<externalReferences>.*?</externalReferences>', '', data, flags=re.DOTALL)
                        zout.writestr(filename, data_clean.encode('utf-8'))
                        continue
                    zout.writestr(item, zin.read(filename))
        os.remove(file_path)
        os.rename(temp_file_path, file_path)
    except Exception as e:
        if os.path.exists(temp_file_path): os.remove(temp_file_path)
        print(f"[경고] 외부 링크 세척 중 예외: {e}")

def generate_excel_report(selected_date, target_dir=None):
    """
    오직 엑셀 파일 복사 및 셀 덮어쓰기 서식 제어에만 집중하는 리모델링된 레포트 함수
    """
    if target_dir:
        output_file = os.path.join(target_dir, f"{selected_date}_전기실_운영일지.xlsx")
    else:  
        output_file = os.path.join(db_manager.DB_DIR, f"{selected_date}_전기실_운영일지.xlsx")
    
    if not os.path.exists(TEMPLATE_IN_APPDATA):
        raise FileNotFoundError(f"템플릿 원본 파일이 부재합니다: {TEMPLATE_IN_APPDATA}")
    
    # 1. 원본 서식 복제 및 문서 오픈
    shutil.copy(TEMPLATE_IN_APPDATA, output_file)
    wb = openpyxl.load_workbook(output_file, data_only=False)
    
    if hasattr(wb, 'external_link_refs'): wb.external_link_refs = []
    if hasattr(wb, '_external_links'): wb._external_links = []

    dt = datetime.strptime(selected_date, "%Y-%m-%d")
    date_str_formatted = f"{dt.year}년 {dt.month:02d}월 {dt.day:02d}일"
    
    # 시트 매핑 구조화
    ws_summary = wb.worksheets[0]
    ws_detail = wb.worksheets[1] if len(wb.worksheets) > 1 else wb.worksheets[0]
    
    for sheet in wb.worksheets:
        if "운전현황" in sheet.title or "운영현황" in sheet.title:
            ws_summary = sheet
            sheet.title = f"{selected_date}_전력설비_운전현황"
        elif "상세내역" in sheet.title:
            ws_detail = sheet
            sheet.title = f"{selected_date}_상세내역"

    # =========================================================================
    # [파트 1] 최고/최저 통계 데이터 매핑 (db_manager API 위임)
    # =========================================================================
    extremes_dict = db_manager.get_excel_extremes_data(selected_date)

    for row in ws_summary.iter_rows(max_row=20):
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                val_strip = cell.value.strip().replace(" ", "")
                if "일시:" in val_strip or ("일시" in val_strip and ":" in val_strip):
                    cell.value = f"일시 : {date_str_formatted}"
                elif "max(" in val_strip:
                    label = cell.value.split('"')[1].strip() if '"' in cell.value else cell.value.replace("max(", "").replace(")", "").strip()
                    cell.value = extremes_dict.get(("MAX", label), "-")
                elif "min(" in val_strip:
                    label = cell.value.split('"')[1].strip() if '"' in cell.value else cell.value.replace("min(", "").replace(")", "").strip()
                    cell.value = extremes_dict.get(("MIN", label), "-")

    # =========================================================================
    # [파트 2 & 3] 요약 사용 전력량 수식 매핑
    # =========================================================================
    day_min_val = extremes_dict.get(("MIN", "KEP_P_kWh"), "-")
    day_max_val = extremes_dict.get(("MAX", "KEP_P_kWh"), "-")
    
    # 당월 시작일 기준의 누적 검침량 산출 위임
    start_of_month = f"{dt.year}-{dt.month:02d}-01"
    conn_raw = db_manager.get_db_raw_connection()
    c_raw = conn_raw.cursor()
    c_raw.execute('''
        SELECT KEP_P_kWh FROM raw_data 
        WHERE log_date >= %s AND log_date <= %s AND KEP_P_kWh IS NOT NULL 
        ORDER BY log_date ASC, log_time ASC LIMIT 1
    ''', (start_of_month, selected_date))
    month_start_res = c_raw.fetchone()
    month_start_val = round(float(month_start_res[0]), 1) if month_start_res and month_start_res[0] is not None else "-"
    
    # 한전 적산 요약 연산 차이 구하기
    try:
        diff_mwh = round(float(day_max_val) - float(day_min_val), 1) if day_max_val != "-" and day_min_val != "-" else "-"
    except:
        diff_mwh = "-"
    c_raw.close()
    conn_raw.close()

    # 21~22행 전력량 영역 가공
    for row_idx in [21, 22]:
        for cell in ws_summary[row_idx]:
            if cell.value and isinstance(cell.value, str):
                text_clean = cell.value.strip().replace(" ", "")
                if row_idx == 21:
                    if 'min("KEP_P_kWh")' in text_clean: cell.value = day_min_val
                    elif 'max("KEP_P_kWh")' in text_clean: cell.value = day_max_val
                    elif 'E21-C21' in text_clean: cell.value = "=E21-C21"
                elif row_idx == 22:
                    if 'start("KEP_P_kWh")' in text_clean: cell.value = month_start_val
                    elif 'end("KEP_P_kWh")' in text_clean: cell.value = day_max_val
                    elif 'E22-C22' in text_clean: cell.value = "=E22-C22"

    # 26~30행 한전 요약 하드코딩 치환 구역 가공
    for row in ws_summary.iter_rows(min_row=26, max_row=30):
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                val_strip = cell.value.strip()
                if val_strip == "1469.79": cell.value = day_max_val
                elif val_strip == "1464.06": cell.value = day_min_val
                elif val_strip == "5.7300000000000182": cell.value = diff_mwh

    # =========================================================================
    # [파트 4] 독립 수동 검침 연동 구역 (db_manager API 위임)
    # =========================================================================
    prev_day = (dt - timedelta(days=1)).strftime('%Y-%m-%d')
    prev_month_last_day = (dt.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    meter_data = db_manager.get_excel_manual_meters(selected_date, prev_day, prev_month_last_day)

    for row in ws_summary.iter_rows(min_row=27, max_row=35, min_col=3, max_col=10):
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                val_strip = cell.value.strip().replace(" ", "")
                match = re.match(r'(금일|전일|전월)\(["\']?([a-zA-Z0-9_]+)["\']?\)', val_strip)
                if match:
                    time_type, field_name = match.group(1), match.group(2)  
                    if field_name in db_manager.METER_FIELDS:
                        db_val = meter_data.get(time_type, {}).get(field_name, None)
                        cell.value = float(db_val) if db_val is not None else ""

    # =========================================================================
    # [파트 5] 현장 점검 정보 연동 구역 (db_manager API 위임)
    # =========================================================================
    inspection_data = db_manager.get_field_inspections_for_date(selected_date)
    for row in ws_summary["E40:G48"]:
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                cell_text = cell.value.strip()
                for round_idx, label in [(1, "1차"), (2, "2차"), (3, "3차")]:
                    if label in cell_text and "점검자" in cell_text:
                        cell.value = inspection_data[round_idx]["name"] if inspection_data[round_idx]["name"] else "-"
                    elif label in cell_text and "시간" in cell_text:
                        cell.value = inspection_data[round_idx]["time"] if inspection_data[round_idx]["time"] else "-"

    # =========================================================================
    # [파트 6] 상세내역 시트 - 24시간 시간별 데이터 주입 (db_manager API 위임)
    # =========================================================================
    for row in ws_detail.iter_rows(max_row=3):
        for cell in row:
            if cell.value and isinstance(cell.value, str) and "일자" in cell.value:
                cell.value = f"일자 : {date_str_formatted}"

    hourly_data = db_manager.get_excel_hourly_averages(selected_date)

    for row_idx, row in enumerate(ws_detail.iter_rows(min_row=4, max_row=60), start=4):
        first_cell_val = str(row[0].value).strip() if row[0].value is not None else ""
        if first_cell_val == "0":
            col_mapping = {}
            for col_idx, cell in enumerate(row):
                if cell.value and isinstance(cell.value, str):
                    clean_label = cell.value.strip().replace('"', '')
                    if clean_label in db_manager.DATA_LABELS:
                        col_mapping[col_idx] = clean_label
            
            if col_mapping:
                for h in range(24):
                    target_row = row_idx + h
                    ws_detail.cell(row=target_row, column=1).value = h
                    for col_idx, label in col_mapping.items():
                        val = hourly_data.get((h, label), "-")
                        ws_detail.cell(row=target_row, column=col_idx + 1).value = val
            break

    wb.save(output_file)
    wb.close()
    clean_external_links_physically(output_file)
    print(f"✅ [엑셀 엔진] 일지 출력이 완벽하게 완료되었습니다. -> {output_file}")
    return True