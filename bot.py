import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from playwright.async_api import async_playwright

BOT_TOKEN = "8737096321:AAFwCWXI1NHqSspXMZI0OqoxAs60JDf0ihc"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def parse_booking_strict(url: str):
    results = []
    
    async with async_playwright() as p:
        # ВОТ ЭТИ НАСТРОЙКИ СПАСАЮТ RAILWAY ОТ ЗАВИСАНИЙ
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='ru-RU' 
        )
        page = await context.new_page()
        
        try:
            await page.goto(url, timeout=60000)
            
            try:
                await page.wait_for_selector('[data-testid="property-card"]', timeout=15000)
            except:
                return "empty"
            
            cards = await page.query_selector_all('[data-testid="property-card"]')
            
            for card in cards:
                card_text = await card.inner_text()
                
                if "Предоплата не требуется" not in card_text or "Бесплатная отмена" not in card_text:
                    continue 
                
                title_el = await card.query_selector('[data-testid="title"]')
                link_el = await card.query_selector('[data-testid="title-link"]')
                price_el = await card.query_selector('[data-testid="price-and-discounted-price"]')
                
                if title_el and link_el and price_el:
                    title = await title_el.inner_text()
                    link = await link_el.get_attribute('href')
                    price_text = await price_el.inner_text()
                    
                    price_numbers = re.sub(r'[^\d]', '', price_text)
                    
                    if price_numbers:
                        price_value = int(price_numbers)
                        
                        if price_value >= 100: 
                            full_link = link.split('?')[0]
                            results.append(
                                f"🏨 <b>{title}</b>\n"
                                f"💰 Цена: {price_text}\n"
                                f"✅ Без предоплаты и с бесплатной отменой\n"
                                f"🔗 <a href='{full_link}'>Смотреть объявление</a>"
                            )
                            
                if len(results) >= 5:
                    break
                    
        except Exception as e:
            return f"error: {e}"
            
        finally:
            await browser.close()
            
    return results

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("Привет! Пришли мне название города ИЛИ готовую ссылку с Booking.com, и я отфильтрую результаты.")

@dp.message()
async def handle_search(message: types.Message):
    user_input = message.text
    
    if user_input.startswith("http"):
        await message.answer("🔗 Вижу ссылку! Запускаю сканирование этой страницы...")
        url = user_input
    else:
        await message.answer(f"⏳ Формирую поиск по городу: {user_input}...")
        url = f"https://www.booking.com/searchresults.ru.html?ss={user_input}"
    
    apartments = await parse_booking_strict(url)
    
    if apartments == "empty":
        await message.answer("❌ Букинг не показал ни одного отеля (возможно, на эти даты всё занято или сайт выдал капчу).")
    elif isinstance(apartments, str) and apartments.startswith("error:"):
        await message.answer(f"⚠️ Ошибка при загрузке: {apartments}")
    elif apartments:
        for apt in apartments:
            await message.answer(apt, parse_mode="HTML")
    else:
        await message.answer("❌ На этой странице нет вариантов, подходящих под все условия.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
