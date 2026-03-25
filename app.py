from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import sqlite3
import os
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'survey_secret_key_2024'
DB_PATH = os.path.join(os.path.dirname(__file__), 'survey.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        order_num INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS surveys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        answers TEXT,
        suggestions TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT NOT NULL,
        city TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        title TEXT DEFAULT '员工满意度',
        subtitle TEXT DEFAULT '您的意见对我们非常重要，请如实填写',
        badge TEXT DEFAULT '匿名问卷 · 您的回答将严格保密',
        suggestion_title TEXT DEFAULT '您对公司还有哪些建议？',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    try:
        c.execute('SELECT suggestion_title FROM settings WHERE id = 1')
    except:
        c.execute('ALTER TABLE settings ADD COLUMN suggestion_title TEXT DEFAULT "您对公司还有哪些建议？"')
    
    c.execute('SELECT COUNT(*) FROM settings')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO settings (id, title, subtitle, badge, suggestion_title) VALUES (1, ?, ?, ?, ?)',
            ('员工满意度', '您的意见对我们非常重要，请如实填写', '匿名问卷 · 您的回答将严格保密', '您对公司还有哪些建议？'))
    
    c.execute('SELECT COUNT(*) FROM questions')
    if c.fetchone()[0] == 0:
        default_questions = [
            '您对公司制度的满意程度？',
            '您对上下班时间合理性的满意程度？',
            '您对通勤便利程度的满意程度？',
            '您对自身岗位的满意程度？',
            '您对同事相处融洽氛围的满意程度？',
            '您对薪资水平的满意程度？',
            '您对个人成长的满意程度？'
        ]
        for i, q in enumerate(default_questions, 1):
            c.execute('INSERT INTO questions (title, order_num) VALUES (?, ?)', (q, i))
    
    conn.commit()
    conn.close()


def get_settings():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT title, subtitle, badge, suggestion_title FROM settings WHERE id = 1')
    row = c.fetchone()
    conn.close()
    if row:
        return {'title': row[0], 'subtitle': row[1], 'badge': row[2], 'suggestion_title': row[3]}
    return {'title': '问卷', 'subtitle': '', 'badge': '', 'suggestion_title': ''}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    return redirect(url_for('survey_page'))


@app.route('/survey')
def survey_page():
    return app.send_static_file('survey.html')


