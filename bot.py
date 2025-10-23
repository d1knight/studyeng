import aiohttp
import asyncio
import ssl
import certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())

BACKEND_URL = "http://127.0.0.1:8000/api/v1/bot/generate-code/"

TOKEN = '7787604557:AAFfGkZc_Gau65wVpm1u5wd9W0s6GAbjKA8'
API_URL = f"https://api.telegram.org/bot{TOKEN}"


# === Получаем фото профиля пользователя ===
async def get_user_photo(session, user_id):
    url = f"{API_URL}/getUserProfilePhotos"
    params = {"user_id": user_id, "limit": 1}
    async with session.get(url, params=params) as resp:
        data = await resp.json()
        photos = data.get("result", {}).get("photos")
        if photos:
            file_id = photos[0][-1]["file_id"]  # Берем фото максимального размера
            return file_id
        return None


# === Скачиваем файл по file_id ===
async def download_user_photo(session, file_id):
    file_info_resp = await session.get(f"{API_URL}/getFile", params={"file_id": file_id})
    file_info = await file_info_resp.json()
    file_path = file_info.get("result", {}).get("file_path")
    if not file_path:
        return None

    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    async with session.get(file_url) as file_resp:
        if file_resp.status == 200:
            return await file_resp.read()
    return None


# === Отправляем данные пользователя и аватарку на backend ===
async def get_otp_code(tg_id, phone_number, first_name, last_name, photo_bytes=None):
    form = aiohttp.FormData()
    form.add_field("tg_id", str(tg_id))
    form.add_field("phone_number", phone_number)
    form.add_field("first_name", first_name or "")
    form.add_field("last_name", last_name or "")
    if photo_bytes:
        form.add_field("avatar", photo_bytes, filename=f"{tg_id}.jpg", content_type="image/jpeg")

    async with aiohttp.ClientSession() as session:
        async with session.post(BACKEND_URL, data=form) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Error from backend: {response.status}")
                return None


# === Клавиатура для запроса телефона ===
def phone_keyboard():
    return {
        "keyboard": [[{"text": "🔑 Получить подтверждающий код", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


# === Отправка сообщений ===
async def send_message(session, chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await session.post(f"{API_URL}/sendMessage", json=payload)


# === Основная логика бота ===
async def main():
    offset = 0
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        while True:
            resp = await session.get(f"{API_URL}/getUpdates", params={"timeout": 30, "offset": offset})
            data = await resp.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text")
                contact = message.get("contact")
                first_name = message.get("from", {}).get("first_name")
                last_name = message.get("from", {}).get("last_name")

                if text == "/start":
                    await send_message(
                        session,
                        chat_id,
                        "Привет! Для получения подтверждающего кода нажмите кнопку снизу👇",
                        phone_keyboard()
                    )

                elif contact:
                    phone_number = contact.get("phone_number")

                    # 1️⃣ Получаем фото пользователя
                    file_id = await get_user_photo(session, chat_id)
                    photo_bytes = None
                    if file_id:
                        photo_bytes = await download_user_photo(session, file_id)

                    # 2️⃣ Отправляем все данные на backend
                    response_data = await get_otp_code(chat_id, phone_number, first_name, last_name, photo_bytes)

                    # 3️⃣ Отправляем пользователю код
                    if response_data and response_data.get("code"):
                        code = response_data.get("code")
                        await send_message(session, chat_id, f"✅ Подтверждающий код: `{code}`")
                    else:
                        await send_message(session, chat_id, "❌ Произошла ошибка. Повторите попытку позже.")

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
