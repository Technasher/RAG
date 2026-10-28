const API_BASE = 'http://localhost:8000'; // URL вашего FastAPI бэкенда
const SESSION_KEY = 'rag_chat_session_id';

// --- Управление сессией ---
function getSessionId() {
    let sid = localStorage.getItem(SESSION_KEY);
    if (!sid) {
        // Генерируем UUID v4 (простая реализация)
        sid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
        localStorage.setItem(SESSION_KEY, sid);
    }
    return sid;
}

// --- Отправка сообщения ---
async function sendMessage(text, isIntent = false) {
    if (!text.trim()) return;
    appendMessage('user', text);

    const payload = {
        session_id: getSessionId(),
        channel: 'web',
        // Если это intent, отправляем его, иначе текст
        ...(isIntent ? { intent: text } : { message: text })
    };

    try {
        const response = await fetch(`${API_BASE}/api/v1/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        appendMessage('assistant', data.answer, data.attachments, data.quick_replies);
    } catch (error) {
        appendMessage('assistant', '⚠️ Ошибка соединения. Попробуйте позже.');
        console.error(error);
    }
}

// --- Отрисовка сообщения ---
function appendMessage(role, text, attachments = [], quickReplies = []) {
    const container = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.textContent = text;
    container.appendChild(msgDiv);

    // Вложения
    if (attachments.length > 0) {
        attachments.forEach(att => {
            const link = document.createElement('a');
            link.href = `${API_BASE}${att.url}`;
            link.download = att.filename;
            link.className = 'attachment-link';
            link.innerHTML = `📎 ${att.filename} (${(att.size / 1024).toFixed(0)} КБ)`;
            container.appendChild(link);
        });
    }

    // Быстрые ответы (кнопки)
    if (quickReplies.length > 0) {
        const btnContainer = document.createElement('div');
        btnContainer.className = 'quick-replies';
        quickReplies.forEach(qr => {
            const btn = document.createElement('button');
            btn.textContent = qr.label;
            btn.className = 'quick-reply-btn';
            // По клику отправляем intent
            btn.onclick = () => sendMessage(qr.intent, true);
            btnContainer.appendChild(btn);
        });
        container.appendChild(btnContainer);
    }

    container.scrollTop = container.scrollHeight;
}

// --- Инициализация ---
document.getElementById('chat-send').addEventListener('click', () => {
    const input = document.getElementById('chat-input');
    sendMessage(input.value);
    input.value = '';
});
document.getElementById('chat-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const input = document.getElementById('chat-input');
        sendMessage(input.value);
        input.value = '';
    }
});