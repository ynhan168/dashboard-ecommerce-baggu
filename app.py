import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import json
import re

# Cấu hình giao diện Streamlit rộng toàn màn hình
st.set_page_config(page_title="Dashboard Quản Trị Đa Sàn", layout="wide", page_icon="📊")

# ==================== 1. FORM BẢO VỆ BẰNG MẬT KHẨU ====================
def check_password():
    def password_entered():
        # Lấy mật khẩu an toàn: ưu tiên đọc từ secrets (khi lên web), nếu ở máy cá nhân chưa có file thì mặc định là 'admin123'
        correct_password = "admin123"
        try:
            if hasattr(st, "secrets") and "PASSWORD" in st.secrets:
                correct_password = st.secrets["PASSWORD"]
        except Exception:
            correct_password = "admin123"

        if st.session_state["password_input"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("### 🔒 Đăng Nhập Quản Trị Hệ Thống")
        st.text_input("Nhập mật khẩu truy cập nội bộ:", type="password", on_change=password_entered, key="password_input")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("### 🔒 Đăng Nhập Quản Trị Hệ Thống")
        st.text_input("Mật khẩu không đúng, vui lòng nhập lại:", type="password", on_change=password_entered, key="password_input")
        return False
    return True

if not check_password():
    st.stop()

# ==================== 2. HÀM BỔ TRỢ XỬ LÝ DỮ LIỆU ====================
def clean_num(val):
    """Làm sạch tiền tệ dạng chuỗi thành số thực"""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).replace(',', '').replace('đ', '').replace('VND', '').replace(' ', '').strip()
    try:
        return float(val_str)
    except:
        return 0.0

def parse_filename_meta(filename):
    """Tự động phân tích tên file theo quy chuẩn của shop"""
    fn = filename.lower()
    fn_clean = re.sub(r'\.(xlsx|csv|xls)$', '', fn)
    parts = fn_clean.split('_')
    
    # 1. Loại file
    file_type = "other"
    if "ads" in parts:
        file_type = "ads"
    elif "income" in parts:
        file_type = "income"
    elif "donhoanthanh" in parts or "donhang" in parts:
        file_type = "orders"

    # 2. Sàn
    platform = "Khác"
    if "tts" in parts or "tiktok" in parts:
        platform = "TikTok Shop"
    elif "sp" in parts or "shopee" in parts:
        platform = "Shopee"
    elif "ngoai" in parts:
        platform = "Ngoại sàn"

    # 3. Thương hiệu
    brand = "Khác"
    if "baggudiy" in parts:
        brand = "Baggudiy"
    elif "bagguandu" in parts:
        brand = "Bagguandu"

    # 4. Kỳ thời gian (Tuần / Tháng / Năm)
    week = None
    month = datetime.date.today().month
    year = datetime.date.today().year
    
    for p in parts:
        if re.match(r'^(t|w)\d+$', p):
            week = p.upper()
        elif re.match(r'^\d{2}$', p) and int(p) <= 12:
            month = int(p)
        elif re.match(r'^\d{4}$', p):
            year = int(p)
            
    period_label = f"{week} - T{month:02d}/{year}" if week else f"Tháng {month:02d}/{year}"
    shop_id = f"{platform} - {brand}"

    return {
        "file_type": file_type,
        "platform": platform,
        "brand": brand,
        "shop_id": shop_id,
        "week": week,
        "month": month,
        "year": year,
        "period": period_label,
        "is_weekly": week is not None
    }

def extract_key_val_from_sheet(df):
    """Bóc tách cặp Tên chỉ số -> Số tiền từ sheet Báo Cáo hoặc Summary"""
    kv_map = {}
    for _, row in df.iterrows():
        valid_cells = [c for c in row if pd.notna(c) and str(c).strip() != '']
        if len(valid_cells) >= 2:
            for i in range(len(valid_cells) - 1):
                key = str(valid_cells[i]).strip()
                val = clean_num(valid_cells[i+1])
                if key and val != 0.0:
                    kv_map[key] = val
    return kv_map

DATA_COLUMNS = [
    "Năm", "Tháng", "Kỳ", "Shop", "Sàn", "Thương hiệu",
    "Tổng Doanh Thu Gốc", "Tổng Phí Sàn Đã Trừ", "Doanh Số Thực Nhận Về Ví",
    "Doanh số thực", "Tổng doanh thu gộp", "Phí sàn", "Chi tiết phí",
    "Chi phí Ads gốc", "Thuế Ads (10%)", "Chi phí Ads", "Giá vốn",
    "Lợi Nhuận Gộp Sau Marketing (MAM)", "Lợi nhuận",
    "Tổng Doanh Thu Kiện Hàng", "Chi Phí Marketing KOC", "Chi Phí Gửi Hàng Bù"
]
HISTORY_FILE = "lich_su_doanh_so.csv"

