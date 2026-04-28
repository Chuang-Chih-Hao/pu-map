import subprocess
import sys
import os

# 自動檢查並安裝必要套件
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

import os # 如果最上面沒有 import os，記得補上

# --- 1. 金鑰設定 ---
GOOGLE_MAPS_API_KEY = "AIzaSyBVas_ZbdGfz7-DM-IU9sd6TGw0cyKRlW0"

# 安全取用金鑰：優先從環境變數拿，拿不到才回傳 None
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 

if not GEMINI_API_KEY:
    print("⚠️ 嚴重警告：系統找不到 GEMINI_API_KEY 環境變數！AI 功能將無法啟動。")

# --- 2. AI 模型自動偵測 ---
genai.configure(api_key=GEMINI_API_KEY)
model = None
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            model = genai.GenerativeModel(m.name.replace('models/', ''))
            print(f"✅ AI 核心已啟動：使用模型 {m.name}")
            break
except Exception as e:
    print(f"❌ AI 初始化失敗: {e}")

# --- 3. 靜宜大學座標與科系資料庫 (終極更新版) ---
pu_locations = {
    # 已更新科系對應的五大學院大樓
    "伯鐸樓": {
        "lat": 24.226435, "lng": 120.580714, 
        "desc": "代碼: SP | 外語學院", 
        "depts": "SP 英國語文學系 西班牙語文學系 日本語文學系"
    },
    "任垣樓": {
        "lat": 24.226948, "lng": 120.579975, 
        "desc": "代碼: AK | 人文暨社會科學院", 
        "depts": "AK 中國文學系 社會工作與兒童少年福利學系 社工系 台灣文學系 法律學系 生態人文學系 大眾傳播學系 師資培育中心 教育研究所 犯罪防治碩士學位學程 社會企業與文化創意碩士學位學程 原住民族健康與社會福利博士學位學程 原住民族文化碩士學位學程 健康照顧社會工作學士學位學程原住民專班 犯罪防治學士學位學程原住民專班 法律學士學位學程原住民專班 藝術跨域創作學士學位學程 通識教育中心"
    },
    "靜安樓": {
        "lat": 24.226224, "lng": 120.582118, 
        "desc": "代碼: JA | 理學院", 
        "depts": "JA 財務工程學系 應用化學系 食品營養學系 化粧品科學系 民生與環境科技檢測中心 永續環境與智慧科技學士學位學程"
    },
    "思源樓": {
        "lat": 24.227036, "lng": 120.582479, 
        "desc": "代碼: SY | 管理學院", 
        "depts": "SY 行銷與數位經營管理學系 國際企業學系 會計學系 觀光事業學系 財務金融學系 管理碩士在職專班(EMBA) 創新與創業管理碩士學位學程 經營管理進修學士班 管理學院AACSB認證辦公室"
    },
    "主顧樓": {
        "lat": 24.227070, "lng": 120.583291, 
        "desc": "代碼: PH | 資訊學院", 
        "depts": "PH 資訊管理學系 資訊工程學系 人工智慧應用學系 資料科學暨大數據分析與應用學系 晶片設計學士學位學程 資訊應用與科技管理碩士在職專班 國際資訊學士學位學程"
    },
    "蓋夏圖書館": {
        "lat": 24.226303, "lng": 120.581292, 
        "desc": "靜宜大學圖書館", 
        "depts": "閱讀書寫暨素養課程研發中心"
    },
    
    # 保留原本的其他機能建築
    "格倫樓": {"lat": 24.226231, "lng": 120.583049, "desc": "代碼: TG"},
    "方濟樓": {"lat": 24.227963, "lng": 120.583452, "desc": "代碼: SF"},
    "第一研究大樓": {"lat": 24.226224, "lng": 120.582118, "desc": "代碼: 1R"},
    "第二研究大樓": {"lat": 24.227036, "lng": 120.582479, "desc": "代碼: 2R"},
    "計算機中心": {"lat": 24.226327, "lng": 120.579860, "desc": "代碼: AK-3C"},
    "文興樓": {"lat": 24.227107, "lng": 120.581128, "desc": "行政大樓"},
    "至善美食廣場": {"lat": 24.228039, "lng": 120.579704, "desc": "學生餐廳"},
    "宜園餐廳": {"lat": 24.227275, "lng": 120.579522, "desc": "學生餐廳"},
    "靜園餐廳": {"lat": 24.227622, "lng": 120.581652, "desc": "學生餐廳"},
    "靜宜小木屋鬆餅": {"lat": 24.228612, "lng": 120.581368, "desc": "美食小點"},
    "體育館": {"lat": 24.229167, "lng": 120.581063, "desc": "代碼: ST"},
    "田徑場": {"lat": 24.227980, "lng": 120.579140, "desc": "代碼: SD"},
    "希嘉學苑": {"lat": 24.228139, "lng": 120.580264, "desc": "女宿"},
    "思高學苑": {"lat": 24.228805, "lng": 120.581961, "desc": "男宿"},
    "善牧學苑": {"lat": 24.228856, "lng": 120.582487, "desc": "男女宿"},
    "主顧聖母堂": {"lat": 24.228076, "lng": 120.581420, "desc": "打卡聖地"},
    "靜宜大學校門": {"lat": 24.225843, "lng": 120.577191, "desc": "主要出入口"},
    "校門口公車站": {"lat": 24.225341, "lng": 120.577765, "desc": "公車搭乘處"}
    
}

@app.route('/')
def index():
    return render_template('index.html', api_key=GOOGLE_MAPS_API_KEY, locations=pu_locations)

@app.route('/api/ai_search', methods=['POST'])
def ai_search():
    data = request.get_json()
    user_query = data.get('query', '')
    
    # 強化 Prompt，讓 AI 根據資料庫（含科系）幫新生帶路
    prompt = f"""
    你是靜宜大學的新生導航 AI。
    使用者問：'{user_query}'。
    請根據以下的校園資料庫（包含大樓與對應科系），找出最適合的地點。
    資料庫：{pu_locations}
    
    規則：
    1. 只能回傳資料庫中存在的「大樓名稱」(例如：主顧樓、任垣樓)。
    2. 絕對不要附加任何解釋或標點符號。
    3. 如果真的找不到關聯，請回傳 '無'。
    """

    try:
        response = model.generate_content(prompt)
        res_text = response.text.strip()
        if res_text in pu_locations:
            return jsonify({"target": res_text})
        return jsonify({"error": "找不到相對應的地點或科系！"}), 404
    except:
        return jsonify({"error": "AI 連線失敗"}), 500

if __name__ == '__main__':
    print("\n" + "="*55)
    print("🌍 靜宜大學新生防迷路地圖 (AI 強化版) 上線囉！")
    print("👉 請按住 Ctrl (或 Cmd) 並點擊下方網址進入：")
    print("🔗 https://nonportentously-subdermal-buster.ngrok-free.dev")
    print("="*55 + "\n")
    
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)