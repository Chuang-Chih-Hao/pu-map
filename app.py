import subprocess
import sys
import os
import time
import uuid

# 自動安裝套件
def install_required_packages():
    packages = {'flask': 'flask', 'google.generativeai': 'google-generativeai', 'flask_socketio': 'flask-socketio', 'eventlet': 'eventlet'}
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
socketio = SocketIO(app, cors_allowed_origins="*")

# --- 金鑰安全設定 ---
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- AI 模型自動偵測 ---
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model = genai.GenerativeModel(m.name.replace('models/', ''))
                break
    except: pass

# --- 靜宜大學資料庫 (更新版) ---
pu_locations = {
    "伯鐸樓": {"lat": 24.226435, "lng": 120.580714, "desc": "外語學院"},
    "任垣樓": {"lat": 24.226948, "lng": 120.579975, "desc": "人社院", "depts": "社工系"},
    "靜安樓": {"lat": 24.226224, "lng": 120.582118, "desc": "理學院"},
    "思源樓": {"lat": 24.227036, "lng": 120.582479, "desc": "管理學院"},
    "主顧樓": {"lat": 24.227070, "lng": 120.583291, "desc": "資訊學院"},
    "蓋夏圖書館": {"lat": 24.226303, "lng": 120.581292, "desc": "圖書館", "depts": "看書 借書 睡覺"},
    "希嘉學苑": {"lat": 24.228139, "lng": 120.580264, "desc": "女宿", "depts": "宿舍 睡覺"},
    "思高學苑": {"lat": 24.228805, "lng": 120.581961, "desc": "男宿", "depts": "宿舍 睡覺"},
    "善牧學苑": {"lat": 24.228856, "lng": 120.582487, "desc": "男女宿", "depts": "宿舍 睡覺"},
    "體育館": {"lat": 24.229167, "lng": 120.581063, "desc": "室內球場", "depts": "打球 運動"}, # 移除游泳池關聯
    "田徑場": {"lat": 24.227980, "lng": 120.579140, "desc": "操場", "depts": "跑步 運動"},
    "至善美食廣場": {"lat": 24.228039, "lng": 120.579704, "desc": "學餐", "depts": "餐廳 吃飯"},
    "宜園餐廳": {"lat": 24.227275, "lng": 120.579522, "desc": "學餐", "depts": "餐廳 吃飯"},
    "靜園餐廳": {"lat": 24.227622, "lng": 120.581652, "desc": "學餐", "depts": "餐廳 吃飯"},
    "子母車(一)": {"lat": 24.229661, "lng": 120.579876, "desc": "大型垃圾收集點", "depts": "子母車 垃圾"},
    "子母車(二)": {"lat": 24.229232, "lng": 120.581998, "desc": "大型垃圾收集點", "depts": "子母車 垃圾"},
    "溜冰場": {"lat": 24.229695, "lng": 120.580013, "desc": "戶外溜冰場", "depts": "溜冰 運動"},
    "游泳池": {"lat": 24.229497, "lng": 120.580427, "desc": "校內游泳池", "depts": "游泳 運動"},
    "校門口公車站": {"lat": 24.225341, "lng": 120.577765, "desc": "公車站", "depts": "搭車 回家"}
}

active_groups = []
chat_history = {}

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
        return jsonify({"error": "找不到地點"}), 404
    except: return jsonify({"error": "AI 當機"}), 500

@app.route('/api/groups', methods=['GET', 'POST'])
def manage_groups():
    global active_groups
    if request.method == 'GET':
        active_groups = [g for g in active_groups if g['expires_at'] > time.time()]
        return jsonify(active_groups)
    if request.method == 'POST':
        data = request.get_json()
        new_group = {"id": str(uuid.uuid4()), "title": data.get('title'), "location": data.get('location'), "expires_at": time.time() + (30 * 60)}
        active_groups.append(new_group)
        chat_history[new_group['id']] = []
        return jsonify({"success": True, "group": new_group})

@socketio.on('join_chat')
def on_join(data):
    room = data['group_id']
    join_room(room)
    emit('chat_history', chat_history.get(room, []), to=request.sid)

@socketio.on('send_message')
def on_message(data):
    room = data['group_id']
    msg_data = {"user": data['username'], "msg": data['msg']}
    if room in chat_history:
        chat_history[room].append(msg_data)
        emit('receive_message', msg_data, room=room)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)