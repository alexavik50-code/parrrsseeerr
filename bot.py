import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from playwright.async_api import async_playwright

BOT_TOKEN = "8737096321:AAFwCWXI1NHqSspXMZI0OqoxAs60JDf0ihc"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def parse_booking_strict(url: str, message: types.Message):
    results = []
    
    # Очищаем ссылку от старых оффсетов, если они там были
    base_url = re.sub(r'&offset=\d+', '', url)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='ru-RU' 
        )
        
        try:
            # ЛИСТАЕМ ВСЕ СТРАНИЦЫ (максимум Букинга - 40 страниц)
            for page_num in range(40):
                # 💥 ГЕНИАЛЬНЫЙ МАНЕВР: Создаем новую вкладку для каждой страницы
                page = await context.new_page()
                
                # Турбо-режим: блокируем картинки и стили для скорости
                async def route_intercept(route):
                    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                        await route.abort()
                    else:
                        await route.continue_()
                await page.route("**/*", route_intercept)

                current_offset = page_num * 25
                page_url = f"{base_url}&offset={current_offset}"
                
                # Отправляем апдейт в чат каждые 5 страниц
                if page_num % 5 == 0 and page_num > 0:
                    await message.answer(f"🔄 Просканировал {page_num} страниц, продолжаю поиск...")
                
                await page.goto(page_url, timeout=60000)
                
                try:
                    await page.wait_for_selector('[data-testid="property-card"]', timeout=15000)
                except:
                    await page.close() # Закрываем вкладку перед выходом
                    break
                
                cards = await page.query_selector_all('[data-testid="property-card"]')
                
                if not cards:
                    await page.close() # Закрываем вкладку перед выходом
                    break
                
                for card in cards:
                    card_text = await card.inner_text()
                    text_lower = card_text.lower()
                    
                    has_cancel = "бесплатная отмена" in text_lower or "отмена бесплатно" in text_lower
                    has_noprepay = "предоплата не" in text_lower or "без предоплаты" in text_lower or "платите на месте" in text_lower
                    
                    if not (has_cancel and has_noprepay):
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
                            
                            # Проверка цены
                            if price_value >= 100: 
                                full_link = link.split('?')[0]
                                results.append(
                                    f"🏨 <b>{title}</b>\n"
                                    f"💰 Цена: {price_text}\n"
                                    f"✅ Без предоплаты и с бесплатной отменой\n"
                                    f"🔗 <a href='{full_link}'>Смотреть объявление</a>"
                                )
                
                # 💥 ЗАКРЫВАЕМ ВКЛАДКУ В КОНЦЕ ЦИКЛА! Память очищается полностью!
                await page.close()
                                
        except Exception as e:
            return f"error: {e}"
            
        finally:
            await browser.close()
            
    return results

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("Привет! Пришли ссылку с Booking.com. Я прочешу ВЕСЬ список (до 1000 отелей) и выдам только те, где есть бесплатная отмена и нет предоплаты.")

@dp.message()
async def handle_search(message: types.Message):
    user_input = message.text
    
    if user_input.startswith("http"):
        await message.answer("🔗 Погнали! Сканирую всю доступную выдачу. Это займет несколько минут...")
        url = user_input
    else:
        await message.answer("Скинь ссылку, чтобы я начал работу.")
        return
    
    apartments = await parse_booking_strict(url, message)
    
    if apartments == "empty" or not apartments:
        await message.answer("❌ Я проверил страницы, но нигде не нашел совпадений по всем условиям.")
    elif isinstance(apartments, str) and apartments.startswith("error:"):
        await message.answer(f"⚠️ Ошибка сервера: {apartments}")
    else:
        await message.answer(f"🎉 Готово! Нашел {len(apartments)} подходящих вариантов. Отправляю...")
        
        # Отправляем результаты с задержкой, чтобы Телеграм не забанил бота
        for apt in apartments:
            try:
                await message.answer(apt, parse_mode="HTML")
                await asyncio.sleep(0.3) 
            except Exception:
                pass
                
        await message.answer("✅ Весь список успешно отправлен!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