def sample_history_rows():
    """Create useful local history for a first run without uploaded files."""
    return [
        {"Năm": 2026, "Tháng": 7, "Kỳ": "Tháng 07/2026", "Shop": "TikTok Shop - Bagguandu", "Sàn": "TikTok Shop", "Thương hiệu": "Bagguandu", "Doanh số thực": 52000000, "Tổng doanh thu gộp": 74000000, "Phí sàn": 22000000, "Chi tiết phí": {"Hoa hồng TikTok": 10500000, "Phí giao dịch": 3900000, "Affiliate": 3400000}, "Chi phí Ads gốc": 9000000, "Thuế Ads (10%)": 900000, "Chi phí Ads": 9900000, "Giá vốn": 23400000, "Lợi nhuận": 18700000},
        {"Năm": 2026, "Tháng": 7, "Kỳ": "Tháng 07/2026", "Shop": "Shopee - Baggudiy", "Sàn": "Shopee", "Thương hiệu": "Baggudiy", "Doanh số thực": 38000000, "Tổng doanh thu gộp": 50000000, "Phí sàn": 12000000, "Chi tiết phí": {"Phí cố định": 6000000, "Phí Dịch Vụ": 3500000, "Tiếp thị liên kết": 2500000}, "Chi phí Ads gốc": 5000000, "Thuế Ads (10%)": 500000, "Chi phí Ads": 5500000, "Giá vốn": 17100000, "Lợi nhuận": 15400000},
        {"Năm": 2026, "Tháng": 8, "Kỳ": "Tháng 08/2026", "Shop": "TikTok Shop - Bagguandu", "Sàn": "TikTok Shop", "Thương hiệu": "Bagguandu", "Doanh số thực": 55879126, "Tổng doanh thu gộp": 78809000, "Phí sàn": 23083874, "Chi tiết phí": {"Hoa hồng TikTok": 11069485, "Phí giao dịch": 4043157, "Affiliate": 3669870}, "Chi phí Ads gốc": 10000000, "Thuế Ads (10%)": 1000000, "Chi phí Ads": 11000000, "Giá vốn": 25145500, "Lợi nhuận": 19733500},
        {"Năm": 2026, "Tháng": 8, "Kỳ": "Tháng 08/2026", "Shop": "Shopee - Baggudiy", "Sàn": "Shopee", "Thương hiệu": "Baggudiy", "Doanh số thực": 700781, "Tổng doanh thu gộp": 1041000, "Phí sàn": 340219, "Chi tiết phí": {"Phí cố định": 166560, "Phí Dịch Vụ": 75258, "Phí xử lý": 62460}, "Chi phí Ads gốc": 0, "Thuế Ads (10%)": 0, "Chi phí Ads": 0, "Giá vốn": 315351, "Lợi nhuận": 385211}
    ]

def normalize_history(history):
    """Convert CSV values back to the types used by the dashboard."""
    if history is None or history.empty:
        return []

    rows = []
    for _, source_row in history.iterrows():
        row = {column: source_row.get(column, 0) for column in DATA_COLUMNS}
        row["Tổng Doanh Thu Gốc"] = source_row.get("Tổng Doanh Thu Gốc", source_row.get("Tổng doanh thu gộp", 0))
        row["Tổng Phí Sàn Đã Trừ"] = source_row.get("Tổng Phí Sàn Đã Trừ", source_row.get("Phí sàn", 0))
        row["Doanh Số Thực Nhận Về Ví"] = source_row.get("Doanh Số Thực Nhận Về Ví", source_row.get("Doanh số thực", 0))
        row["Lợi Nhuận Gộp Sau Marketing (MAM)"] = source_row.get(
            "Lợi Nhuận Gộp Sau Marketing (MAM)", source_row.get("Lợi nhuận", 0)
        )
        fee_detail = row["Chi tiết phí"]
        if isinstance(fee_detail, str):
            try:
                fee_detail = json.loads(fee_detail)
            except (TypeError, json.JSONDecodeError):
                fee_detail = {}
        row["Chi tiết phí"] = fee_detail if isinstance(fee_detail, dict) else {}
        for column in [
            "Năm", "Tháng", "Tổng Doanh Thu Gốc", "Tổng Phí Sàn Đã Trừ", "Doanh Số Thực Nhận Về Ví",
            "Doanh số thực", "Tổng doanh thu gộp", "Phí sàn",
            "Chi phí Ads gốc", "Thuế Ads (10%)", "Chi phí Ads", "Giá vốn", "Lợi nhuận"
        ]:
            row[column] = clean_num(row[column])
        row["Lợi Nhuận Gộp Sau Marketing (MAM)"] = clean_num(row["Lợi Nhuận Gộp Sau Marketing (MAM)"])
        for column in [
            "Tổng Doanh Thu Kiện Hàng", "Chi Phí Marketing KOC", "Chi Phí Gửi Hàng Bù"
        ]:
            row[column] = clean_num(row[column])
        row["Lợi Nhuận Gộp Sau Marketing (MAM)"] = (
            row["Doanh Số Thực Nhận Về Ví"]
            - row["Chi phí Ads"]
            - row["Chi Phí Marketing KOC"]
            - row["Chi Phí Gửi Hàng Bù"]
            - row["Giá vốn"]
        )
        row["Lợi nhuận"] = row["Lợi Nhuận Gộp Sau Marketing (MAM)"]
        rows.append(row)
    return rows

