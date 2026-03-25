from pyrogram import Client, filters

@Client.on_message(filters.command("test"))
async def test_plugin(client, message):
    await message.reply_text("প্লাগিন সিস্টেম সঠিকভাবে কাজ করছে!")
