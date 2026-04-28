import subprocess
import sys
import os
import time
import uuid

# 自動檢查並安裝必要套件 (針對本地端開發方便，雲端部署主要看 requirements.txt)
def install_required_packages():
    packages = {'flask': 'flask', 'google.generativeai': 'google-generativeai'}
    for module_name, pip_name in packages.items():
        try:
            __import__(module_name)
        except ImportError:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--break-system-packages', pip_name])

install_required_packages()

from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# --- 1. 金鑰安全設定 (從環境變數讀取) ---
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    print("⚠️ 警告：找不到 GOOGLE_MAPS_API_KEY 環境變數！地圖可能無法顯示。")
if not GEMINI_API_KEY:
    print("⚠️ 嚴重警告：找不到 GEMINI_API_KEY 環境變數！AI 導航功能將無法運作。")

# --- 2. AI 模型自動偵測 ---
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model = genai.GenerativeModel(m.name.replace('models/', ''))
                print(f"✅ AI 核心已啟動：使用模型 {m.name}")
                break
    except Exception as e:
        print(f"❌ AI 初始化失敗: {e}")

# --- 3. 靜宜大學座標與科系資料庫 ---
pu_locations = {
    "伯鐸樓": {"lat": 24.226435, "lng": 120.580714, "desc": "代碼: SP | 外語學院", "depts": "英國語文學系 西班牙語文學系 日本語文學系"},
    "任垣樓": {"lat": 24.226948, "lng": 120.579975, "desc": "代碼: AK | 人文暨社會科學院", "depts": "中國文學系 社會工作與兒童少年福利學系 台灣文學系 法律學系 生態人文學系 大眾傳播學系 師資培育中心 教育研究所 犯罪防治碩士學位學程 社會企業與文化創意碩士學位學程 原住民族健康與社會福利博士學位學程 原住民族文化碩士學位學程 健康照顧社會工作學士學位學程原住民專班 犯罪防治學士學位學程原住民專班 法律學士學位學程原住民專班 藝術跨域創作學士學位學程 通識教育中心"},
    "靜安樓": {"lat": 24.226224, "lng": 120.582118, "desc": "代碼: JA | 理學院", "depts": "財務工程學系 應用化學系 食品營養學系 化粧品科學系 民生與環境科技檢測中心 永續環境與智慧科技學士學位學程"},
    "思源樓": {"lat": 24.227036, "lng": 120.582479, "desc": "代碼: SY | 管理學院", "depts": "行銷與數位經營管理學系 國際企業學系 會計學系 觀光事業學系 財務金融學系 管理碩士在職專班(EMBA) 創新與創業管理碩士學位學程 經營管理進修學士班 管理學院AACSB認證辦公室"},
    "主顧樓": {"lat": 24.227070, "lng": 120.583291, "desc": "代碼: PH | 資訊學院", "depts": "資訊管理學系 資訊工程學系 人工智慧應用學系 資料科學暨大數據分析與應用學系 晶片設計學士學位學程 資訊應用與科技管理碩士在職專班 國際資訊學士學位學程"},
    "蓋夏圖書館": {"lat": 24.226303, "lng": 120.581292, "desc": "靜宜大學圖書館", "depts": "閱讀書寫暨素養課程研發中心 看書 借書 睡覺"},
    "希嘉學苑": {"lat": 24.228139, "lng": 120.580264, "desc": "女宿", "depts": "睡覺 休息 裝水 洗衣服"},
    "思高學苑": {"lat": 24.228805, "lng": 120.581961, "desc": "男宿", "depts": "睡覺 休息 裝水 洗衣服"},
    "善牧學苑": {"lat": 24.228856, "lng": 120.582487, "desc": "男女宿", "depts": "睡覺 休息 裝水 洗衣服"},
    "體育館": {"lat": 24.229167, "lng": 120.581063, "desc": "代碼: ST | 室內球場與泳池", "depts": "打球 游泳 運動"},
    "田徑場": {"lat": 24.227980, "lng": 120.579140, "desc": "代碼: SD | 操場", "depts": "跑步 運動 散步"},
    "至善美食廣場": {"lat": 24.228039, "lng": 120.579704, "desc": "主要學餐區", "depts": "吃飯 肚子餓 午餐 晚餐"},
    "宜園餐廳": {"lat": 24.227275, "lng": 120.579522, "desc": "學生餐廳", "depts": "吃飯 肚子餓 午餐 晚餐"},
    "靜園餐廳": {"lat": 24.227622, "lng": 120.581652, "desc": "學生餐廳", "depts": "吃飯 肚子餓 午餐 晚餐"},
    "靜宜小木屋鬆餅": {"lat": 24.228612, "lng": 120.581368, "desc": "美食小點", "depts": "吃點心 下午茶 鬆餅"},
    "格倫樓": {"lat": 24.226231, "lng": 120.583049, "desc": "代碼: TG"},
    "方濟樓": {"lat": 24.227963, "lng": 120.583452, "desc": "代碼: SF"},
    "第一研究大樓": {"lat": 24.226224, "lng": 120.582118, "desc": "代碼: 1R"},
    "第二研究大樓": {"lat": 24.227036, "lng": 120.582479, "desc": "代碼: 2R"},
    "計算機中心": {"lat": 24.226327, "lng": 120.579860, "desc": "代碼: AK-3C | 電腦教室", "depts": "印講義 上網 印表機"},
    "文興樓": {"lat": 24.227107, "lng": 120.581128, "desc": "行政大樓", "depts": "繳費 辦休學 申請成績單"},
    "主顧聖母堂": {"lat": 24.228076, "lng": 120.581420, "desc": "打卡聖地", "depts": "教堂 拍照"},
    "靜宜大學校門": {"lat": 24.225843, "lng": 120.577191, "desc": "主要出入口"},
    "校門口公車站": {"lat": 24.225341, "lng": 120.577765, "desc": "公車搭乘處", "depts": "搭車 回家 台灣大道"}
}