def rows_for_csv(rows):
    serialized = []
    for row in rows:
        output = {column: row.get(column, 0) for column in DATA_COLUMNS}
        gross_revenue = row.get("Tổng Doanh Thu Gốc", row.get("Tổng doanh thu gộp", 0))
        platform_fees = row.get("Tổng Phí Sàn Đã Trừ", row.get("Phí sàn", 0))
        wallet_revenue = row.get("Doanh Số Thực Nhận Về Ví", row.get("Doanh số thực", 0))
        mam = row.get("Lợi Nhuận Gộp Sau Marketing (MAM)", row.get("Lợi nhuận", 0))
        output.update({
            "Tổng Doanh Thu Gốc": gross_revenue,
            "Tổng Phí Sàn Đã Trừ": platform_fees,
            "Doanh Số Thực Nhận Về Ví": wallet_revenue,
            "Lợi Nhuận Gộp Sau Marketing (MAM)": mam,
        })
        output["Chi tiết phí"] = json.dumps(output["Chi tiết phí"], ensure_ascii=False)
        serialized.append(output)
    return pd.DataFrame(serialized, columns=DATA_COLUMNS)

def load_history():
    try:
        history = pd.read_csv(HISTORY_FILE)
    except FileNotFoundError:
        initial_rows = sample_history_rows()
        initial_frame = rows_for_csv(initial_rows)
        initial_frame.to_csv(HISTORY_FILE, index=False, encoding="utf-8-sig")
        return normalize_history(initial_frame)
    except pd.errors.EmptyDataError:
        initial_rows = sample_history_rows()
        initial_frame = rows_for_csv(initial_rows)
        initial_frame.to_csv(HISTORY_FILE, index=False, encoding="utf-8-sig")
        return normalize_history(initial_frame)
    except Exception as error:
        st.warning(f"Không đọc được file lịch sử: {error}")
        return []
    return normalize_history(history)

def save_history(rows):
    try:
        existing_rows = load_history()
        new_keys = {(str(row["Shop"]), str(row["Kỳ"])) for row in rows}
        kept_rows = [
            row for row in existing_rows
            if (str(row.get("Shop", "")), str(row.get("Kỳ", ""))) not in new_keys
        ]
        rows_for_csv(kept_rows + rows).to_csv(HISTORY_FILE, index=False, encoding="utf-8-sig")
        return True
    except Exception as error:
        st.error(f"Không thể ghi dữ liệu vào file lịch sử: {error}")
        return False

# ==================== 3. THANH ĐIỀU HƯỚNG BÊN TRÁI (SIDEBAR) ====================
with st.sidebar:
    st.header("⚙️ Nạp Báo Cáo")
    cogs_rate = st.slider("Tỷ lệ Giá Vốn Hàng Bán (% Doanh số):", min_value=20, max_value=70, value=45, step=1) / 100.0
    
    uploaded_files = st.file_uploader(
        "Kéo thả các file tuần/tháng vào đây:",
        type=["xlsx", "csv"],
        accept_multiple_files=True
    )
    st.info("Hệ thống tự nhận diện: `tts`, `sp`, `ngoai`, `baggudiy`, `bagguandu`, `ads`, `income`...")

history_data = load_history()

# ==================== 4. XỬ LÝ VÀ PHÂN LOẠI FILE NẠP LÊN ====================
current_data = []

