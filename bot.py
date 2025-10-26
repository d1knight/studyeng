import aiohttp
import asyncio
import ssl
import certifi


ssl_context = ssl.create_default_context(cafile=certifi.where())

BACKEND_URL = "https://studyeng.uz/api/v1/bot/generate-code/"

TOKEN = '7787604557:AAFfGkZc_Gau65wVpm1u5wd9W0s6GAbjKA8'
API_URL = f"https://api.telegram.org/bot{TOKEN}"

async def get_otp_code(tg_id, phone_number, first_name, last_name):
    data = {
        "tg_id": tg_id,
        "phone_number": phone_number,
        "first_name": first_name,
        "last_name": last_name
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(BACKEND_URL, json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Error from backend: {response.status}, ")
                return None 




def phone_keyboard():
    return {
        "keyboard": [[{"text": "🔑 Получить подтверждающий код", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }


async def send_message(session, chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await session.post(f"{API_URL}/sendMessage", json=payload)


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
                    await send_message(session, chat_id, "Привет! Для получения подтверждающего кода нажмите кнопку снизу👇", phone_keyboard())

                elif contact:
                    phone_number = contact.get("phone_number")
                    response_data = await get_otp_code(chat_id, phone_number, first_name, last_name)
                    if response_data and response_data.get("code"):
                        code = response_data.get("code")
                        await send_message(session, chat_id, f"✅ Подтвеждающий код: `{code}`")
                    else:
                        await send_message(session, chat_id, "❌ Произошла ошибка. Повторите попытку позже.")

            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
