(function() {
    // 1. Создаём плавающую кнопку
    const button = document.createElement('button');
    button.innerHTML = '💬'; // Иконка чата
    button.style.cssText = `
        position: fixed; bottom: 20px; right: 20px;
        width: 60px; height: 60px; border-radius: 50%;
        background: #4f46e5; color: white; border: none;
        font-size: 24px; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
    `;
    document.body.appendChild(button);

    // 2. Создаём iframe (скрытый по умолчанию)
    const iframe = document.createElement('iframe');
    iframe.src = 'http://localhost:3000/index.html'; // URL, где лежит index.html
    iframe.style.cssText = `
        position: fixed; bottom: 90px; right: 20px;
        width: 400px; height: 600px;
        border: none; border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
        z-index: 9998; display: none;
        background: white;
    `;
    document.body.appendChild(iframe);

    // 3. Логика открытия/закрытия
    button.addEventListener('click', () => {
        const isHidden = iframe.style.display === 'none';
        iframe.style.display = isHidden ? 'block' : 'none';
        button.innerHTML = isHidden ? '✕' : '💬'; // Меняем иконку
    });
})();