if uploaded_files:
    # Bước A: Đọc các file Ads trước để tính chi phí và cộng thêm 10% thuế
    ads_lookup = {}
    for f in uploaded_files:
        meta = parse_filename_meta(f.name)
        if meta["file_type"] == "ads":
            try:
                df_ads = pd.read_csv(f) if f.name.endswith(".csv") else pd.read_excel(f)
                cost_col = next((c for c in df_ads.columns if str(c).strip().lower() in ['cost', 'chi tiêu', 'total spend']), None)
                if cost_col:
                    raw_ads = df_ads[cost_col].apply(clean_num).sum()
                    tax_ads = raw_ads * 0.10 # Thuế nạp ads 10%
                    total_ads = raw_ads + tax_ads
                    
                    key = (meta["brand"], meta["period"])
                    ads_lookup[key] = {
                        "raw": ads_lookup.get(key, {}).get("raw", 0.0) + raw_ads,
                        "tax": ads_lookup.get(key, {}).get("tax", 0.0) + tax_ads,
                        "total": ads_lookup.get(key, {}).get("total", 0.0) + total_ads
                    }
            except Exception as e:
                st.error(f"Lỗi đọc file Ads {f.name}: {e}")

    # Bước B: Đọc các file Income và file Đơn ngoài sàn
    for f in uploaded_files:
        meta = parse_filename_meta(f.name)
        if meta["file_type"] != "income" and meta["platform"] != "Ngoại sàn":
            continue

        shop_id = meta["shop_id"]
        period = meta["period"]
        platform = meta["platform"]
        brand = meta["brand"]

        # Lấy Ads tương ứng với đúng Thương hiệu và Kỳ này (Shopee/Ngoại sàn mặc định = 0)
        ads_info = ads_lookup.get((brand, period), {"raw": 0.0, "tax": 0.0, "total": 0.0}) if platform == "TikTok Shop" else {"raw": 0.0, "tax": 0.0, "total": 0.0}
        external_metrics = {
            "Tổng Doanh Thu Kiện Hàng": 0.0,
            "Chi Phí Marketing KOC": 0.0,
            "Chi Phí Gửi Hàng Bù": 0.0
        }

        try:
            # 1. Xử lý TikTok Shop (Đọc sheet 'Báo cáo')
            if platform == "TikTok Shop":
                excel_obj = pd.ExcelFile(f)
                sheet_target = "Báo cáo" if "Báo cáo" in excel_obj.sheet_names else excel_obj.sheet_names[0]
                df_report = pd.read_excel(f, sheet_name=sheet_target, header=None)
                kv = extract_key_val_from_sheet(df_report)

                net_payout = kv.get("Tổng số tiền quyết toán", 0.0)
                gross_sales = kv.get("Tổng doanh thu", 0.0)
                total_fees = abs(kv.get("Tổng phí", 0.0))
                
                fee_detail = {
                    "Hoa hồng TikTok": abs(kv.get("Phí hoa hồng của TikTok Shop", 0.0)),
                    "Phí giao dịch": abs(kv.get("Phí giao dịch", 0.0)),
                    "Phí vận chuyển": abs(kv.get("Phí vận chuyển của người bán", 0.0)),
                    "Affiliate": abs(kv.get("Hoa hồng liên kết", 0.0)),
                    "Phí xử lý đơn": abs(kv.get("Phí xử lý đơn hàng", 0.0)),
                    "Thuế sàn khấu trừ": abs(kv.get("Thuế GTGT do TikTok Shop khấu trừ", 0.0)) + abs(kv.get("Thuế TNCN do TikTok Shop khấu trừ", 0.0)),
                    "Điều chỉnh": kv.get("Điều chỉnh", 0.0)
                }

            # 2. Xử lý Shopee (Đọc sheet 'Summary')
            elif platform == "Shopee":
                excel_obj = pd.ExcelFile(f)
                sheet_target = "Summary" if "Summary" in excel_obj.sheet_names else excel_obj.sheet_names[0]
                df_summary = pd.read_excel(f, sheet_name=sheet_target, header=None)
                kv_s = extract_key_val_from_sheet(df_summary)

                net_payout = kv_s.get("3. Tổng số tiền", kv_s.get("Tổng số tiền", 0.0))
                gross_sales = kv_s.get("1. Tổng doanh thu", kv_s.get("Tổng doanh thu", 0.0))
                total_fees = abs(kv_s.get("2. Tổng chi phí", kv_s.get("Tổng chi phí", 0.0)))

                fee_detail = {
                    "Phí cố định": abs(kv_s.get("Phí cố định", 0.0)),
                    "Phí Dịch Vụ": abs(kv_s.get("Phí Dịch Vụ", 0.0)),
                    "Phí xử lý giao dịch": abs(kv_s.get("Phí xử lý giao dịch", 0.0)),
                    "Tiếp thị liên kết": abs(kv_s.get("Phí hoa hồng Tiếp thị liên kết", 0.0)),
                    "Thuế GTGT + TNCN": abs(kv_s.get("Thuế GTGT", 0.0)) + abs(kv_s.get("Thuế TNCN", 0.0))
                }

            # 3. Xử lý Ngoại sàn (Đơn COD & KOC)
            elif platform == "Ngoại sàn":
                df_ngoai = (
                    pd.read_csv(f, header=2)
                    if f.name.lower().endswith(".csv")
                    else pd.read_excel(f, header=2)
                )
                required_columns = [
                    "Item List", "Tracking Status", "Parcel Value", "COD Amount",
                    "Actual Shipping Fee", "Estimated Shipping Fee"
                ]
                missing_columns = [column for column in required_columns if column not in df_ngoai.columns]
                if missing_columns:
                    raise ValueError(
                        "Thiếu cột trong báo cáo 3PL: " + ", ".join(missing_columns)
                    )

                status_text = df_ngoai["Tracking Status"].fillna("").astype(str).str.lower()
                delivered = status_text.str.contains("đã giao|delivered", regex=True, na=False)
                df_ngoai = df_ngoai.loc[delivered].copy()

                item_text = df_ngoai["Item List"].fillna("").astype(str).str.lower()
                is_koc = item_text.str.contains("koc", regex=False, na=False)
                is_replacement = item_text.str.contains("bù", regex=False, na=False)
                is_customer = ~is_koc & ~is_replacement

                df_ngoai["parcel_value"] = df_ngoai["Parcel Value"].apply(clean_num)
                df_ngoai["shipping_fee"] = df_ngoai["Actual Shipping Fee"].apply(clean_num)

                gross_sales = df_ngoai.loc[is_customer, "parcel_value"].sum()
                customer_shipping = df_ngoai.loc[is_customer, "shipping_fee"].sum()
                koc_ship = df_ngoai.loc[is_koc, "shipping_fee"].sum()
                replacement_ship = df_ngoai.loc[is_replacement, "shipping_fee"].sum()

                net_payout = gross_sales - customer_shipping
                total_fees = customer_shipping
                fee_detail = {
                    "Phí Vận Chuyển 3PL": customer_shipping,
                    "Chi Phí Marketing KOC": koc_ship,
                    "Chi Phí Gửi Hàng Bù": replacement_ship
                }
                ads_info = {"raw": 0.0, "tax": 0.0, "total": 0.0}
                external_metrics = {
                    "Tổng Doanh Thu Kiện Hàng": gross_sales,
                    "Chi Phí Marketing KOC": koc_ship,
                    "Chi Phí Gửi Hàng Bù": replacement_ship
                }

            cogs = net_payout * cogs_rate
            marketing_cost = (
                ads_info["total"]
                + external_metrics["Chi Phí Marketing KOC"]
                + external_metrics["Chi Phí Gửi Hàng Bù"]
            )
            profit = net_payout - marketing_cost - cogs

            current_data.append({
                "Năm": meta["year"],
                "Tháng": meta["month"],
                "Kỳ": period,
                "Shop": shop_id,
                "Sàn": platform,
                "Thương hiệu": brand,
                "Tổng Doanh Thu Gốc": gross_sales,
                "Tổng Phí Sàn Đã Trừ": total_fees,
                "Doanh Số Thực Nhận Về Ví": net_payout,
                "Doanh số thực": net_payout,
                "Tổng doanh thu gộp": gross_sales,
                "Phí sàn": total_fees,
                "Chi tiết phí": fee_detail,
                "Chi phí Ads gốc": ads_info["raw"],
                "Thuế Ads (10%)": ads_info["tax"],
                "Chi phí Ads": ads_info["total"],
                "Giá vốn": cogs,
                "Lợi Nhuận Gộp Sau Marketing (MAM)": profit,
                "Lợi nhuận": profit,
                **external_metrics
            })
        except Exception as e:
            st.error(f"Lỗi đọc file {f.name}: {e}")

