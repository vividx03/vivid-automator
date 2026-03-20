import telebot
import re
import os
import json
from telebot import types

# 🛠️ Render Environment Variable Fix
# Render Dashboard -> Environment -> Add Variable (Key: BOT_TOKEN)
token_env = os.environ.get('BOT_TOKEN')

if not token_env:
    print("❌ ERROR: Render dashboard mein BOT_TOKEN nahi mila!")

bot = telebot.TeleBot(token_env)

user_data = {}

def clean_html_text(text):
    # HTML safe cleaning - Only basic quotes and newlines to <br>
    return text.replace('"', '&quot;').replace('\n', '<br>').strip()

@bot.message_handler(commands=['start'])
def start_cmd(message):
    # Template direct local repo se load hoga (QUIZ.html hona chahiye repo mein)
    try:
        with open("QUIZ.html", "r", encoding="utf-8") as f:
            static_template = f.read()
    except FileNotFoundError:
        bot.send_message(message.chat.id, "❌ <b>Error:</b> QUIZ.html not found in repo!", parse_mode="HTML")
        return

    user_data[message.chat.id] = {"template": static_template, "buffer": "", "state": 1}
    
    welcome = (
        "<b>💎 VIVID PREMIUM AUTOMATOR 💎</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>System initialized. Ready for deployment.</i>\n\n"
        "How would you like to provide your questions?"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_text = types.InlineKeyboardButton("📝 SEND TEXT MODE", callback_data="mode_text")
    btn_file = types.InlineKeyboardButton("📁 UPLOAD TXT FILE", callback_data="mode_file")
    markup.add(btn_text, btn_file)
    
    bot.send_message(message.chat.id, welcome, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("mode_"))
def set_input_mode(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    if call.data == "mode_text":
        bot.send_message(chat_id, "🚀 <b>TEXT FEED ACTIVE</b>\nPaste your questions. Type <b>/vivid</b> when finished.", parse_mode="HTML")
    else:
        bot.send_message(chat_id, "📁 <b>FILE MODE ACTIVE</b>\nPlease upload your <b>Questions.txt</b> file.", parse_mode="HTML")

@bot.message_handler(content_types=['document'], func=lambda m: user_data.get(m.chat.id, {}).get("state") == 1)
def handle_txt_file(message):
    chat_id = message.chat.id
    file_info = bot.get_file(message.document.file_id)
    content = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')
    user_data[chat_id]["buffer"] = content
    user_data[chat_id]["state"] = 2
    bot.send_message(chat_id, "📥 <b>FILE RECEIVED</b>\nNow send the <b>Answer Key</b> (e.g., <code>1=A, 2=C</code>).", parse_mode="HTML")

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("state") == 1)
def buffer_questions(message):
    chat_id = message.chat.id
    if message.text == "/vivid":
        user_data[chat_id]["state"] = 2
        bot.send_message(chat_id, "📥 <b>QUESTIONS BUFFERED</b>\nNow send the <b>Answer Key</b> (e.g., <code>1=A, 2=C</code>).", parse_mode="HTML")
        return
    user_data[chat_id]["buffer"] += "\n" + message.text
    count = len(re.findall(r'(?i)Question[\s\u200b\u200c]*No', user_data[chat_id]["buffer"]))
    bot.send_message(chat_id, f"✅ <b>Chunk added.</b> (Detected: ~{count})\nKeep sending or type <b>/vivid</b>.", parse_mode="HTML")

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("state") == 2)
def handle_key(message):
    chat_id = message.chat.id
    ans_map = {}
    matches = re.findall(r'(\d+)\s*=\s*([A-D])', message.text, re.I)
    for num, opt in matches:
        ans_map[int(num)] = ord(opt.upper()) - 65

    raw_text = user_data[chat_id]["buffer"]
    clean_raw = raw_text.replace('\u200b', '').replace('\u200c', '').replace('\ufeff', '')
    blocks = re.split(r'(?i)Question[\s]*No[:\s]*(\d+)', clean_raw)
    
    final_qs = []
    for i in range(1, len(blocks), 2):
        try:
            q_num = int(blocks[i])
            content = blocks[i+1].strip()
            
            parts = re.split(r'(?i)Solution[:\s]*', content)
            body = parts[0].strip()
            sol = parts[1].strip() if len(parts) > 1 else ""

            opt_a = re.search(r'\n\s*A[\)\.\s-]', body)
            opt_b = re.search(r'\n\s*B[\)\.\s-]', body)
            opt_c = re.search(r'\n\s*C[\)\.\s-]', body)
            opt_d = re.search(r'\n\s*D[\)\.\s-]', body)

            if opt_a and opt_b and opt_c and opt_d:
                q_text = body[:opt_a.start()].strip()
                a_txt = body[opt_a.end():opt_b.start()].strip()
                b_txt = body[opt_b.end():opt_c.start()].strip()
                c_txt = body[opt_c.end():opt_d.start()].strip()
                d_txt = body[opt_d.end():].strip()
                options = [a_txt, b_txt, c_txt, d_txt]
            else:
                raw_opts = re.split(r'\n\s*[A-D][\)\.\s-]\s*', body)
                q_text = raw_opts[0].strip()
                options = [o.split('\n')[0].strip() for o in raw_opts[1:5]]

            final_qs.append({
                "q": clean_html_text(q_text),
                "options": [clean_html_text(o) for o in options],
                "ans": ans_map.get(q_num, 0),
                "sol": clean_html_text(sol)
            })
        except: continue

    user_data[chat_id]["final_qs"] = final_qs
    user_data[chat_id]["state"] = 3
    bot.send_message(chat_id, "🎯 <b>LOGIC MAPPED</b>\nSend the <b>Quiz Title</b> (Topic Name) now.", parse_mode="HTML")

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("state") == 3)
def finish_quiz(message):
    chat_id = message.chat.id
    topic = message.text.strip()
    
    display_title = topic
    if len(topic) > 15:
        words = topic.split()
        if len(words) > 1:
            mid = len(words) // 2
            display_title = " ".join(words[:mid]) + "<br>" + " ".join(words[mid:])

    template = user_data[chat_id]["template"]
    qs_json = json.dumps(user_data[chat_id]["final_qs"], ensure_ascii=False, indent=4)
    
    template = re.sub(r'<title>.*?</title>', f'<title>{topic} ~ Vivid</title>', template, flags=re.IGNORECASE)
    template = template.replace(">Delhi Sultanate P-1<", f">{display_title}<")
    template = template.replace(">Delhi Sultanate<", f">{display_title}<")
    template = re.sub(r'const questions\s*=\s*\[.*?\n?\];', f'const questions = {qs_json};', template, flags=re.DOTALL)
    
    clean_name = re.sub(r'[^\w\s-]', '', topic).replace(' ', '_')
    file_name = f"{clean_name}_Vivid.html"
    
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(template)

    with open(file_name, "rb") as f:
        bot.send_document(chat_id, f, caption=f"✨ <b>QUIZ DEPLOYED</b>\n━━━━━━━━━━━━━━━━━━━━\n<b>Topic:</b> {topic}\n<b>Creator:</b> Vivid", parse_mode="HTML")
    
    os.remove(file_name)
    user_data[chat_id] = {"template": None, "buffer": "", "state": 0}

bot.infinity_polling()
