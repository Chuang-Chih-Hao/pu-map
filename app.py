import subprocess
import sys
import os
import time
import uuid

# 自動安裝套件 (新增 flask-socketio 與 eventlet)
def install_required_packages():
    packages = {
        'flask': 'flask', 
        'google.generativeai': 'google-generativeai',
        'flask_socketio': 'flask-socketio',
        'eventlet': 'eventlet'
    }
    for module_name, pip_name in packages.items():
        try:
            __import__(module_name)
        except ImportError:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--break-system-packages', pip_name])

install_required_packages()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import google.generativeai as genai

app = Flask(__name__)
# 啟動 SocketIO 即時通訊引擎
socketio = SocketIO(app, cors_allowed_origins="*")

# --- 1. 金鑰安全設定 ---
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    print("⚠️ 警告：找不到 GOOGLE_MAPS_API_KEY 環境變數！")
if not GEMINI_API_KEY:
    print("⚠️ 嚴重警告：找不到 GEMINI_API_KEY 環境變數！")

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

# --- 3. 靜宜大學資料庫 ---
pu_locations = {
    "伯鐸樓": {"lat": 24.226435, "lng": 120.580714, "desc": "外語學院"},
    "任垣樓": {"lat": 24.226948, "lng": 120.579975, "desc": "人文暨社會科學院", "depts": "社工系"},
    "靜安樓": {"lat": 24.226224, "lng": 120.582118, "desc": "理學院"},
    "思源樓": {"lat": 24.227036, "lng": 120.582479, "desc": "管理學院"},
    "主顧樓": {"lat": 24.227070, "lng": 120.583291, "desc": "資訊學院"},
    "蓋夏圖書館": {"lat": 24.226303, "lng": 120.581292, "desc": "靜宜大學圖書館", "depts": "看書 借書 睡覺"},
    "希嘉學苑": {"lat": 24.228139, "lng": 120.580264, "desc": "女宿", "depts": "睡覺 休息"},
    "思高學苑": {"lat": 24.228805, "lng": 120.581961, "desc": "男宿", "depts": "睡覺 休息"},
    "善牧學苑": {"lat": 24.228856, "lng": 120.582487, "desc": "男女宿", "depts": "睡覺 休息"},
    "體育館": {"lat": 24.229167, "lng": 120.581063, "desc": "室內球場與泳池", "depts": "打球 游泳 運動"},
    "田徑場": {"lat": 24.227980, "lng": 120.579140, "desc": "操場", "depts": "跑步 運動 散步"},
    "至善美食廣場": {"lat": 24.228039, "lng": 120.579704, "desc": "主要學餐區", "depts": "吃飯 肚子餓 午餐 晚餐"},
    "計算機中心": {"lat": 24.226327, "lng": 120.579860, "desc": "電腦教室", "depts": "印講義 上網 印表機"},
    "主顧聖母堂": {"lat": 24.228076, "lng": 120.581420, "desc": "打卡聖地", "depts": "教堂 拍照"},
    "校門口公車站": {"lat": 24.225341, "lng": 120.577765, "desc": "搭車 回家 台灣大道"}
}

# --- 4. 揪團與聊天室資料庫 (暫存於記憶體) ---
active_groups = []
chat_history = {} # 格式: { "group_id": [ {"user": "某人", "msg": "哈囉"} ] }

@app.route('/')
def index():
    return render_template('index.html', api_key=GOOGLE_MAPS_API_KEY, locations=pu_locations)

@app.route('/api/ai_search', methods=['POST'])
def ai_search():
    if not model: return jsonify({"error": "AI 未啟動"}), 500
    user_query = request.get_json().get('query', '')
    prompt = f"任務：校園導航。使用者輸入：'{user_query}'。可用地點：{list(pu_locations.keys())}。請只回傳最適合的一個地點名稱，找不到回傳'無'。"
    try:
        res_text = model.generate_content(prompt).text.strip()
        for loc_name in pu_locations.keys():
            if loc_name in res_text: return jsonify({"target": loc_name})
        return jsonify({"error": "找不到相對應的地點！"}), 404
    except:
        return jsonify({"error": "AI 腦袋當機了"}), 500

@app.route('/api/groups', methods=['GET', 'POST'])
def manage_groups():
    global active_groups
    current_time = time.time()
    # 清理過期揪團與對應的聊天紀錄
    valid_groups = []
    for g in active_groups:
        if g['expires_at'] > current_time:
            valid_groups.append(g)
        else:
            chat_history.pop(g['id'], None) # 清除過期聊天紀錄
    active_groups = valid_groups

    if request.method == 'GET':
        return jsonify(active_groups)
    
    if request.method == 'POST':
        data = request.get_json()
        new_group = {
            "id": str(uuid.uuid4()),
            "title": data.get('title'),
            "location": data.get('location'),
            "expires_at": time.time() + (30 * 60)
        }
        active_groups.append(new_group)
        chat_history[new_group['id']] = [] # 建立專屬聊天室紀錄
        return jsonify({"success": True, "group": new_group})

# --- 5. WebSocket 聊天室即時邏輯 ---
@socketio.on('join_chat')
def on_join(data):
    room = data['group_id']
    join_room(room)
    # 把過去的歷史訊息傳給剛加入的人
    history = chat_history.get(room, [])
    emit('chat_history', history, to=request.sid)

@socketio.on('send_message')
def on_message(data):
    room = data['group_id']
    msg_data = {"user": data['username'], "msg": data['msg']}
    
    if room in chat_history:
        chat_history[room].append(msg_data)
        # 廣播給在這個聊天室的所有人
        emit('receive_message', msg_data, room=room)

if __name__ == '__main__':
    # 注意：這裡改用 socketio.run 才能支援即時通訊
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)