is_preview = bool(uploaded_files and current_data)
if is_preview:
    display_data = current_data
    st.info("🔎 Chế độ Xem trước: dữ liệu mới chưa được lưu vào file lịch sử.")
else:
    period_options = sorted({str(row["Kỳ"]) for row in history_data})
    if period_options:
        selected_period = st.selectbox("Chọn kỳ lịch sử để xem", ["Tất cả"] + period_options)
        display_data = (
            history_data
            if selected_period == "Tất cả"
            else [row for row in history_data if str(row["Kỳ"]) == selected_period]
        )
    else:
        display_data = []
        st.info("Chưa có dữ liệu lịch sử. Hãy kéo file mới vào để xem trước và lưu kỳ đầu tiên.")

df_now = pd.DataFrame(display_data, columns=DATA_COLUMNS)

# ==================== 5. GIAO DIỆN HIỂN THỊ CHỈ SỐ KPI ====================
st.title("📊 Báo Cáo Phân Tích Hiệu Quả & Dòng Tiền Đa Sàn")

total_gross_revenue = df_now["Tổng Doanh Thu Gốc"].sum()
total_sales = df_now["Doanh Số Thực Nhận Về Ví"].sum()
total_fees = df_now["Tổng Phí Sàn Đã Trừ"].sum()
total_ads = df_now["Chi phí Ads"].sum()
total_profit = df_now["Lợi Nhuận Gộp Sau Marketing (MAM)"].sum()
sales_rate = total_sales / total_gross_revenue * 100 if total_gross_revenue > 0 else 0.0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tổng Doanh Thu Gốc", f"{total_gross_revenue:,.0f} đ")
c2.metric("Thực Thu Về Ví", f"{total_sales:,.0f} đ", delta=f"{sales_rate:.1f}% doanh thu gốc")
c3.metric("Tổng Phí Sàn Đã Trừ", f"{total_fees:,.0f} đ", delta=f"{(total_fees/total_gross_revenue*100 if total_gross_revenue > 0 else 0):.1f}% DT gốc", delta_color="inverse")
c4.metric("Tổng Ads", f"{total_ads:,.0f} đ", delta=f"{(total_ads/total_sales*100 if total_sales > 0 else 0):.1f}% thực thu", delta_color="inverse")
c5.metric("MAM", f"{total_profit:,.0f} đ", delta=f"Biên MAM: {(total_profit/total_gross_revenue*100 if total_gross_revenue > 0 else 0):.1f}%")

