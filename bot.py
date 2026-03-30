import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from playwright.async_api import async_playwright

BOT_TOKEN = "8737096321:AAGaATp37FQY6dA8qOBB2uD1kemGDMfzE5s"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def parse_booking_strict(city: str):
    # Берем самую базовую ссылку только с городом
    url = f"https://www.booking.com/searchresults.ru.html?ss={city}"
    
    results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector('[data-testid="property-card"]', timeout=15000)
            
            # Собираем все карточки на странице
            cards = await page.query_selector_all('[data-testid="property-card"]')
            
            for card in cards:
                # Получаем ВЕСЬ текст внутри карточки отеля разом
                card_text = await card.inner_text()
                
                # ЖЕСТКАЯ ПРОВЕРКА: Ищем точные фразы из твоего скриншота
                if "Предоплата не требуется" not in card_text or "Бесплатная отмена" not in card_text:
                    continue # Пропускаем, если нет нужных условий
                
                # Извлекаем элементы, если текстовые условия совпали
                title_el = await card.query_selector('[data-testid="title"]')
                link_el = await card.query_selector('[data-testid="title-link"]')
                price_el = await card.query_selector('[data-testid="price-and-discounted-price"]')
                
                if title_el and link_el and price_el:
                    title = await title_el.inner_text()
                    link = await link_el.get_attribute('href')
                    price_text = await price_el.inner_text()
                    
                    # Очищаем цену от валюты и пробелов
                    price_numbers = re.sub(r'[^\d]', '', price_text)
                    
                    if price_numbers:
                        price_value = int(price_numbers)
                        
                        # Проверяем условие: от 100 условных единиц (евро)
                        if price_value >= 100: 
                            full_link = link.split('?')[0]
                            results.append(
                                f"🏨 <b>{title}</b>\n"
                                f"💰 Цена: {price_text}\n"
                                f"✅ Без предоплаты и с бесплатной отменой\n"
                                f"🔗 <a href='{full_link}'>Смотреть объявление</a>"
                            )
                            
                # Для теста останавливаемся на 5 подходящих вариантах
                if len(results) >= 5:
                    break
                    
        except Exception as e:
            print(f"Ошибка парсинга или капча: {e}")
            
        finally:
            await browser.close()
            
    return results

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("Привет! Напиши город, и я соберу базу вариантов строго от 100€, без предоплаты и с бесплатной отменой.")

@dp.message()
async def handle_city_search(message: types.Message):
    city = message.text
    await message.answer(f"⏳ Сканирую все карточки в: {city}...\nИщу совпадения по тексту.")
    
    apartments = await parse_booking_strict(city)
    
    if apartments:
        for apt in apartments:
            await message.answer(apt, parse_mode="HTML")
    else:
        await message.answer("Не нашел подходящих вариантов на первой странице или Букинг выдал капчу.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