# --- 4. 限時揪團系統資料庫 (暫存於記憶體) ---
active_groups = []

@app.route('/')
def index():
    return render_template('index.html', api_key=GOOGLE_MAPS_API_KEY, locations=pu_locations)

@app.route('/api/ai_search', methods=['POST'])
def ai_search():
    if not model:
        return jsonify({"error": "AI 系統未啟動 (可能是 API Key 問題)"}), 500

    data = request.get_json()
    user_query = data.get('query', '')
    location_names = list(pu_locations.keys())
    
    prompt = f"""
    任務：你是校園導航系統。
    使用者輸入："{user_query}"
    可用地點清單：{location_names}
    規則：
    1. 推理使用者想做的事，並從「可用地點清單」中選出最合理的一個地點。
    2. 範例：輸入"睡覺" -> 回傳"希嘉學苑" 或 "思高學苑"；輸入"借書" -> 回傳"蓋夏圖書館"；輸入"肚子餓" -> 回傳"至善美食廣場"。
    3. 你的回應【只能】包含地點名稱，絕對不能有任何其他文字、標點符號或解釋。
    4. 如果完全無法判斷，請回傳 "無"。
    """

    try:
        response = model.generate_content(prompt)
        res_text = response.text.strip().replace("'", "").replace('"', '')
        
        for loc_name in location_names:
            if loc_name in res_text:
                return jsonify({"target": loc_name})
                
        print(f"⚠️ AI 回傳了無法辨識的結果：{res_text}")
        return jsonify({"error": f"AI 說：{res_text}，但在靜宜地圖上找不到！"}), 404
    except Exception as e:
        print(f"⚠️ 呼叫 Gemini 發生錯誤：{e}")
        return jsonify({"error": "AI 腦袋當機了，請稍後再試！"}), 500

# --- 5. 揪團系統 API ---
@app.route('/api/groups', methods=['GET'])
def get_groups():
    """獲取目前有效的所有揪團"""
    global active_groups
    current_time = time.time()
    # 清理過期的揪團 (時效性機制)
    active_groups = [g for g in active_groups if g['expires_at'] > current_time]
    return jsonify(active_groups)

@app.route('/api/groups', methods=['POST'])
def create_group():
    """創建一個新的限時揪團"""
    data = request.get_json()
    title = data.get('title')
    location = data.get('location')
    
    if not title or not location or location not in pu_locations:
        return jsonify({"error": "資料不完整或地點無效"}), 400
        
    # 設定 30 分鐘後過期 (30 * 60 秒)
    expires_at = time.time() + (30 * 60)
    
    new_group = {
        "id": str(uuid.uuid4()),
        "title": title,
        "location": location,
        "expires_at": expires_at
    }
    
    active_groups.append(new_group)
    return jsonify({"success": True, "group": new_group})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)