st.markdown("#### Đối chiếu chi phí Ads nạp thẻ")
ads_kpi_1, ads_kpi_2, ads_kpi_3 = st.columns(3)
ads_kpi_1.metric("Tiền Ads gốc (chưa thuế)", f"{df_now['Chi phí Ads gốc'].sum():,.0f} đ")
ads_kpi_2.metric("Thuế Ads 10% nạp thẻ", f"{df_now['Thuế Ads (10%)'].sum():,.0f} đ")
ads_kpi_3.metric("Tổng chi phí Ads thực tế", f"{total_ads:,.0f} đ")

# Cảnh báo báo động đỏ
for _, r in df_now.iterrows():
    ads_pct = (r["Chi phí Ads"] / r["Tổng Doanh Thu Gốc"] * 100) if r["Tổng Doanh Thu Gốc"] > 0 else 0
    fees_pct = (r["Tổng Phí Sàn Đã Trừ"] / r["Tổng Doanh Thu Gốc"] * 100) if r["Tổng Doanh Thu Gốc"] > 0 else 0
    if ads_pct > 20:
        st.error(f"🚨 **BÁO ĐỘNG ĐỎ:** `{r['Shop']}` có tỷ lệ Ads chiếm tới **{ads_pct:.1f}%** doanh thu gốc (vượt ngưỡng 20%)!")
    if fees_pct > 22:
        st.warning(f"⚠️ **CẢNH BÁO:** `{r['Shop']}` có phí sàn chiếm **{fees_pct:.1f}%** doanh thu gốc!")

st.markdown("---")

# ==================== 6. BIỂU ĐỒ SO SÁNH & MỔ XẺ TỪNG SHOP ====================
tab_summary, tab_detail = st.tabs(["🌐 So Sánh Tổng Thể Các Shop", "🔍 Mổ Xẻ Từng Shop (P&L Thác Nước)"])