@app.route('/api/user', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        nickname = request.json.get('nickname', '').strip()
        city = request.json.get('city', '').strip()
        if not nickname:
            return jsonify({'error': '请输入昵称'}), 400
        if not city:
            return jsonify({'error': '请输入所在城市'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('SELECT id, nickname, city FROM users WHERE nickname = ? AND city = ?', (nickname, city))
        user = c.fetchone()
        
        if not user:
            c.execute('INSERT INTO users (nickname, city) VALUES (?, ?)', (nickname, city))
            user_id = c.lastrowid
        else:
            user_id = user[0]
        
        conn.commit()
        conn.close()
        
        session['user_id'] = user_id
        session['nickname'] = nickname
        session['city'] = city
        return jsonify({'success': True, 'user_id': user_id, 'nickname': nickname, 'city': city})
    
    user_id = session.get('user_id')
    nickname = session.get('nickname')
    city = session.get('city')
    return jsonify({'logged_in': bool(user_id), 'user_id': user_id, 'nickname': nickname, 'city': city})


@app.route('/api/user/logout', methods=['POST'])
def user_logout():
    session.pop('user_id', None)
    session.pop('nickname', None)
    session.pop('city', None)
    return jsonify({'success': True})


@app.route('/api/my-survey', methods=['GET'])
def get_my_survey():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': '未登录'}), 401
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, answers, suggestions, created_at FROM surveys WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (user_id,))
    survey = c.fetchone()
    c.execute('SELECT id, title, order_num FROM questions ORDER BY order_num')
    questions = c.fetchall()
    conn.close()
    
    if not survey:
        return jsonify({'error': '暂无提交记录'}), 404
    
    try:
        answers = json.loads(survey[1]) if survey[1] else {}
    except:
        answers = {}
    
    answers_str_keys = {}
    for k, v in answers.items():
        answers_str_keys[str(k)] = v
    
    return jsonify({
        'id': survey[0],
        'answers': answers_str_keys,
        'suggestions': survey[2],
        'created_at': survey[3],
        'questions': [{'id': str(q[0]), 'title': q[1]} for q in questions]
    })


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT title, subtitle, badge, suggestion_title FROM settings WHERE id = 1')
    row = c.fetchone()
    conn.close()
    return jsonify({
        'title': row[0] if row else '员工满意度',
        'subtitle': row[1] if row else '您的意见对我们非常重要，请如实填写',
        'badge': row[2] if row else '匿名问卷 · 您的回答将严格保密',
        'suggestion_title': row[3] if row and row[3] else '您对公司还有哪些建议？'
    })


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def manage_settings():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        subtitle = request.form.get('subtitle', '').strip()
        badge = request.form.get('badge', '').strip()
        suggestion_title = request.form.get('suggestion_title', '').strip()
        c.execute('UPDATE settings SET title = ?, subtitle = ?, badge = ?, suggestion_title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1',
            (title, subtitle, badge, suggestion_title))
        conn.commit()
    
    c.execute('SELECT title, subtitle, badge, suggestion_title FROM settings WHERE id = 1')
    row = c.fetchone()
    conn.close()
    settings = get_settings()
    return render_template('settings.html', 
        title=settings['title'],
        subtitle=settings['subtitle'],
        badge=settings['badge'],
        suggestion_title=settings['suggestion_title'],
        system_title=settings['title'] + '问卷调查')


@app.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'admin':
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            settings = get_settings()
            return render_template('login.html', error='用户名或密码错误', system_title=settings['title'] + '问卷调查')
    settings = get_settings()
    return render_template('login.html', system_title=settings['title'] + '问卷调查')


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM surveys')
    total = c.fetchone()[0]
    c.execute('SELECT title FROM questions ORDER BY order_num')
    questions = c.fetchall()
    conn.close()
    settings = get_settings()
    stats = {'total': total, 'questions': [q[0] for q in questions]}
    return render_template('dashboard.html', stats=stats, total=total, system_title=settings['title'] + '问卷调查')


@app.route('/questions', methods=['GET', 'POST'])
@login_required
def manage_questions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            title = request.form.get('title')
            c.execute('SELECT COALESCE(MAX(order_num), 0) + 1 FROM questions')
            order_num = c.fetchone()[0]
            c.execute('INSERT INTO questions (title, order_num) VALUES (?, ?)', (title, order_num))
        
        elif action == 'delete':
            qid = request.form.get('id')
            c.execute('DELETE FROM questions WHERE id = ?', (qid,))
            c.execute('SELECT id FROM questions ORDER BY order_num')
            remaining = c.fetchall()
            for idx, (qid,) in enumerate(remaining, 1):
                c.execute('UPDATE questions SET order_num = ? WHERE id = ?', (idx, qid))
        
        elif action == 'edit':
            qid = request.form.get('id')
            title = request.form.get('title')
            c.execute('UPDATE questions SET title = ? WHERE id = ?', (title, qid))
        
        elif action == 'reorder':
            order_data = request.form.get('order_data')
            if order_data and order_data.strip():
                try:
                    order_list = json.loads(order_data)
                    if isinstance(order_list, list):
                        for idx, qid in enumerate(order_list, 1):
                            c.execute('UPDATE questions SET order_num = ? WHERE id = ?', (idx, qid))
                except (json.JSONDecodeError, ValueError):
                    pass
        
        conn.commit()
    
    c.execute('SELECT id, title, order_num FROM questions ORDER BY order_num')
    questions = c.fetchall()
    conn.close()
    settings = get_settings()
    return render_template('questions.html', questions=questions, system_title=settings['title'] + '问卷调查')


@app.route('/surveys')
@login_required
def survey_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT s.id, s.answers, s.suggestions, s.created_at, u.nickname, u.city 
                 FROM surveys s 
                 LEFT JOIN users u ON s.user_id = u.id 
                 ORDER BY s.created_at DESC''')
    surveys = c.fetchall()
    c.execute('SELECT id, title, order_num FROM questions ORDER BY order_num')
    questions = c.fetchall()
    conn.close()
    
    result = []
    for s in surveys:
        try:
            answers = json.loads(s[1]) if s[1] else {}
        except (json.JSONDecodeError, ValueError):
            answers = {}
        answers_str_keys = {}
        for k, v in answers.items():
            answers_str_keys[str(k)] = v
        result.append({
            'id': s[0],
            'answers': answers_str_keys,
            'suggestions': s[2],
            'created_at': s[3],
            'nickname': s[4] or '匿名',
            'city': s[5] or ''
        })
    
    settings = get_settings()
    return render_template('survey_list.html', surveys=result, questions=questions, system_title=settings['title'] + '问卷调查')


@app.route('/survey/<int:id>')
@login_required
def survey_detail(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, answers, suggestions, created_at FROM surveys WHERE id = ?', (id,))
    survey = c.fetchone()
    c.execute('SELECT id, title, order_num FROM questions ORDER BY order_num')
    questions = c.fetchall()
    conn.close()
    
    if not survey:
        return 'Not Found', 404
    
    try:
        answers = json.loads(survey[1]) if survey[1] else {}
    except (json.JSONDecodeError, ValueError):
        answers = {}
    
    answers_str_keys = {}
    for k, v in answers.items():
        answers_str_keys[str(k)] = v
    
    data = {
        'id': survey[0],
        'answers': answers_str_keys,
        'suggestions': survey[2],
        'created_at': survey[3],
        'questions': {str(q[0]): q[1] for q in questions}
    }
    settings = get_settings()
    return render_template('survey_detail.html', survey=data, system_title=settings['title'] + '问卷调查')


@app.route('/api/questions', methods=['GET'])
def get_questions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, title, order_num FROM questions ORDER BY order_num')
    questions = c.fetchall()
    conn.close()
    return jsonify([{'id': q[0], 'title': q[1], 'order': q[2]} for q in questions])


@app.route('/success')
def success_page():
    settings = get_settings()
    return render_template('success.html', system_title=settings['title'] + '问卷调查')


@app.route('/api/survey', methods=['POST'])
def submit_survey():
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    
    user_id = session.get('user_id')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO surveys (user_id, answers, suggestions) VALUES (?, ?, ?)',
        (user_id, json.dumps(data.get('answers', {})), data.get('suggestions', '')))
    survey_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '提交成功', 'survey_id': survey_id})


@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM surveys')
    total = c.fetchone()[0]
    
    c.execute('SELECT answers FROM surveys')
    surveys = c.fetchall()
    
    c.execute('SELECT id, title FROM questions ORDER BY order_num')
    questions = c.fetchall()
    
    stats = {'total': total, 'questions': {}}
    
    for q in questions:
        stats['questions'][q[0]] = {'title': q[1], 'scores': [], 'avg': 0}
    
    for s in surveys:
        if s[0]:
            try:
                answers = json.loads(s[0])
            except (json.JSONDecodeError, ValueError):
                answers = {}
            for qid, ans in answers.items():
                if qid in stats['questions'] and isinstance(ans, dict) and 'rating' in ans:
                    stats['questions'][qid]['scores'].append(ans['rating'])
    
    for qid, data in stats['questions'].items():
        if data['scores']:
            data['avg'] = round(sum(data['scores']) / len(data['scores']), 2)
    
    conn.close()
    return jsonify(stats)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
