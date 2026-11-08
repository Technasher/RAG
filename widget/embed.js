(function () {
    // 1. Берём origin из URL самого скрипта (document.currentScript)
    //    → http://127.0.0.1:8000 на локале
    //    → https://xxx.ngrok-free.app на ngrok
    //    → https://your-domain.com в проде
    const script = document.currentScript
        || document.querySelector('script[src*="embed.js"]');
    const API_ORIGIN = new URL(script.src).origin;

    // 2. Кнопка
    const button = document.createElement('button');
    button.innerHTML = '💬';
    button.style.cssText = `
        position: fixed; bottom: 20px; right: 20px;
        width: 60px; height: 60px; border-radius: 50%;
        background: #4f46e5; color: white; border: none;
        font-size: 24px; cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
    `;
    document.body.appendChild(button);

    // 3. iframe — АБСОЛЮТНЫЙ URL на origin embed.js
    const iframe = document.createElement('iframe');
    iframe.src = `${API_ORIGIN}/widget/index.html`;   // ← ключевая строка
    iframe.style.cssText = `
        position: fixed; bottom: 90px; right: 20px;
        width: 400px; height: 600px;
        border: none; border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
        z-index: 9998; display: none; background: white;
    `;
    document.body.appendChild(iframe);

    // 4. Открытие/закрытие
    button.addEventListener('click', () => {
        const isHidden = iframe.style.display === 'none';
        iframe.style.display = isHidden ? 'block' : 'none';
        button.innerHTML = isHidden ? '✕' : '💬';
    });
})();