with tab_summary:
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        fig_bar = px.bar(
            df_now, x="Shop", y=["Tổng Doanh Thu Gốc", "Doanh Số Thực Nhận Về Ví", "Chi phí Ads", "Lợi Nhuận Gộp Sau Marketing (MAM)"],
            barmode="group", title="Doanh Thu Gốc, Thực Thu và MAM", text_auto=".2s"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    with col_chart2:
        df_now["% Phí Sàn"] = (df_now["Tổng Phí Sàn Đã Trừ"] / df_now["Tổng Doanh Thu Gốc"].replace(0, pd.NA) * 100).fillna(0).round(1)
        df_now["% Chi Phí Ads"] = (df_now["Chi phí Ads"] / df_now["Tổng Doanh Thu Gốc"].replace(0, pd.NA) * 100).fillna(0).round(1)
        df_now["% MAM"] = (df_now["Lợi Nhuận Gộp Sau Marketing (MAM)"] / df_now["Tổng Doanh Thu Gốc"].replace(0, pd.NA) * 100).fillna(0).round(1)
        fig_rate = px.bar(
            df_now, x="Shop", y=["% Phí Sàn", "% Chi Phí Ads", "% MAM"],
            barmode="group", title="Tỷ Trọng Chi Phí và Biên MAM (%)", text_auto=True
        )
        st.plotly_chart(fig_rate, use_container_width=True)

with tab_detail:
    shop_list = df_now["Shop"].tolist()
    subtabs = st.tabs(shop_list)
    for idx, r in df_now.iterrows():
        with subtabs[idx]:
            st.subheader(f"📌 {r['Shop']} | {r['Kỳ']}")
            gross_revenue = float(r["Tổng Doanh Thu Gốc"])
            wallet_revenue = float(r["Doanh Số Thực Nhận Về Ví"])
            marketing_cost = float(r["Chi phí Ads"]) + float(r["Chi Phí Marketing KOC"]) + float(r["Chi Phí Gửi Hàng Bù"])

            def pnl_row(label, amount):
                amount = float(amount)
                ratio = amount / gross_revenue * 100 if gross_revenue > 0 else 0.0
                return {
                    "Khoản Mục": label,
                    "Số Tiền (đ)": f"{amount:,.0f} đ",
                    "Tỷ Trọng (% / Doanh Thu Gốc)": f"{ratio:.1f}%"
                }

            pnl_rows = [
                {"Khoản Mục": "I. DOANH THU", "Số Tiền (đ)": "", "Tỷ Trọng (% / Doanh Thu Gốc)": ""},
                pnl_row("1. Tổng Doanh Thu Gốc (GMV sàn ghi nhận)", gross_revenue),
                pnl_row("2. Doanh Thu Thực Nhận Về Ví", wallet_revenue),
                {"Khoản Mục": "II. CHI PHÍ NỀN TẢNG & SÀN", "Số Tiền (đ)": "", "Tỷ Trọng (% / Doanh Thu Gốc)": ""},
            ]

            if r["Sàn"] == "Ngoại sàn":
                platform_rows = [
                    ("Phí Vận Chuyển 3PL", r["Tổng Phí Sàn Đã Trừ"]),
                ]
            else:
                platform_rows = list(r["Chi tiết phí"].items())

            pnl_rows.extend(pnl_row(label, amount) for label, amount in platform_rows)
            platform_total = float(r["Tổng Phí Sàn Đã Trừ"])
            pnl_rows.extend([
                pnl_row("TỔNG CHI PHÍ NỀN TẢNG ĐÃ TRỪ", platform_total),
                {"Khoản Mục": "III. CHI PHÍ MARKETING & QUẢNG CÁO", "Số Tiền (đ)": "", "Tỷ Trọng (% / Doanh Thu Gốc)": ""},
                pnl_row("Tiền Ads gốc", r["Chi phí Ads gốc"]),
                pnl_row("Thuế Ads 10%", r["Thuế Ads (10%)"]),
            ])
            if r["Sàn"] == "Ngoại sàn":
                pnl_rows.extend([
                    pnl_row("Chi phí gửi mẫu KOC", r["Chi Phí Marketing KOC"]),
                    pnl_row("Chi phí gửi bù hàng lỗi", r["Chi Phí Gửi Hàng Bù"]),
                ])
            pnl_rows.extend([
                pnl_row("TỔNG CHI PHÍ MARKETING", marketing_cost),
                {"Khoản Mục": "IV. GIÁ VỐN HÀNG BÁN (COGS)", "Số Tiền (đ)": "", "Tỷ Trọng (% / Doanh Thu Gốc)": ""},
                pnl_row(f"Giá vốn hàng bán ({cogs_rate * 100:.0f}%)", r["Giá vốn"]),
                {"Khoản Mục": "V. HIỆU QUẢ KINH DOANH", "Số Tiền (đ)": "", "Tỷ Trọng (% / Doanh Thu Gốc)": ""},
                pnl_row("LỢI NHUẬN GỘP SAU MARKETING (MAM)", r["Lợi Nhuận Gộp Sau Marketing (MAM)"]),
                {
                    "Khoản Mục": "TỶ SUẤT LỢI NHUẬN (% MAM / DOANH THU GỐC)",
                    "Số Tiền (đ)": "",
                    "Tỷ Trọng (% / Doanh Thu Gốc)": f"{(r['Lợi Nhuận Gộp Sau Marketing (MAM)'] / gross_revenue * 100 if gross_revenue > 0 else 0):.1f}%"
                },
            ])

            pnl_df = pd.DataFrame(pnl_rows)
            table_col, chart_col = st.columns([1.15, 1])
            with table_col:
                def highlight_profit(row):
                    if row["Khoản Mục"] == "LỢI NHUẬN GỘP SAU MARKETING (MAM)":
                        color = "#d1fae5" if r["Lợi Nhuận Gộp Sau Marketing (MAM)"] >= 0 else "#fee2e2"
                        return [f"background-color: {color}; font-weight: 700"] * len(row)
                    if row["Khoản Mục"].startswith(("I. ", "II. ", "III. ", "IV. ", "V. ")):
                        return ["background-color: #e2e8f0; font-weight: 700"] * len(row)
                    if row["Khoản Mục"].startswith("TỔNG "):
                        return ["font-weight: 700; border-top: 1px solid #94a3b8"] * len(row)
                    return [""] * len(row)

                st.dataframe(
                    pnl_df.style.apply(highlight_profit, axis=1),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption("(Chưa bao gồm chi phí cố định: Mặt bằng, Lương nhân sự, Điện nước, Khấu hao & Vận hành chung)")
            with chart_col:
                waterfall_labels = [
                    "Doanh Thu Gốc", "Phí Sàn / 3PL", "Thực Nhận Về Ví",
                    "Ads / KOC / Gửi Bù", "Giá Vốn", "MAM"
                ]
                waterfall_values = [
                    gross_revenue, -r["Tổng Phí Sàn Đã Trừ"], 0,
                    -marketing_cost, -r["Giá vốn"], 0
                ]

                fig_wf = go.Figure(go.Waterfall(
                    name="P&L",
                    orientation="v",
                    measure=["relative", "relative", "total", "relative", "relative", "total"],
                    x=waterfall_labels,
                    y=waterfall_values,
                    connector={"line": {"color": "rgb(63, 63, 63)"}},
                ))
                fig_wf.update_layout(title=f"Dòng Chảy MAM - {r['Shop']}", showlegend=False)
                st.plotly_chart(fig_wf, use_container_width=True)

st.markdown("---")

# ==================== 7. LƯU LỊCH SỬ DỮ LIỆU ====================
st.markdown("### 💾 Lưu Trữ & Xu Hướng Lịch Sử")

CSV_FILE = "lich_su_doanh_so.csv"

if st.button("📥 Bấm Để Lưu Dữ Liệu Kỳ Này Vào Cơ Sở Dữ Liệu Lịch Sử"):
    if not df_now.empty:
        # 1. Tạo bản sao và loại bỏ cột dict phức tạp để lưu CSV an toàn 100%
        df_to_save = df_now.copy()
        if "Chi tiết phí" in df_to_save.columns:
            df_to_save = df_to_save.drop(columns=["Chi tiết phí"])

        # 2. Đọc file cũ nếu đã tồn tại
        try:
            old_df = pd.read_csv(CSV_FILE)
            # Kết hợp dữ liệu mới và cũ, nếu trùng (Shop, Kỳ) thì cập nhật dòng mới nhất
            combined_df = pd.concat([old_df, df_to_save], ignore_index=True)
            if "Shop" in combined_df.columns and "Kỳ" in combined_df.columns:
                combined_df = combined_df.drop_duplicates(subset=["Shop", "Kỳ"], keep="last")
        except Exception:
            # Chưa có file CSV trước đó
            combined_df = df_to_save

        # 3. Ghi đè vào file CSV với chuẩn utf-8-sig (để mở bằng Excel không lỗi tiếng Việt)
        combined_df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
        st.success(f"✅ Đã lưu thành công dữ liệu vào file `{CSV_FILE}` trên máy tính!")
        st.rerun()
    else:
        st.warning("Không có dữ liệu mới để lưu!")